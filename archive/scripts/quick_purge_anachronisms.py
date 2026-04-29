#!/usr/bin/env python3
"""
Quick purge of known anachronistic tickers
"""
from pathlib import Path

# Known time travelers from analysis
bad_tickers = [
    'ABNG',  # ETF launched 2025, has 2021 data
    'AGGH',  # ETF launched Feb 2022, has 2021 data  
    'CARY',  # ETF launched Nov 2022, has 2021 data
    'AEON',  # Launched Jan 2023, has 2021 data
]

# Also remove tickers with invalid suffixes
invalid_suffixes = []
cache_dir = Path('data/cache')

for pkl in cache_dir.glob('*_earnings.pkl'):
    invalid_suffixes.append(pkl.stem)
for pkl in cache_dir.glob('*_daily.pkl'):
    invalid_suffixes.append(pkl.stem)

all_to_remove = bad_tickers + invalid_suffixes

print(f"Purging {len(all_to_remove)} bad tickers...")
print(f"  Time travelers: {len(bad_tickers)}")
print(f"  Invalid suffixes: {len(invalid_suffixes)}")

removed = 0
for ticker in all_to_remove:
    pkl_file = cache_dir / f"{ticker}.pkl"
    if pkl_file.exists():
        pkl_file.unlink()
        removed += 1
        print(f"  ✓ Removed {ticker}")

print(f"\n✓ Purged {removed} files")
print(f"Remaining: {len(list(cache_dir.glob('*.pkl')))} tickers")
