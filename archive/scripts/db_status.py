import sqlite3
conn = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
rows = conn.execute("""
    SELECT
        SUM(CASE WHEN last_date >= '2026-01-01' THEN 1 ELSE 0 END) as current_2026,
        SUM(CASE WHEN last_date >= '2025-01-01' AND last_date < '2026-01-01' THEN 1 ELSE 0 END) as only_2025,
        SUM(CASE WHEN last_date < '2025-01-01' THEN 1 ELSE 0 END) as stale_pre2025
    FROM (SELECT ticker, MAX(date) as last_date FROM ohlcv_cache GROUP BY ticker)
""").fetchone()
print('Up to 2026:', rows[0])
print('Only 2025 :', rows[1])
print('Pre-2025  :', rows[2])
stale = conn.execute("""
    SELECT ticker, MAX(date) FROM ohlcv_cache
    GROUP BY ticker HAVING MAX(date) < '2025-01-01'
    ORDER BY MAX(date) LIMIT 10
""").fetchall()
print('Sample stale:')
for x in stale: print(' ', x[0], x[1])