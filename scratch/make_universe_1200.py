import sqlite3
from pathlib import Path

db_path = Path("data/ticker_cache.db")
out_path = Path("data/universe_1200.txt")

conn = sqlite3.connect(db_path)
query = """
    SELECT ticker
    FROM ohlcv_cache
    WHERE ticker NOT LIKE '%-%' AND ticker NOT LIKE '%.%'
    GROUP BY ticker
    HAVING MAX(date) >= '2026-06-01'
    ORDER BY ticker
"""
rows = conn.execute(query).fetchall()
conn.close()

with open(out_path, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(r[0] + "\n")

print(f"[OK] Generado {out_path} con {len(rows)} tickers (Junio + Julio 2026).")
