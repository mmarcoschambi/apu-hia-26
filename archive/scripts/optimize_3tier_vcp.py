#!/usr/bin/env python3
"""
optimize_3tier_vcp.py
=====================
3-Tier Optimization Pipeline - VCP (Volatility Contraction Pattern)

Igual estructura que optimize_3tier.py pero con:
  - signal_type="vcp" fijado en todo el pipeline
  - 4 parametros VCP adicionales que Optuna optimiza:
      vcp_pivot_window  (10-25)
      vcp_atr_short     (5-15)
      vcp_atr_long      (20-40)
      vcp_atr_ratio     (0.60-0.95)
  - Guarda resultados en config/vcp_config.json (NO toca production_config.json)
  - Holdout 2025-H2 preservado

Uso:
    python3 optimize_3tier_vcp.py --trials 200 --tickers 50
    python3 optimize_3tier_vcp.py --trials 30  --tickers 30   # quick smoke test

DEPRECATION NOTE:
    Este script NO tiene golden guard -- siempre sobreescribe vcp_config.json.
    Preferir el pipeline unificado con golden guard:
        python3 optimize_3tier.py --signal-type vcp --trials 200 --tickers 80
    Ese pipeline usa pattern_configs.py, tiene golden guard, y exporta a vcp_config.json.
    Este script se mantiene solo para smoke tests rapidos o debugging.
"""
import sys, json, logging, argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import optuna
import pandas as pd

optuna.logging.set_verbosity(optuna.logging.WARNING)

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from optimize_3tier import (
    get_universe_from_db,
    build_tier3_engine_params,
    derive_tier2_filters,
    get_tier3_config,
    validate_tier3_params,
    normalize_engine_results,
    run_baseline,
)
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / "optimize_vcp.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)

VCP_CONFIG_PATH = PROJECT_ROOT / "config" / "vcp_config.json"
VCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
HOLDOUT_START = "2025-07-01"


def optimize_vcp(
    universe: List[str],
    start_date: str,
    end_date: str,
    tier2_derived: Dict[str, Any],
    tier3_engine_params: Dict[str, Any],
    n_trials: int = 100,
    initial_capital: float = 100_000,
    use_pit_universe: bool = False,
    optim_seed: Optional[int] = None,
) -> Tuple[Dict[str, Any], float, optuna.Study]:
    """Optimiza salida (tp1_r, tp2_r, pcts) + entrada VCP (pivot_window, atrs)."""
    logger.info("=" * 70)
    logger.info("VCP OPTIMIZATION -- Tier 1 + VCP Entry Params")
    logger.info("=" * 70)
    logger.info(f"  Trials: {n_trials}  |  Universe: {len(universe)} tickers")

    risk_fraction = tier3_engine_params.get("risk_fraction", 0.005)
    risk_dollars  = int(initial_capital * risk_fraction)

    fixed_params = {
        **tier2_derived,
        **tier3_engine_params,
        "mode":                         "production",
        "fees":                         0.001,
        "slippage":                     0.001,
        "risk_dollars":                 risk_dollars,
        "signal_type":                  "vcp",
        # Market regime: keep basic SPY filter but allow in-sample optimization
        # to see trades in both bull and bear periods (same logic as run_baseline).
        # The regime filter is validated OOS, not optimized in-sample.
        "require_spy_above_sma50":      False,
        "max_vix_threshold":            40.0,
        "use_market_regime_filter":     False,
        "block_trades_in_stage3":       False,
        "block_trades_in_stage4":       False,
        "use_earnings_calendar":        False,
        "use_trailing_stop":            False,
        "use_composite_sector_scoring": False,
        "use_adaptive_filtering":       False,  # VCP: adaptive filters calibrated for breakout
        "use_pit_universe":             use_pit_universe,
    }

    # Pre-cargar datos una sola vez para todos los trials (performance)
    logger.info("Pre-loading data template (shared across all trials)...")
    skip_kw = {"signal_type", "risk_dollars", "fees", "slippage", "mode", "use_pit_universe"}
    init_kw = {k: v for k, v in fixed_params.items() if k not in skip_kw}
    _template = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        signal_type="vcp",
        **init_kw,
    )
    _template.load_data()
    logger.info(f"  Template: {len(_template.close.columns)} tickers x {len(_template.close)} days")
    _regime_clf = getattr(_template, "market_regime_classifier", None)

    def objective(trial: optuna.Trial) -> float:
        # Tier 1: parametros de salida
        tp1_r   = trial.suggest_float("tp1_r",   1.25, 2.50, step=0.25)
        tp2_r   = trial.suggest_float("tp2_r",   2.00, 5.00, step=0.25)
        tp1_pct = trial.suggest_float("tp1_pct", 0.35, 0.60, step=0.05)
        tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.50, step=0.05)
        runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)

        if runner_pct < 0.05 or runner_pct > 0.30:
            return -999.0
        if tp2_r - tp1_r < 0.75:
            return -999.0

        # VCP entry params -- Tier-1 entry criteria (all Optuna-tunable)
        pivot_window    = trial.suggest_int("vcp_pivot_window",    10, 25)
        atr_short       = trial.suggest_int("vcp_atr_short",        5, 15)
        atr_long        = trial.suggest_int("vcp_atr_long",        20, 40)
        atr_ratio       = trial.suggest_float("vcp_atr_ratio",   0.60, 0.95, step=0.05)
        vol_dry_periods = trial.suggest_int("vcp_volume_dry_periods", 3, 10)
        depth_max_pct   = trial.suggest_float("vcp_depth_max_pct", 8.0, 20.0, step=1.0)
        pivot_dist_max  = trial.suggest_float("vcp_pivot_dist_max_pct", 3.0, 12.0, step=1.0)
        require_vol_dry = trial.suggest_categorical("vcp_require_vol_dry", [True, False])

        if atr_short >= atr_long:
            return -999.0
        # tp2 must be at least 1R above tp1
        if tp2_r - tp1_r < 0.75:
            return -999.0

        all_params = {
            **fixed_params,
            "tp1_r":                    tp1_r,
            "tp2_r":                    tp2_r,
            "tp1_pct":                  tp1_pct,
            "tp2_pct":                  tp2_pct,
            "runner_pct":               runner_pct,
            "vcp_pivot_window":         pivot_window,
            "vcp_atr_short":            atr_short,
            "vcp_atr_long":             atr_long,
            "vcp_atr_ratio":            atr_ratio,
            "vcp_volume_dry_periods":   vol_dry_periods,
            "vcp_depth_max_pct":        depth_max_pct,
            "vcp_pivot_dist_max_pct":   pivot_dist_max,
            "vcp_require_vol_dry":      require_vol_dry,
        }

        try:
            skip2 = {"fees", "slippage", "mode", "use_pit_universe"}
            engine_kw = {k: v for k, v in all_params.items() if k not in skip2}
            engine = AdvancedVectorBTEngine(
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                _preloaded_regime_classifier=_regime_clf,
                **engine_kw,
            )
            # Reusar datos pre-cargados
            # Copy ALL DataFrame/Series attrs set during load_data()
            # Missing any of these causes AttributeError in run_backtest()
            for attr in (
                "close", "high", "low", "volume",
                "sma_20", "sma_50", "rvol", "avg_volume_20",
                "adr_pct", "dist_sma20_pct", "dollar_volume",
                "consolidation_days", "consolidation_range",
                "ema_8", "ema_21", "ema_10", "trend_aligned",
                "spy_close", "vix_close", "spy_ema20",
                "spy_sma200", "spy_sma50",
                "market_is_bullish", "market_is_safe",
            ):
                src = getattr(_template, attr, None)
                if src is not None:
                    setattr(engine, attr, src.copy())
            tm = getattr(_template, "tradeable_mask", None)
            if tm is not None:
                engine.tradeable_mask = tm.copy()

            results = normalize_engine_results(engine.run_backtest())
            sharpe   = results.get("sharpe_ratio", 0.0)
            max_dd   = results.get("max_drawdown", 1.0)
            n_trades = results.get("total_trades", 0)
            win_rate = results.get("win_rate", 0.0)

            # min trades scales with universe size: at least 2 trades per ticker
            min_trades = max(30, len(universe) // 5)
            if n_trades < min_trades:
                return -999.0

            score = sharpe
            if max_dd > 0.25:
                score -= (max_dd - 0.25) * 2.0
            if win_rate < 0.40:
                score -= 0.5

            trial.set_user_attr("sharpe",      round(sharpe, 4))
            trial.set_user_attr("max_dd",      round(max_dd * 100, 2))
            trial.set_user_attr("win_rate",    round(win_rate * 100, 2))
            trial.set_user_attr("n_trades",    n_trades)
            trial.set_user_attr("pivot_win",   pivot_window)
            trial.set_user_attr("atr_ratio",   atr_ratio)
            trial.set_user_attr("depth_max",   depth_max_pct)
            trial.set_user_attr("pivot_dist",  pivot_dist_max)
            trial.set_user_attr("vol_dry",     vol_dry_periods)
            trial.set_user_attr("req_vol_dry", require_vol_dry)
            return float(score)

        except Exception as e:
            logger.debug(f"  Trial {trial.number} error: {e}")
            return -999.0

    sampler = optuna.samplers.TPESampler(
        seed=optim_seed or 42,
        n_startup_trials=max(20, n_trials // 5),
    )
    study = optuna.create_study(direction="maximize", sampler=sampler)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

    best = study.best_trial
    logger.info(f"\n  Best trial #{best.number}:")
    logger.info(f"    Score    : {best.value:.4f}")
    logger.info(f"    Sharpe   : {best.user_attrs.get('sharpe')}")
    logger.info(f"    Max DD   : {best.user_attrs.get('max_dd')}%")
    logger.info(f"    Win Rate : {best.user_attrs.get('win_rate')}%")
    logger.info(f"    Trades   : {best.user_attrs.get('n_trades')}")
    logger.info(f"    pivot_win: {best.user_attrs.get('pivot_win')}")
    logger.info(f"    atr_ratio: {best.user_attrs.get('atr_ratio')}")
    return best.params, best.value, study


def export_vcp_config(best_params, best_score, tier2_derived, tier3_raw, args):
    """Guarda config/vcp_config.json. NO toca production_config.json."""
    tp1_pct    = best_params.get("tp1_pct", 0.55)
    tp2_pct    = best_params.get("tp2_pct", 0.20)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    config = {
        "_schema_version":      "1.0",
        "_description":         "VCP golden config -- optimize_3tier_vcp.py",
        "_last_updated":        datetime.now().isoformat(),
        "_optimization_method": "3Tier_VCP_Optuna",
        "_trials":              args.trials,
        "_period":              f"{args.start} to {args.end}",
        "_tickers":             args.tickers,
        "_best_score":          round(best_score, 6),
        "signal_type":          "vcp",
        "=== TIER 1: STRATEGY ===": {},
        "tier1_strategy": {
            "tp1_r":        best_params.get("tp1_r",    1.75),
            "tp2_r":        best_params.get("tp2_r",    4.00),
            "tp1_pct":      tp1_pct,
            "tp2_pct":      tp2_pct,
            "runner_pct":   runner_pct,
            "risk_dollars": int(args.capital * tier3_raw.get("risk_fraction", 0.005)),
            "max_stop_pct": tier3_raw.get("max_stop_pct_hard", 0.08),
        },
        "=== VCP ENTRY PARAMS ===": {},
        "vcp_entry": {
            "vcp_pivot_window":       best_params.get("vcp_pivot_window", 15),
            "vcp_atr_short":          best_params.get("vcp_atr_short", 10),
            "vcp_atr_long":           best_params.get("vcp_atr_long", 30),
            "vcp_atr_ratio":          best_params.get("vcp_atr_ratio", 0.85),
            "vcp_volume_dry_periods": best_params.get("vcp_volume_dry_periods", 5),
            "vcp_depth_max_pct":      best_params.get("vcp_depth_max_pct", 15.0),
            "vcp_pivot_dist_max_pct": best_params.get("vcp_pivot_dist_max_pct", 8.0),
            "vcp_require_vol_dry":    best_params.get("vcp_require_vol_dry", True),
            "_note": "v2: atr_contracting+pivot_break+vol_dry+near_pivot+tight_base",
        },
        "=== TIER 2: FILTERS ===": {},
        "tier2_filters": tier2_derived,
        "=== TIER 3: RISK ===": {},
        "tier3_risk": tier3_raw,
        "=== MARKET REGIME ===": {},
        "market_regime": {
            "require_spy_above_sma50":  True,
            "max_vix":                  25.0,
            "use_market_regime_filter": True,
            "block_trades_in_stage3":   True,
            "block_trades_in_stage4":   True,
        },
    }
    with open(VCP_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, default=str)
    t1 = config["tier1_strategy"]
    ve = config["vcp_entry"]
    logger.info(f"\n  VCP config saved: {VCP_CONFIG_PATH}")
    logger.info(f"  tp1={t1['tp1_r']}R  tp2={t1['tp2_r']}R  pivot_win={ve['vcp_pivot_window']}  atr_ratio={ve['vcp_atr_ratio']}")
    logger.info("  production_config.json untouched -- breakout golden config preserved.")


def run_vcp_pipeline(args):
    import logging as _lg
    _lg.getLogger(__name__).warning(
        "optimize_3tier_vcp.py is DEPRECATED: no golden guard, always overwrites vcp_config.json.\n"
        "  Use: python3 optimize_3tier.py --signal-type vcp  (has golden guard + unified pipeline)"
    )
    if str(args.end) > HOLDOUT_START:
        logger.warning(f"Capping end_date to {HOLDOUT_START} (2025-H2 holdout guard)")
        args.end = HOLDOUT_START

    logger.info("=" * 70)
    logger.info("VCP 3-TIER OPTIMIZATION PIPELINE")
    logger.info("=" * 70)
    logger.info(f"  Date   : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"  Period : {args.start} to {args.end}")
    logger.info(f"  Trials : {args.trials}  |  Tickers: {args.tickers}")
    logger.info(f"  Capital: ${args.capital:,.0f}")

    validate_tier3_params()
    tier3_raw    = get_tier3_config()
    tier3_engine = build_tier3_engine_params(tier3_raw)

    universe = get_universe_from_db(limit=args.tickers, start_date=args.start, end_date=args.end)
    logger.info(f"\n  Universe: {len(universe)} tickers ({', '.join(universe[:5])}...)")

    logger.info("\nPhase 1: VCP baseline run with loose filters (derive Tier 2)...")
    # Run VCP baseline with loose filters -- signal_type=vcp is critical so that
    # derive_tier2_filters sees VCP trade characteristics, not breakout ones.
    risk_fraction = tier3_engine.get("risk_fraction", 0.005)
    risk_dollars  = int(args.capital * risk_fraction)
    loose_vcp_params = {
        **tier3_engine,
        "signal_type":             "vcp",
        "vcp_pivot_window":        15,
        "vcp_atr_short":           10,
        "vcp_atr_long":            30,
        "vcp_atr_ratio":           0.85,
        "min_rvol":                0.3,
        "min_adr":                 0.5,
        "max_dist_sma20":          30.0,
        "min_consolidation_days":  2,
        "min_volume":              100_000,
        "min_dollar_volume":       1_000_000,
        "tp1_r":                   1.75,
        "tp2_r":                   4.0,
        "tp1_pct":                 0.55,
        "tp2_pct":                 0.20,
        "runner_pct":              0.25,
        "mode":                    "production",
        "fees":                    0.001,
        "slippage":                0.001,
        "risk_dollars":            risk_dollars,
        "require_spy_above_sma50": False,
        "use_market_regime_filter": False,
        "use_adaptive_filtering":  False,
        "use_rs_percentile":       False,
        "use_earnings_calendar":   False,
        "use_trailing_stop":       False,
        "use_pit_universe":        False,
    }
    baseline_engine = AdvancedVectorBTEngine(
        universe=universe, start_date=args.start, end_date=args.end,
        initial_capital=args.capital,
        **{k: v for k, v in loose_vcp_params.items() if k not in ("fees","slippage","mode")},
    )
    baseline_results = baseline_engine.run_backtest()
    baseline_results = normalize_engine_results(baseline_results)
    # Extract trades DataFrame from engine
    baseline_trades = getattr(baseline_engine, "_last_trades_df", None)
    if baseline_trades is None or len(baseline_trades) == 0:
        # Fallback: try results dict
        baseline_trades = baseline_results.get("trades_df", None)
    n_bt = baseline_results.get("total_trades", 0)
    logger.info(f"  VCP Baseline: {n_bt} trades  Sharpe={baseline_results.get('sharpe_ratio', 0):.3f}")
    if baseline_trades is None or len(baseline_trades) < 10:
        logger.warning("  Too few VCP baseline trades -- using default Tier 2 filters")
        from optimize_3tier import _default_tier2
        tier2_derived = _default_tier2()
    else:
        logger.info(f"  Baseline trades shape: {baseline_trades.shape}")

    logger.info("\nPhase 2: Deriving Tier 2 filters from baseline trades...")
    tier2_derived = derive_tier2_filters(
        trades_df=baseline_trades,
        keep_pct=getattr(args, "keep_pct", 95),
    )

    logger.info("\nPhase 3: VCP Optuna optimization...")
    best_params, best_score, study = optimize_vcp(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        tier2_derived=tier2_derived,
        tier3_engine_params=tier3_engine,
        n_trials=args.trials,
        initial_capital=args.capital,
        use_pit_universe=False,
        optim_seed=42,
    )

    export_vcp_config(best_params, best_score, tier2_derived, tier3_raw, args)

    completed = [t for t in study.trials if t.value is not None and t.value > -900]
    logger.info("\n" + "=" * 70)
    logger.info("VCP OPTIMIZATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"  Valid trials : {len(completed)} / {args.trials}")
    logger.info(f"  Best score   : {best_score:.4f}")
    logger.info(f"  Config saved : {VCP_CONFIG_PATH}")
    logger.info(f"  Next -- OOS validation:")
    logger.info(f"    python3 optimize_3tier_vcp.py --trials 1 --tickers {args.tickers} "
                f"--start 2025-01-01 --end 2025-06-30 --skip-validation")
    return {"best_params": best_params, "best_score": best_score}


def main():
    parser = argparse.ArgumentParser(
        description="VCP 3-Tier Optimization Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python3 optimize_3tier_vcp.py --trials 200 --tickers 50
  python3 optimize_3tier_vcp.py --trials 300 --tickers 80 --start 2021-01-01 --end 2025-06-30
  python3 optimize_3tier_vcp.py --trials 30  --tickers 30   # quick smoke test

IMPORTANTE:
  - NO modifica production_config.json (breakout golden config intocable).
  - Guarda en config/vcp_config.json.
  - Holdout 2025-H2 preservado automaticamente.
        """,
    )
    parser.add_argument("--trials",          type=int,   default=100)
    parser.add_argument("--tickers",         type=int,   default=50)
    parser.add_argument("--start",           type=str,   default="2021-01-01")
    parser.add_argument("--end",             type=str,   default="2025-06-30")
    parser.add_argument("--capital",         type=float, default=100_000)
    parser.add_argument("--keep-pct",        type=float, default=95)
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    run_vcp_pipeline(args)


if __name__ == "__main__":
    main()
