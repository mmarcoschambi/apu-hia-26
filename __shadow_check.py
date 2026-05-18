import json, sqlite3, pandas as pd

# 1. Leer radar rotation mas reciente
with open("/home/marcos/trade/momentum-v2/outputs/telegram_monitor/2026-05-08/radar_rotation.json") as f:
    radar = json.load(f)

print("=== RADAR 2026-05-08 ===")
print(json.dumps(radar, indent=2)[:3000])

# 2. Estado de candidate_state
conn = sqlite3.connect("/home/marcos/trade/momentum-v2/data/ticker_cache.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\n=== Tablas en DB: {[t[0] for t in tables]}")

if any(t[0] == "candidate_state" for t in tables):
    r = conn.execute("SELECT MIN(date),MAX(date),COUNT(DISTINCT date),COUNT(*) FROM candidate_state").fetchone()
    print(f"candidate_state: {r[0]} -> {r[1]} | {r[2]} días | {r[3]} filas")
    sample = conn.execute("""
        SELECT date, ticker, score, rank_universe, dist_sma20_pct,
               near_breakout, setup_age, status, sector_etf
        FROM candidate_state ORDER BY date DESC, rank_universe LIMIT 10
    """).fetchall()
    print("\nTop 10 candidatos más recientes:")
    for row in sample:
        print(f"  {row[0]} {row[1]:<8} score={row[2]:.1f} rank={row[3]} dist={row[4]:.1f}% near={row[5]} age={row[6]} {row[7]} {row[8]}")

if any(t[0] == "sector_cohort" for t in tables):
    r2 = conn.execute("SELECT MIN(date),MAX(date),COUNT(DISTINCT date) FROM sector_cohort").fetchone()
    print(f"\nsector_cohort: {r2[0]} -> {r2[1]} | {r2[2]} días")
    sc = conn.execute("""
        SELECT date, sector_etf, ticker_count, score_mean, score_delta_5d, rank_today, rank_delta
        FROM sector_cohort WHERE date = (SELECT MAX(date) FROM sector_cohort)
        ORDER BY score_mean DESC
    """).fetchall()
    print("\nSector cohort último día:")
    for row in sc:
        delta = f"+{row[4]:.1f}" if row[4] and row[4] > 0 else f"{row[4]:.1f}" if row[4] else "n/a"
        rdelta = f"+{row[6]}" if row[6] and row[6] > 0 else f"{row[6]}" if row[6] else "n/a"
        print(f"  {row[0]} {row[1]:<6} n={row[2]:>3} score={row[3]:.1f} delta5d={delta} rank={row[4]} rdelta={rdelta}")

conn.close()
