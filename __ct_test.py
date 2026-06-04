import sys, logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
sys.path.insert(0, ".")

from src.data.candidate_tracker import CandidateTracker
import sqlite3

# Probar sobre el ultimo dia disponible en daily_rs_rankings
conn = sqlite3.connect("data/ticker_cache.db")
last_date = conn.execute("SELECT MAX(date) FROM daily_rs_rankings").fetchone()[0]
conn.close()
print(f"Ultimo dia en daily_rs_rankings: {last_date}")

tracker = CandidateTracker()
tracker.populate_day(last_date)

# Verificar resultados
conn = sqlite3.connect("data/ticker_cache.db")
r = conn.execute(f"""
    SELECT ticker, close, sma20, dist_sma20_pct, rvol, ma_stack,
           near_breakout, status, breakout_level
    FROM candidate_state
    WHERE date = '{last_date}'
      AND sma20 IS NOT NULL
    ORDER BY rs_composite DESC NULLS LAST
    LIMIT 10
""").fetchall()

r2 = conn.execute(f"""
    SELECT
        COUNT(*) total,
        SUM(CASE WHEN sma20 IS NOT NULL THEN 1 ELSE 0 END) sma20_ok,
        SUM(CASE WHEN rvol IS NOT NULL THEN 1 ELSE 0 END) rvol_ok,
        SUM(CASE WHEN near_breakout = 1 THEN 1 ELSE 0 END) near_n
    FROM candidate_state WHERE date = '{last_date}'
""").fetchone()
conn.close()

print(f"\nResumen: total={r2[0]} sma20_ok={r2[1]} rvol_ok={r2[2]} near_breakout={r2[3]}")
print(f"\nTop 10 candidatos con sma20 calculado:")
print(f"{'Ticker':<8} {'Close':>8} {'SMA20':>8} {'Dist%':>7} {'RVOL':>6} {'MA':>3} {'Near':>5} {'Status':<12} {'BO_level':>10}")
for row in r:
    print(f"  {row[0]:<6} {row[1]:>8.2f} {row[2]:>8.2f} {row[3]:>7.2f} {row[4]:>6.2f} {str(row[5]):>3} {str(row[6]):>5} {row[7]:<12} {str(row[8])[:9]:>10}")
