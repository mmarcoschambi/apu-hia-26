#!/usr/bin/env python3
"""
VectorBT Backtest Runner
------------------------
Ultra-fast backtesting using vectorized operations.
"""

import argparse
import pandas as pd
from datetime import datetime
import time

from src.backtest.vectorbt_engine import run_vectorbt_backtest

def main():
    parser = argparse.ArgumentParser(description="VectorBT Fast Backtesting")
    
    # Date range
    parser.add_argument('--start', type=str, default='2021-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2021-12-31', help='End date (YYYY-MM-DD)')
    
    # Capital and risk
    parser.add_argument('--equity', type=float, default=100000, help='Initial capital')
    parser.add_argument('--risk', type=float, default=0.5, help='Risk per trade (%)')
    parser.add_argument('--max_exp', type=float, default=25, help='Max exposure per position (%)')
    parser.add_argument('--stop_loss', type=float, default=None, help='Fixed stop loss (%)')
    
    # Universe
    parser.add_argument('--tickers', type=str, help='Comma-separated list of tickers')
    parser.add_argument('--limit', type=int, default=50, help='Auto-select top N by liquidity')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🚀 VECTORBT BACKTESTING ENGINE")
    print("=" * 80)
    print(f"📅 Period: {args.start} to {args.end}")
    print(f"💰 Capital: ${args.equity:,.0f}")
    print(f"⚠️  Risk: {args.risk}% per trade")
    print(f"📊 Max Exposure: {args.max_exp}% per position")
    if args.stop_loss:
        print(f"🛑 Stop Loss: {args.stop_loss}%")
    print("=" * 80)
    
    # Build universe
    if args.tickers:
        universe = [t.strip().upper() for t in args.tickers.split(',')]
    else:
        # Get top N by liquidity from database directly
        print(f"🔍 Auto-selecting top {args.limit} tickers by liquidity...")
        import sqlite3
        
        conn = sqlite3.connect('./data/ticker_cache.db')
        query = """
        SELECT ticker, AVG(dollar_volume) as avg_dv
        FROM ohlcv_cache
        WHERE date BETWEEN ? AND ?
        AND dollar_volume IS NOT NULL
        GROUP BY ticker
        HAVING COUNT(*) >= 100
        ORDER BY avg_dv DESC
        LIMIT ?
        """
        
        cursor = conn.execute(query, (args.start, args.end, args.limit))
        universe = [row[0] for row in cursor.fetchall()]
        conn.close()
    
    print(f"🎯 Universe: {len(universe)} tickers")
    print(f"   {', '.join(universe[:10])}{'...' if len(universe) > 10 else ''}")
    print("=" * 80)
    
    # Run backtest
    start_time = time.time()
    
    try:
        results = run_vectorbt_backtest(
            universe=universe,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.equity,
            risk_pct=args.risk,
            max_exposure=args.max_exp,
            stop_loss=args.stop_loss
        )
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 80)
        print("📊 RESULTS")
        print("=" * 80)
        print(f"⏱️  Execution Time: {elapsed:.2f} seconds")
        print(f"💹 Total Return: {results['total_return']*100:+.2f}%")
        print(f"📈 Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"📉 Max Drawdown: {results['max_drawdown']*100:.2f}%")
        print(f"✅ Win Rate: {results['win_rate']*100:.1f}%")
        print(f"📝 Total Trades: {results['total_trades']}")
        print("=" * 80)
        
        # Save results
        output_file = f"outputs/vectorbt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        results['trades'].to_csv(output_file)
        print(f"💾 Trade log saved: {output_file}")
        
        # Save equity curve
        equity_file = f"outputs/vectorbt_equity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        results['equity_curve'].to_csv(equity_file)
        print(f"💾 Equity curve saved: {equity_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
