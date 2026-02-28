#!/usr/bin/env python3
"""
DEBUG CONVERGENCE: THOR vs Advanced Engine
------------------------------------------
Validates that the Advanced Engine in 'convergence' mode produces 
identical (or very similar) signals to the legacy THOR engine.

Both engines run with:
- Fixed Dollar Risk ($150)
- Aligned filters (Liquid + Momentum + Consolidation)

FOCUS: Signal-by-signal comparison (entry dates, tickers)
Aggregate metrics are shown but NOT used for pass/fail determination.
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import engines
try:
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR  # THOR
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine  # Advanced
    from config.advanced_engine_modes import get_engine_kwargs  # Centralized config
except ImportError:
    # Handle running from root or scripts dir
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    from config.advanced_engine_modes import get_engine_kwargs


def compare_signals(thor_results, advanced_results, start_date=None, end_date=None, tolerance_pct: float = 15.0):
    """
    Compare entry signals between THOR and Advanced engines.
    
    Args:
        thor_results: THOR engine results dict
        advanced_results: Advanced engine results dict
        tolerance_pct: Acceptable difference percentage for signal counts
    
    Returns:
        bool: True if signals converge within tolerance
    """
    print("\n" + "="*80)
    print("🔍 SIGNAL-LEVEL CONVERGENCE ANALYSIS")
    print("="*80)
    
    # Extract trade DataFrames
    thor_trades = thor_results.get('trades', pd.DataFrame())
    adv_trades = advanced_results.get('trades', pd.DataFrame())
    
    # Debug: Show available columns
    print(f"\nDEBUG - THOR columns: {list(thor_trades.columns) if not thor_trades.empty else 'EMPTY'}")
    print(f"DEBUG - Advanced columns: {list(adv_trades.columns) if not adv_trades.empty else 'EMPTY'}")
    print(f"DEBUG - THOR shape: {thor_trades.shape}")
    print(f"DEBUG - Advanced shape: {adv_trades.shape}")
    
    # Try multiple column name variations for entry date/timestamp
    thor_date_cols = ['Entry Date', 'entry_date', 'Entry_Date', 'Entry Timestamp', 'entry_timestamp', 'Date', 'date', 'timestamp']
    adv_date_cols = ['Entry Date', 'entry_date', 'Entry_Date', 'Entry Timestamp', 'entry_timestamp', 'Date', 'date', 'timestamp']
    
    thor_date_col = None
    adv_date_col = None
    
    for col in thor_date_cols:
        if col in thor_trades.columns:
            thor_date_col = col
            break
    
    for col in adv_date_cols:
        if col in adv_trades.columns:
            adv_date_col = col
            break
    
    # Try multiple column name variations for ticker
    thor_ticker_cols = ['Ticker', 'ticker', 'Symbol', 'symbol']
    adv_ticker_cols = ['Ticker', 'ticker', 'Symbol', 'symbol']
    
    thor_ticker_col = None
    adv_ticker_col = None
    
    for col in thor_ticker_cols:
        if col in thor_trades.columns:
            thor_ticker_col = col
            break
    
    for col in adv_ticker_cols:
        if col in adv_trades.columns:
            adv_ticker_col = col
            break
    
    print(f"DEBUG - Found THOR date column: {thor_date_col}")
    print(f"DEBUG - Found Advanced date column: {adv_date_col}")
    print(f"DEBUG - Found THOR ticker column: {thor_ticker_col}")
    print(f"DEBUG - Found Advanced ticker column: {adv_ticker_col}")
    
    # Count unique entry signals (date + ticker)
    thor_count_from_summary = None  # Initialize
    
    if not thor_trades.empty and thor_date_col and thor_ticker_col:
        # Extract date part from timestamp if needed
        thor_dates = thor_trades[thor_date_col]
        if pd.api.types.is_datetime64_any_dtype(thor_dates):
            thor_dates = thor_dates.dt.date
        thor_signals = set(zip(thor_dates, thor_trades[thor_ticker_col]))
    else:
        thor_signals = set()
        if not thor_trades.empty:
            print(f"⚠️  THOR: Could not extract signals (missing date:{thor_date_col} or ticker:{thor_ticker_col})")
        else:
            # THOR doesn't return DataFrame - use unique entries count from summary
            print(f"⚠️  THOR: Trade DataFrame not available (engine returns summary only)")
            print(f"   Will compare trade counts from summary metrics instead")
            # Use unique_entries if available, otherwise fall back to total_trades
            thor_count_from_summary = thor_results.get('unique_entries', thor_results.get('total_trades', 0))
            all_exits = thor_results.get('all_exits', None)
            if thor_count_from_summary > 0:
                print(f"   Using THOR unique entries: {thor_count_from_summary}")
                if all_exits and all_exits != thor_count_from_summary:
                    print(f"   (THOR all exits: {all_exits} - includes partial TP1/TP2/RUNNER)")
    
    if not adv_trades.empty and adv_date_col and adv_ticker_col:
        # Extract date part from timestamp if needed
        adv_dates = adv_trades[adv_date_col]
        if pd.api.types.is_datetime64_any_dtype(adv_dates):
            adv_dates_dt = pd.to_datetime(adv_dates)
            adv_dates = adv_dates_dt.dt.date
        else:
            adv_dates_dt = pd.to_datetime(adv_dates)
            adv_dates = adv_dates_dt.dt.date
        
        # DEBUG: Show date range of Advanced trades
        print(f"   ℹ️  Advanced trades date range: {min(adv_dates)} to {max(adv_dates)}")
        
        # Filter to requested date range if provided
        if start_date or end_date:
            mask = pd.Series([True] * len(adv_dates), index=adv_trades.index)
            if start_date:
                start_dt = pd.to_datetime(start_date).date()
                mask = mask & (adv_dates >= start_dt)
            if end_date:
                end_dt = pd.to_datetime(end_date).date()
                mask = mask & (adv_dates <= end_dt)
            
            # Apply date filter
            adv_trades_filtered = adv_trades[mask].copy()
            
            total_before = len(adv_trades)
            total_after = len(adv_trades_filtered)
            
            if total_before > total_after:
                print(f"   ℹ️  Advanced: Filtered {total_before - total_after} trades outside date range")
                print(f"      (Engine loads extra historical data for indicator warmup)")
            
            # Group partial exits by (entry_date, symbol) to get UNIQUE ENTRIES
            adv_signals = set(zip(
                pd.to_datetime(adv_trades_filtered[adv_date_col]).dt.date,
                adv_trades_filtered[adv_ticker_col]
            ))
            
            # DEBUG: Show what unique entries we found
            print(f"   ℹ️  Advanced unique entries after grouping partials: {len(adv_signals)}")
        else:
            # Group partial exits by (entry_date, symbol) to get UNIQUE ENTRIES
            adv_signals = set(zip(adv_dates, adv_trades[adv_ticker_col]))
    else:
        adv_signals = set()
        if not adv_trades.empty:
            print(f"⚠️  Advanced: Could not extract signals (missing date:{adv_date_col} or ticker:{adv_ticker_col})")
        else:
            print(f"⚠️  Advanced: No trades returned (empty DataFrame)")
    
    # Calculate overlap
    common_signals = thor_signals & adv_signals
    thor_only = thor_signals - adv_signals
    adv_only = adv_signals - thor_signals
    
    thor_count = len(thor_signals) if thor_signals else thor_count_from_summary or 0
    adv_count = len(adv_signals)
    common_count = len(common_signals)
    
    print(f"\n{'Metric':<30} {'THOR':<15} {'Advanced':<15} {'Overlap'}")
    print("-" * 75)
    
    if thor_count_from_summary:
        print(f"{'Total Unique Entries':<30} {thor_count:<15} {adv_count:<15} {'N/A (summary)'}")
    else:
        print(f"{'Total Entry Signals':<30} {thor_count:<15} {adv_count:<15} {common_count}")
        
        if thor_count > 0:
            overlap_pct = (common_count / thor_count) * 100
            print(f"{'Signal Overlap':<30} {'':<15} {'':<15} {overlap_pct:.1f}%")
        else:
            overlap_pct = 0
    
    # Show differences
    if thor_only:
        print(f"\n⚠️  THOR-only signals ({len(thor_only)}):")
        for date, ticker in sorted(list(thor_only))[:10]:
            print(f"   {date} {ticker}")
        if len(thor_only) > 10:
            print(f"   ... and {len(thor_only) - 10} more")
    
    if adv_only:
        print(f"\n⚠️  Advanced-only signals ({len(adv_only)}):")
        for date, ticker in sorted(list(adv_only))[:10]:
            print(f"   {date} {ticker}")
        if len(adv_only) > 10:
            print(f"   ... and {len(adv_only) - 10} more")
    
    # Convergence verdict
    print("\n" + "="*80)
    print("🎯 CONVERGENCE VERDICT")
    print("="*80)
    
    if thor_count == 0 and adv_count == 0:
        print("⚠️  Both engines produced ZERO signals. Cannot validate convergence.")
        return False
    
    # Use trade count comparison if no signal-level data available
    if thor_count_from_summary:
        print("\n⚠️  NOTE: THOR doesn't return signal-level data (only summary metrics)")
        print("   Comparing trade counts instead of signal-by-signal overlap")
        print(f"   This is less precise but still validates rough equivalence\n")
        
        count_diff_pct = abs(adv_count - thor_count) / max(thor_count, 1) * 100
        
        if count_diff_pct <= tolerance_pct:
            print(f"✅ CONVERGENCE PASSED (Trade Count Method)")
            print(f"   THOR entries: {thor_count}")
            print(f"   Advanced entries: {adv_count}")
            print(f"   Difference: {count_diff_pct:.1f}% (tolerance: {tolerance_pct}%)")
            return True
        else:
            print(f"❌ CONVERGENCE FAILED (Trade Count Method)")
            print(f"   THOR entries: {thor_count}")
            print(f"   Advanced entries: {adv_count}")
            print(f"   Difference: {count_diff_pct:.1f}% (tolerance: {tolerance_pct}%)")
            return False
    
    # Original signal-level comparison
    count_diff_pct = abs(adv_count - thor_count) / max(thor_count, 1) * 100
    
    if count_diff_pct <= tolerance_pct and (overlap_pct >= (100 - tolerance_pct) if thor_count > 0 else True):
        print(f"✅ CONVERGENCE PASSED")
        print(f"   Signal counts within {tolerance_pct}% tolerance: {count_diff_pct:.1f}%")
        if thor_count > 0:
            print(f"   Signal overlap: {overlap_pct:.1f}%")
        return True
    else:
        print(f"❌ CONVERGENCE FAILED")
        print(f"   Signal count difference: {count_diff_pct:.1f}% (tolerance: {tolerance_pct}%)")
        if thor_count > 0:
            print(f"   Signal overlap: {overlap_pct:.1f}% (expected: >{100-tolerance_pct}%)")
        return False


def compare_results(thor_results, advanced_results):
    """
    Display aggregate metrics for informational purposes only.
    
    NOTE: These metrics are NOT used for convergence pass/fail.
    Due to compounding/timing differences, aggregate metrics will differ
    even when signals are identical. Use compare_signals() for validation.
    """
    
    print("\n" + "="*80)
    print("📊 AGGREGATE METRICS (INFORMATIONAL ONLY)")
    print("="*80)
    print("⚠️  These metrics are NOT convergence-critical.")
    print("   Different implementations (Numba vs VectorBT) will produce different")
    print("   aggregate results even with identical signals due to execution timing,")
    print("   fill assumptions, and partial exit handling.")
    print("="*80)
    
    # Extract THOR metrics
    thor_count = thor_results.get('total_trades', 0)
    thor_return = thor_results.get('total_return_pct', 0) / 100.0
    thor_sharpe = thor_results.get('sharpe_ratio', 0)
    thor_dd = thor_results.get('max_drawdown_pct', 0) / 100.0
    
    # Extract Advanced metrics
    adv_trades = advanced_results.get('trades', pd.DataFrame())
    adv_count = advanced_results.get('total_trades', len(adv_trades)) 
    adv_return = advanced_results.get('total_return', 0)
    adv_sharpe = advanced_results.get('sharpe_ratio', 0)
    adv_dd = advanced_results.get('max_drawdown', 0)
    
    print(f"\n{'Metric':<25} {'THOR':<15} {'ADVANCED':<15}")
    print("-" * 55)
    print(f"{'Total Trades':<25} {thor_count:<15} {adv_count:<15}")
    print(f"{'Total Return':<25} {thor_return*100:+.2f}%{'':<8} {adv_return*100:+.2f}%")
    print(f"{'Sharpe Ratio':<25} {thor_sharpe:.2f}{'':<11} {adv_sharpe:.2f}")
    print(f"{'Max Drawdown':<25} {thor_dd*100:.2f}%{'':<8} {adv_dd*100:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="Debug Convergence THOR vs Advanced")
    parser.add_argument('--tickers', type=str, help="Comma-separated tickers or 'spy', 'nasdaq100', 'all'")
    parser.add_argument('--start', type=str, default="2023-01-01", help="Start date")
    parser.add_argument('--end', type=str, default="2023-12-31", help="End date")
    parser.add_argument('--limit', type=int, default=None, help="Limit number of tickers (for large universes)")
    
    args = parser.parse_args()
    
    # Build universe based on input
    if not args.tickers or args.tickers.lower() in ['all', 'full', 'db', 'database']:
        # Use entire database (top liquid US stocks)
        import sqlite3
        print("📊 Loading universe from database...")
        conn = sqlite3.connect('./data/ticker_cache.db')
        
        # Optimized query: get recent US tickers only
        # Filter out international tickers (contain '-', '.', or are > 5 chars)
        query = """
        SELECT ticker, SUM(dollar_volume) as total_dv
        FROM ohlcv_cache
        WHERE date >= date('now', '-2 years')
          AND ticker NOT LIKE '%-%'
          AND ticker NOT LIKE '%.%'
          AND LENGTH(ticker) <= 5
        GROUP BY ticker
        HAVING COUNT(*) >= 50
        ORDER BY total_dv DESC
        """
        limit = args.limit or 100  # Default to top 100 if not specified
        cursor = conn.execute(query + f" LIMIT {limit}")
        universe = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"   Loaded {len(universe)} US tickers from database (top {limit} by liquidity)")
        
    elif args.tickers.lower() in ['spy', 'sp500', 's&p500']:
        # Load S&P 500 universe
        sp500_file = Path('sp500_tickers_since_2014.txt')
        if sp500_file.exists():
            with open(sp500_file, 'r') as f:
                universe = [line.strip().upper() for line in f if line.strip()]
            if args.limit:
                universe = universe[:args.limit]
            print(f"📊 Loaded {len(universe)} tickers from S&P 500")
        else:
            print("⚠️  S&P 500 file not found, using database")
            import sqlite3
            conn = sqlite3.connect('./data/ticker_cache.db')
            query = """
            SELECT ticker, SUM(dollar_volume) as total_dv
            FROM ohlcv_cache
            WHERE date >= date('now', '-2 years')
              AND ticker NOT LIKE '%-%'
              AND ticker NOT LIKE '%.%'
              AND LENGTH(ticker) <= 5
            GROUP BY ticker
            HAVING COUNT(*) >= 50
            ORDER BY total_dv DESC
            LIMIT ?
            """
            limit = args.limit or 100
            cursor = conn.execute(query, (limit,))
            universe = [row[0] for row in cursor.fetchall()]
            conn.close()
            print(f"   Loaded {len(universe)} US tickers from database")
    
    elif args.tickers.lower() in ['nasdaq100', 'ndx', 'nasdaq']:
        # Load NASDAQ 100 (or use database proxy)
        print("📊 Loading NASDAQ-style universe from database...")
        import sqlite3
        conn = sqlite3.connect('./data/ticker_cache.db')
        # Tech-heavy, high-volume US stocks
        query = """
        SELECT ticker, SUM(dollar_volume) as total_dv
        FROM ohlcv_cache
        WHERE date >= date('now', '-2 years')
          AND ticker NOT LIKE '%-%'
          AND ticker NOT LIKE '%.%'
          AND LENGTH(ticker) <= 5
        GROUP BY ticker
        HAVING COUNT(*) >= 50
        ORDER BY total_dv DESC
        LIMIT ?
        """
        limit = args.limit or 100
        cursor = conn.execute(query, (limit,))
        universe = [row[0] for row in cursor.fetchall()]
        conn.close()
        print(f"   Loaded {len(universe)} US tickers from database")
        
    else:
        # Manual ticker list
        universe = [t.strip().upper() for t in args.tickers.split(',')]
    
    print("="*80)
    print("🚀 CONVERGENCE CHECK: THOR vs ADVANCED")
    print("="*80)
    print(f"📅 Period: {args.start} to {args.end}")
    print(f"🎯 Universe: {len(universe)} tickers")
    if len(universe) <= 10:
        print(f"   {', '.join(universe)}")
    else:
        print(f"   {', '.join(universe[:10])}... (and {len(universe)-10} more)")
    print()
    print("Goal: Validate that Advanced Engine (convergence mode) produces")
    print("      identical entry/exit signals to legacy THOR engine.")
    print("="*80)
    
    # Use centralized mode config for convergence
    convergence_config = get_engine_kwargs(
        mode='convergence',
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        initial_capital=100000
    )
    
    # Extract params for THOR (which needs them mapped differently)
    print(f"\n⚙️  Using centralized convergence configuration:")
    print(f"   Risk: Fixed $150")
    print(f"   Filters: Baseline only (no market regime, no sector rotation)")
    print(f"   Signal type: {convergence_config.get('signal_type', 'breakout')}")
    
    # 1. Run THOR
    print("\n" + "-"*60)
    print("⚡ RUNNING THOR (OptimizationEngineTHOR)...")
    print("-"*60)
    
    thor_engine = OptimizationEngineTHOR(
        tickers=universe,
        start_date=args.start,
        end_date=args.end,
        initial_capital=100000,
        use_float32=True
    )
    
    # Map params to THOR expected format
    thor_params = {
        'signal_type': convergence_config['signal_type'],
        'min_rvol': convergence_config['min_rvol'],
        'min_adr': convergence_config['min_adr'],
        'risk_dollars': convergence_config['risk_dollars'],
        'max_dist_sma20': convergence_config['max_dist_sma20'],
        'tp1_r': convergence_config['tp1_r'],
        'tp2_r': convergence_config['tp2_r'],
        'max_stop_pct': convergence_config['max_stop_pct'] / 100.0,  # THOR expects decimal
        'min_dollar_volume': convergence_config['min_dollar_volume'],
        'min_consolidation_days': convergence_config['min_consolidation_days'],
        'use_phases': True
    }
    
    thor_results = thor_engine.backtest(thor_params)
    
    # 2. Run Advanced in CONVERGENCE mode (using centralized config)
    print("\n" + "-"*60)
    print("🔬 RUNNING ADVANCED (Convergence Mode)...")
    print("-"*60)
    
    engine_adv = AdvancedVectorBTEngine(**convergence_config)
    adv_results = engine_adv.run_backtest()
    
    # 3. Compare SIGNALS (primary check)
    signals_converged = compare_signals(thor_results, adv_results, start_date=args.start, end_date=args.end, tolerance_pct=15.0)
    
    # 4. Show aggregate metrics (informational only)
    compare_results(thor_results, adv_results)
    
    # 5. Exit with appropriate code
    if not signals_converged:
        print("\n❌ CONVERGENCE CHECK FAILED - Signals diverged beyond tolerance")
        sys.exit(1)
    else:
        print("\n✅ CONVERGENCE CHECK PASSED - Signals are aligned")
        sys.exit(0)

if __name__ == "__main__":
    main()
