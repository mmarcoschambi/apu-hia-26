#!/usr/bin/env python3
"""
scripts/validate_optuna_results_oos.py
====================================
Validación OOS real para Optuna S4.

- IS: 0-60% del período
- Val: 60-80% del período
- OOS: 80-100% del período

Para cada candidato top-N:
1. Re-run backtest en cada split
2. Bootstrap CI sobre OOS sharpes de candidatos
3. DSR proxy + PBO proxy

Usage:
    python3 scripts/validate_optuna_results_oos.py --study-name smoke_v4 --top-n 10 --universe-size 80
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "optuna_s4"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

from walk_forward_combos import get_universe_from_db
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.optimization.s4_gates import _normalize_cost_label


def load_latest_results(study_name: str) -> tuple:
    """Carga el último results JSON para un study."""
    import glob

    pattern = str(OUTPUTS_DIR / f"results_{study_name}_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        raise FileNotFoundError(f"No results file for {study_name} in {OUTPUTS_DIR}")

    logger.info(f"Loading from: {files[0]}")
    return json.load(open(files[0])), Path(files[0])


def split_period(start: str, end: str) -> Dict[str, tuple]:
    """Divide período en IS/Val/OOS."""
    idx = pd.date_range(start=start, end=end, freq="B")
    n = len(idx)
    if n < 30:
        raise ValueError(f"Período muy corto: {n} días")

    is_end_idx = int(n * 0.60)
    val_end_idx = int(n * 0.80)

    return {
        "is": (idx[0].strftime("%Y-%m-%d"), idx[is_end_idx].strftime("%Y-%m-%d")),
        "val": (
            (idx[is_end_idx] + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            idx[val_end_idx].strftime("%Y-%m-%d"),
        ),
        "oos": (
            (idx[val_end_idx] + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            idx[-1].strftime("%Y-%m-%d"),
        ),
    }


def build_engine_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Builder de kwargs desde params de Optuna."""
    risk_pct = params.get("risk_per_trade_pct", 0.02)
    return {
        "risk_dollars": 100_000 * risk_pct,
        "min_rs_percentile": params.get("min_rs_percentile", 70.0),
        "max_dist_sma20": params.get("max_dist_sma20", 10.0),
        "min_rvol": params.get("min_rvol", 1.0),
        "min_adr": params.get("min_adr", 2.0),
        "max_exposure_pct": params.get("max_exposure_pct", 0.35),
        "use_composite_sector_scoring": params.get(
            "use_composite_sector_scoring", False
        ),
        "sector_top_percentile": params.get("sector_top_percentile", 0.40),
        "use_atr_stop": params.get("use_atr_stop", False),
        "atr_stop_multiplier": params.get("atr_stop_multiplier", 1.5),
        "atr_trailing_multiplier": params.get("atr_trailing_multiplier", 2.5),
        "fees": 0.001,
        "slippage": 0.001,
    }


def run_backtest(
    universe: List[str], start: str, end: str, kwargs: Dict[str, Any]
) -> Dict[str, Any]:
    """Ejecuta backtest y extrae métricas."""
    eng = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start,
        end_date=end,
        initial_capital=100_000,
        **kwargs,
    )
    try:
        r = eng.run_backtest()
        m = r.get("metrics", {})
        raw_dd = m.get("max_drawdown", 0) or r.get("max_drawdown", 0) or 0
        return {
            "sharpe": float(m.get("sharpe_ratio", 0) or r.get("sharpe_ratio", 0) or 0),
            "pf": float(m.get("profit_factor", 0) or r.get("profit_factor", 0) or 0),
            "calmar": float(m.get("calmar_ratio", 0) or r.get("calmar_ratio", 0) or 0),
            "mdd": abs(float(raw_dd)),
            "trades": r.get("total_trades", 0) or len(r.get("trades_df", [])),
        }
    except Exception as e:
        logger.warning(f"Backtest failed {start}→{end}: {e}")
        return {"sharpe": -999, "pf": 0, "calmar": 0, "mdd": 0, "trades": 0}
    finally:
        eng.cleanup()


def bootstrap_ci(values: List[float], n: int = 2000) -> Dict[str, float]:
    """Bootstrap confidence interval."""
    if len(values) < 2:
        return {"ci_lower": 0.0, "ci_upper": 0.0, "mean": 0.0}

    arr = np.array(values, dtype=float)
    np.random.seed(42)
    samples = [
        np.mean(np.random.choice(arr, size=len(arr), replace=True)) for _ in range(n)
    ]

    return {
        "mean": float(np.mean(samples)),
        "ci_lower": float(np.percentile(samples, 2.5)),
        "ci_upper": float(np.percentile(samples, 97.5)),
    }


def main():
    parser = argparse.ArgumentParser(description="OOS Validation for Optuna S4")
    parser.add_argument("--study-name", required=True, help="Study name")
    parser.add_argument(
        "--top-n", type=int, default=10, help="Top N candidates to validate"
    )
    parser.add_argument("--universe-size", type=int, default=80, help="Universe size")
    args = parser.parse_args()

    # Load results
    data, src_file = load_latest_results(args.study_name)
    period = data.get("period", {})
    start, end = period.get("start"), period.get("end")

    if not start or not end:
        raise ValueError(f"Invalid period in {src_file}")

    logger.info(f"Period: {start} → {end}")
    splits = split_period(start, end)
    logger.info(f"Splits: IS={splits['is']}, Val={splits['val']}, OOS={splits['oos']}")

    # Load universe
    universe = get_universe_from_db(start, end, args.universe_size)
    logger.info(f"Universe: {len(universe)} symbols")

    # Get candidates
    cands = data.get("candidates", [])[: args.top_n]
    if not cands:
        raise ValueError(f"No candidates in {src_file}")

    logger.info(f"Validating top {len(cands)} candidates...")

    # Validate each candidate across splits
    results = []
    for i, c in enumerate(cands):
        kwargs = build_engine_kwargs(c.get("params", {}))

        # FIX: logger.info no acepta end=, usar print para la línea inline
        print(f"  [{i + 1}/{len(cands)}] Trial {c['trial_id']}...", end=" ", flush=True)

        is_m = run_backtest(universe, *splits["is"], kwargs)
        val_m = run_backtest(universe, *splits["val"], kwargs)
        oos_m = run_backtest(universe, *splits["oos"], kwargs)

        # Calculate degradation IS→Val
        if is_m.get("sharpe", 0) > 0:
            deg = (is_m["sharpe"] - val_m["sharpe"]) / is_m["sharpe"]
        else:
            deg = None

        results.append(
            {
                "trial_id": c["trial_id"],
                "score_composed": c.get("score_composed", 0),
                "is": is_m,
                "val": val_m,
                "oos": oos_m,
                "degradation_is_val": deg,
            }
        )

        # Resultado en la misma línea del print anterior
        print(
            f"IS={is_m['sharpe']:.2f} Val={val_m['sharpe']:.2f} OOS={oos_m['sharpe']:.2f}"
        )

    # Aggregate OOS metrics
    oos_sharpes = [r["oos"]["sharpe"] for r in results if r["oos"]["sharpe"] > -999]
    if not oos_sharpes:
        raise ValueError("No valid OOS sharpes computed")

    top_oos = max(oos_sharpes)
    ci = bootstrap_ci(oos_sharpes, n=2000)

    # DSR proxy (deflated Sharpe)
    mean_s = np.mean(oos_sharpes)
    std_s = np.std(oos_sharpes)
    z = (top_oos - mean_s) / std_s if std_s > 0 else 0.0
    pbo_proxy = float(1 / (1 + np.exp(-(z - 2.5))))

    # DSR adjustment factor
    n_trials = len(results)
    adjustment = 0.3 * (1.96 * np.sqrt(np.log(6 / n_trials))) if n_trials > 6 else 0
    deflated_sharpe = max(0, top_oos - adjustment)
    lcl = max(0, top_oos - 1.96 * std_s)

    output = {
        "study_name": args.study_name,
        "source_file": str(src_file),
        "generated_at": datetime.now().isoformat(),
        "period": {"start": start, "end": end},
        "splits": splits,
        "universe_size": len(universe),
        "n_candidates_validated": len(results),
        "top_oos_sharpe": round(top_oos, 3),
        "oos_bootstrap_ci": ci,
        "deflated_sharpe": round(deflated_sharpe, 3),
        "lcl": round(lcl, 3),
        "pbo_proxy": round(pbo_proxy, 3),
        "interpretation": (
            "LOW_OVERFITTING_RISK"
            if pbo_proxy < 0.2
            else "MODERATE_OVERFITTING_RISK"
            if pbo_proxy < 0.5
            else "HIGH_OVERFITTING_RISK"
        ),
        "candidates": [
            {
                "trial_id": r["trial_id"],
                "is_sharpe": round(r["is"]["sharpe"], 3),
                "val_sharpe": round(r["val"]["sharpe"], 3),
                "oos_sharpe": round(r["oos"]["sharpe"], 3),
                "oos_pf": round(r["oos"]["pf"], 3),
                "oos_calmar": round(r["oos"]["calmar"], 3),
                "oos_mdd": round(r["oos"]["mdd"], 4),
                "oos_trades": r["oos"]["trades"],
                "degradation_is_val": round(r["degradation_is_val"], 3)
                if r["degradation_is_val"] is not None
                else None,
            }
            for r in results
        ],
    }

    out_path = (
        OUTPUTS_DIR
        / f"optuna_validation_oos_{args.study_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info(f"\n✅ Saved: {out_path}")
    logger.info(f"\n=== VALIDATION SUMMARY ===")
    logger.info(f"Study:               {args.study_name}")
    logger.info(f"Candidates validated: {len(results)}")
    logger.info(f"Top OOS Sharpe:       {top_oos:.3f}")
    logger.info(f"OOS 95% CI:           [{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}]")
    logger.info(f"Deflated Sharpe:      {deflated_sharpe:.3f}  (LCL: {lcl:.3f})")
    logger.info(f"PBO Proxy:            {pbo_proxy:.3f}  → {output['interpretation']}")


if __name__ == "__main__":
    main()
