#!/usr/bin/env python3
"""
Populate Historical Metrics in ohlcv_cache
-------------------------------------------
Calculates and stores:
- ADR (14 days) in $ and %
- SMA 50 and SMA 200
- Trend alignment flags

This is a ONE-TIME computation that makes future backtests INSTANT.
Run this whenever you add new historical data.
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def calculate_metrics_for_ticker(conn, ticker):
    """Calculate all metrics for a single ticker"""
    
    # Fetch all data for this ticker
    query = """
        SELECT date, open, high, low, close, volume 
        FROM ohlcv_cache 
        WHERE ticker = ?
        ORDER BY date ASC
    """
    
    df = pd.read_sql_query(query, conn, params=(ticker,))
    
    if df.empty or len(df) < 200:
        return 0  # Not enough data
    
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # Calculate ADR (14 days)
    df['daily_range'] = df['high'] - df['low']
    df['daily_range_pct'] = (df['daily_range'] / df['low']) * 100
    df['adr_14'] = df['daily_range'].rolling(window=14, min_periods=14).mean()
    df['adr_pct_14'] = df['daily_range_pct'].rolling(window=14, min_periods=14).mean()
    
    # Calculate SMAs
    df['sma_50'] = df['close'].rolling(window=50, min_periods=50).mean()
    df['sma_200'] = df['close'].rolling(window=200, min_periods=200).mean()
    
    # Calculate trend flags
    df['price_above_sma50'] = (df['close'] > df['sma_50']).astype(int)
    df['price_above_sma200'] = (df['close'] > df['sma_200']).astype(int)
    df['sma50_above_sma200'] = (df['sma_50'] > df['sma_200']).astype(int)
    df['trend_aligned'] = (df['price_above_sma50'] & df['sma50_above_sma200']).astype(int)
    
    # Prepare update data (only non-null values)
    updates = []
    for date, row in df.iterrows():
        updates.append((
            row['adr_14'] if not pd.isna(row['adr_14']) else None,
            row['adr_pct_14'] if not pd.isna(row['adr_pct_14']) else None,
            row['sma_50'] if not pd.isna(row['sma_50']) else None,
            row['sma_200'] if not pd.isna(row['sma_200']) else None,
            row['price_above_sma50'],
            row['price_above_sma200'],
            row['sma50_above_sma200'],
            row['trend_aligned'],
            ticker,
            date.strftime('%Y-%m-%d')
        ))
    
    # Batch update
    cursor = conn.cursor()
    cursor.executemany("""
        UPDATE ohlcv_cache 
        SET adr_14 = ?,
            adr_pct_14 = ?,
            sma_50 = ?,
            sma_200 = ?,
            price_above_sma50 = ?,
            price_above_sma200 = ?,
            sma50_above_sma200 = ?,
            trend_aligned = ?
        WHERE ticker = ? AND date = ?
    """, updates)
    
    return len(updates)

def main():
    db_path = Path(__file__).resolve().parent.parent / "data" / "ticker_cache.db"
    conn = sqlite3.connect(str(db_path))
    
    # Get all unique tickers
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Calculating historical metrics for {len(tickers)} tickers...")
    print(f"⏱️  This will take a while but only needs to run ONCE.\n")
    
    total_rows = 0
    errors = 0
    
    for i, ticker in enumerate(tickers, 1):
        try:
            rows_updated = calculate_metrics_for_ticker(conn, ticker)
            total_rows += rows_updated
            
            if i % 10 == 0 or i == len(tickers):
                print(f"  Progress: {i}/{len(tickers)} ({i/len(tickers)*100:.1f}%) - {total_rows:,} rows updated")
            
            # Commit every 50 tickers to avoid memory issues
            if i % 50 == 0:
                conn.commit()
                
        except Exception as e:
            errors += 1
            print(f"  ❌ Error processing {ticker}: {e}")
    
    # Final commit
    conn.commit()
    conn.close()
    
    print(f"\n✅ Completed!")
    print(f"   Total rows updated: {total_rows:,}")
    print(f"   Errors: {errors}")
    print(f"\n💡 Future backtests will now be MUCH faster!")

if __name__ == "__main__":
    main()
