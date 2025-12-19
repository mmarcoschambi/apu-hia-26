#!/usr/bin/env python3
"""
Headless Backtest Runner for Dashboard Integration
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.backtest.backtest import HistoricalBacktester
from src.backtest.visualizer import BacktestVisualizer

def load_watchlist(json_path):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        # Flatten all categories into one list
        symbols = []
        for cat in data.values():
            symbols.extend(cat)
        return list(set(symbols)) # Unique
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return ['AAPL', 'MSFT', 'TSLA', 'NVDA'] # Fallback

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--watchlist', default='config/watchlist.json')
    args = parser.parse_args()

    print(f"Starting backtest from {args.start} to {args.end}")
    
    symbols = load_watchlist(args.watchlist)
    total_symbols = len(symbols)
    print(f"Loaded {total_symbols} symbols from watchlist.")

    backtester = HistoricalBacktester()
    all_results = []
    
    # Custom iteration to print progress
    for i, symbol in enumerate(symbols):
        print(f"__PROGRESS__{i+1}/{total_symbols}__{symbol}") # Special marker for Streamlit
        try:
            # We use backtest_symbol directly instead of backtest_watchlist to control loop
            res = backtester.backtest_symbol(symbol, args.start, args.end)
            if not res.empty:
                all_results.append(res)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if all_results:
        import pandas as pd
        combined = pd.concat(all_results, ignore_index=True)
        backtester.save_results(combined, 'backtest_results.csv')
        
        # Generate Summary Dashboard Image only (faster than all charts)
        print("Generating summary dashboard...")
        viz = BacktestVisualizer()
        viz.create_summary_dashboard('backtest_results.csv')
        print("Done.")
    else:
        print("No trades found in the specified period.")
        # Create empty csv to avoid errors
        import pandas as pd
        pd.DataFrame(columns=['entry_date', 'exit_date', 'entry_price', 'exit_price', 'returns_pct', 
                              'is_profitable', 'signal_type', 'signal_reason', 'symbol']).to_csv('backtest_results.csv', index=False)

if __name__ == "__main__":
    main()
