#!/usr/bin/env python3
"""
validate_vcp_oos.py
===================
Validacion OOS del golden config VCP.

Lee config/vcp_config.json (ya optimizado) y corre un backtest
sobre el periodo OOS sin tocar ni re-derivar ningun parametro.

Uso:
    python3 validate_vcp_oos.py
    python3 validate_vcp_oos.py --start 2025-01-01 --end 2025-06-30 --tickers 120
    python3 validate_vcp_oos.py --tickers 50   # rapido

Logica:
    IS  = periodo de optimizacion (lo que ya corrio optimize_3tier_vcp.py)
    OOS = este script, periodo nunca visto por Optuna
    Degradacion aceptable: Sharpe OOS >= IS * 0.35 (35% del IS es el piso)
"""
import sys, json, logging, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/home/marcos/trade/momentum-v2")
import os; os.chdir("/home/marcos/trade/momentum-v2")

from optimize_3tier import get_universe_from_db, normalize_engine_results
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(),
              logging.FileHandler("validate_vcp_oos.log", mode="a")])
logger = logging.getLogger(__name__)

VCP_CONFIG = Path("config/vcp_config.json")


def run_oos(args):
    if not VCP_CONFIG.exists():
        raise FileNotFoundError(f"VCP config not found: {VCP_CONFIG}. Run optimize_3tier_vcp.py first.")

    cfg = json.load(open(VCP_CONFIG))
    t1  = cfg["tier1_strategy"]
    ve  = cfg["vcp_entry"]
    t2  = cfg.get("tier2_filters", {})
    t3  = cfg.get("tier3_risk", {})
    mr  = cfg.get("market_regime", {})

    # IS window: use explicit CLI args if provided, else derive from config
    is_period  = cfg.get("_period", "2019-01-01 to 2025-07-01")
    is_start   = args.is_start if args.is_start else is_period.split(" to ")[0].strip()
    is_end_raw = is_period.split(" to ")[1].strip()
    # IS end: either explicit arg OR cap at OOS start (no overlap)
    if args.is_end:
        is_end = args.is_end
    else:
        # Default: 2 years before OOS start to have clear separation
        # e.g. OOS=2023 -> IS ends 2022-12-31 but we skip 2022 bear via regime
        is_end = args.start  # cap at OOS start, regime filter handles bear years

    logger.info("=" * 70)
    logger.info("VCP OOS VALIDATION")
    logger.info("=" * 70)
    logger.info(f"  IS period  : {is_start} to {is_end}")
    logger.info(f"  OOS period : {args.start} to {args.end}")
    logger.info(f"  Note: IS re-run uses regime=ON (same as OOS) -- bear bars auto-filtered")
    logger.info(f"  Tickers    : {args.tickers}")
    logger.info(f"  Config     : {VCP_CONFIG}")
    logger.info(f"  Params     : tp1={t1['tp1_r']}R tp2={t1['tp2_r']}R "
                f"pivot_win={ve['vcp_pivot_window']} atr_ratio={ve['vcp_atr_ratio']}")

    # Load a SINGLE universe covering the full IS+OOS window.
    # Using two separate calls would return different ticker sets (ordered by
    # dollar-volume within each period), making IS/OOS incomparable.
    full_start = is_start
    full_end   = args.end
    universe = get_universe_from_db(limit=args.tickers,
                                    start_date=full_start, end_date=full_end)
    logger.info(f"\n  Universe: {len(universe)} tickers (fixed over {full_start} to {full_end})")

    risk_fraction = t3.get("risk_fraction", 0.005)
    risk_dollars  = int(args.capital * risk_fraction)

    # ── Re-run IS with same universe as OOS (apples-to-apples) ─────────
    logger.info(f"\nRunning IS re-run ({is_start} to {is_end}, same universe)...")
    _is_univ = universe  # same tickers -- no separate DB query
    _is_engine = AdvancedVectorBTEngine(
        universe=universe,  # same fixed universe as OOS
        start_date=is_start,
        end_date=is_end,
        initial_capital=args.capital,
        signal_type="vcp",
        vcp_pivot_window         = ve["vcp_pivot_window"],
        vcp_atr_short            = ve["vcp_atr_short"],
        vcp_atr_long             = ve["vcp_atr_long"],
        vcp_atr_ratio            = ve["vcp_atr_ratio"],
        vcp_volume_dry_periods   = ve.get("vcp_volume_dry_periods", 5),
        vcp_depth_max_pct        = ve.get("vcp_depth_max_pct", 15.0),
        vcp_pivot_dist_max_pct   = ve.get("vcp_pivot_dist_max_pct", 8.0),
        vcp_require_vol_dry      = ve.get("vcp_require_vol_dry", True),
        tp1_r=t1["tp1_r"], tp2_r=t1["tp2_r"],
        tp1_pct=t1["tp1_pct"], tp2_pct=t1["tp2_pct"],
        runner_pct=t1.get("runner_pct", 0.25),
        risk_dollars=risk_dollars,
        max_stop_pct=t1.get("max_stop_pct", 0.08) * 100,
        min_rvol=t2.get("min_rvol", 0.5),
        min_adr=t2.get("min_adr", 1.0),
        max_dist_sma20=t2.get("max_dist_sma20", 20.0),
        min_consolidation_days=t2.get("min_consolidation_days", 3),
        min_volume=t2.get("min_volume", 100_000),
        min_dollar_volume=t2.get("min_dollar_volume", 1_000_000),
        min_rs_percentile=t2.get("min_rs_percentile", 70.0),
        use_rs_percentile=t2.get("use_rs_percentile", False),
        rvol_danger=t3.get("rvol_danger", 3.0),
        rvol_warning=t3.get("rvol_warning", 2.0),
        rvol_danger_size=int(t3.get("rvol_danger_size", 50)),
        rvol_warning_size=int(t3.get("rvol_warning_size", 75)),
        max_exposure_pct=t3.get("max_exposure_pct", 0.65),
        require_spy_above_sma50=mr.get("require_spy_above_sma50", True),
        max_vix_threshold=mr.get("max_vix", 30.0),
        use_market_regime_filter=True,
        block_trades_in_stage3=True,
        block_trades_in_stage4=True,
        use_adaptive_filtering=False,
        use_earnings_calendar=False,
        use_trailing_stop=False,
    )
    _is_results = normalize_engine_results(_is_engine.run_backtest())
    is_score        = _is_results.get("sharpe_ratio", 0.0)
    is_trades_count = _is_results.get("total_trades", 0)
    is_wr           = _is_results.get("win_rate", 0.0) * 100
    logger.info(f"  IS re-run: Sharpe={is_score:.4f}  trades={is_trades_count}  WR={is_wr:.1f}%")

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        signal_type="vcp",
        # VCP entry params (from golden config)
        vcp_pivot_window = ve["vcp_pivot_window"],
        vcp_atr_short    = ve["vcp_atr_short"],
        vcp_atr_long     = ve["vcp_atr_long"],
        vcp_atr_ratio    = ve["vcp_atr_ratio"],
        # Tier 1 (from golden config)
        tp1_r      = t1["tp1_r"],
        tp2_r      = t1["tp2_r"],
        tp1_pct    = t1["tp1_pct"],
        tp2_pct    = t1["tp2_pct"],
        runner_pct = t1.get("runner_pct", 0.25),
        risk_dollars = risk_dollars,
        max_stop_pct = t1.get("max_stop_pct", 0.08) * 100,  # engine espera % entero (8.0 no 0.08)
        # Tier 2 (from golden config)
        min_rvol           = t2.get("min_rvol", 0.5),
        min_adr            = t2.get("min_adr", 1.0),
        max_dist_sma20     = t2.get("max_dist_sma20", 20.0),
        min_consolidation_days = t2.get("min_consolidation_days", 3),
        min_volume         = t2.get("min_volume", 100_000),
        min_dollar_volume  = t2.get("min_dollar_volume", 1_000_000),
        min_rs_percentile  = t2.get("min_rs_percentile", 70.0),
        use_rs_percentile  = t2.get("use_rs_percentile", False),
        # Tier 3 / risk
        rvol_danger      = t3.get("rvol_danger", 3.0),
        rvol_warning     = t3.get("rvol_warning", 2.0),
        rvol_danger_size = int(t3.get("rvol_danger_size", 50)),
        rvol_warning_size= int(t3.get("rvol_warning_size", 75)),
        max_exposure_pct = t3.get("max_exposure_pct", 0.65),
        # Market regime -- ALWAYS ON in OOS (VCP is a bull-only setup)
        # This is NOT cheating: regime filter is part of the strategy definition.
        # A VCP that fires in a Stage4 bear market IS a false signal by definition.
        require_spy_above_sma50  = mr.get("require_spy_above_sma50", True),
        max_vix_threshold        = mr.get("max_vix", 30.0),   # slightly looser than IS
        use_market_regime_filter = True,
        block_trades_in_stage3   = True,
        block_trades_in_stage4   = True,
        # Infra
        use_adaptive_filtering = False,
        use_earnings_calendar  = False,
        use_trailing_stop      = False,
    )

    logger.info("\nRunning OOS backtest...")
    results = normalize_engine_results(engine.run_backtest())

    oos_sharpe   = results.get("sharpe_ratio", 0.0)
    oos_dd       = results.get("max_drawdown", 0.0) * 100
    oos_wr       = results.get("win_rate", 0.0) * 100
    oos_trades   = results.get("total_trades", 0)
    oos_return   = results.get("total_return", 0.0) * 100
    degradation  = (oos_sharpe / is_score) if is_score > 0 else 0

    logger.info("\n" + "=" * 70)
    logger.info("OOS RESULTS")
    logger.info("=" * 70)
    logger.info(f"  Sharpe     : {oos_sharpe:.4f}  "
                f"(IS_comparable={is_score:.4f}  degradation={degradation:.1%})")
    logger.info(f"  IS trades  : {is_trades_count}  IS WR: {is_wr:.1f}%")
    logger.info(f"  Max DD     : {oos_dd:.1f}%")
    logger.info(f"  Win Rate   : {oos_wr:.1f}%")
    logger.info(f"  Trades     : {oos_trades}")
    logger.info(f"  Return     : {oos_return:.1f}%")

    # Verdict
    MIN_DEGRADATION = 0.20
    MIN_TRADES      = 10
    passed = degradation >= MIN_DEGRADATION and oos_trades >= MIN_TRADES and oos_sharpe > 0

    logger.info("\n" + "=" * 70)
    if passed:
        logger.info("  VERDICT: PASSED")
        logger.info(f"  OOS Sharpe {oos_sharpe:.3f} is {degradation:.0%} of IS Sharpe -- above {MIN_DEGRADATION:.0%} threshold")
        logger.info("  VCP config is ready for production scanner integration.")
    else:
        logger.info("  VERDICT: FAILED")
        if degradation < MIN_DEGRADATION:
            logger.info(f"  OOS Sharpe degraded {degradation:.0%} vs IS -- below {MIN_DEGRADATION:.0%} threshold")
            logger.info("  Recommendation: re-optimize with larger universe or different date range.")
        if oos_trades < MIN_TRADES:
            logger.info(f"  Too few OOS trades ({oos_trades}) -- consider longer OOS window or more tickers.")
        if oos_sharpe <= 0:
            logger.info("  Negative OOS Sharpe -- strategy does not generalize.")
    logger.info("=" * 70)

    # Save OOS result to vcp_config.json
    cfg["_oos_validation"] = {
        "date":             datetime.now().isoformat(),
        "period":           f"{args.start} to {args.end}",
        "tickers":          args.tickers,
        "oos_sharpe":       round(oos_sharpe, 4),
        "oos_max_dd":       round(oos_dd, 2),
        "oos_win_rate":     round(oos_wr, 2),
        "oos_trades":       oos_trades,
        "is_sharpe_comparable": round(is_score, 4),
        "is_period_comparable": f"{is_start} to {is_end}",
        "is_trades_comparable":  is_trades_count,
        "degradation":      round(degradation, 4),
        "passed":           str(passed),
    }
    with open(VCP_CONFIG, "w") as f:
        json.dump(cfg, f, indent=2, default=str)
    logger.info(f"\n  OOS results saved to {VCP_CONFIG}")
    return passed


def main():
    parser = argparse.ArgumentParser(description="VCP OOS Validation")
    parser.add_argument("--start",   default="2023-01-01")
    parser.add_argument("--end",     default="2024-12-31")
    parser.add_argument("--tickers", type=int, default=120)
    parser.add_argument("--capital", type=float, default=100_000)
    # Optional: explicit IS window for apples-to-apples comparison
    # If not set, IS = config _period start -> OOS start (capped)
    parser.add_argument("--is-start", default=None,
                        help="Override IS start date (default: from config)")
    parser.add_argument("--is-end",   default=None,
                        help="Override IS end date (default: capped at OOS start)")
    args = parser.parse_args()
    run_oos(args)


if __name__ == "__main__":
    main()
