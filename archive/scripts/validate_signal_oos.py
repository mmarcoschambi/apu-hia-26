#!/usr/bin/env python3
"""
validate_signal_oos.py
======================
Generic OOS validator for any signal type (vcp, pocket_pivot, flat_base).
Creates validate scripts on-the-fly similar to validate_vcp_oos.py.

Usage:
    python3 validate_signal_oos.py --signal-type pocket_pivot
    python3 validate_signal_oos.py --signal-type flat_base --tickers 100
    python3 validate_signal_oos.py --signal-type vcp --start 2024-01-01 --end 2025-12-31
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
              logging.FileHandler(f"validate_oos.log", mode="a")])
logger = logging.getLogger(__name__)


def run_oos_validation(signal_type: str, args):
    """Run OOS validation for any signal type"""
    config_file = Path(f"config/{signal_type}_config.json")
    
    if not config_file.exists():
        raise FileNotFoundError(
            f"{signal_type.upper()} config not found: {config_file}\n"
            f"Run: python3 optimize_3tier.py --signal-type {signal_type} --trials 200 --tickers 80"
        )

    cfg = json.load(open(config_file))
    t1  = cfg["tier1_strategy"]
    t2  = cfg.get("tier2_filters", {})
    t3  = cfg.get("tier3_risk", {})
    mr  = cfg.get("market_regime", {})
    
    # Signal-specific entry params
    signal_params = {}
    if signal_type == "vcp":
        ve = cfg.get("vcp_entry", cfg.get("tier1_strategy", {}))
        signal_params = {
            "vcp_pivot_window": ve["vcp_pivot_window"],
            "vcp_atr_short": ve["vcp_atr_short"],
            "vcp_atr_long": ve["vcp_atr_long"],
            "vcp_atr_ratio": ve["vcp_atr_ratio"],
            "vcp_volume_dry_periods": ve.get("vcp_volume_dry_periods", 5),
            "vcp_depth_max_pct": ve.get("vcp_depth_max_pct", 15.0),
            "vcp_pivot_dist_max_pct": ve.get("vcp_pivot_dist_max_pct", 8.0),
            "vcp_require_vol_dry": ve.get("vcp_require_vol_dry", True),
        }
    elif signal_type == "pocket_pivot":
        pp = cfg.get("pocket_pivot_entry", {})
        signal_params = {
            "pp_lookback_days": pp.get("pp_lookback_days", 10),
            "pp_min_rvol": pp.get("pp_min_rvol", 1.0),
        }
    elif signal_type == "flat_base":
        fb = cfg.get("flat_base_entry", {})
        signal_params = {
            "fb_min_days": fb.get("fb_min_days", 5),
            "fb_max_depth_pct": fb.get("fb_max_depth_pct", 8.0),
            "fb_breakout_margin": fb.get("fb_breakout_margin", 0.01),
        }
    elif signal_type == "breakout":
        bo = cfg.get("breakout_entry", {})
        signal_params = {
            "breakout_lookback": bo.get("breakout_lookback", 20),
            "breakout_margin": bo.get("breakout_margin", 0.01),
            "breakout_min_consolidation": bo.get("breakout_min_consolidation", 10),
        }

    # IS window
    is_period  = cfg.get("_period", "2019-01-01 to 2025-07-01")
    is_start   = args.is_start if args.is_start else is_period.split(" to ")[0].strip()
    is_end     = args.is_end if args.is_end else args.start

    logger.info("=" * 70)
    logger.info(f"{signal_type.upper()} OOS VALIDATION")
    logger.info("=" * 70)
    logger.info(f"  Signal type: {signal_type}")
    logger.info(f"  IS period  : {is_start} to {is_end}")
    logger.info(f"  OOS period : {args.start} to {args.end}")
    logger.info(f"  Tickers    : {args.tickers}")
    logger.info(f"  Config     : {config_file}")
    logger.info(f"  Params     : tp1={t1['tp1_r']}R tp2={t1['tp2_r']}R")

    # Fixed universe covering full IS+OOS window
    full_start = is_start
    full_end   = args.end
    universe = get_universe_from_db(limit=args.tickers,
                                    start_date=full_start, end_date=full_end)
    logger.info(f"\n  Universe: {len(universe)} tickers (fixed over {full_start} to {full_end})")

    risk_fraction = t3.get("risk_fraction", 0.005)
    risk_dollars  = int(args.capital * risk_fraction)

    # Common engine params
    common_params = {
        "universe": universe,
        "initial_capital": args.capital,
        "signal_type": signal_type,
        "tp1_r": t1["tp1_r"],
        "tp2_r": t1["tp2_r"],
        "tp1_pct": t1["tp1_pct"],
        "tp2_pct": t1["tp2_pct"],
        "runner_pct": t1.get("runner_pct", 0.25),
        "risk_dollars": risk_dollars,
        "max_stop_pct": t1.get("max_stop_pct", 0.08) * 100,
        "min_rvol": t2.get("min_rvol", 0.5),
        "min_adr": t2.get("min_adr", 1.0),
        "max_dist_sma20": t2.get("max_dist_sma20", 20.0),
        "min_consolidation_days": t2.get("min_consolidation_days", 3),
        "min_volume": t2.get("min_volume", 100_000),
        "min_dollar_volume": t2.get("min_dollar_volume", 1_000_000),
        "min_rs_percentile": t2.get("min_rs_percentile", 70.0),
        "use_rs_percentile": t2.get("use_rs_percentile", False),
        "rvol_danger": t3.get("rvol_danger", 3.0),
        "rvol_warning": t3.get("rvol_warning", 2.0),
        "rvol_danger_size": int(t3.get("rvol_danger_size", 50)),
        "rvol_warning_size": int(t3.get("rvol_warning_size", 75)),
        "max_exposure_pct": t3.get("max_exposure_pct", 0.65),
        "require_spy_above_sma50": mr.get("require_spy_above_sma50", True),
        "max_vix_threshold": mr.get("max_vix", 30.0),
        "use_market_regime_filter": True,
        "block_trades_in_stage3": True,
        "block_trades_in_stage4": True,
        "use_adaptive_filtering": False,
        "use_earnings_calendar": False,
        "use_trailing_stop": False,
    }
    common_params.update(signal_params)

    # IS re-run
    logger.info(f"\nRunning IS re-run ({is_start} to {is_end}, same universe)...")
    is_engine = AdvancedVectorBTEngine(
        start_date=is_start,
        end_date=is_end,
        **common_params
    )
    is_results = normalize_engine_results(is_engine.run_backtest())
    is_score = is_results.get("sharpe_ratio", 0.0)
    is_trades = is_results.get("total_trades", 0)
    is_wr = is_results.get("win_rate", 0.0) * 100
    logger.info(f"  IS re-run: Sharpe={is_score:.4f}  trades={is_trades}  WR={is_wr:.1f}%")

    # OOS run
    logger.info("\nRunning OOS backtest...")
    oos_engine = AdvancedVectorBTEngine(
        start_date=args.start,
        end_date=args.end,
        **common_params
    )
    results = normalize_engine_results(oos_engine.run_backtest())

    oos_sharpe = results.get("sharpe_ratio", 0.0)
    oos_dd = results.get("max_drawdown", 0.0) * 100
    oos_wr = results.get("win_rate", 0.0) * 100
    oos_trades = results.get("total_trades", 0)
    oos_return = results.get("total_return", 0.0) * 100
    # Degradation logic:
    # - IS > 0 and OOS > 0: normal ratio (OOS/IS >= 0.20 to pass)
    # - IS <= 0 and OOS > 0: IS was garbage, OOS improved -> PASS outright
    # - IS > 0 and OOS <= 0: strategy got worse -> FAIL
    # - IS <= 0 and OOS <= 0: both bad -> FAIL
    if is_score <= 0 and oos_sharpe > 0:
        degradation = 1.0  # OOS better than IS -> treat as passing
        degradation_note = f"IS={is_score:.3f} (negative/zero IS, OOS positive -> improvement)"
    elif is_score > 0:
        degradation = oos_sharpe / is_score
        degradation_note = f"OOS/IS = {degradation:.1%}"
    else:
        degradation = 0.0  # both negative
        degradation_note = f"IS={is_score:.3f} OOS={oos_sharpe:.3f} (both negative)"

    logger.info("\n" + "=" * 70)
    logger.info("OOS RESULTS")
    logger.info("=" * 70)
    logger.info(f"  Sharpe     : {oos_sharpe:.4f}  "
                f"(IS_comparable={is_score:.4f}  {degradation_note})")
    logger.info(f"  IS trades  : {is_trades}  IS WR: {is_wr:.1f}%")
    logger.info(f"  Max DD     : {oos_dd:.1f}%")
    logger.info(f"  Win Rate   : {oos_wr:.1f}%")
    logger.info(f"  Trades     : {oos_trades}")
    logger.info(f"  Return     : {oos_return:.1f}%")

    # Verdict
    MIN_DEGRADATION = 0.20
    MIN_TRADES = 10
    passed = degradation >= MIN_DEGRADATION and oos_trades >= MIN_TRADES and oos_sharpe > 0

    logger.info("\n" + "=" * 70)
    if passed:
        logger.info("  VERDICT: ✅ PASSED")
        logger.info(f"  OOS Sharpe {oos_sharpe:.3f} | {degradation_note} -- above {MIN_DEGRADATION:.0%} threshold")
        logger.info(f"  {signal_type.upper()} config is ready for production scanner integration.")
    else:
        logger.info("  VERDICT: ❌ FAILED")
        if degradation < MIN_DEGRADATION:
            logger.info(f"  Degradation {degradation:.1%} below {MIN_DEGRADATION:.0%} threshold | {degradation_note}")
            logger.info("  Recommendation: re-optimize with larger universe or different date range.")
        if oos_trades < MIN_TRADES:
            logger.info(f"  Too few OOS trades ({oos_trades}) -- consider longer OOS window or more tickers.")
        if oos_sharpe <= 0:
            logger.info("  Negative OOS Sharpe -- strategy does not generalize.")
    logger.info("=" * 70)

    # Save OOS result back to config
    cfg["_oos_validation"] = {
        "date": datetime.now().isoformat(),
        "period": f"{args.start} to {args.end}",
        "tickers": args.tickers,
        "oos_sharpe": round(oos_sharpe, 4),
        "oos_max_dd": round(oos_dd, 2),
        "oos_win_rate": round(oos_wr, 2),
        "oos_trades": oos_trades,
        "is_sharpe_comparable": round(is_score, 4),
        "is_period_comparable": f"{is_start} to {is_end}",
        "is_trades_comparable": is_trades,
        "degradation": round(degradation, 4),
        "passed": str(passed),
    }
    # Golden guard: only overwrite if new OOS beats existing by >=5%
    _existing_oos = cfg.get("_oos_sharpe", 0.0)
    _margin = 0.05
    _should_save = (
        not passed  # always save failed runs (they update the _oos_validation block)
        or _existing_oos == 0.0  # no prior golden
        or oos_sharpe >= _existing_oos * (1 + _margin)  # new beats golden
    )
    if passed and not _should_save:
        logger.info(f"  GOLDEN GUARD: OOS {oos_sharpe:.3f} does not beat "
                    f"existing {_existing_oos:.3f} by >{_margin*100:.0f}% -- config preserved")
    else:
        if passed:
            cfg["_oos_sharpe"] = round(oos_sharpe, 2)
            cfg["_oos_stamped"] = datetime.now().isoformat()
        with open(config_file, "w") as f:
            json.dump(cfg, f, indent=2, default=str)
        logger.info(f"\n  OOS results saved to {config_file}")
    
    return passed


def main():
    parser = argparse.ArgumentParser(description="Generic OOS Validation for any signal type")
    parser.add_argument("--signal-type", required=True, 
                        choices=["vcp", "pocket_pivot", "flat_base", "breakout"],
                        help="Signal type to validate")
    parser.add_argument("--start", default="2023-01-01", help="OOS start date")
    parser.add_argument("--end", default="2024-12-31", help="OOS end date")
    parser.add_argument("--tickers", type=int, default=120, help="Universe size")
    parser.add_argument("--capital", type=float, default=100_000, help="Initial capital")
    parser.add_argument("--is-start", default=None, help="Override IS start date")
    parser.add_argument("--is-end", default=None, help="Override IS end date")
    args = parser.parse_args()
    
    run_oos_validation(args.signal_type, args)


if __name__ == "__main__":
    main()
