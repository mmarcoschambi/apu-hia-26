import yfinance as yf
import sqlite3
import pandas as pd
from src.data.theme_taxonomy import THEME_MAP
from pathlib import Path

DB_PATH = Path("data/ticker_cache.db")
conn = sqlite3.connect(DB_PATH)

start, end = "2018-01-01", "2020-12-31"
tickers = list(THEME_MAP.keys())

# Filter only missing ones for 2019
missing = []
for t in tickers:
    c = conn.execute('SELECT COUNT(*) FROM ohlcv_cache WHERE ticker=? AND date >= \"2019-01-01\" AND date <= \"2019-12-31\"', (t,)).fetchone()[0]
    if c == 0: missing.append(t)

print(f"Missing {len(missing)} theme tickers for 2019-2020.")
if not missing:
    print("All theme tickers exist!")
else:
    for i in range(0, len(missing), 50):
        chunk = missing[i:i+50]
        print(f"Downloading chunk {i//50 + 1}...")
        data = yf.download(chunk, start=start, end=end, progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in chunk:
                try:
                    df = data.xs(ticker, axis=1, level=1).dropna()
                    if df.empty: continue
                    df = df.reset_index()
                    df.columns = [c.lower() for c in df.columns]
                    df = df.rename(columns={'adj close': 'close'})
                    for _, row in df.iterrows():
                        conn.execute("INSERT OR REPLACE INTO ohlcv_cache (ticker, date, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                     (ticker, row['date'].strftime('%Y-%m-%d %H:%M:%S'), row['open'], row['high'], row['low'], row['close'], row['volume']))
                except: pass
            conn.commit()

conn.close()
