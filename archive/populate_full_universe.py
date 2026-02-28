#!/usr/bin/env python3
"""
Populate FULL Universe (6000+ Tickers)
======================================
Downloads historical data for ALL tickers in the 'universe' table.
Solves the "Survivorship Bias" and "Patchy Data" issue.

Usage:
    python3 populate_full_universe.py --start-date 2014-01-01 --end-date 2024-12-31
"""

import sys
import sqlite3
import pandas as pd
import yfinance as yf
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("populate_full.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PopulateFull")

def get_db_path():
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    return data_dir / "ticker_cache.db"

def get_all_tickers(db_path):
    """Fetch all tickers from the universe table."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT ticker FROM universe ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers

def get_existing_tickers(db_path):
    """Fetch tickers that already have data."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache")
        tickers = {row[0] for row in cursor.fetchall()}
    except:
        tickers = set()
    conn.close()
    return tickers

def download_and_cache(ticker, start_date, end_date, db_path):
    """Download data for a single ticker and save to SQLite."""
    try:
        # Download from yfinance
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        
        if df is None or len(df) == 0:
            return False, "No data"
        
        # Normalize columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        df.columns = [col.lower() for col in df.columns]
        
        # Ensure date format
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        # Connect to DB per ticker to avoid thread issues
        conn = sqlite3.connect(str(db_path))
        
        # Insert data
        records = []
        for _, row in df.iterrows():
            # Calculate dollar volume
            close = float(row['close']) if pd.notnull(row['close']) else 0
            volume = int(row['volume']) if pd.notnull(row['volume']) else 0
            dollar_vol = close * volume
            
            records.append((
                ticker,
                str(row['date']),
                float(row['open']) if pd.notnull(row['open']) else None,
                float(row['high']) if pd.notnull(row['high']) else None,
                float(row['low']) if pd.notnull(row['low']) else None,
                close,
                volume,
                dollar_vol,
                None # rolling_dollar_vol (calculated later or strictly not needed for cache raw)
            ))
            
        conn.executemany("""
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        
        conn.commit()
        conn.close()
        
        return True, f"{len(df)} records"
        
    except Exception as e:
        return False, str(e)

def main():
    parser = argparse.ArgumentParser(description='Populate FULL universe data')
    parser.add_argument('--start-date', default='2014-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of tickers (0 for all)')
    parser.add_argument('--skip-existing', action='store_true', help='Skip tickers already in cache')
    args = parser.parse_args()
    
    db_path = get_db_path()
    
    print(f"\n🌍 POPULATE FULL UNIVERSE (10 YEARS)")
    print(f"=====================================")
    print(f"📅 Range: {args.start_date} -> {args.end_date}")
    
    # Get tickers
    all_tickers = get_all_tickers(db_path)
    print(f"📊 Total tickers in Universe: {len(all_tickers)}")
    
    if args.skip_existing:
        existing = get_existing_tickers(db_path)
        all_tickers = [t for t in all_tickers if t not in existing]
        print(f"⏩ Skipping {len(existing)} existing. Remaining: {len(all_tickers)}")
    
    if args.limit > 0:
        all_tickers = all_tickers[:args.limit]
        print(f"✂️ Limiting to first {args.limit} tickers")
    
    print(f"🚀 Starting download for {len(all_tickers)} tickers...")
    print(f"   (This may take several hours. Logs in populate_full.log)\n")
    
    success_count = 0
    fail_count = 0
    
    start_time = time.time()
    
    try:
        for i, ticker in enumerate(all_tickers, 1):
            sys.stdout.write(f"\r[{i}/{len(all_tickers)}] {ticker: <6} ")
            
            success, msg = download_and_cache(ticker, args.start_date, args.end_date, db_path)
            
            if success:
                success_count += 1
                sys.stdout.write(f"✅ {msg}")
            else:
                fail_count += 1
                logger.error(f"{ticker}: Failed - {msg}")
                sys.stdout.write(f"❌ {msg}")
            
            sys.stdout.flush()
            
            # Rate limiting protection
            if i % 20 == 0:
                time.sleep(1) 
                
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user.")
    
    elapsed = (time.time() - start_time) / 60
    print(f"\n\n🏁 DONE in {elapsed:.1f} minutes.")
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed:  {fail_count}")

if __name__ == "__main__":
    main()
