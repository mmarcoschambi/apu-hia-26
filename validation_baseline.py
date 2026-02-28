#!/usr/bin/env python3
"""
VALIDATION BASELINE & CONVERGENCE TOOL
======================================

Utility script to align 'OptimizationEngineTHOR' and 'AdvancedVectorBTEngine'.
Follows the Convergence Plan:
    Phase 1: Baseline Convergence (Features OFF)
    Phase 2: Feature Impact Analysis
    Phase 3: Production Configuration
    Phase 4: Re-optimization (Advanced)

Usage:
    python validation_baseline.py --phase 1
    python validation_baseline.py --phase 2
    python validation_baseline.py --phase 3
    python validation_baseline.py --all
"""

import sys
import os
import logging
import pandas as pd
import numpy as np
import argparse
from typing import Dict, List, Optional
from pathlib import Path

# Setup paths to import from src
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

# Try imports
try:
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
except ImportError as e:
    print(f"❌ Critical Import Error: {e}")
    print("Ensure you are running this from the project root and 'src' is accessible.")
    sys.exit(1)

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ValidationTool")

# =============================================================================
# GLOBAL CONFIG
# =============================================================================

TEST_TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
TEST_PERIOD = ("2023-01-01", "2023-12-31")

# Original baseline params for Phase 1 (pre-optimization)
PARAMS_BASELINE_ORIGINAL = {
    "signal_type": "breakout",
    "min_rvol": 2.0,
    "min_adr": 2.5,
    "risk_dollars": 150,
    "max_dist_sma20": 12.5,
    "min_consolidation_days": 10,
    "max_stop_pct": 7.0,
    "tp1_r": 1.5,
    "tp2_r": 3.0,
    "use_phases": True,
    # Advanced features (ALL OFF for baseline)
    "use_dynamic_thresholds": False,
    "use_market_regime_filter": False,
    "use_adaptive_filtering": False,
    "use_earnings_calendar": False,
    "require_spy_above_sma50": False,
    "require_positive_rs": False,
    "use_trailing_stop": False,
    "use_rs_percentile": False,
    "use_sma50_atr_filter": False,
}

# Optimized params (from Trial 29) for Phase 3-4
PARAMS_OPTIMIZED = {
    "signal_type": "breakout",
    "min_rvol": 1.5,
    "min_adr": 2.0,
    "risk_dollars": 100,
    "max_dist_sma20": 10.0,
    "min_consolidation_days": 10,
    "max_stop_pct": 7.0,
    "tp1_r": 1.25,
    "tp2_r": 3.0,
    "use_phases": True,
    # Validated features
    "use_dynamic_thresholds": False,
    "use_market_regime_filter": False,
    "use_adaptive_filtering": False,
    "use_earnings_calendar": False,
    "require_spy_above_sma50": True,
    "require_positive_rs": False,
    "use_trailing_stop": False,
    "use_rs_percentile": False,
    "use_sma50_atr_filter": False,
}

# THOR expects floats (0.65)
PARAMS_THOR = PARAMS_BASELINE_ORIGINAL.copy()
PARAMS_THOR.update(
    {
        "rvol_warning_size": 0.65,
        "rvol_danger_size": 0.30,
        "rvol_warning": 2.0,
        "rvol_danger": 3.0,
    }
)

# Advanced expects ints (65)
PARAMS_ADVANCED = PARAMS_BASELINE_ORIGINAL.copy()
PARAMS_ADVANCED.update(
    {
        "rvol_warning_size": 65,
        "rvol_danger_size": 30,
        "rvol_warning": 2.0,
        "rvol_danger": 3.0,
    }
)

# =============================================================================
# PHASE 1: BASELINE CONVERGENCE
# =============================================================================


def run_phase_1_baseline():
    print("=" * 70)
    print("🔧 PHASE 1: BASELINE CONVERGENCE (Features OFF)")
    print("=" * 70)

    # --- TEST 1: THOR ---
    print("\n⚡ Running THOR Engine...")
    thor = OptimizationEngineTHOR(
        tickers=TEST_TICKERS,
        start_date=TEST_PERIOD[0],
        end_date=TEST_PERIOD[1],
        use_float32=True,
        chunk_size=50,
    )
    result_thor = thor.backtest(PARAMS_THOR)

    # --- TEST 2: ADVANCED ---
    print("\n🔬 Running Advanced Engine...")
    advanced = AdvancedVectorBTEngine(
        universe=TEST_TICKERS,
        start_date=TEST_PERIOD[0],
        end_date=TEST_PERIOD[1],
        **PARAMS_ADVANCED,
    )
    result_advanced = advanced.run_backtest()

    # --- COMPARISON ---
    print("\n" + "=" * 70)
    print("📊 BASELINE CONVERGENCE REPORT")
    print("=" * 70)

    # Extract phase breakdown from THOR
    thor_breakdown = result_thor.get("phase_breakdown", {})
    thor_unique = result_thor["total_trades"]
    thor_all_exits = result_thor.get("all_exits", thor_unique)

    print(f"\n🔍 THOR Phase Breakdown:")
    print(f"   Unique Entries: {thor_unique}")
    print(f"   TP1 exits: {thor_breakdown.get('tp1_trades', 0)}")
    print(f"   TP2 exits: {thor_breakdown.get('tp2_trades', 0)}")
    print(f"   Runner exits: {thor_breakdown.get('runner_trades', 0)}")
    print(f"   Total exits: {thor_all_exits}")

    print(f"\n🔍 Advanced:")
    print(f"   Total trades (all exits): {result_advanced['total_trades']}")

    print(
        f"\n{'Metric':<15} | {'THOR':<10} | {'Advanced':<10} | {'Diff':<8} | {'Status':<10}"
    )
    print("-" * 65)

    metrics = [
        (
            "Sharpe",
            result_thor["sharpe_ratio"],
            result_advanced["sharpe_ratio"],
            0.3,
            0.6,
        ),
        ("Total Exits", thor_all_exits, result_advanced["total_trades"], 5, 10),
        (
            "Return %",
            result_thor["total_return_pct"],
            result_advanced["total_return"] * 100,
            2.0,
            5.0,
        ),
        (
            "Max DD %",
            result_thor["max_drawdown_pct"],
            result_advanced["max_drawdown"] * 100,
            2.0,
            5.0,
        ),
    ]

    all_passed = True

    for name, val_thor, val_adv, limit_ok, limit_warn in metrics:
        diff = abs(val_thor - val_adv)

        if diff <= limit_ok:
            status = "✅ OK"
        elif diff <= limit_warn:
            status = "⚠️ CHECK"
        else:
            status = "❌ FAIL"
            all_passed = False

        print(
            f"{name:<15} | {val_thor:<10.2f} | {val_adv:<10.2f} | {diff:<8.2f} | {status}"
        )

    # Win rate comparison (informational)
    print(f"\n📊 Win Rate Analysis:")
    print(f"   THOR:     {result_thor['win_rate_pct']:.1f}% (across all exits)")
    print(f"   Advanced: {result_advanced['win_rate'] * 100:.1f}% (across all exits)")
    print(f"   ℹ️  Note: Win rates calculated per exit, not per entry")

    print("-" * 65)

    if all_passed:
        print("\n✅ SUCCESS: Engines are aligned. Proceed to Phase 2.")
    else:
        print("\n❌ CRITICAL: Engines diverged. Do not proceed.")
        print("Suggested Actions:")
        print("  1. Check entry signal logic in both files.")
        print("  2. Verify position sizing calculations.")
        print("  3. Ensure same data source/adjustments.")

    return result_advanced  # Return baseline for comparison


# =============================================================================
# PHASE 2: IMPACT ANALYSIS
# =============================================================================


def run_phase_2_impact(baseline_result):
    print("\n" + "=" * 70)
    print("🔎 PHASE 2: FEATURE IMPACT ANALYSIS")
    print("=" * 70)

    features_to_test = [
        ("require_spy_above_sma50", True),
        ("use_earnings_calendar", True),
        ("use_trailing_stop", True),
        ("use_adaptive_filtering", True),
    ]

    results = []

    for feature, value in features_to_test:
        print(f"\nTesting feature: {feature} = {value} ...")

        params_test = PARAMS_ADVANCED.copy()
        params_test[feature] = value

        advanced_test = AdvancedVectorBTEngine(
            universe=TEST_TICKERS,
            start_date=TEST_PERIOD[0],
            end_date=TEST_PERIOD[1],
            **params_test,
        )
        res = advanced_test.run_backtest()

        delta_sharpe = res["sharpe_ratio"] - baseline_result["sharpe_ratio"]
        trades_blocked = baseline_result["total_trades"] - res["total_trades"]

        verdict = "⚪ NEUTRAL"
        if delta_sharpe > 0.05:
            verdict = "✅ IMPROVES"
        elif delta_sharpe < -0.05:
            verdict = "❌ DEGRADES"

        results.append(
            {
                "Feature": feature,
                "New Sharpe": res["sharpe_ratio"],
                "Delta Sharpe": delta_sharpe,
                "Trades Blocked": trades_blocked,
                "Verdict": verdict,
            }
        )

    print("\n" + "=" * 70)
    print("📊 IMPACT SUMMARY")
    print("=" * 70)
    print(
        f"{'Feature':<25} | {'Sharpe':<8} | {'Delta':<8} | {'Blocked':<8} | {'Verdict'}"
    )
    print("-" * 75)

    for r in results:
        print(
            f"{r['Feature']:<25} | {r['New Sharpe']:<8.3f} | {r['Delta Sharpe']:<+8.3f} | {r['Trades Blocked']:<8} | {r['Verdict']}"
        )

    print("-" * 75)
    print("Recommendation: Enable features marked ✅. Use caution with ❌.")


# =============================================================================
# PHASE 3: PRODUCTION CONFIG
# =============================================================================


def get_production_params():
    """Returns the recommended production configuration based on optimization results."""
    # Use optimized params as base
    params = PARAMS_OPTIMIZED.copy()

    # Add position sizing format for Advanced engine
    params.update(
        {
            "rvol_warning_size": 65,
            "rvol_danger_size": 30,
        }
    )
    return params


def run_phase_3_config():
    print("\n" + "=" * 70)
    print("🏭 PHASE 3: PRODUCTION CONFIGURATION")
    print("=" * 70)

    params = get_production_params()
    print("Generated Production Parameters:")
    for k, v in params.items():
        if k not in PARAMS_ADVANCED or params[k] != PARAMS_ADVANCED[k]:
            print(f"  🔹 {k}: {v}")

    return params


# =============================================================================
# PHASE 4: RE-OPTIMIZATION (Advanced Engine)
# =============================================================================


def run_phase_4_optimization(production_params):
    print("\n" + "=" * 70)
    print("🚀 PHASE 4: RE-OPTIMIZATION (Advanced Engine)")
    print("=" * 70)

    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError:
        print("⚠️ Optuna not installed. Skipping optimization.")
        return

    print("🔍 Starting optimization (30 trials) on 2022-2023 data...")

    # Define optimization period (In-Sample)
    IS_START = "2022-01-01"
    IS_END = "2023-12-31"

    # Define validation period (Out-of-Sample)
    OOS_START = "2024-01-01"
    OOS_END = "2024-06-30"

    def objective(trial):
        params = production_params.copy()

        # Search Space - Narrow range around optimal params from Trial 29
        params["min_rvol"] = trial.suggest_categorical("min_rvol", [1.0, 1.5, 2.0])
        params["min_adr"] = trial.suggest_categorical("min_adr", [1.5, 2.0, 2.5])
        params["risk_dollars"] = trial.suggest_categorical(
            "risk_dollars", [100, 150, 200]
        )
        params["max_dist_sma20"] = trial.suggest_categorical(
            "max_dist_sma20", [8.0, 10.0, 12.0]
        )
        params["tp1_r"] = trial.suggest_categorical("tp1_r", [1.0, 1.25, 1.5])
        params["tp2_r"] = trial.suggest_categorical("tp2_r", [2.5, 3.0, 3.5])

        # Ensure critical feature is ON
        params["require_spy_above_sma50"] = True

        engine = AdvancedVectorBTEngine(
            universe=TEST_TICKERS, start_date=IS_START, end_date=IS_END, **params
        )
        res = engine.run_backtest()

        # CRITICAL FIX: Require minimum 30 trades for statistical significance
        if res["total_trades"] < 30:
            return -999

        # Penalize extreme drawdowns
        sharpe = res["sharpe_ratio"]
        if res["max_drawdown"] > 0.30:
            sharpe *= 0.5

        return sharpe

    # Run Optimization
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=30, show_progress_bar=True)

    print("\n🏆 BEST PARAMS (In-Sample 2022-2023):")
    best_params = production_params.copy()
    best_params.update(study.best_params)

    for k, v in study.best_params.items():
        print(f"   🔹 {k}: {v}")
    print(f"   Best Sharpe: {study.best_value:.3f}")

    # Validate Out-of-Sample
    print("\n" + "-" * 70)
    print("🔮 OUT-OF-SAMPLE VALIDATION (2024)")
    print("-" * 70)

    oos_engine = AdvancedVectorBTEngine(
        universe=TEST_TICKERS, start_date=OOS_START, end_date=OOS_END, **best_params
    )
    oos_res = oos_engine.run_backtest()

    print(f"   Sharpe (OOS): {oos_res['sharpe_ratio']:.3f}")
    print(f"   Return (OOS): {oos_res['total_return'] * 100:.2f}%")
    print(f"   Trades (OOS): {oos_res['total_trades']}")
    print(f"   Win Rate:     {oos_res['win_rate'] * 100:.1f}%")
    print(f"   Max DD:       {oos_res['max_drawdown'] * 100:.2f}%")

    # Analysis
    if study.best_value > 0:
        degradation = (
            (oos_res["sharpe_ratio"] - study.best_value) / study.best_value * 100
        )
        print(f"\n📊 Performance Change (OOS vs IS): {degradation:+.1f}%")

        if degradation > -20:
            print("✅ ROBUST: Excellent stability across periods.")
        elif degradation > -50:
            print("⚠️ ACCEPTABLE: Some degradation expected in different regimes.")
        else:
            print("❌ UNSTABLE: Significant overfitting detected.")
    else:
        print("\n❌ INCONCLUSIVE: Baseline Sharpe was negative.")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validation Baseline Tool")
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4], help="Run specific phase"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all phases sequentially"
    )
    parser.add_argument(
        "--year", type=int, default=2023, help="Year to test (default: 2023)"
    )

    args = parser.parse_args()

    # Update Global Config based on arguments
    TEST_PERIOD = (f"{args.year}-01-01", f"{args.year}-12-31")
    print(f"📅 Testing Year: {args.year}")

    # Default to Phase 1 if nothing specified
    if not args.phase and not args.all:
        args.phase = 1

    baseline_res = None

    # Phase 2 requires Phase 1 results
    if args.phase == 1 or args.phase == 2 or args.all:
        baseline_res = run_phase_1_baseline()

    if (args.phase == 2 or args.all) and baseline_res:
        run_phase_2_impact(baseline_res)

    prod_params = None
    if args.phase == 3 or args.all:
        prod_params = run_phase_3_config()

    if args.phase == 4 or args.all:
        if not prod_params:
            prod_params = get_production_params()
        run_phase_4_optimization(prod_params)
