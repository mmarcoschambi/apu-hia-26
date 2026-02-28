#!/usr/bin/env python3
"""
Refresh ALL cached tickers to get current dividend adjustments
"""
import os
import glob
from pathlib import Path
import yfinance as yf
import pandas as pd
from datetime import datetime

cache_dir = Path('data/cache')
pkl_files = list(cache_dir.glob('*.pkl'))

print(f"Found {len(pkl_files)} cached tickers")
print("Starting refresh (this may take 15-30 minutes)...\n")

failed = []
for i, pkl_file in enumerate(pkl_files, 1):
    ticker_symbol = pkl_file.stem
    
    try:
        print(f"[{i}/{len(pkl_files)}] {ticker_symbol}...", end=' ', flush=True)
        
        # Download fresh data
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(start='2014-01-01', auto_adjust=True, actions=False)
        
        if len(data) == 0:
            print(f"❌ No data")
            failed.append(ticker_symbol)
            continue
            
        # Save
        data.to_pickle(pkl_file)
        print(f"✓ {len(data)} bars")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        failed.append(ticker_symbol)

print(f"\n✓ Completed. Failed: {len(failed)}")
if failed:
    print(f"Failed tickers: {', '.join(failed[:10])}")
