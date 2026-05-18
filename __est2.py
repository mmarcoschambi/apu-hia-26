import sqlite3
conn = sqlite3.connect("data/ticker_cache.db")
r  = conn.execute("SELECT COUNT(DISTINCT ticker), COUNT(*) FROM ohlcv_cache WHERE sma20 IS NULL").fetchone()
r2 = conn.execute("SELECT COUNT(DISTINCT ticker), COUNT(*) FROM ohlcv_cache").fetchone()
print("Total:", r2[0], "tickers", r2[1], "filas")
print("sma20 NULL:", r[0], "tickers", r[1], "filas")
conn.close()
