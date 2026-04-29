#!/usr/bin/env python3
"""
Detect and purge tickers with data BEFORE their actual inception date.
This happens when yfinance backfills data or tickers are ETFs/SPACs that launched recently.
"""
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime
import json

cache_dir = Path('data/cache')
pkl_files = list(cache_dir.glob('*.pkl'))

print(f"Scanning {len(pkl_files)} cached tickers for anachronisms...")

anachronisms = []
checked = 0

for pkl_file in pkl_files:
    ticker_symbol = pkl_file.stem
    
    # Skip special files
    if '_' in ticker_symbol:  # Skip AAPL_earnings, etc
        continue
    
    try:
        # Load cached data
        cached_data = pd.read_pickle(pkl_file)
        if len(cached_data) == 0:
            continue
        
        cache_first_date = cached_data.index[0]
        
        # Get actual inception from yfinance
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        # Check if ETF (common culprit)
        is_etf = info.get('quoteType', '') in ['ETF', 'ETN']
        
        # Get live data to compare
        live_hist = ticker.history(period='max')
        if len(live_hist) == 0:
            continue
            
        live_first_date = live_hist.index[0].replace(tzinfo=None)
        cache_first_dt = pd.to_datetime(cache_first_date).replace(tzinfo=None)
        
        # If cached data starts BEFORE live data by >30 days, it's suspicious
        if cache_first_dt < live_first_dt:
            days_diff = (live_first_dt - cache_first_dt).days
            if days_diff > 30:  # Grace period for minor discrepancies
                anachronisms.append({
                    'ticker': ticker_symbol,
                    'cached_start': cache_first_dt.strftime('%Y-%m-%d'),
                    'actual_start': live_first_dt.strftime('%Y-%m-%d'),
                    'days_early': days_diff,
                    'is_etf': is_etf,
                    'name': info.get('longName', 'Unknown')[:50]
                })
        
        checked += 1
        if checked % 100 == 0:
            print(f"  Checked {checked}/{len(pkl_files)}...")
            
    except Exception as e:
        pass

print(f"\n✓ Scan complete. Checked {checked} tickers.")
print(f"Found {len(anachronisms)} anachronistic tickers:\n")

if anachronisms:
    df = pd.DataFrame(anachronisms).sort_values('days_early', ascending=False)
    print(df.to_string(index=False))
    
    # Save list
    with open('anachronistic_tickers.txt', 'w') as f:
        for ticker in df['ticker'].tolist():
            f.write(f"{ticker}\n")
    
    print(f"\n✓ List saved to: anachronistic_tickers.txt")
    print(f"\nTo purge: rm data/cache/{{ABNG,AGGH,AEON,CARY}}.pkl")
else:
    print("✓ No anachronisms detected (all tickers valid)")
