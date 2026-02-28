
import sqlite3
import pandas as pd
from pathlib import Path

def check_ticker(ticker):
    db_path = "data/ticker_cache.db"
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    
    # Check universe entry
    print(f"--- Checking Universe for {ticker} ---")
    cursor = conn.execute("SELECT * FROM universe WHERE ticker = ?", (ticker,))
    universe_row = cursor.fetchone()
    if universe_row:
        print(f"Found in universe: {universe_row}")
    else:
        print(f"NOT found in universe table.")

    # Check OHLCV data
    print(f"\n--- Checking OHLCV Data for {ticker} ---")
    query = "SELECT COUNT(*) FROM ohlcv_cache WHERE ticker = ?"
    count = conn.execute(query, (ticker,)).fetchone()[0]
    print(f"Total rows in cache: {count}")

    if count > 0:
        print("\nFirst 5 days of data (Start):")
        df_start = pd.read_sql_query(f"SELECT * FROM ohlcv_cache WHERE ticker = '{ticker}' ORDER BY date ASC LIMIT 5", conn)
        print(df_start)

        print("\nLast 5 days of data (End):")
        df_end = pd.read_sql_query(f"SELECT * FROM ohlcv_cache WHERE ticker = '{ticker}' ORDER BY date DESC LIMIT 5", conn)
        print(df_end)
    
    conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', type=str, required=True)
    parser.add_argument('--start', type=str, default=None)
    parser.add_argument('--end', type=str, default=None)
    args = parser.parse_args()
    
    check_ticker(args.ticker)
