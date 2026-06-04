import sqlite3
conn = sqlite3.connect("/home/marcos/trade/momentum-v2/data/ticker_cache.db")
r = conn.execute("""
    SELECT
        COUNT(DISTINCT ticker) tickers_null,
        COUNT(*) rows_null
    FROM ohlcv_cache WHERE sma20 IS NULL
""").fetchone()
r2 = conn.execute("SELECT COUNT(DISTINCT ticker), COUNT(*) FROM ohlcv_cache").fetchone()
print(f"Total: {r2[0]:,} tickers, {r2[1]:,} filas")
print(f"Con sma20 NULL: {r[0]:,} tickers, {r[1]:,} filas")
print(f"Estimado incremental (60d): ", end="")
r3 = conn.execute("""
    SELECT COUNT(DISTINCT ticker), COUNT(*)
    FROM ohlcv_cache
    WHERE date >= DATE('now','-60 days') AND sma20 IS NULL
""").fetchone()
print(f"{r3[0]:,} tickers, {r3[1]:,} filas")
conn.close()
