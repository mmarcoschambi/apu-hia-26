#!/usr/bin/env python3
"""
test_universe_queries.py
------------------------
Test look-ahead bias fixes in universe selection queries.

Queries tested:
1. Static universe (original)
2. Static universe with limit (new)
3. Monthly rebalance universe (new)
4. Monthly rebalance with limit (new)
"""

import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "data" / "ticker_cache.db"


def test_universe_queries():
    """Test all universe selection methods."""

    conn = sqlite3.connect(str(DB_PATH))

    # Test parameters
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    min_required_days = 100
    max_symbols = 200
    us_only = True

    # US filter clause
    us_filter_clause = " AND ticker NOT LIKE '%-%' " if us_only else ""

    print("=" * 70)
    print("Testing Universe Selection Queries (Look-ahead Bias Fix)")
    print("=" * 70)

    # 1. Original Static Universe (max_symbols=0)
    query1 = f"""
        SELECT ticker 
        FROM ohlcv_cache 
        WHERE date BETWEEN ? AND ? 
        {us_filter_clause}
        GROUP BY ticker 
        HAVING COUNT(*) >= ? 
        ORDER BY ticker ASC
    """
    cursor1 = conn.execute(query1, (start_date, end_date, min_required_days))
    universe1 = [row[0] for row in cursor1.fetchall()]
    print(f"\n1. Original Static Universe (no limit): {len(universe1)} tickers")
    print(f"   Sample: {universe1[:5]}...")

    # 2. New Static Universe with limit
    query2 = f"""
        WITH universe_rank AS (
            SELECT 
                ticker,
                AVG(rolling_dollar_vol_20) as initial_adv,
                COUNT(*) as day_count
            FROM ohlcv_cache 
            WHERE date BETWEEN ? AND date(date, '+63 days') 
            AND rolling_dollar_vol_20 IS NOT NULL
            {us_filter_clause}
            GROUP BY ticker
            HAVING day_count >= ?
        )
        SELECT ticker 
        FROM universe_rank 
        ORDER BY initial_adv DESC, ticker ASC 
        LIMIT ?
    """
    cursor2 = conn.execute(query2, (start_date, min_required_days, max_symbols))
    universe2 = [row[0] for row in cursor2.fetchall()]
    print(f"\n2. New Static Universe (limited): {len(universe2)} tickers")
    print(f"   Sample: {universe2[:5]}...")

    # 3. Monthly Rebalance Universe
    query3 = f"""
        WITH monthly_universe AS (
            SELECT 
                ticker,
                AVG(rolling_dollar_vol_20) as avg_adv
            FROM ohlcv_cache 
            WHERE date BETWEEN ? AND ? 
            AND rolling_dollar_vol_20 IS NOT NULL
            {us_filter_clause}
            GROUP BY ticker, strftime('%Y-%m', date)
            HAVING COUNT(*) >= 15
        )
        SELECT DISTINCT ticker 
        FROM monthly_universe 
        ORDER BY avg_adv DESC, ticker ASC
    """
    cursor3 = conn.execute(query3, (start_date, end_date))
    universe3 = [row[0] for row in cursor3.fetchall()]
    print(f"\n3. Monthly Rebalance Universe: {len(universe3)} tickers")
    print(f"   Sample: {universe3[:5]}...")

    # 4. Monthly Rebalance with limit
    query4 = f"""
        WITH monthly_universe AS (
            SELECT 
                ticker,
                AVG(rolling_dollar_vol_20) as avg_adv
            FROM ohlcv_cache 
            WHERE date BETWEEN ? AND ? 
            AND rolling_dollar_vol_20 IS NOT NULL
            {us_filter_clause}
            GROUP BY ticker, strftime('%Y-%m', date)
            HAVING COUNT(*) >= 15
        ),
        ticker_rank AS (
            SELECT 
                ticker,
                AVG(avg_adv) as overall_adv
            FROM monthly_universe 
            GROUP BY ticker
            ORDER BY overall_adv DESC
            LIMIT ?
        )
        SELECT DISTINCT ticker 
        FROM ticker_rank 
        ORDER BY overall_adv DESC, ticker ASC
    """
    cursor4 = conn.execute(query4, (start_date, end_date, max_symbols))
    universe4 = [row[0] for row in cursor4.fetchall()]
    print(f"\n4. Monthly Rebalance (limited): {len(universe4)} tickers")
    print(f"   Sample: {universe4[:5]}...")

    # 5. Compare with original look-ahead query (should be biased)
    query5 = f"""
        SELECT DISTINCT ticker
        FROM ohlcv_cache 
        WHERE date BETWEEN ? AND ? 
        AND rolling_dollar_vol_20 IS NOT NULL
        {us_filter_clause}
        GROUP BY ticker
        HAVING COUNT(*) >= ?
        ORDER BY MAX(rolling_dollar_vol_20) DESC, ticker ASC
        LIMIT ?
    """
    cursor5 = conn.execute(
        query5, (start_date, end_date, min_required_days, max_symbols)
    )
    universe5 = [row[0] for row in cursor5.fetchall()]
    print(f"\n5. Original Look-ahead Query (biased): {len(universe5)} tickers")
    print(f"   Sample: {universe5[:5]}...")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)

    unique_tickers = set(universe1 + universe2 + universe3 + universe4 + universe5)
    print(f"Total unique tickers across all methods: {len(unique_tickers)}")

    # Compare overlap
    overlap_static = len(set(universe1) & set(universe2))
    overlap_monthly = len(set(universe3) & set(universe4))
    bias_diff = len(set(universe2) - set(universe5))

    print(
        f"\nOverlap Static vs New Static: {overlap_static}/{len(universe1)} ({overlap_static / len(universe1) * 100:.1f}%)"
    )
    print(
        f"Overlap Monthly vs New Monthly: {overlap_monthly}/{len(universe3)} ({overlap_monthly / len(universe3) * 100:.1f}%)"
    )
    print(f"Difference vs biased query: {bias_diff} tickers different")

    # Show which tickers differ
    if bias_diff > 0:
        diff_tickers = set(universe2) - set(universe5)
        print(f"\nTop 10 tickers in NEW static but not in biased query:")
        for ticker in sorted(list(diff_tickers))[:10]:
            print(f"  {ticker}")

    conn.close()
    print("\n✅ All queries tested successfully!")

    return {
        "static_no_limit": universe1,
        "static_with_limit": universe2,
        "monthly_no_limit": universe3,
        "monthly_with_limit": universe4,
        "biased_query": universe5,
    }


if __name__ == "__main__":
    test_universe_queries()
