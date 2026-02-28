#!/usr/bin/env python3
"""
Compare entry signals directly between THOR and Advanced engines.
This identifies EXACTLY where the entry logic differs.
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


def get_thor_entry_signals():
    """Get THOR entry signals."""
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR

    thor = OptimizationEngineTHOR(
        tickers=TICKERS,
        start_date="2022-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        offline_mode=True,
    )

    # Calculate THOR entry logic (extract from backtest)
    # Recreate the entry logic from THOR's backtest method

    # Liquidity filters
    liquidity = (
        (thor.rvol >= COMMON_PARAMS["min_rvol"])
        & (thor.adr >= COMMON_PARAMS["min_adr"])
        & (thor.vol_sma20 >= COMMON_PARAMS["min_volume"])
        & ((thor.close * thor.vol_sma20) >= COMMON_PARAMS["min_dollar_volume"])
    )

    # Quality filter
    quality = thor.dist_sma20 <= COMMON_PARAMS["max_dist_sma20"]

    # Consolidation quality
    consolidation = (
        thor.consolidation_days >= COMMON_PARAMS["min_consolidation_days"]
    ) & (thor.consolidation_range <= COMMON_PARAMS["max_consolidation_range"])

    # Breakout signal
    breakout = thor.close > thor.high.shift().rolling(20).max()

    # Combine
    entries_thor = liquidity & quality & consolidation & breakout

    return {
        "entries": entries_thor,
        "liquidity": liquidity,
        "quality": quality,
        "consolidation": consolidation,
        "breakout": breakout,
        "consolidation_range": thor.consolidation_range,
        "consolidation_days": thor.consolidation_days,
        "dist_sma20": thor.dist_sma20,
    }


def get_advanced_entry_signals():
    """Get Advanced entry signals."""
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    advanced = AdvancedVectorBTEngine(
        universe=TICKERS,
        start_date="2022-01-01",
        end_date="2024-01-01",
        initial_capital=100000,
        offline_mode=True,
        # Use baseline mode params
        signal_type="breakout",
        min_rvol=COMMON_PARAMS["min_rvol"],
        min_adr=COMMON_PARAMS["min_adr"],
        min_volume=COMMON_PARAMS["min_volume"],
        min_dollar_volume=COMMON_PARAMS["min_dollar_volume"],
        max_dist_sma20=COMMON_PARAMS["max_dist_sma20"],
        min_consolidation_days=COMMON_PARAMS["min_consolidation_days"],
    )

    advanced.load_data()

    # Calculate Advanced entry logic (extract from run_backtest baseline mode)
    from src.filters.liquidity import LiquidityFilters
    from src.indicators.technical import TechnicalIndicators

    safe_sma20 = advanced.sma_20.fillna(0)
    safe_avg_vol = advanced.avg_volume_20.fillna(1)
    dollar_volume = advanced.close * safe_avg_vol

    # RVOL
    rvol = advanced.rvol

    # ADR
    adr = TechnicalIndicators.adr(
        advanced.high, advanced.low, advanced.close, period=20
    )

    # Distance to SMA20
    dist_sma20_pct = (advanced.close - safe_sma20) / safe_sma20 * 100

    # Consolidation days
    bb_std = advanced.close.rolling(20).std()
    bb_upper = safe_sma20 + (bb_std * 2)
    bb_lower = safe_sma20 - (bb_std * 2)
    inside_bb = (advanced.close >= bb_lower) & (advanced.close <= bb_upper)
    consolidation_days = inside_bb.rolling(20).sum()

    # Consolidation range
    consolidation_range = advanced.consolidation_range

    # Liquidity
    liquidity = LiquidityFilters.get_mask(
        rvol=rvol,
        adr=adr,
        avg_volume=safe_avg_vol,
        dollar_volume=dollar_volume,
        min_rvol=COMMON_PARAMS["min_rvol"],
        min_adr=COMMON_PARAMS["min_adr"],
        min_volume=200000,
        min_dollar_volume=5e6,
    )

    # Quality
    quality = dist_sma20_pct <= COMMON_PARAMS["max_dist_sma20"]

    # Consolidation
    consolidation = (consolidation_days >= COMMON_PARAMS["min_consolidation_days"]) & (
        consolidation_range <= 15.0
    )

    # Breakout
    breakout = advanced.close > advanced.high.shift().rolling(20).max()

    # Combine
    entries_adv = liquidity & quality & consolidation & breakout

    return {
        "entries": entries_adv,
        "liquidity": liquidity,
        "quality": quality,
        "consolidation": consolidation,
        "breakout": breakout,
        "consolidation_range": consolidation_range,
        "consolidation_days": consolidation_days,
        "dist_sma20": dist_sma20_pct,
    }


def main():
    print("=" * 80)
    print("🔍 ENTRY SIGNAL COMPARISON: THOR vs Advanced")
    print("=" * 80)
    print()

    # Get signals from both engines
    thor_signals = get_thor_entry_signals()
    adv_signals = get_advanced_entry_signals()

    # Align to common index and columns
    common_index = thor_signals["entries"].index.intersection(
        adv_signals["entries"].index
    )
    common_cols = thor_signals["entries"].columns.intersection(
        adv_signals["entries"].columns
    )

    thor_entries = thor_signals["entries"].loc[common_index, common_cols]
    adv_entries = adv_signals["entries"].loc[common_index, common_cols]

    # Compare
    thor_count = thor_entries.sum().sum()
    adv_count = adv_entries.sum().sum()

    print(f"📊 Entry Signal Counts:")
    print(f"   THOR:     {thor_count} entry signals")
    print(f"   Advanced:  {adv_count} entry signals")
    print(
        f"   Diff:      {adv_count - thor_count} ({abs(adv_count - thor_count) / max(thor_count, 1) * 100:.1f}%)"
    )
    print()

    # Find matches and mismatches
    matches = (thor_entries == adv_entries).values
    match_count = matches.sum()
    total_cells = matches.size

    print(f"📊 Cell-by-Cell Comparison:")
    print(f"   Total cells:      {total_cells:,}")
    print(
        f"   Matching cells:   {match_count:,} ({match_count / total_cells * 100:.2f}%)"
    )
    print(
        f"   Mismatch cells:   {total_cells - match_count:,} ({(total_cells - match_count) / total_cells * 100:.2f}%)"
    )
    print()

    # Find differences
    diff_mask = thor_entries ^ adv_entries  # XOR: True where they differ

    if diff_mask.sum().sum() > 0:
        print("🔍 DETAILED DIFFERENCES:")
        print()

        # Find THOR-only and Advanced-only entries
        thor_only = thor_entries & ~adv_entries
        adv_only = adv_entries & ~thor_entries

        print(f"   THOR-only entries: {thor_only.sum().sum()}")
        print(f"   Advanced-only entries: {adv_only.sum().sum()}")
        print()

        # Sample differences
        print("   Sample THOR-only entries (5):")
        thor_only_coords = [
            (i, j)
            for i in range(len(common_index))
            for j in range(len(common_cols))
            if thor_only.iloc[i, j]
        ]
        for i, j in thor_only_coords[:5]:
            ticker = common_cols[j]
            date = common_index[i]
            dist_sma20 = thor_signals["dist_sma20"].iloc[i, j]
            cons_days = thor_signals["consolidation_days"].iloc[i, j]
            cons_range = thor_signals["consolidation_range"].iloc[i, j]
            print(
                f"      {ticker} @ {date.date()}: dist_sma20={dist_sma20:.2f}%, "
                f"cons_days={cons_days:.0f}, cons_range={cons_range:.2f}%"
            )
        print()

        print("   Sample Advanced-only entries (5):")
        adv_only_coords = [
            (i, j)
            for i in range(len(common_index))
            for j in range(len(common_cols))
            if adv_only.iloc[i, j]
        ]
        for i, j in adv_only_coords[:5]:
            ticker = common_cols[j]
            date = common_index[i]
            dist_sma20 = adv_signals["dist_sma20"].iloc[i, j]
            cons_days = adv_signals["consolidation_days"].iloc[i, j]
            cons_range = adv_signals["consolidation_range"].iloc[i, j]
            print(
                f"      {ticker} @ {date.date()}: dist_sma20={dist_sma20:.2f}%, "
                f"cons_days={cons_days:.0f}, cons_range={cons_range:.2f}%"
            )
        print()

        # Analyze filter differences
        print("   Filter Pass/Fail Analysis (for mismatched cells):")

        for i, j in adv_only_coords[:3]:  # Check 3 Advanced-only entries
            ticker = common_cols[j]
            date = common_index[i]
            print(f"\n   {ticker} @ {date.date()} (Advanced-only):")
            print(f"      THOR liquidity:   {thor_signals['liquidity'].iloc[i, j]}")
            print(f"      ADV liquidity:    {adv_signals['liquidity'].iloc[i, j]}")
            print(f"      THOR quality:     {thor_signals['quality'].iloc[i, j]}")
            print(f"      ADV quality:      {adv_signals['quality'].iloc[i, j]}")
            print(f"      THOR cons:        {thor_signals['consolidation'].iloc[i, j]}")
            print(f"      ADV cons:         {adv_signals['consolidation'].iloc[i, j]}")
            print(f"      THOR breakout:     {thor_signals['breakout'].iloc[i, j]}")
            print(f"      ADV breakout:      {adv_signals['breakout'].iloc[i, j]}")

            # Show raw values for debugging
            print(
                f"      THOR dist_sma20:   {thor_signals['dist_sma20'].iloc[i, j]:.4f}%"
            )
            print(
                f"      ADV dist_sma20:    {adv_signals['dist_sma20'].iloc[i, j]:.4f}%"
            )
            print(
                f"      THOR cons_days:    {thor_signals['consolidation_days'].iloc[i, j]:.1f}"
            )
            print(
                f"      ADV cons_days:     {adv_signals['consolidation_days'].iloc[i, j]:.1f}"
            )
            print(
                f"      THOR cons_range:   {thor_signals['consolidation_range'].iloc[i, j]:.2f}%"
            )
            print(
                f"      ADV cons_range:    {adv_signals['consolidation_range'].iloc[i, j]:.2f}%"
            )

    print("=" * 80)


if __name__ == "__main__":
    main()
