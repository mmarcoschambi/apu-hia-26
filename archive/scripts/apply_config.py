#!/usr/bin/env python3
"""
Apply Config to Production - Automates the entire 3-tier workflow
=================================================================

Pipeline:
  1. Run backtest CLI to generate enriched trades
  2. Derive Tier 2 filters statistically from trades
  3. Optimize Tier 1 with THOR using derived Tier 2
  4. Update production_config.json + validated_production_params.json
  5. Validate the config

Usage:
    # Full workflow (backtest -> derive tier2 -> optimize tier1 -> apply)
    python3 apply_config.py --full --trials 100

    # Just update from existing optimization results (reads tier1_thor_report.json + tier2_filters_derived.json)
    python3 apply_config.py --update-only

    # Quick test mode (20 trials)
    python3 apply_config.py --full --quick

File paths (canonical):
    Trades:     outputs/backtests/complete_trades_clean.csv
    Tier 2:     config/tier2_filters_derived.json
    Tier 1:     outputs/tier1_optimization_thor/tier1_thor_report.json
    Tickers:    config/db_tickers.txt
    Config:     config/production_config.json
    Validated:  config/validated_production_params.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src" / "config"))

from dynamic_config import (
    update_production_config,
    load_production_config,
    get_engine_params,
)

# ======================================================================
# CANONICAL FILE PATHS - Single source of truth for the pipeline
# ======================================================================
TRADES_FILE = "outputs/backtests/complete_trades_clean.csv"
TIER2_FILE = "config/tier2_filters_derived.json"
TIER1_REPORT = "outputs/tier1_optimization_thor/tier1_thor_report.json"
TICKER_FILE = "config/db_tickers.txt"
PRODUCTION_CONFIG = "config/production_config.json"
VALIDATED_PARAMS = "config/validated_production_params.json"

# Date ranges aligned with DB data (38 tickers have 2021-2025 data)
IN_SAMPLE_START = "2021-01-01"
IN_SAMPLE_END = "2024-06-30"
VAL_START = "2024-07-01"
VAL_END = "2025-12-31"


def run_backtest_cli():
    """Step 0: Run backtest to generate enriched trades for Tier 2 derivation."""
    print("=" * 70)
    print("STEP 0: Running CLI Backtest (generates enriched trades)")
    print("=" * 70)

    result = subprocess.run(
        ["python3", "run_backtest_cli.py"],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Backtest CLI failed")
        return False

    if not Path(TRADES_FILE).exists():
        print(f"ERROR: Trades file not generated: {TRADES_FILE}")
        return False

    print(f"OK: Trades saved to {TRADES_FILE}")
    return True


def run_tier2_derivation():
    """Step 1: Derive Tier 2 filters from trades."""
    print("\n" + "=" * 70)
    print("STEP 1: Deriving Tier 2 Filters")
    print("=" * 70)

    if not Path(TRADES_FILE).exists():
        print(f"ERROR: Trades file not found: {TRADES_FILE}")
        print("   Run a backtest first (python3 run_backtest_cli.py)")
        return False

    result = subprocess.run(
        [
            "python3",
            "derive_tier2_filters.py",
            "--trades-file",
            TRADES_FILE,
            "--output",
            TIER2_FILE,
        ],
        capture_output=False,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Tier 2 derivation failed")
        return False

    print(f"OK: Tier 2 filters derived -> {TIER2_FILE}")

    with open(TIER2_FILE, "r") as f:
        tier2 = json.load(f)

    return tier2


def run_tier1_optimization(trials=100, tickers=50, quick=False):
    """Step 2: Optimize Tier 1 with THOR."""
    print("\n" + "=" * 70)
    print("STEP 2: Optimizing Tier 1 (THOR)")
    print("=" * 70)

    if not Path(TIER2_FILE).exists():
        print(f"ERROR: Tier 2 config not found: {TIER2_FILE}")
        print("   Run with --full to derive Tier 2 first")
        return False

    if not Path(TICKER_FILE).exists():
        print(f"ERROR: Ticker file not found: {TICKER_FILE}")
        print("   Create config/db_tickers.txt with one ticker per line")
        return False

    if quick:
        trials = 20
        print(f"Quick mode: {trials} trials")
    else:
        print(f"Full mode: {trials} trials")

    print(f"Ticker file: {TICKER_FILE}")
    print(f"Tier 2 config: {TIER2_FILE}")
    print(f"In-sample: {IN_SAMPLE_START} to {IN_SAMPLE_END}")
    print(f"Validation: {VAL_START} to {VAL_END}")

    cmd = [
        "python3",
        "bugatti_optuna_tier1_thor.py",
        "--trials",
        str(trials),
        "--tickers",
        str(tickers),
        "--tier2-config",
        TIER2_FILE,
        "--ticker-file",
        TICKER_FILE,
        "--in-start",
        IN_SAMPLE_START,
        "--in-end",
        IN_SAMPLE_END,
        "--val-start",
        VAL_START,
        "--val-end",
        VAL_END,
    ]

    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        print(f"ERROR: Tier 1 optimization failed")
        return False

    if not Path(TIER1_REPORT).exists():
        print(f"ERROR: Report file not found: {TIER1_REPORT}")
        return False

    print(f"OK: Tier 1 optimized -> {TIER1_REPORT}")

    with open(TIER1_REPORT, "r") as f:
        results = json.load(f)

    return results


def update_config(tier1_results, tier2_config):
    """Step 3: Update production config with optimized values."""
    print("\n" + "=" * 70)
    print("STEP 3: Updating Production Config")
    print("=" * 70)

    tier1 = tier1_results.get("tier1_optimized", {})
    perf = tier1_results.get("validation", {})

    # Build Tier 1 update
    tier1_update = {
        "tp1_r": tier1.get("tp1_r"),
        "tp2_r": tier1.get("tp2_r"),
        "tp1_pct": tier1.get("tp1_pct"),
        "tp2_pct": tier1.get("tp2_pct"),
        "runner_pct": tier1.get("runner_pct"),
        "max_stop_pct": tier1.get("max_stop_pct"),
        "risk_dollars": tier1.get("risk_dollars"),
        "use_phases": True,
        "signal_type": "any",
        "_optimized_with": "THOR Engine (38 DB tickers)",
        "_trials": tier1_results.get("trials", 0),
        "_sharpe_in_sample": round(
            tier1_results.get("in_sample", {}).get("value", 0), 4
        ),
        "_sharpe_validation": round(perf.get("sharpe", 0), 4),
    }

    # Build Tier 2 update (strip metadata for clean config)
    tier2_update = {
        "min_rvol": tier2_config.get("min_rvol", 1.5),
        "min_adr": tier2_config.get("min_adr", 2.0),
        "max_dist_sma20": tier2_config.get("max_dist_sma20", 10.0),
        "min_consolidation_days": tier2_config.get("min_consolidation_days", 10),
        "min_volume": tier2_config.get("min_volume", 200000),
        "min_dollar_volume": tier2_config.get("min_dollar_volume", 3000000),
        "max_consolidation_range": tier2_config.get("max_consolidation_range", 15.0),
        "require_sector_strength": tier2_config.get("require_sector_strength", True),
        "sector_top_percentile": tier2_config.get("sector_top_percentile", 0.4),
        "require_positive_rs": tier2_config.get("require_positive_rs", False),
        "_source": f"Statistically derived from {tier2_config.get('analysis_metadata', {}).get('trades_analyzed', '?')} trades",
    }

    # Build performance update
    perf_update = {
        "target_sharpe": 0.7,
        "target_win_rate": 45.0,
        "max_acceptable_drawdown": 10.0,
        "validation_max_degradation_pct": 20.0,
        "sharpe_ratio": round(perf.get("sharpe", 0), 4),
        "degradation_pct": round(perf.get("degradation_pct", 0), 1),
        "total_trades": perf.get("total_trades", 0),
        "win_rate_pct": round(perf.get("win_rate_pct", 0), 2),
        "total_return_pct": round(perf.get("total_return_pct", 0), 2),
        "max_drawdown_pct": round(perf.get("max_drawdown_pct", 0), 2),
    }

    updates = {
        "_last_updated": datetime.now().isoformat(),
        "_optimization_method": "Tier1_THOR_38tickers",
        "tier1_strategy": tier1_update,
        "tier2_filters": tier2_update,
        "performance": perf_update,
    }

    update_production_config(updates)

    print("OK: Production config updated")
    return True


def validate_config():
    """Step 4: Validate and display the config."""
    print("\n" + "=" * 70)
    print("STEP 4: Validating Config")
    print("=" * 70)

    try:
        config = load_production_config()
        flat = get_engine_params()

        t1 = config.get("tier1_strategy", {})
        t2 = config.get("tier2_filters", {})
        t3 = config.get("tier3_risk", {})

        print(f"\nConfig Summary:")
        print(f"  Version: {config['system']['version']}")
        print(f"  Last Updated: {config['_last_updated']}")
        print(f"  Total Parameters: {len(flat)}")

        print(f"\nTier 1 (Strategy):")
        print(f"  TP1/TP2: {t1.get('tp1_r', 0)}R / {t1.get('tp2_r', 0)}R")
        print(
            f"  Distribution: {t1.get('tp1_pct', 0) * 100:.0f}% / {t1.get('tp2_pct', 0) * 100:.0f}% / {t1.get('runner_pct', 0) * 100:.0f}%"
        )
        print(f"  Max Stop: {t1.get('max_stop_pct', 0) * 100:.1f}%")
        print(f"  Risk Dollars: ${t1.get('risk_dollars', 0)}")

        print(f"\nTier 2 (Filters):")
        print(f"  Min RVOL: {t2.get('min_rvol', 0)}x")
        print(f"  Min ADR: {t2.get('min_adr', 0)}%")
        print(f"  Max Dist SMA20: {t2.get('max_dist_sma20', 0)}%")
        print(f"  Min Consolidation: {t2.get('min_consolidation_days', 0)}d")

        print(f"\nTier 3 (Risk - FIXED):")
        print(
            f"  RVOL Danger/Warning: {t3.get('rvol_danger', 0)}x / {t3.get('rvol_warning', 0)}x"
        )
        print(f"  Max Exposure: {t3.get('max_exposure_pct', 0) * 100:.0f}%")

        perf = config.get("performance", {})
        print(f"\nPerformance (THOR Validation):")
        print(f"  Sharpe: {perf.get('sharpe_ratio', 'N/A')}")
        print(f"  Win Rate: {perf.get('win_rate_pct', 'N/A')}%")
        print(f"  Trades: {perf.get('total_trades', 'N/A')}")
        print(f"  Total Return: {perf.get('total_return_pct', 'N/A')}%")
        print(f"  Max Drawdown: {perf.get('max_drawdown_pct', 'N/A')}%")
        print(f"  Degradation: {perf.get('degradation_pct', 'N/A')}%")

        return True

    except Exception as e:
        print(f"ERROR: Validation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def copy_to_validated():
    """Copy production config to validated_production_params for backwards compatibility."""
    print("\n" + "=" * 70)
    print("STEP 5: Syncing validated_production_params.json")
    print("=" * 70)

    config = load_production_config()
    flat = get_engine_params()

    old_format = {
        "validated_date": config["_last_updated"],
        "config_name": "3-Tier-Optimized",
        "source": config.get("_optimization_method", "unknown"),
        "parameters": flat,
        "performance": config.get("performance", {}),
    }

    with open(VALIDATED_PARAMS, "w") as f:
        json.dump(old_format, f, indent=2)

    print(f"OK: Synced to {VALIDATED_PARAMS}")


def main():
    parser = argparse.ArgumentParser(
        description="Apply 3-Tier Configuration to Production"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run complete workflow (backtest -> derive tier2 -> optimize tier1 -> apply)",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Update config from existing results (tier2_filters_derived.json + tier1_thor_report.json)",
    )
    parser.add_argument("--quick", action="store_true", help="Quick mode (20 trials)")
    parser.add_argument(
        "--trials",
        type=int,
        default=100,
        help="Number of trials for Tier 1 optimization",
    )
    parser.add_argument(
        "--tickers", type=int, default=50, help="Max tickers for optimization"
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Skip Step 0 (backtest CLI) if trades already exist",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("BUGATTI 3-TIER CONFIGURATION PIPELINE")
    print("=" * 70)
    print(f"\nCanonical file paths:")
    print(f"  Trades:    {TRADES_FILE}")
    print(f"  Tier 2:    {TIER2_FILE}")
    print(f"  Tier 1:    {TIER1_REPORT}")
    print(f"  Tickers:   {TICKER_FILE}")
    print(f"  Config:    {PRODUCTION_CONFIG}")
    print(f"  Validated: {VALIDATED_PARAMS}")

    if args.full:
        # ============================================================
        # FULL WORKFLOW: Backtest -> Derive Tier 2 -> Optimize Tier 1
        # ============================================================

        # Step 0: Backtest
        if not args.skip_backtest:
            if not run_backtest_cli():
                print("\nFAILED at Step 0 (Backtest)")
                return 1
        else:
            if not Path(TRADES_FILE).exists():
                print(f"\nERROR: --skip-backtest but {TRADES_FILE} does not exist")
                return 1
            print(f"\nSkipping backtest, using existing {TRADES_FILE}")

        # Step 1: Derive Tier 2
        tier2 = run_tier2_derivation()
        if not tier2:
            print("\nFAILED at Step 1 (Tier 2 Derivation)")
            return 1

        # Step 2: Optimize Tier 1
        tier1_results = run_tier1_optimization(
            trials=args.trials, tickers=args.tickers, quick=args.quick
        )
        if not tier1_results:
            print("\nFAILED at Step 2 (Tier 1 Optimization)")
            return 1

        # Step 3: Update config
        if not update_config(tier1_results, tier2):
            print("\nFAILED at Step 3 (Config Update)")
            return 1

    elif args.update_only:
        # ============================================================
        # UPDATE ONLY: Read existing results and apply
        # ============================================================
        if not Path(TIER1_REPORT).exists():
            print(f"\nERROR: Missing {TIER1_REPORT}")
            print("  Run with --full first to generate optimization results")
            return 1

        if not Path(TIER2_FILE).exists():
            print(f"\nERROR: Missing {TIER2_FILE}")
            print("  Run with --full first to derive Tier 2 filters")
            return 1

        print(f"\nReading existing results:")
        print(f"  Tier 1: {TIER1_REPORT}")
        print(f"  Tier 2: {TIER2_FILE}")

        with open(TIER1_REPORT, "r") as f:
            tier1_results = json.load(f)
        with open(TIER2_FILE, "r") as f:
            tier2 = json.load(f)

        if not update_config(tier1_results, tier2):
            print("\nFAILED at Config Update")
            return 1

    else:
        print("\nERROR: No action specified. Use --full or --update-only")
        parser.print_help()
        return 1

    # Step 4: Validate
    if not validate_config():
        return 1

    # Step 5: Sync validated_production_params.json
    copy_to_validated()

    print("\n" + "=" * 70)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print(f"\nNext steps:")
    print(f"   1. Review: cat {PRODUCTION_CONFIG}")
    print(f"   2. Launch: streamlit run app.py")
    print(f"   3. Or verify: python3 run_backtest_cli.py")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
