#!/usr/bin/env python3
"""
OPTIMIZED BACKTEST RUNNER
=========================

Executes the AdvancedVectorBTEngine with the finalized, optimized parameters
over a specified historical period.

Usage:
    python run_optimized_backtest.py [--start 2020-01-01] [--end 2024-12-31] [--tickers "AAPL NVDA ..."]
"""

import sys
import argparse
import pandas as pd
import logging
from pathlib import Path

# Setup paths
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("OptimizedRunner")

# Default Universe (Diverse mix)
DEFAULT_TICKERS = [
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'GOOGL', 'AMZN', 'META',  # Mag 7
    'AMD', 'NFLX', 'PLTR', 'COIN', 'MSTR',                   # Tech / Crypto
    'LLY', 'AVGO', 'SMCI', 'ARM',                            # Semis / Pharma
    'UNH', 'NVO',                                            # Health
    'XOM', 'CVX'                                             # Energy (Cyclical)
]

def main():
    parser = argparse.ArgumentParser(description="Run Optimized Backtest")
    parser.add_argument('--start', type=str, default='2020-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Space-separated list of tickers')
    parser.add_argument('--csv', action='store_true', help='Save trades to CSV')
    
    args = parser.parse_args()
    
    # Parse tickers
    if args.tickers:
        tickers = args.tickers.split()
    else:
        tickers = DEFAULT_TICKERS
        
    print("=" * 70)
    print("🚀 OPTIMIZED PRODUCTION BACKTEST")
    print("=" * 70)
    print(f"📅 Period: {args.start} to {args.end}")
    print(f"🎯 Universe: {len(tickers)} tickers")
    print("⚙️  Engine: AdvancedVectorBTEngine (Production Config)")
    print("-" * 70)
    
    # Initialize Engine (Uses hardcoded defaults which are now the optimized ones)
    engine = AdvancedVectorBTEngine(
        universe=tickers,
        start_date=args.start,
        end_date=args.end,
        # Explicitly enabling critical features just in case, 
        # though defaults should handle it.
        require_spy_above_sma50=True,
        min_rvol=2.0,
        min_adr=2.0,
        risk_dollars=100
    )
    
    # Run
    try:
        results = engine.run_backtest()
        
        # Display Results
        print("\n" + "=" * 70)
        print("📊 BACKTEST RESULTS")
        print("=" * 70)
        
        metrics = [
            ("Total Return", f"{results['total_return']*100:.2f}%"),
            ("Sharpe Ratio", f"{results['sharpe_ratio']:.3f}"),
            ("Max Drawdown", f"{results['max_drawdown']*100:.2f}%"),
            ("Win Rate", f"{results['win_rate']*100:.1f}%"),
            ("Total Trades", str(results['total_trades'])),
            ("Profit Factor", f"{results['profit_factor']:.2f}"),
        ]
        
        for label, value in metrics:
            print(f"{label:20s}: {value:>10s}")
            
        print("-" * 70)
        
        # Save CSV if requested
        if args.csv and 'trades_df' in results and results['trades_df'] is not None:
            filename = f"optimized_backtest_{args.start}_{args.end}.csv"
            results['trades_df'].to_csv(filename, index=False)
            print(f"💾 Trades saved to: {filename}")
            
    except Exception as e:
        print(f"\n❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
