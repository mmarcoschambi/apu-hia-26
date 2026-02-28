
import yfinance as yf
import pandas as pd
import sqlite3
from pathlib import Path

symbol = "AAP"
target_date = "2018-07-18"

print(f"Fetching data for {symbol} around {target_date}...")
ticker = yf.Ticker(symbol)

# 1. Fetch from Yahoo Finance (Fresh Data)
# Get a window around the date
start_date = "2018-07-10"
end_date = "2018-07-25"

df = ticker.history(start=start_date, end=end_date, auto_adjust=False)
df_adj = ticker.history(start=start_date, end=end_date, auto_adjust=True)

print("\n--- Yahoo Finance Data (Unadjusted) ---")
print(df.loc[target_date:target_date][['Open', 'High', 'Low', 'Close', 'Volume']])

print("\n--- Yahoo Finance Data (Adjusted) ---")
print(df_adj.loc[target_date:target_date][['Open', 'High', 'Low', 'Close', 'Volume']])

# 2. Check Local Cache (PKL)
pkl_path = Path(f"data/cache/{symbol}.pkl")
print(f"\n--- Checking Local Cache ({pkl_path}) ---")
if pkl_path.exists():
    try:
        import pickle
        with open(pkl_path, "rb") as f:
            cached_df = pickle.load(f)
        
        # Ensure index is datetime
        if not isinstance(cached_df.index, pd.DatetimeIndex):
            cached_df.index = pd.to_datetime(cached_df.index)
            
        if target_date in cached_df.index:
            print(cached_df.loc[target_date][['Open', 'High', 'Low', 'Close', 'Volume']])
        else:
            print(f"Date {target_date} not found in cache.")
    except Exception as e:
        print(f"Error reading pickle: {e}")
else:
    print("Cache file not found.")

# 3. Check Local Cache (SQL)
db_path = Path("data/ticker_cache.db")
print(f"\n--- Checking Local SQL Cache ---")
try:
    conn = sqlite3.connect(db_path)
    query = f"SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker = '{symbol}' AND date = '{target_date}'"
    df_sql = pd.read_sql_query(query, conn)
    print(df_sql)
    conn.close()
except Exception as e:
    print(f"SQLite Error: {e}")
