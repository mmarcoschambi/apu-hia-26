#!/usr/bin/env python3
"""
Add Historical Metrics Columns to ohlcv_cache
----------------------------------------------
Adds pre-calculated metrics to avoid recalculating on every backtest:
- adr_14: Average Daily Range (14 days) in $
- adr_pct_14: Average Daily Range (14 days) in %
- sma_50: Simple Moving Average 50 days
- sma_200: Simple Moving Average 200 days
- price_above_sma50: Boolean
- price_above_sma200: Boolean
- sma50_above_sma200: Boolean (trend alignment)
"""

import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def add_metrics_columns(db_path):
    """Add new columns for historical metrics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(ohlcv_cache)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    new_columns = {
        'adr_14': 'REAL',           # Average Daily Range (14d) in dollars
        'adr_pct_14': 'REAL',       # Average Daily Range (14d) in %
        'sma_50': 'REAL',           # SMA 50
        'sma_200': 'REAL',          # SMA 200
        'price_above_sma50': 'INTEGER',    # Boolean: 1/0
        'price_above_sma200': 'INTEGER',   # Boolean: 1/0
        'sma50_above_sma200': 'INTEGER',   # Boolean: 1/0
        'trend_aligned': 'INTEGER'         # Boolean: price > sma50 > sma200
    }
    
    print("🔧 Adding historical metrics columns to ohlcv_cache...")
    
    for col_name, col_type in new_columns.items():
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE ohlcv_cache ADD COLUMN {col_name} {col_type}")
                print(f"  ✅ Added column: {col_name} ({col_type})")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    print(f"  ⚠️  Column {col_name} already exists")
                else:
                    raise
        else:
            print(f"  ⏭️  Column {col_name} already exists")
    
    conn.commit()
    conn.close()
    print("✅ Schema updated successfully!")

if __name__ == "__main__":
    db_path = Path(__file__).resolve().parent.parent / "data" / "ticker_cache.db"
    add_metrics_columns(db_path)
