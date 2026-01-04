#!/usr/bin/env python3
"""
Demo: Fast Filter Lookups vs Traditional Calculation
Shows the speed improvement of using pre-calculated metrics
"""

import sys
from pathlib import Path
import time

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.core.stock_filters import StockFilters
from src.data.market_data import MarketDataProvider

def test_traditional_method():
    """Test old method: Load full DataFrame and calculate"""
    print("\n🐢 TRADITIONAL METHOD (Calculate on-the-fly):")
    print("=" * 60)
    
    filters = StockFilters(min_dollar_volume=50e6, min_adr_pct=1.5)
    data_provider = MarketDataProvider()
    
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN', 'NFLX', 'SPY']
    
    start = time.time()
    results = []
    
    for ticker in tickers:
        df = data_provider.get_daily_data(ticker, period='1y')
        if not df.empty:
            result = filters.passes_all_filters(df, ticker)
            results.append((ticker, result['passed']))
    
    elapsed = time.time() - start
    
    print(f"✅ Processed {len(results)} tickers in {elapsed:.2f} seconds")
    print(f"   Average: {elapsed/len(results)*1000:.0f} ms per ticker")
    
    return elapsed, results

def test_fast_method():
    """Test new method: Direct database lookup"""
    print("\n🚀 FAST METHOD (Pre-calculated metrics):")
    print("=" * 60)
    
    filters = StockFilters(min_dollar_volume=50e6, min_adr_pct=1.5)
    
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMD', 'META', 'AMZN', 'NFLX', 'SPY']
    test_date = '2024-12-27'  # Recent date
    
    start = time.time()
    results = []
    
    for ticker in tickers:
        result = filters.passes_filters_fast(ticker, test_date)
        results.append((ticker, result['passed']))
    
    elapsed = time.time() - start
    
    print(f"✅ Processed {len(results)} tickers in {elapsed:.4f} seconds")
    print(f"   Average: {elapsed/len(results)*1000:.1f} ms per ticker")
    
    return elapsed, results

def main():
    print("\n" + "="*70)
    print("📊 PERFORMANCE COMPARISON: Traditional vs Pre-calculated Metrics")
    print("="*70)
    
    # Note: First check if metrics are populated
    from src.core.stock_filters import StockFilters
    filters = StockFilters()
    result = filters.passes_filters_fast('AAPL', '2024-12-27')
    
    if result['metrics'].get('adr_pct') == 0:
        print("\n⚠️  WARNING: Historical metrics not yet populated!")
        print("   Run this first: python3 scripts/populate_historical_metrics.py")
        print("\n   Skipping fast method test...")
        test_traditional_method()
    else:
        time_traditional, results_trad = test_traditional_method()
        time_fast, results_fast = test_fast_method()
        
        print("\n" + "="*70)
        print("📈 RESULTS:")
        print("="*70)
        print(f"  Traditional: {time_traditional:.2f}s")
        print(f"  Fast Method: {time_fast:.4f}s")
        print(f"  🚀 SPEEDUP: {time_traditional/time_fast:.1f}x FASTER!")
        print("\n💡 For a backtest with 500 tickers over 252 days:")
        print(f"   Traditional: ~{time_traditional/10*500*252/60:.0f} minutes")
        print(f"   Fast Method: ~{time_fast/10*500*252/60:.0f} minutes")

if __name__ == "__main__":
    main()
