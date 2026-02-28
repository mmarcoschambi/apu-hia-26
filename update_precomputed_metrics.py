#!/usr/bin/env python3
"""
Update Precomputed Metrics for New Data Only
-----------------------------------------------
This script only updates precomputed metrics for data that doesn't have them yet.
Much faster than full population - only processes missing rows.

Usage:
    python update_precomputed_metrics.py

Run daily after market close to keep cache up to date.
"""

import sqlite3
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'data' / 'ticker_cache.db'

def update_ticker_missing_metrics(conn, ticker):
    """
    Calculate and update metrics for rows that don't have them yet.
    
    Args:
        conn: SQLite connection
        ticker: Ticker symbol
        
    Returns:
        int: Number of rows updated
    """
    # Get all OHLCV data for this ticker
    cursor = conn.execute('''
        SELECT date, open, high, low, close, volume, sma20, sma50, adr_pct_20
        FROM ohlcv_cache
        WHERE ticker = ?
        ORDER BY date
    ''', (ticker,))
    
    rows = cursor.fetchall()
    if not rows:
        return 0
    
    df = pd.DataFrame(rows, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'sma20', 'sma50', 'adr_pct_20'])
    
    # Find rows missing metrics
    missing_mask = (
        (df['sma20'].isna()) | 
        (df['sma50'].isna()) | 
        (df['adr_pct_20'].isna())
    )
    
    missing_df = df[missing_mask]
    
    if len(missing_df) == 0:
        return 0
    
    # Calculate metrics for ALL data (to get proper rolling values)
    full_df = df.copy()
    full_df['calc_sma20'] = full_df['close'].rolling(window=20, min_periods=1).mean()
    full_df['calc_sma50'] = full_df['close'].rolling(window=50, min_periods=1).mean()
    full_df['calc_adr_pct_20'] = ((full_df['high'] - full_df['low']) / full_df['low'] * 100).rolling(window=20, min_periods=1).mean()
    
    # Update only missing rows
    updated_rows = 0
    
    for idx in missing_df.index:
        row = full_df.loc[idx]
        
        try:
            conn.execute('''
                UPDATE ohlcv_cache
                SET sma20 = ?, sma50 = ?, adr_pct_20 = ?
                WHERE ticker = ? AND date = ?
            ''', (
                row['calc_sma20'],
                row['calc_sma50'],
                row['calc_adr_pct_20'],
                ticker,
                row['date']
            ))
            updated_rows += 1
        except Exception as e:
            logger.error(f"Error updating {ticker} on {row['date']}: {e}")
    
    if updated_rows > 0:
        conn.commit()
    
    return updated_rows

def main():
    """Main execution function."""
    
    logger.info("="*60)
    logger.info("Updating Precomputed Metrics (New Data Only)")
    logger.info("="*60)
    
    # Connect to database
    logger.info(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    
    # Get all tickers
    logger.info("\nLoading ticker list...")
    cursor = conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker")
    tickers = [row[0] for row in cursor.fetchall()]
    logger.info(f"Found {len(tickers)} tickers")
    
    # Count missing metrics before update
    logger.info("\nChecking for missing metrics...")
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total_rows,
            CASE WHEN sma20 IS NULL THEN 1 ELSE 0 END as has_na_sma20,
            CASE WHEN sma50 IS NULL THEN 1 ELSE 0 END as has_na_sma50,
            CASE WHEN adr_pct_20 IS NULL THEN 1 ELSE 0 END as has_na_adr
        FROM ohlcv_cache
    ''')
    
    total_before = cursor.fetchone()[0]
    
    # Update metrics for tickers with missing data
    logger.info("\nUpdating missing metrics...")
    
    total_updated = 0
    tickers_updated = 0
    
    for ticker in tqdm(tickers, desc="Processing tickers"):
        try:
            rows_updated = update_ticker_missing_metrics(conn, ticker)
            
            if rows_updated > 0:
                total_updated += rows_updated
                tickers_updated += 1
                
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("COMPLETED!")
    logger.info("="*60)
    logger.info(f"Tickers with updates: {tickers_updated}/{len(tickers)}")
    logger.info(f"Total rows updated: {total_updated:,}")
    
    # Verify data after update
    logger.info("\nVerifying updated metrics...")
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total_rows,
            COUNT(sma20) as sma20_count,
            COUNT(sma50) as sma50_count,
            COUNT(adr_pct_20) as adr_count
        FROM ohlcv_cache
    ''')
    
    row = cursor.fetchone()
    total_after = row[0]
    sma20_count = row[1]
    sma50_count = row[2]
    adr_count = row[3]
    
    logger.info(f"Total rows in ohlcv_cache: {total_after:,}")
    logger.info(f"SMA20 calculated: {sma20_count:,} ({sma20_count/total_after*100:.1f}%)")
    logger.info(f"SMA50 calculated: {sma50_count:,} ({sma50_count/total_after*100:.1f}%)")
    logger.info(f"ADR20 calculated: {adr_count:,} ({adr_count/total_after*100:.1f}%)")
    
    conn.close()
    
    logger.info("\n" + "="*60)
    logger.info("DONE!")
    logger.info("="*60)
    
    return total_updated

if __name__ == "__main__":
    main()