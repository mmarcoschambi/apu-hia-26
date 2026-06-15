#!/usr/bin/env python3
"""
Debug Max DD calculation difference between THOR and Advanced.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

COMMON_PARAMS = {
    "signal_type": "breakout",
    "min_rvol": 1.5,
    "min_adr": 2.0,
    "min_volume": 200000,
    "min_dollar_volume": 5_000_000,
    "max_dist_sma20": 7.0,
    "min_consolidation_days": 10,
    "max_consolidation_range": 15.0,
    "risk_dollars": 150,
    "max_stop_pct": 7.0,
    "max_exposure_pct": 0.25,
    "tp1_r": 1.5,
    "tp2_r": 3.0,
    "tp1_pct": 0.5,
    "tp2_pct": 0.3,
    "runner_pct": 0.2,
}

TICKERS = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]  # Small set for debugging


def run_thor():
    """Run THOR and return equity curve."""
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR

    thor = OptimizationEngineTHOR(
        tickers=TICKERS,
        start_date="2022-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        offline_mode=True,
    )

    thor_params = {
        "signal_type": COMMON_PARAMS["signal_type"],
        "min_rvol": COMMON_PARAMS["min_rvol"],
        "min_adr": COMMON_PARAMS["min_adr"],
        "min_volume": COMMON_PARAMS["min_volume"],
        "min_dollar_volume": COMMON_PARAMS["min_dollar_volume"],
        "max_dist_sma20": COMMON_PARAMS["max_dist_sma20"],
        "min_consolidation_days": COMMON_PARAMS["min_consolidation_days"],
        "max_consolidation_range": COMMON_PARAMS["max_consolidation_range"],
        "risk_dollars": COMMON_PARAMS["risk_dollars"],
        "max_stop_pct": COMMON_PARAMS["max_stop_pct"] / 100.0,
        "max_exposure_pct": COMMON_PARAMS["max_exposure_pct"],
        "tp1_r": COMMON_PARAMS["tp1_r"],
        "tp2_r": COMMON_PARAMS["tp2_r"],
        "tp1_pct": COMMON_PARAMS["tp1_pct"],
        "tp2_pct": COMMON_PARAMS["tp2_pct"],
        "runner_pct": COMMON_PARAMS["runner_pct"],
        "rvol_danger": 3.0,
        "rvol_warning": 2.0,
        "rvol_danger_size": 0.30,
        "rvol_warning_size": 0.65,
        "require_bullish_spy": False,
        "require_spy_above_sma50": False,
        "require_positive_rs": False,
        "require_sma_trend": False,
        "use_phases": True,
    }

    result = thor.backtest(thor_params)

    print("✅ THOR Results:")
    print(f"   Total Return: {result.get('total_return_pct', 0):.2f}%")
    print(f"   Max DD: {result.get('max_drawdown_pct', 0):.2f}%")
    print(f"   Sharpe: {result.get('sharpe_ratio', 0):.2f}")
    print(f"   Profit Factor: {result.get('profit_factor', 0):.2f}")
    print()

    return result


def run_advanced():
    """Run Advanced and return equity curve."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    advanced = AdvancedVectorBTEngine(
        universe=TICKERS,
        start_date="2022-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        risk_dollars=COMMON_PARAMS["risk_dollars"],
        max_stop_pct=COMMON_PARAMS["max_stop_pct"],
        max_exposure_pct=COMMON_PARAMS["max_exposure_pct"],
        tp1_r=COMMON_PARAMS["tp1_r"],
        tp2_r=COMMON_PARAMS["tp2_r"],
        tp1_pct=COMMON_PARAMS["tp1_pct"],
        tp2_pct=COMMON_PARAMS["tp2_pct"],
        runner_pct=COMMON_PARAMS["runner_pct"],
        min_rvol=COMMON_PARAMS["min_rvol"],
        min_adr=COMMON_PARAMS["min_adr"],
        min_volume=COMMON_PARAMS["min_volume"],
        min_dollar_volume=COMMON_PARAMS["min_dollar_volume"],
        max_dist_sma20=COMMON_PARAMS["max_dist_sma20"],
        min_consolidation_days=COMMON_PARAMS["min_consolidation_days"],
        signal_type=COMMON_PARAMS["signal_type"],
        offline_mode=True,
        use_market_regime_filter=False,
        use_dynamic_thresholds=False,
        require_spy_above_sma50=False,
        use_adaptive_filtering=False,
        require_positive_rs=False,
        use_rs_percentile=False,
        use_sma50_atr_filter=False,
        use_trailing_stop=False,
    )

    result = advanced.run_backtest()

    print("✅ Advanced Results:")
    print(f"   Total Return: {result.get('total_return', 0) * 100:.2f}%")
    adv_dd_pct = result.get("max_drawdown", 0) * 100
    print(f"   Max DD: {adv_dd_pct:.2f}%")
    print(f"   Sharpe: {result.get('sharpe_ratio', 0):.2f}")
    print(f"   Profit Factor: {result.get('profit_factor', 0):.2f}")
    print()

    return result


def main():
    print("=" * 80)
    print("🔍 MAX DD DEBUG: THOR vs Advanced")
    print("=" * 80)
    print(f"📅 Period: 2022-01-01 to 2024-01-01")
    print(f"🎯 Tickers: {TICKERS}")
    print()

    # Run both engines
    thor_result = run_thor()
    adv_result = run_advanced()

    # Compare
    print("=" * 80)
    print("📊 COMPARISON")
    print("=" * 80)

    thor_dd = thor_result.get("max_drawdown_pct", 0)
    adv_dd = adv_result.get("max_drawdown", 0) * 100

    print(f"   THOR Max DD:     {thor_dd:.2f}%")
    print(f"   Advanced Max DD: {adv_dd:.2f}%")
    print(f"   Difference:       {abs(thor_dd - adv_dd):.2f}%")

    if abs(thor_dd - adv_dd) > 1.0:
        print()
        print("🔍 DIAGNOSIS:")
        print("   ⚠️ WARNING: Max DD difference > 1%")
        print()
        print("   Possible causes:")
        print("   1. Different equity curve calculation methods")
        print("   2. Different stop/exit execution timing")
        print("   3. One engine not accounting for fees/slippage properly")
        print("   4. VectorBT vs custom simulation differences")

        print()
        print("   Debugging steps:")
        print("   - Check final equity values")
        print("   - Verify drawdown calculation formula")
        print("   - Compare equity curves point-by-point")

        print()
        print("   THOR final value:", thor_result.get("final_value", 0))
        print("   Advanced final value:", adv_result.get("final_value", 0))
        print("   Initial capital: 100000")
        print()
        thor_return = (thor_result.get("final_value", 0) - 100000) / 100000 * 100
        adv_return = (adv_result.get("final_value", 0) - 100000) / 100000 * 100
        print(f"   THOR return: {thor_return:.2f}%")
        print(f"   Advanced return: {adv_return:.2f}%")

    print("=" * 80)


if __name__ == "__main__":
    main()
