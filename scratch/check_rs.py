"""Check RS rankings table."""
import sqlite3
from pathlib import Path

db = Path("data/ticker_cache.db")
conn = sqlite3.connect(str(db))

tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print("Tables:", tables)

for tbl in tables:
    if "rs" in tbl.lower() or "rank" in tbl.lower():
        cols = [d[1] for d in conn.execute(f"PRAGMA table_info({tbl!r})").fetchall()]
        print(f"\n=== {tbl} ===")
        print(f"  Columns: {cols}")
        rows = conn.execute(f"SELECT * FROM {tbl} LIMIT 5").fetchall()
        print(f"  Sample: {rows}")
        if "date" in cols:
            last = conn.execute(f"SELECT MAX(date) FROM {tbl}").fetchone()
            print(f"  Latest date: {last[0]}")
        count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  Row count: {count}")
        
        # Check AAPL
        if "ticker" in cols:
            aapl = conn.execute(
                f"SELECT * FROM {tbl} WHERE ticker='AAPL' ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if aapl:
                print(f"  AAPL latest: {aapl}")

conn.close()
