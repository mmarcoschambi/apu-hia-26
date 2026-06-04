import sys, logging, time
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
sys.path.insert(0, ".")
import sqlite3

conn = sqlite3.connect("data/ticker_cache.db")
last_date = conn.execute("SELECT MAX(date) FROM daily_rs_rankings").fetchone()[0]
conn.close()
print(f"Procesando: {last_date}")

t0 = time.time()
from src.data.candidate_tracker import CandidateTracker
tracker = CandidateTracker()
tracker.populate_day(last_date)
elapsed = time.time() - t0
print(f"Tiempo: {elapsed:.1f}s")

conn = sqlite3.connect("data/ticker_cache.db")
r = conn.execute(f"""
    SELECT
        COUNT(*) total,
        SUM(CASE WHEN sma20 IS NOT NULL THEN 1 ELSE 0 END) sma20_ok,
        SUM(CASE WHEN rvol IS NOT NULL THEN 1 ELSE 0 END) rvol_ok,
        SUM(CASE WHEN ma_stack IS NOT NULL THEN 1 ELSE 0 END) ma_ok,
        SUM(CASE WHEN near_breakout = 1 THEN 1 ELSE 0 END) near_n,
        SUM(CASE WHEN status = 'NEAR' THEN 1 ELSE 0 END) near_status
    FROM candidate_state WHERE date = '{last_date}'
""").fetchone()
print(f"\nResumen {last_date}:")
print(f"  Total: {r[0]}  sma20_ok: {r[1]}  rvol_ok: {r[2]}  ma_ok: {r[3]}  near_bo: {r[4]}  NEAR_status: {r[5]}")

sample = conn.execute(f"""
    SELECT ticker, close, sma20, dist_sma20_pct, rvol, ma_stack,
           near_breakout, status, breakout_level, breakout_gap
    FROM candidate_state
    WHERE date = '{last_date}' AND near_breakout = 1
    ORDER BY rs_composite DESC NULLS LAST LIMIT 8
""").fetchall()
conn.close()

print(f"\nCandidatos NEAR BREAKOUT:")
print(f"  {'Ticker':<8} {'Close':>8} {'SMA20':>8} {'Dist%':>7} {'RVOL':>6} {'MA':>3} {'BO_level':>10} {'Gap%':>7}")
for row in sample:
    d = f"{row[9]:.2f}" if row[9] is not None else "n/a"
    r2 = f"{row[4]:.2f}" if row[4] is not None else "n/a"
    print(f"  {row[0]:<6} {row[1]:>8.2f} {str(row[2])[:7]:>8} {str(row[3])[:6]:>7} {r2:>6} {str(row[5]):>3} {str(row[8])[:9]:>10} {d:>7}")
