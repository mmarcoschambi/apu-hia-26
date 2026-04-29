#!/usr/bin/env python3
"""
Clean universe JSON files to remove anachronistic and invalid tickers
"""
import json
from pathlib import Path
import pandas as pd

# Load list of valid cached tickers
cache_dir = Path('data/cache')
valid_tickers = {p.stem for p in cache_dir.glob('*.pkl')}

print(f"Valid tickers in cache: {len(valid_tickers)}")

# Clean universe files
universe_dir = Path('data/universe')
if not universe_dir.exists():
    print("No universe directory found")
    exit(0)

for json_file in universe_dir.glob('*.json'):
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if 'tickers' in data:
            original_count = len(data['tickers'])
            # Remove invalid tickers
            data['tickers'] = [t for t in data['tickers'] if t in valid_tickers]
            cleaned_count = len(data['tickers'])
            
            if original_count > cleaned_count:
                removed = original_count - cleaned_count
                print(f"\n{json_file.name}:")
                print(f"  Removed {removed} invalid tickers ({original_count} → {cleaned_count})")
                
                # Save cleaned version
                with open(json_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"  ✓ Updated")
    except Exception as e:
        print(f"Error processing {json_file.name}: {e}")

print("\n✓ Universe files cleaned")
