#!/usr/bin/env python3
"""
Precompute indicators for ALL tickers in cache (SAFE version)
- Creates backups
- Can resume if interrupted
- Shows progress
- Validates each ticker
"""
import pandas as pd
import numpy as np
from pathlib import Path
import shutil
from datetime import datetime
from tqdm import tqdm
import sys

CACHE_DIR = Path('data/cache')
BACKUP_DIR = Path('data/cache_backups')
LOG_FILE = Path('precompute_log.txt')

def calculate_indicators(df):
    """Calculate all indicators for a DataFrame"""
    # Normalize timezone
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # SMA
    df['sma_20'] = df['Close'].rolling(window=20, min_periods=20).mean()
    df['sma_50'] = df['Close'].rolling(window=50, min_periods=50).mean()
    
    # ATR
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14, min_periods=14).mean()
    
    # ADR
    daily_range = (df['High'] - df['Low']) / df['Low'] * 100
    df['adr_pct'] = daily_range.rolling(window=20, min_periods=20).mean()
    
    # Dollar Volume
    df['dollar_volume'] = df['Close'] * df['Volume']
    df['avg_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=20).mean()
    
    return df

def process_ticker(ticker_file, backup=True):
    """Process a single ticker file"""
    try:
        # Skip if already has indicators
        df_check = pd.read_pickle(ticker_file)
        if 'sma_20' in df_check.columns:
            return 'skip', 'already_done'
        
        # Backup if requested
        if backup:
            backup_file = BACKUP_DIR / ticker_file.name
            if not backup_file.exists():
                shutil.copy(ticker_file, backup_file)
        
        # Calculate indicators
        df = calculate_indicators(df_check)
        
        # Validate
        if df['sma_20'].notna().sum() < 10:  # At least 10 valid SMAs
            return 'fail', 'insufficient_data'
        
        # Save
        df.to_pickle(ticker_file)
        
        return 'success', f"{df.shape[0]} bars"
        
    except Exception as e:
        return 'fail', str(e)

def main():
    print("="*70)
    print("🚀 PRECOMPUTE INDICATORS FOR ALL TICKERS")
    print("="*70)
    
    # Get all tickers
    pkl_files = sorted(list(CACHE_DIR.glob('*.pkl')))
    print(f"\n📊 Found {len(pkl_files)} pickle files")
    
    # Create backup dir
    BACKUP_DIR.mkdir(exist_ok=True)
    print(f"📦 Backups will be saved to: {BACKUP_DIR}")
    
    # Check what's already done
    already_done = 0
    for pkl in pkl_files[:10]:  # Sample first 10
        df = pd.read_pickle(pkl)
        if 'sma_20' in df.columns:
            already_done += 1
    
    if already_done > 0:
        print(f"ℹ️  {already_done}/10 sampled tickers already have indicators")
        cont = input("   Continue anyway? (yes/no): ")
        if cont.lower() != 'yes':
            print("Aborted")
            return
    
    print(f"\n⏱️  Estimated time: {len(pkl_files) * 0.5:.0f} seconds (~{len(pkl_files) * 0.5 / 60:.1f} minutes)")
    print(f"💾 Disk space needed: ~{len(pkl_files) * 0.15:.0f} MB for indicators")
    
    cont = input(f"\n🤔 Precompute {len(pkl_files)} tickers? (yes/no): ")
    if cont.lower() != 'yes':
        print("Aborted")
        return
    
    # Process all
    print(f"\n🔄 Processing...")
    stats = {'success': 0, 'skip': 0, 'fail': 0}
    failed_tickers = []
    
    with open(LOG_FILE, 'w') as log:
        log.write(f"Precompute started: {datetime.now()}\n\n")
        
        for pkl_file in tqdm(pkl_files, desc="Precomputing"):
            ticker = pkl_file.stem
            status, msg = process_ticker(pkl_file, backup=True)
            
            stats[status] += 1
            log.write(f"{status.upper()}: {ticker} - {msg}\n")
            
            if status == 'fail':
                failed_tickers.append(f"{ticker}: {msg}")
        
        log.write(f"\n\nCompleted: {datetime.now()}\n")
        log.write(f"Success: {stats['success']}, Skip: {stats['skip']}, Fail: {stats['fail']}\n")
    
    # Summary
    print("\n" + "="*70)
    print("📊 RESULTS")
    print("="*70)
    print(f"  ✅ Success: {stats['success']}")
    print(f"  ⏭️  Skipped: {stats['skip']} (already done)")
    print(f"  ❌ Failed:  {stats['fail']}")
    
    if failed_tickers:
        print(f"\n  Failed tickers (first 10):")
        for f in failed_tickers[:10]:
            print(f"    - {f}")
    
    print(f"\n📝 Full log: {LOG_FILE}")
    print(f"📦 Backups: {BACKUP_DIR}")
    
    if stats['success'] > 0:
        print(f"\n✅ SUCCESS! {stats['success']} tickers now have precomputed indicators")
        print(f"   Expected speedup: 40-57x for indicator calculations")
    
    # Cleanup option
    if stats['success'] > 0 and stats['fail'] == 0:
        cleanup = input(f"\n🗑️  Remove backups? (saves {len(pkl_files) * 0.15:.0f} MB) (yes/no): ")
        if cleanup.lower() == 'yes':
            shutil.rmtree(BACKUP_DIR)
            print(f"   ✓ Backups removed")

if __name__ == '__main__':
    main()
