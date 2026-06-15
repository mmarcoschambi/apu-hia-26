import yfinance as yf
import sqlite3
import pandas as pd
from src.utils.sector_rotation import SECTOR_ETFS
from pathlib import Path

DB_PATH = Path("data/ticker_cache.db")
conn = sqlite3.connect(DB_PATH)

start, end = "2018-01-01", "2020-12-31" # extra lookback for SMAs
tickers = SECTOR_ETFS + ["SPY", "^VIX"]

print(f"Downloading {len(tickers)} tickers for {start} to {end}...")
data = yf.download(tickers, start=start, end=end, progress=False)

if isinstance(data.columns, pd.MultiIndex):
    for ticker in tickers:
        print(f"Processing {ticker}...")
        df = data.xs(ticker, axis=1, level=1).dropna()
        if df.empty: continue
        
        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={'adj close': 'close'})
        
        for _, row in df.iterrows():
            conn.execute("""
                INSERT OR REPLACE INTO ohlcv_cache (ticker, date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ticker, row['date'].strftime('%Y-%m-%d %H:%M:%S'), row['open'], row['high'], row['low'], row['close'], row['volume']))
    conn.commit()
    print("Done!")
conn.close()
