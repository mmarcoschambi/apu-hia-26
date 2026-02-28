
import pickle
import pandas as pd
import sqlite3
from pathlib import Path

# Paths
pkl_path_1 = Path("data/cache/ATLO.pkl")
pkl_path_2 = Path("data/cache/ATLO_daily.pkl")
db_path = Path("data/ticker_cache.db")

target_dates = ["2022-01-07", "2022-01-25"]

print(f"--- Inspecting Pickles ---")
for p in [pkl_path_1, pkl_path_2]:
    if p.exists():
        print(f"\nFile: {p}")
        try:
            with open(p, "rb") as f:
                df = pickle.load(f)
                
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            
            # Filter for dates
            print(df.loc[df.index.isin(pd.to_datetime(target_dates))][['Open', 'High', 'Low', 'Close', 'Volume']])
        except Exception as e:
            print(f"Error reading {p}: {e}")
    else:
        print(f"File not found: {p}")

print(f"\n--- Inspecting SQLite ---")
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Table: ohlcv_cache (checking existence)")
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ohlcv_cache';")
    if cursor.fetchone():
        query = f"""
            SELECT date, open, high, low, close, volume 
            FROM ohlcv_cache 
            WHERE ticker = 'ATLO' 
            AND date IN ('2022-01-07', '2022-01-25')
        """
        df_sql = pd.read_sql_query(query, conn)
        print(df_sql)
    else:
        print("Table 'ohlcv_cache' does not exist.")
        
    conn.close()
except Exception as e:
    print(f"SQLite Error: {e}")
