#!/usr/bin/env python3
"""
Check Bugatti Readiness - Ticker Analysis
==========================================
Muestra cuántos tickers están listos para Bugatti EVO.

Usage:
    python3 check_bugatti_ready.py
    python3 check_bugatti_ready.py --detailed
    python3 check_bugatti_ready.py --period 2020-01-01 2024-12-31
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
import pandas as pd
import argparse


def check_ticker_quality(cache: TickerCache, ticker: str, start_date: str, end_date: str, min_days: int = 100):
    """Verifica si un ticker tiene suficiente data de calidad."""
    query = """
    SELECT COUNT(*) as days, MIN(date) as first, MAX(date) as last
    FROM ohlcv_cache 
    WHERE ticker = ? AND date BETWEEN ? AND ?
    """
    result = cache.conn.execute(query, (ticker, start_date, end_date)).fetchone()
    
    if result and result[0] >= min_days:
        return {
            'days': result[0],
            'first': result[1],
            'last': result[2],
            'ready': True
        }
    else:
        return {
            'days': result[0] if result else 0,
            'first': result[1] if result else None,
            'last': result[2] if result else None,
            'ready': False
        }


def main():
    parser = argparse.ArgumentParser(description='Check Bugatti readiness')
    parser.add_argument('--detailed', '-d', action='store_true', help='Show detailed ticker list')
    parser.add_argument('--period', nargs=2, metavar=('START', 'END'), 
                        default=['2020-01-01', '2024-12-31'],
                        help='Date range to check (default: 2020-01-01 2024-12-31)')
    parser.add_argument('--min-days', type=int, default=100,
                        help='Minimum days required (default: 100)')
    args = parser.parse_args()
    
    start_date, end_date = args.period
    
    print(f"🏎️ BUGATTI EVO READINESS CHECK")
    print(f"="*70)
    print(f"📅 Period: {start_date} → {end_date}")
    print(f"📊 Min days required: {args.min_days}")
    print(f"="*70)
    
    cache = TickerCache()
    
    # Get all tickers
    query = "SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker"
    all_tickers = [row[0] for row in cache.conn.execute(query).fetchall()]
    
    print(f"\n📊 Total tickers in database: {len(all_tickers)}")
    
    # Check each period
    periods = {
        'IN-SAMPLE (2020-2022)': ('2020-01-01', '2022-12-31'),
        'VALIDATION (2023 H1)': ('2023-01-01', '2023-06-30'),
        'OOS (2023-2024)': ('2023-07-01', '2024-12-31'),
        'FULL RANGE': (start_date, end_date)
    }
    
    ready_by_period = {}
    
    for period_name, (p_start, p_end) in periods.items():
        ready = []
        not_ready = []
        
        for ticker in all_tickers:
            info = check_ticker_quality(cache, ticker, p_start, p_end, args.min_days)
            if info['ready']:
                ready.append((ticker, info))
            else:
                not_ready.append((ticker, info))
        
        ready_by_period[period_name] = {
            'ready': ready,
            'not_ready': not_ready,
            'start': p_start,
            'end': p_end
        }
        
        print(f"\n📌 {period_name}")
        print(f"   ✅ Ready: {len(ready)}")
        print(f"   ❌ Not ready: {len(not_ready)}")
    
    # Tickers ready for ALL periods (critical for walk-forward)
    ready_all = set([t for t, _ in ready_by_period['IN-SAMPLE (2020-2022)']['ready']])
    for period_name in ['VALIDATION (2023 H1)', 'OOS (2023-2024)']:
        ready_all &= set([t for t, _ in ready_by_period[period_name]['ready']])
    
    ready_all = sorted(ready_all)
    
    print(f"\n{'='*70}")
    print(f"🎯 BUGATTI EVO READY TICKERS (ALL PERIODS)")
    print(f"{'='*70}")
    print(f"   ✅ Ready for all periods: {len(ready_all)}")
    print(f"   ❌ Missing some periods: {len(all_tickers) - len(ready_all)}")
    
    # Suggested fold-size
    if len(ready_all) > 0:
        suggested_fold_sizes = {
            'conservative': int(len(ready_all) * 0.6),
            'balanced': int(len(ready_all) * 0.75),
            'aggressive': int(len(ready_all) * 0.9)
        }
        
        print(f"\n💡 SUGGESTED FOLD SIZES:")
        print(f"   Conservative (60%): {suggested_fold_sizes['conservative']}")
        print(f"   Balanced (75%): {suggested_fold_sizes['balanced']} ⭐")
        print(f"   Aggressive (90%): {suggested_fold_sizes['aggressive']}")
        
        print(f"\n🚀 READY TO RUN:")
        print(f"   python3 bugatti_evo.py \\")
        print(f"     --k-folds 3 \\")
        print(f"     --fold-size {suggested_fold_sizes['balanced']} \\")
        print(f"     --l1-trials 50 \\")
        print(f"     --l2-trials 30")
    else:
        print(f"\n⚠️ NO TICKERS READY!")
        print(f"   Run: python3 populate_custom_list.py --skip-existing")
    
    # Detailed list
    if args.detailed and ready_all:
        print(f"\n📋 DETAILED LIST OF READY TICKERS:")
        print(f"="*70)
        
        for i, ticker in enumerate(ready_all, 1):
            # Get stats for full range
            info = check_ticker_quality(cache, ticker, start_date, end_date, args.min_days)
            print(f"   {i:3d}. {ticker:6s} - {info['days']:4d} days ({info['first']} → {info['last']})")
            
            if i % 20 == 0:
                input("   Press Enter to continue...")
    
    elif ready_all and not args.detailed:
        print(f"\n📋 READY TICKERS (first 30):")
        for i, ticker in enumerate(ready_all[:30], 1):
            print(f"   {ticker}", end="  ")
            if i % 10 == 0:
                print()
        
        if len(ready_all) > 30:
            print(f"\n   ... and {len(ready_all) - 30} more")
        
        print(f"\n💡 Use --detailed to see full list")
    
    # Save to file
    if ready_all:
        output_file = Path('bugatti_ready_tickers.txt')
        with open(output_file, 'w') as f:
            f.write(f"# Bugatti EVO Ready Tickers\n")
            f.write(f"# Generated: {pd.Timestamp.now()}\n")
            f.write(f"# Period: {start_date} to {end_date}\n")
            f.write(f"# Total: {len(ready_all)}\n\n")
            for ticker in ready_all:
                f.write(f"{ticker}\n")
        
        print(f"\n💾 Full list saved to: {output_file}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
