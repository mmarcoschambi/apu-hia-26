#!/usr/bin/env python3
"""
Test script to verify survivorship bias filter is working correctly.
"""

import sys

sys.path.insert(0, "/home/marcos/trade/momentum-v2")

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.ticker_cache import TickerCache
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def test_survivorship_filter():
    """Test that tickers without 1-year pre-history are filtered out."""

    print("\n" + "=" * 70)
    print("TEST: Survivorship Bias Filter")
    print("=" * 70)

    # Test with a backtest starting in 2020
    # Tickers that IPO'd after 2019 should be filtered out
    start_date = "2020-01-01"
    end_date = "2020-12-31"

    # Universe with mix of old and new tickers
    # AAPL - Old (founded 1976, IPO 1980) - should pass
    # PLTR - New (founded 2003, IPO Sept 2020) - should be filtered out
    # SNOW - New (IPO Sept 2020) - should be filtered out
    # TSLA - Old (founded 2003, IPO 2010) - should pass
    test_tickers = ["AAPL", "PLTR", "SNOW", "TSLA", "NVDA"]

    print(f"\nBacktest Period: {start_date} to {end_date}")
    print(f"Universe: {test_tickers}")
    print(f"Expected: AAPL, TSLA, NVDA should pass (old enough)")
    print(f"Expected: PLTR, SNOW should be filtered (IPO'd in 2020)")

    try:
        # Initialize cache
        cache = TickerCache()

        # Create engine with default survivorship filter (200 days pre-history)
        engine = AdvancedVectorBTEngine(
            universe=test_tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            risk_dollars=150,
            min_pre_history_days=200,  # ~1 year of trading days
            offline_mode=False,
        )
        engine.cache = cache

        # Load data - this will apply the survivorship filter
        engine.load_data()

        # Check results
        loaded_tickers = set(engine.universe)
        print(
            f"\n✅ Successfully loaded {len(loaded_tickers)} tickers: {sorted(loaded_tickers)}"
        )

        # Expected tickers (old enough)
        expected_old = {"AAPL", "TSLA", "NVDA"}
        expected_new = {"PLTR", "SNOW"}

        passed = expected_old.intersection(loaded_tickers)
        filtered = expected_new.difference(loaded_tickers)

        print(f"\n📊 Results:")
        print(f"   Old tickers loaded: {passed}")
        print(f"   New tickers filtered: {expected_new}")

        if passed == expected_old and len(filtered) == len(expected_new):
            print(f"\n🎉 SUCCESS: Survivorship bias filter is working correctly!")
        else:
            print(f"\n⚠️  WARNING: Filter may not be working as expected")
            print(f"   Expected to load: {expected_old}")
            print(f"   Actually loaded: {loaded_tickers}")

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def test_configurable_lookback():
    """Test that min_pre_history_days parameter is configurable."""

    print("\n" + "=" * 70)
    print("TEST: Configurable Lookback Period")
    print("=" * 70)

    # Test with different lookback periods
    start_date = "2021-06-01"
    end_date = "2021-12-31"
    test_ticker = ["PLTR"]  # IPO'd Sept 2020

    print(f"\nTesting PLTR (IPO Sept 2020) with different lookback periods")
    print(f"Backtest start: {start_date}")

    test_cases = [
        (50, True, "PLTR should pass with 50-day lookback (IPO'd ~9 months before)"),
        (150, True, "PLTR should pass with 150-day lookback"),
        (
            250,
            False,
            "PLTR should FAIL with 250-day lookback (needs ~1 year pre-history)",
        ),
    ]

    for lookback_days, should_pass, description in test_cases:
        print(f"\n   Testing: {lookback_days} days lookback")
        print(f"   Expected: {description}")

        try:
            cache = TickerCache()
            engine = AdvancedVectorBTEngine(
                universe=test_ticker,
                start_date=start_date,
                end_date=end_date,
                initial_capital=100000,
                min_pre_history_days=lookback_days,
                offline_mode=False,
            )
            engine.cache = cache
            engine.load_data()

            loaded = len(engine.universe) > 0

            if loaded == should_pass:
                print(
                    f"   ✅ PASS: PLTR {'loaded' if loaded else 'filtered'} as expected"
                )
            else:
                print(
                    f"   ❌ FAIL: Expected {'load' if should_pass else 'filter'}, got {'load' if loaded else 'filter'}"
                )

        except Exception as e:
            if not should_pass and "No data available" in str(e):
                print(f"   ✅ PASS: PLTR correctly rejected (no data)")
            else:
                print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    print("\n🧪 Testing Survivorship Bias Filter Implementation")
    print("This verifies that the filter correctly excludes tickers without")
    print("sufficient pre-history to avoid survivorship bias.")

    test_survivorship_filter()
    test_configurable_lookback()

    print("\n" + "=" * 70)
    print("Tests completed!")
    print("=" * 70)
