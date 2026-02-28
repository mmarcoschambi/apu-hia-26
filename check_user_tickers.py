import sqlite3
import pandas as pd
from pathlib import Path

# Path to database
base_dir = Path(".").resolve()
db_path = base_dir / "data" / "ticker_cache.db"

tickers_to_check = [
    "APWC", "ARBK", "ARCM", "ARCT", "ARCC", "ARCO", "ARGT", "ARKQ", 
    "ARMK", "ARLP", "ARL", "ARLO", "AROW", "ASC", "ASND", "ASM", 
    "ASRT", "ASYS", "ATHA", "ATKR", "ATLCL", "ATLX", "ATS", "AUPH", 
    "AVDE", "AVBH", "AVDV", "AVIG", "AVSD", "AVSU"
]

print(f"Checking {len(tickers_to_check)} tickers in {db_path}...")

conn = sqlite3.connect(str(db_path))

# Check universe table
print("\n--- Universe Status ---")
placeholders = ','.join(['?'] * len(tickers_to_check))
cursor = conn.execute(f"SELECT ticker, last_updated FROM universe WHERE ticker IN ({placeholders})", tickers_to_check)
universe_data = {row[0]: row[1] for row in cursor.fetchall()}

for t in tickers_to_check:
    status = universe_data.get(t, "NOT IN UNIVERSE")
    print(f"{t}: {status}")

# Check ohlcv counts
print("\n--- OHLCV Counts ---")
cursor = conn.execute(f"SELECT ticker, COUNT(*) as count, MAX(date) as last_date FROM ohlcv_cache WHERE ticker IN ({placeholders}) GROUP BY ticker", tickers_to_check)
ohlcv_data = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

for t in tickers_to_check:
    count, last_date = ohlcv_data.get(t, (0, "N/A"))
    print(f"{t}: {count} records, Last Date: {last_date}")

conn.close()
