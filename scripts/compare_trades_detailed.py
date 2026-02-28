#!/usr/bin/env python3
"""
Compare trades trade-by-trade between THOR and Advanced engines.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime

# Common params from debug_convergence.py
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
    "rvol_danger": 3.0,
    "rvol_warning": 2.0,
    "rvol_danger_size": 30,
    "rvol_warning_size": 65,
    "use_market_regime_filter": False,
    "use_dynamic_thresholds": False,
    "require_spy_above_sma50": False,
    "use_adaptive_filtering": False,
    "require_positive_rs": False,
    "use_rs_percentile": False,
    "use_sma50_atr_filter": False,
    "use_trailing_stop": False,
}

TICKERS = [
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "AMD",
    "NFLX",
    "CRM",
    "ADBE",
    "INTC",
    "CSCO",
    "ORCL",
    "IBM",
    "QCOM",
    "TXN",
    "AVGO",
    "MU",
    "AMAT",
    "LRCX",
    "KLAC",
    "MRVL",
    "ON",
    "PYPL",
    "SQ",
    "SHOP",
    "SNOW",
    "DDOG",
    "NET",
    "CRWD",
    "ZS",
    "BA",
    "CAT",
    "DE",
    "GE",
    "HON",
    "MMM",
    "UPS",
    "FDX",
    "JPM",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "C",
    "BLK",
    "SCHW",
]


def get_thor_trades():
    """Run THOR and return trade details."""
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR

    thor = OptimizationEngineTHOR(
        tickers=TICKERS,
        start_date="2022-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        offline_mode=True,
    )

    thor_params = COMMON_PARAMS.copy()
    thor_params["max_stop_pct"] /= 100.0  # THOR expects decimal
    thor_params["rvol_danger_size"] /= 100.0
    thor_params["rvol_warning_size"] /= 100.0
    thor_params["require_bullish_spy"] = False
    thor_params["require_spy_above_sma50"] = False
    thor_params["require_positive_rs"] = False
    thor_params["require_sma_trend"] = False
    thor_params["use_phases"] = True

    result = thor.backtest(thor_params)

    # Return summary stats
    return {
        "engine": "THOR",
        "total_trades": result.get("total_trades", 0),
        "all_exits": result.get("all_exits", 0),
        "win_rate": result.get("win_rate_pct", 0),
        "sharpe": result.get("sharpe_ratio", 0),
        "return_pct": result.get("total_return_pct", 0),
        "max_dd": result.get("max_drawdown_pct", 0),
        "profit_factor": result.get("profit_factor", 0),
        "phase_breakdown": result.get("phase_breakdown", {}),
    }


def get_advanced_trades():
    """Run Advanced and return trade details."""
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
        rvol_danger=COMMON_PARAMS["rvol_danger"],
        rvol_warning=COMMON_PARAMS["rvol_warning"],
        rvol_danger_size=COMMON_PARAMS["rvol_danger_size"],
        rvol_warning_size=COMMON_PARAMS["rvol_warning_size"],
        signal_type=COMMON_PARAMS["signal_type"],
        offline_mode=True,
        # Disable all advanced filters
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

    trades_df = result.get("trades_df", pd.DataFrame())

    # Count exit phases
    if len(trades_df) > 0 and "exit_phase" in trades_df.columns:
        phase_counts = trades_df["exit_phase"].value_counts().to_dict()
    else:
        phase_counts = {}

    return {
        "engine": "Advanced",
        "total_trades": result.get("total_trades", 0),
        "all_exits": len(trades_df),
        "win_rate": result.get("win_rate", 0) * 100,
        "sharpe": result.get("sharpe_ratio", 0),
        "return_pct": result.get("total_return", 0) * 100,
        "max_dd": result.get("max_drawdown", 0) * 100,
        "profit_factor": result.get("profit_factor", 0),
        "phase_breakdown": phase_counts,
        "trades_df": trades_df,
    }


def main():
    print("=" * 80)
    print("🔍 TRADE-BY-TRADE COMPARISON: THOR vs Advanced")
    print("=" * 80)
    print(f"📅 Period: 2022-01-01 to 2024-01-01")
    print(f"🎯 Tickers: {len(TICKERS)}")
    print()

    print("📊 Common Parameters:")
    print(f"   signal_type: {COMMON_PARAMS['signal_type']}")
    print(f"   max_consolidation_range: {COMMON_PARAMS['max_consolidation_range']}%")
    print(f"   min_consolidation_days: {COMMON_PARAMS['min_consolidation_days']}")
    print(f"   max_dist_sma20: {COMMON_PARAMS['max_dist_sma20']}%")
    print(f"   risk_dollars: ${COMMON_PARAMS['risk_dollars']}")
    print()

    # Run both engines
    print("=" * 80)
    print("🔨 Running THOR...")
    print("=" * 80)
    thor_stats = get_thor_trades()

    print(f"✅ THOR Results:")
    print(f"   Unique Entries: {thor_stats['total_trades']}")
    print(f"   All Exit Events: {thor_stats['all_exits']}")
    print(f"   Win Rate: {thor_stats['win_rate']:.1f}%")
    print(f"   Sharpe: {thor_stats['sharpe']:.2f}")
    print(f"   Return: {thor_stats['return_pct']:.2f}%")
    print(f"   Max DD: {thor_stats['max_dd']:.2f}%")
    print(f"   Profit Factor: {thor_stats['profit_factor']:.2f}")
    print(f"   Phase Breakdown: {thor_stats['phase_breakdown']}")
    print()

    print("=" * 80)
    print("⚡ Running Advanced Engine...")
    print("=" * 80)
    adv_stats = get_advanced_trades()

    print(f"✅ Advanced Engine Results:")
    print(f"   Unique Entries: {adv_stats['total_trades']}")
    print(f"   All Exit Events: {adv_stats['all_exits']}")
    print(f"   Win Rate: {adv_stats['win_rate']:.1f}%")
    print(f"   Sharpe: {adv_stats['sharpe']:.2f}")
    print(f"   Return: {adv_stats['return_pct']:.2f}%")
    print(f"   Max DD: {adv_stats['max_dd']:.2f}%")
    print(f"   Profit Factor: {adv_stats['profit_factor']:.2f}")
    print(f"   Phase Breakdown: {adv_stats['phase_breakdown']}")
    print()

    # Comparison
    print("=" * 80)
    print("📊 CONVERGENCE ANALYSIS")
    print("=" * 80)

    unique_diff = abs(thor_stats["total_trades"] - adv_stats["total_trades"])
    unique_diff_pct = unique_diff / max(thor_stats["total_trades"], 1) * 100

    all_exits_diff = abs(thor_stats["all_exits"] - adv_stats["all_exits"])
    all_exits_diff_pct = all_exits_diff / max(thor_stats["all_exits"], 1) * 100

    print(f"   Unique Entries Diff: {unique_diff} ({unique_diff_pct:.1f}%)")
    print(f"   All Exit Events Diff: {all_exits_diff} ({all_exits_diff_pct:.1f}%)")
    print(
        f"   Win Rate Diff: {abs(thor_stats['win_rate'] - adv_stats['win_rate']):.1f}%"
    )
    print(f"   Sharpe Diff: {abs(thor_stats['sharpe'] - adv_stats['sharpe']):.2f}")
    print(
        f"   Return Diff: {abs(thor_stats['return_pct'] - adv_stats['return_pct']):.2f}%"
    )
    print()

    # Diagnose divergence
    if unique_diff > 0:
        print("🔍 DIAGNOSIS:")
        print(f"   THOR has {thor_stats['total_trades']} unique entries")
        print(f"   Advanced has {adv_stats['total_trades']} unique entries")
        print(f"   Difference: {unique_diff} entries")

        # Expected exits
        thor_expected = thor_stats["total_trades"] * 3
        adv_expected = adv_stats["total_trades"] * 3

        print()
        print("   Expected vs Actual Exit Events:")
        print(
            f"   THOR: {thor_expected} expected, {thor_stats['all_exits']} actual ({thor_stats['all_exits'] / thor_expected * 100:.1f}%)"
        )
        print(
            f"   Advanced: {adv_expected} expected, {adv_stats['all_exits']} actual ({adv_stats['all_exits'] / adv_expected * 100:.1f}%)"
        )

        if all_exits_diff_pct > 5:
            print()
            print(
                "   ⚠️ WARNING: Exit event difference > 5% - different exit logic detected"
            )
        elif unique_diff_pct > 10:
            print()
            print(
                "   ⚠️ WARNING: Entry difference > 10% - different entry logic detected"
            )
        else:
            print()
            print(
                "   ✅ Acceptable convergence - minor differences expected due to implementation details"
            )

    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
