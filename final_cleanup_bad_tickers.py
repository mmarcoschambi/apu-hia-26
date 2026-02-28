#!/usr/bin/env python3
"""
Final cleanup: Remove all tickers without 2021-2024 coverage
"""
import pandas as pd
from pathlib import Path

# Load the list of tickers without 2021 data
no_2021 = pd.read_csv('tickers_no_2021_data.csv')
tickers_to_remove = set(no_2021['ticker'].tolist())

print(f"Removing {len(tickers_to_remove)} tickers without 2021 coverage...")

cache_dir = Path('data/cache')
removed = 0

for ticker in tickers_to_remove:
    pkl_file = cache_dir / f"{ticker}.pkl"
    if pkl_file.exists():
        pkl_file.unlink()
        removed += 1

print(f"✓ Removed {removed} cache files")
print(f"✓ Remaining: {len(list(cache_dir.glob('*.pkl')))} tickers")

# Update universe files
import json
universe_dir = Path('data/universe')

for json_file in universe_dir.glob('*.json'):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    if 'tickers' in data:
        before = len(data['tickers'])
        data['tickers'] = [t for t in data['tickers'] if t not in tickers_to_remove]
        after = len(data['tickers'])
        
        if before > after:
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  {json_file.name}: {before} → {after} tickers")

print("\n✅ CLEANUP COMPLETE")
print(f"✅ Cache now has ONLY tickers valid for 2021-2024 backtests")
