import sqlite3, pandas as pd

DB = "/home/marcos/trade/momentum-v2/data/ticker_cache.db"
conn = sqlite3.connect(DB)

c1 = conn.execute("SELECT COUNT(DISTINCT ticker) FROM daily_rs_rankings WHERE date LIKE '2024%'").fetchone()[0]
c2 = conn.execute("SELECT COUNT(DISTINCT date) FROM daily_rs_rankings WHERE date LIKE '2024%'").fetchone()[0]
c3 = conn.execute("SELECT COUNT(*) FROM daily_rs_rankings WHERE date = '2024-03-15'").fetchone()[0]
c4 = conn.execute("SELECT COUNT(*) FROM daily_rs_rankings WHERE date LIKE '2024-03-15%'").fetchone()[0]
c5 = conn.execute("SELECT date FROM daily_rs_rankings ORDER BY date DESC LIMIT 1").fetchone()
c6 = conn.execute("SELECT date FROM daily_rs_rankings ORDER BY date ASC LIMIT 1").fetchone()

print("Tickers con RS en 2024:", c1)
print("Dias con RS en 2024:", c2)
print("Entries exacto 2024-03-15:", c3)
print("Entries LIKE 2024-03-15%:", c4)
print("Fecha mas reciente en RS:", c5)
print("Fecha mas antigua en RS:", c6)

# formato de fechas en la tabla
sample = conn.execute("SELECT date FROM daily_rs_rankings LIMIT 5").fetchall()
print("Sample dates:", sample)

# cuantos tickers del PIT superset tienen RS para una fecha
pit_check = pd.read_sql(
    "SELECT COUNT(DISTINCT ticker) as n FROM daily_rs_rankings WHERE date BETWEEN '2023-01-01' AND '2024-12-31'",
    conn
)
print("Tickers con RS en rango 2023-2024:", pit_check.iloc[0,0])

conn.close()
