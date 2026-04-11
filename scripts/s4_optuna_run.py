#!/usr/bin/env python3
"""
scripts/s4_optuna_run.py
======================
Pipeline de optimización S4 con Optuna.

Stages:
1. Pilot study (80-120 trials) para param importance
2. Main optimization (500-1000 trials) sobre espacio reducido
3. Generate candidates + run cost_sensitivity
4. Apply acceptance gates

Usage:
    python3 scripts/s4_optuna_run.py --trials 1000 --universe-size 200 --start 2019-01-01 --end 2024-12-31
    python3 scripts/s4_optuna_run.py --resume --study-name s4_main
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import optuna
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/s4_optuna_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "optuna_s4"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

from src.optimization.s4_objective import compute_score_composed, get_hard_limits
from src.optimization.s4_gates import check_acceptance_gates, get_gate_summary
from src.analytics.backtest_analytics_bridge import compute_backtest_analytics
from src.analytics.backtest_io import save_backtest_analytics

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from walk_forward_combos import get_universe_from_db


# === PARAMETER SPACE ===


def define_search_space() -> Dict[str, Any]:
    """Espacio de búsqueda S4 (solo params con efecto real en engine)."""
    return {
        # Filtros core (confirmados en engine)
        "min_rs_percentile": {"type": "float", "low": 55.0, "high": 90.0},
        "max_dist_sma20": {"type": "float", "low": 6.0, "high": 16.0},
        "min_rvol": {"type": "float", "low": 0.7, "high": 1.5},
        "min_adr": {"type": "float", "low": 1.5, "high": 5.5},
        # Riesgo/capacidad
        "risk_per_trade_pct": {"type": "float", "low": 0.005, "high": 0.03},
        "max_exposure_pct": {"type": "float", "low": 0.20, "high": 0.50},
        # Sector scoring (nombre real del engine)
        "use_composite_sector_scoring": {"type": "categorical", "choices": [True, False]},
        "sector_top_percentile": {"type": "float", "low": 0.25, "high": 0.50},
        # Stops ATR reales del engine
        "use_atr_stop": {"type": "categorical", "choices": [True, False]},
        "atr_stop_multiplier": {"type": "float", "low": 1.2, "high": 2.5},
        "atr_trailing_multiplier": {"type": "float", "low": 1.8, "high": 3.5},
    }


def build_engine_kwargs_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Builder explícito para evitar kwargs mudos en el engine."""
    risk_pct = params.get("risk_per_trade_pct", 0.02)
    return {
        "risk_dollars": 100_000 * risk_pct,
        "min_rs_percentile": params.get("min_rs_percentile", 70.0),
        "max_dist_sma20": params.get("max_dist_sma20", 10.0),
        "min_rvol": params.get("min_rvol", 1.0),
        "min_adr": params.get("min_adr", 2.0),
        "max_exposure_pct": params.get("max_exposure_pct", 0.35),
        "use_composite_sector_scoring": params.get("use_composite_sector_scoring", False),
        "sector_top_percentile": params.get("sector_top_percentile", 0.40),
        "use_atr_stop": params.get("use_atr_stop", False),
        "atr_stop_multiplier": params.get("atr_stop_multiplier", 1.5),
        "atr_trailing_multiplier": params.get("atr_trailing_multiplier", 2.5),
        "fees": params.get("fees", 0.001),
        "slippage": params.get("slippage", 0.001),
    }


def reduce_search_space(
    importances: Dict[str, float], top_n: int = 6
) -> Dict[str, Any]:
    """Reduce espacio a los top N parámetros más importantes.

    Fallback al espacio completo si importances está vacío o insuficiente
    (pilot con pocos trials, período bajista sin trades suficientes).
    """
    full_space = define_search_space()

    if not importances or len(importances) < top_n:
        logger.warning(
            f"Importances insuficientes ({len(importances)} params, necesitan >= {top_n}). "
            f"Usando espacio completo ({len(full_space)} params) para Stage 2."
        )
        return full_space

    sorted_params = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    top_params = [p[0] for p in sorted_params[:top_n]]
    reduced = {k: v for k, v in full_space.items() if k in top_params}

    logger.info(f"Reduced space to top {top_n}: {top_params}")
    return reduced


# === OBJECTIVE FUNCTION ===


def run_backtest_for_trial(
    params: Dict[str, Any],
    universe: List[str],
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """Ejecuta backtest con los parámetros dados."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    try:
        engine_kwargs = build_engine_kwargs_from_params(params)
        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100_000,
            **engine_kwargs,
        )

        result = engine.run_backtest()
        equity_curve = result.get("equity_curve", pd.Series())
        engine.cleanup()

        metrics = result.get("metrics", {})
        trades_df = result.get("trades_df", pd.DataFrame())

        # FIX: El engine devuelve max_drawdown en decimal (ej: -0.0528), NO max_drawdown_pct.
        # Extraemos el valor correcto y lo convertimos a positivo para los gates.
        raw_mdd = (
            metrics.get("max_drawdown")
            or result.get("max_drawdown")
            or 0.0
        )
        # max_drawdown del engine es negativo (ej: -0.0528 = -5.28%)
        mdd_positive = abs(float(raw_mdd))

        # FIX: Calmar del engine viene como calmar_ratio, no calmar
        calmar = (
            metrics.get("calmar_ratio", 0)
            or result.get("calmar_ratio", 0)
            or 0.0
        )

        return {
            "trades": len(trades_df),
            "sharpe": float(metrics.get("sharpe_ratio", 0) or result.get("sharpe_ratio", 0) or 0),
            "mdd": mdd_positive,          # positivo, decimal (ej: 0.0528)
            "win_rate": float(metrics.get("win_rate", 0) or result.get("win_rate", 0) or 0),
            "pf": float(metrics.get("profit_factor", 0) or result.get("profit_factor", 0) or 0),
            "calmar": float(calmar),
            "cagr": float(metrics.get("annualized_return", 0) or result.get("annualized_return", 0) or 0),
            "equity_curve": equity_curve,
            "trades_df": trades_df,
        }
    except Exception as e:
        logger.warning(f"Backtest failed for trial: {e}")
        return {
            "trades": 0,
            "sharpe": -999,
            "mdd": 0,
            "win_rate": 0,
            "pf": 0,
            "calmar": 0,
            "cagr": 0,
            "error": str(e),
        }


def objective(
    trial: optuna.Trial,
    space: Dict[str, Any],
    start_date: str,
    end_date: str,
    universe: List[str],
) -> float:
    """Función objetivo para Optuna."""
    params = {}
    for name, config in space.items():
        if config["type"] == "float":
            params[name] = trial.suggest_float(name, config["low"], config["high"])
        elif config["type"] == "int":
            params[name] = trial.suggest_int(name, config["low"], config["high"])
        elif config["type"] == "categorical":
            params[name] = trial.suggest_categorical(name, config["choices"])

    metrics = run_backtest_for_trial(params, universe, start_date, end_date)

    if metrics.get("sharpe", 0) == -999:
        trial.set_user_attr("break_reason", metrics.get("error", "BACKTEST_ERROR"))
        return -999.0

    score, meta = compute_score_composed(
        trades=metrics["trades"],
        sharpe=metrics["sharpe"],
        mdd=metrics["mdd"],
        win_rate=metrics["win_rate"],
        profit_factor=metrics["pf"],
    )

    trial.set_user_attr("trades", metrics["trades"])
    trial.set_user_attr("sharpe_raw", metrics["sharpe"])
    trial.set_user_attr("mdd", metrics["mdd"])
    trial.set_user_attr("win_rate", metrics["win_rate"])
    trial.set_user_attr("pf", metrics["pf"])
    trial.set_user_attr("calmar", metrics.get("calmar", 0))
    trial.set_user_attr("cagr", metrics.get("cagr", 0))
    trial.set_user_attr("break_reason", meta.get("break_reason"))

    return score


# === MAIN PIPELINE ===


def run_pilot_study(
    n_trials: int,
    space: Dict[str, Any],
    start_date: str,
    end_date: str,
    universe: List[str],
) -> Dict[str, float]:
    """Stage 1: Pilot study para determinar importance."""
    logger.info(f"=== STAGE 1: Pilot Study ({n_trials} trials) ===")

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        storage=f"sqlite:///{OUTPUTS_DIR}/pilot_study.db",
        study_name="pilot",
        load_if_exists=True,
    )

    study.optimize(
        lambda t: objective(t, space, start_date, end_date, universe),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    try:
        importance = optuna.importance.get_param_importances(study)
        logger.info(f"Parameter importances: {importance}")
        return importance
    except Exception as e:
        logger.warning(f"Could not compute importances: {e}")
        return {}


def run_main_optimization(
    n_trials: int,
    reduced_space: Dict[str, Any],
    start_date: str,
    end_date: str,
    study_name: str,
    universe: List[str],
) -> optuna.Study:
    """Stage 2: Main optimization."""
    logger.info(f"=== STAGE 2: Main Optimization ({n_trials} trials) ===")

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=20, n_warmup_steps=10),
        storage=f"sqlite:///{OUTPUTS_DIR}/{study_name}.db",
        study_name=study_name,
        load_if_exists=True,
    )

    study.optimize(
        lambda t: objective(t, reduced_space, start_date, end_date, universe),
        n_trials=n_trials,
        show_progress_bar=True,
    )

    return study


def generate_candidates(study: optuna.Study, top_n: int = 10) -> List[Dict]:
    """Genera lista de candidatos desde study."""
    trials = sorted(
        study.trials, key=lambda t: t.value if t.value else -999, reverse=True
    )

    candidates = []
    for i, trial in enumerate(trials[:top_n]):
        if trial.value and trial.value > -999:
            candidates.append(
                {
                    "rank": i + 1,
                    "trial_id": trial.number,
                    "score_composed": trial.value,
                    "params": trial.params,
                    "is_sharpe": trial.user_attrs.get("sharpe_raw", 0),
                    "trades": trial.user_attrs.get("trades", 0),
                    "pf": trial.user_attrs.get("pf", 0),
                    "calmar": trial.user_attrs.get("calmar", 0),
                    "cagr": trial.user_attrs.get("cagr", 0),
                    "mdd": trial.user_attrs.get("mdd", 0),
                    "win_rate": trial.user_attrs.get("win_rate", 0),
                    "break_reason": trial.user_attrs.get("break_reason", "UNKNOWN"),
                }
            )

    return candidates


def run_cost_sensitivity_for_candidate(
    params: Dict,
    universe: List[str],
    start_date: str,
    end_date: str,
) -> str:
    """Determina ROBUSTO/MODERADO/FRAGIL según breakeven de costos."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    COST_GRID = [
        {"label": "zero",   "fees": 0.0,    "slippage": 0.0},
        {"label": "light",  "fees": 0.0005, "slippage": 0.0005},
        {"label": "base",   "fees": 0.001,  "slippage": 0.001},
        {"label": "ibkr",   "fees": 0.001,  "slippage": 0.0015},
        {"label": "retail", "fees": 0.002,  "slippage": 0.002},
        {"label": "stress", "fees": 0.005,  "slippage": 0.005},
    ]

    results = []
    for cost in COST_GRID:
        try:
            engine = AdvancedVectorBTEngine(
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=100_000,
                fees=cost["fees"],
                slippage=cost["slippage"],
                **{k: v for k, v in params.items() if k not in ("fees", "slippage")},
            )
            result = engine.run_backtest()
            sharpe = result.get("sharpe_ratio", 0) or 0
            viable = sharpe > 0 and result.get("profit_factor", 0) > 1.0
            rt_bps = int((cost["fees"] + cost["slippage"]) * 2 * 10000)
            results.append({"label": cost["label"], "rt_bps": rt_bps, "viable": viable})
            engine.cleanup()
        except Exception as e:
            logger.warning(f"Cost test {cost['label']} failed: {e}")
            results.append({"label": cost["label"], "rt_bps": 0, "viable": False})

    viable_scenarios = [r for r in results if r["viable"]]
    breakeven_bps = viable_scenarios[-1]["rt_bps"] if viable_scenarios else 0

    if breakeven_bps >= 60:
        return "ROBUSTO"
    elif breakeven_bps >= 25:
        return "MODERADO"
    else:
        return "FRAGIL"


def _estimate_hard_ruin(equity_curve: pd.Series, n_sims: int = 200) -> float:
    """
    Estima hard ruin (>= 50% DD) desde equity_curve real vía bootstrap.
    Fallback a 0.03 si equity_curve tiene menos de 10 puntos.
    """
    if equity_curve is None or len(equity_curve) < 10:
        return 0.03  # default conservador

    arr = equity_curve.values.astype(float)
    returns = np.diff(arr) / arr[:-1]
    returns = returns[~np.isnan(returns) & ~np.isinf(returns)]

    if len(returns) < 5:
        return 0.03

    hard_ruin_count = 0
    for _ in range(n_sims):
        sim = np.random.choice(returns, size=len(returns), replace=True)
        path = np.cumprod(1 + sim) * arr[0]
        peak = np.maximum.accumulate(path)
        dd = (peak - path) / peak
        if dd.max() >= 0.50:
            hard_ruin_count += 1

    return round(hard_ruin_count / n_sims, 4)


def apply_gates_to_candidates(
    candidates: List[Dict],
    universe: List[str],
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    """
    Aplica gates a candidatos.

    gate_results schema por candidato:
        {
            "passed": bool,
            "cost_robustness": str,
            "gate_details": { "pf_gate": {...}, "calmar_gate": {...}, ... }
        }
    """
    gate_results = {}

    for cand in candidates:
        cid = str(cand["trial_id"])

        # mdd del candidato viene en decimal positivo (ej: 0.0528) desde run_backtest_for_trial
        mdd_pct = cand.get("mdd", 0) * 100  # gates espera en %

        # hard_ruin: re-corremos el backtest del candidato para obtener equity_curve real
        # y calcular ruin via bootstrap. Solo para candidatos top (costo aceptable).
        hard_ruin = 0.03  # default
        try:
            from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
            eng = AdvancedVectorBTEngine(
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=100_000,
                **{k: v for k, v in cand.get("params", {}).items()
                   if k not in ("fees", "slippage")},
            )
            res = eng.run_backtest()
            equity_curve = res.get("equity_curve", pd.Series())
            eng.cleanup()
            hard_ruin = _estimate_hard_ruin(equity_curve)
        except Exception as e:
            logger.warning(f"  Could not compute hard_ruin for {cid}: {e}")

        is_metrics = {
            "profit_factor": cand.get("pf", 0),
            "calmar": cand.get("calmar", 0),
            "max_drawdown_90d": mdd_pct,
            "sharpe": cand.get("is_sharpe", 0),
            "win_rate": cand.get("win_rate", 0) * 100,
            "trades": cand.get("trades", 0),
            "risk_checks": {"hard_ruin_50": hard_ruin},  # FIX: valor real, no hardcoded
        }

        cost_robust = run_cost_sensitivity_for_candidate(
            cand.get("params", {}), universe, start_date, end_date
        )

        passed, gate_details = check_acceptance_gates(is_metrics, None, None, cost_robust)

        gate_results[cid] = {
            "passed": passed,
            "cost_robustness": cost_robust,
            "hard_ruin_estimated": hard_ruin,
            "gate_details": gate_details,
        }

        cand["cost_robustness"] = cost_robust
        cand["hard_ruin_estimated"] = hard_ruin

        if passed:
            logger.info(
                f"  ✅ Candidate {cid} PASSED "
                f"(score={cand['score_composed']:.3f}, MDD={mdd_pct:.1f}%, "
                f"ruin={hard_ruin:.3f}, cost={cost_robust})"
            )
        else:
            failed = [
                k for k, v in gate_details.items()
                if isinstance(v, dict) and not v.get("passed")
            ]
            logger.warning(
                f"  ❌ Candidate {cid} REJECTED — failed: {failed} "
                f"(MDD={mdd_pct:.1f}%, ruin={hard_ruin:.3f}, cost={cost_robust})"
            )

    return gate_results


def main():
    parser = argparse.ArgumentParser(description="S4 Optuna Optimization Pipeline")
    parser.add_argument("--trials", type=int, default=1000)
    parser.add_argument("--pilot-trials", type=int, default=80)
    parser.add_argument("--top-params", type=int, default=6)
    parser.add_argument("--universe-size", type=int, default=200)
    parser.add_argument("--start", type=str, default="2019-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--study-name", type=str, default="s4_main")
    parser.add_argument("--resume", action="store_true")

    args = parser.parse_args()

    logger.info(f"Starting S4: {args.trials} trials total")
    logger.info(f"Period: {args.start} → {args.end}")
    logger.info(f"Pilot: {args.pilot_trials} | Main: {args.trials - args.pilot_trials}")

    universe = get_universe_from_db(args.start, args.end, args.universe_size)
    logger.info(f"Universe: {len(universe)} symbols")

    full_space = define_search_space()

    # Stage 1: Pilot
    if not args.resume:
        importances = run_pilot_study(
            args.pilot_trials, full_space, args.start, args.end, universe
        )
        reduced_space = reduce_search_space(importances, args.top_params)
    else:
        logger.info("Resuming — skipping pilot, using full space")
        reduced_space = full_space

    # Stage 2: Main
    main_trials = args.trials - args.pilot_trials
    if main_trials <= 0:
        logger.warning(
            f"main_trials={main_trials} (--trials <= --pilot-trials). "
            "Usando pilot study para candidatos."
        )
        study = optuna.load_study(
            study_name="pilot",
            storage=f"sqlite:///{OUTPUTS_DIR}/pilot_study.db",
        )
    else:
        study = run_main_optimization(
            main_trials, reduced_space, args.start, args.end, args.study_name, universe
        )

    # Stage 3: Candidates
    candidates = generate_candidates(study, top_n=10)
    logger.info(f"Generated {len(candidates)} candidates")

    if not candidates:
        logger.warning(
            "0 candidates con score > -999. "
            "Todos los trials rechazados — revisá el período o umbrales."
        )

    # Stage 4: Gates
    gate_results = {}
    if candidates:
        gate_results = apply_gates_to_candidates(
            candidates, universe, args.start, args.end
        )

    # Summary
    flat_for_summary = {
        cid: {**gr["gate_details"], "passed": gr["passed"]}
        for cid, gr in gate_results.items()
    }

    summary = get_gate_summary(flat_for_summary)
    logger.info(f"\n=== GATE SUMMARY ===")
    logger.info(f"Total: {summary['total_candidates']}")
    logger.info(f"Passed: {summary['passed']}")
    logger.info(f"Rejected: {summary['rejected']}")
    logger.info(f"Gate stats: {summary['gate_stats']}")

    results_path = (
        OUTPUTS_DIR
        / f"results_{args.study_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(results_path, "w") as f:
        json.dump(
            {
                "study_name": args.study_name,
                "period": {"start": args.start, "end": args.end},
                "trials_total": args.trials,
                "trials_pilot": args.pilot_trials,
                "universe_size": len(universe),
                "candidates": candidates,
                "gate_results": gate_results,
                "gate_summary": summary,
            },
            f,
            indent=2,
            default=str,
        )

    logger.info(f"✅ Results saved: {results_path}")


if __name__ == "__main__":
    main()
