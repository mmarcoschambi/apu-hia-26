#!/usr/bin/env python3
"""
Fix Rolling Dollar Volume for Existing Tickers
------------------------------------------------
Recalcula rolling_dollar_vol_20 para todos los tickers que lo tienen NULL.
Soluciona el problema del universo de 5147 tickers → 53 tickers.

Usage:
    python fix_rolling_dollar_volume.py
    python fix_rolling_dollar_volume.py --ticker AAPL  # Solo un ticker
"""

import sqlite3
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
from tqdm import tqdm
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'data' / 'ticker_cache.db'

def fix_ticker_rolling_volume(conn, ticker):
    """
    Recalcula rolling_dollar_vol_20 para un ticker.
    
    Args:
        conn: SQLite connection
        ticker: Ticker symbol
        
    Returns:
        int: Number of rows updated
    """
    # Get all OHLCV data for this ticker
    cursor = conn.execute('''
        SELECT date, close, volume, rolling_dollar_vol_20
        FROM ohlcv_cache
        WHERE ticker = ?
        ORDER BY date
    ''', (ticker,))
    
    rows = cursor.fetchall()
    if not rows:
        return 0
    
    df = pd.DataFrame(rows, columns=['date', 'close', 'volume', 'rolling_dollar_vol_20'])
    
    # Skip if already calculated
    if df['rolling_dollar_vol_20'].notna().all():
        return 0
    
    # Calculate dollar volume and rolling average
    df['dollar_volume'] = df['close'] * df['volume']
    df['calc_rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=1).mean()
    
    # Update all rows
    updated_rows = 0
    
    for idx, row in df.iterrows():
        try:
            conn.execute('''
                UPDATE ohlcv_cache
                SET rolling_dollar_vol_20 = ?
                WHERE ticker = ? AND date = ?
            ''', (
                row['calc_rolling_dollar_vol_20'],
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
    parser = argparse.ArgumentParser(description='Fix rolling dollar volume for tickers')
    parser.add_argument('--ticker', type=str, help='Process only this ticker')
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("Fixing Rolling Dollar Volume (rolling_dollar_vol_20)")
    logger.info("="*60)
    
    # Connect to database
    logger.info(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    
    # Get tickers to process
    if args.ticker:
        tickers = [args.ticker]
        logger.info(f"Processing single ticker: {args.ticker}")
    else:
        logger.info("\nLoading ticker list...")
        cursor = conn.execute("""
            SELECT DISTINCT ticker 
            FROM ohlcv_cache 
            WHERE rolling_dollar_vol_20 IS NULL
            ORDER BY ticker
        """)
        tickers = [row[0] for row in cursor.fetchall()]
        logger.info(f"Found {len(tickers)} tickers with NULL rolling_dollar_vol_20")
    
    # Count missing metrics before update
    logger.info("\nChecking current status...")
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN rolling_dollar_vol_20 IS NULL THEN 1 ELSE 0 END) as null_count,
            SUM(CASE WHEN rolling_dollar_vol_20 IS NOT NULL THEN 1 ELSE 0 END) as non_null_count
        FROM ohlcv_cache
    ''')
    
    stats = cursor.fetchone()
    logger.info(f"Total rows: {stats[0]:,}")
    logger.info(f"Rows with NULL: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
    logger.info(f"Rows with value: {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
    
    # Process tickers
    logger.info("\n" + "="*60)
    logger.info("Processing tickers...")
    logger.info("="*60)
    
    total_updated = 0
    tickers_updated = 0
    
    for ticker in tqdm(tickers, desc="Fixing tickers"):
        try:
            rows_updated = fix_ticker_rolling_volume(conn, ticker)
            
            if rows_updated > 0:
                total_updated += rows_updated
                tickers_updated += 1
                
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
    
    # Final stats
    logger.info("\n" + "="*60)
    logger.info("Checking final status...")
    logger.info("="*60)
    
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total_rows,
            SUM(CASE WHEN rolling_dollar_vol_20 IS NULL THEN 1 ELSE 0 END) as null_count,
            SUM(CASE WHEN rolling_dollar_vol_20 IS NOT NULL THEN 1 ELSE 0 END) as non_null_count
        FROM ohlcv_cache
    ''')
    
    stats = cursor.fetchone()
    logger.info(f"Total rows: {stats[0]:,}")
    logger.info(f"Rows with NULL: {stats[1]:,} ({stats[1]/stats[0]*100:.1f}%)")
    logger.info(f"Rows with value: {stats[2]:,} ({stats[2]/stats[0]*100:.1f}%)")
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("✅ COMPLETED!")
    logger.info("="*60)
    logger.info(f"Tickers processed: {tickers_updated}/{len(tickers)}")
    logger.info(f"Total rows updated: {total_updated:,}")
    
    # Show ticker count impact
    logger.info("\n" + "="*60)
    logger.info("Universe Impact Check")
    logger.info("="*60)
    
    cursor = conn.execute("""
        SELECT COUNT(DISTINCT ticker) as ticker_count
        FROM ohlcv_cache
        WHERE rolling_dollar_vol_20 IS NOT NULL
    """)
    
    ticker_count = cursor.fetchone()[0]
    logger.info(f"Tickers with rolling_dollar_vol_20: {ticker_count}")
    logger.info(f"Expected to fix universe from 53 → ~5000+ tickers")
    
    conn.close()

if __name__ == "__main__":
    main()
