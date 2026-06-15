import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = "data/ticker_cache.db"
conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT date, open, high, low, close FROM ohlcv_cache WHERE ticker='TSLA' AND date >= '2024-12-20'", conn)
print(df)
conn.close()
