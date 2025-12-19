#!/usr/bin/env python3
"""
Headless Backtest Runner for Dashboard Integration (OpenBB Version)
"""
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Import OpenBB implementation instead of old HistoricalBacktester
from src.core.triad_openbb import TriadOpenBB

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
        # Default fallback symbols
        return ['AAPL', 'MSFT', 'TSLA', 'NVDA']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--watchlist', default='config/watchlist.json')
    args = parser.parse_args()

    print(f"Starting OpenBB backtest from {args.start} to {args.end}")
    
    symbols = load_watchlist(args.watchlist)
    total_symbols = len(symbols)
    print(f"Loaded {total_symbols} symbols from watchlist.")

    # Initialize OpenBB Triad system
    triad = TriadOpenBB()
    all_results = []
    
    # Iterate manually to report progress to Streamlit
    for i, symbol in enumerate(symbols):
        print(f"__PROGRESS__{i+1}/{total_symbols}__{symbol}")
        try:
            # We pass a list of 1 symbol to leverage the existing method signature
            res = triad.backtest_with_openbb([symbol], args.start, args.end)
            if not res.empty:
                all_results.append(res)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        # Ensure date columns are datetime for sorting/filtering consistency
        if 'entry_date' in combined.columns:
            combined['entry_date'] = pd.to_datetime(combined['entry_date'])
        if 'exit_date' in combined.columns:
            combined['exit_date'] = pd.to_datetime(combined['exit_date'])
            
        combined.to_csv('backtest_results.csv', index=False)
        print(f"✅ Successfully saved {len(combined)} trades to backtest_results.csv")
    else:
        print("No trades found in the specified period.")
        # Create empty csv with correct columns to avoid dashboard errors
        pd.DataFrame(columns=[
            'entry_date', 'exit_date', 'entry_price', 'exit_price', 
            'returns_pct', 'is_profitable', 'signal_type', 
            'signal_reason', 'symbol'
        ]).to_csv('backtest_results.csv', index=False)

if __name__ == "__main__":
    main()