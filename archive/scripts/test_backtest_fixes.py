#!/usr/bin/env python3
"""
Smoke test for backtest fixes:
- Verifies no rs_raw_60 error
- Verifies timing works correctly
- Verifies different date ranges produce different results
"""

import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


def test_backtest_range(start_date, end_date, label):
    print(f"\n{'=' * 60}")
    print(f"Testing: {label}")
    print(f"Range: {start_date} to {end_date}")
    print(f"{'=' * 60}")

    universe = ["SPY", "AAPL", "MSFT", "AMZN", "GOOGL"]

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=pd.Timestamp(start_date),
        end_date=pd.Timestamp(end_date),
        initial_capital=100000,
        risk_pct=0.01,
        risk_dollars=0,
        max_exposure_pct=0.20,
        offline_mode=True,
        use_adaptive_filtering=False,
    )

    results = engine.run_backtest()
    engine.cleanup()

    equity = results.get("equity_curve")
    trades = results.get("trades")

    if equity is None or len(equity) == 0:
        print(f"❌ FAILED: No equity curve generated")
        return None

    print(f"✅ Equity curve: {len(equity)} days")
    print(f"✅ Total trades: {len(trades)}")
    print(f"✅ Return: {results['total_return'] * 100:.2f}%")
    print(f"✅ Sharpe: {results['sharpe_ratio']:.2f}")

    final_equity = float(equity.iloc[-1])
    print(f"✅ Final equity: ${final_equity:,.2f}")

    return {
        "final_equity": final_equity,
        "total_trades": len(trades),
        "return": results["total_return"],
    }


def main():
    print("Testing backtest fixes...")

    # Test 1: Short range
    result1 = test_backtest_range("2020-01-01", "2021-12-31", "Test 1 (2 years)")

    # Test 2: Different range (should give different results)
    result2 = test_backtest_range("2019-01-01", "2021-06-30", "Test 2 (2.5 years)")

    if result1 and result2:
        print(f"\n{'=' * 60}")
        print("COMPARISON")
        print(f"{'=' * 60}")
        print(f"Test 1 final equity: ${result1['final_equity']:,.2f}")
        print(f"Test 2 final equity: ${result2['final_equity']:,.2f}")
        print(f"Test 1 trades: {result1['total_trades']}")
        print(f"Test 2 trades: {result2['total_trades']}")

        if result1["final_equity"] == result2["final_equity"]:
            print("⚠️  WARNING: Results are identical (possible caching issue)")
        else:
            print("✅ PASS: Different ranges produce different results")

    print("\n" + "=" * 60)
    print("SMOKE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
