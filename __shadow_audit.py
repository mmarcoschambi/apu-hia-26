import sqlite3, pandas as pd, json

conn = sqlite3.connect("/home/marcos/trade/momentum-v2/data/ticker_cache.db")

# Sector cohort ultimo dia con datos
sc = conn.execute("""
    SELECT date, sector_etf, ticker_count, score_mean,
           score_delta_5d, rank_today, rank_delta,
           near_breakout_n, new_entrants, dropped
    FROM sector_cohort
    WHERE date = (SELECT MAX(date) FROM sector_cohort)
    ORDER BY COALESCE(score_delta_5d,0) DESC
""").fetchall()
print(f"=== SECTOR COHORT — {sc[0][0] if sc else 'sin datos'} ===")
print(f"{'Sector':<8} {'N':>4} {'Score':>7} {'Delta5d':>8} {'Rank':>5} {'RDelta':>7} {'Near':>6} {'New':>20} {'Drop':>20}")
for r in sc:
    new_raw = r[8] or "[]"
    drop_raw = r[9] or "[]"
    try: new_t = ",".join(json.loads(new_raw)[:3])
    except: new_t = str(new_raw)[:18]
    try: drop_t = ",".join(json.loads(drop_raw)[:3])
    except: drop_t = str(drop_raw)[:18]
    delta = f"+{r[4]:.1f}" if r[4] and r[4]>0 else f"{r[4]:.1f}" if r[4] else "n/a"
    rdelta = f"+{r[6]}" if r[6] and r[6]>0 else f"{r[6]}" if r[6] else "n/a"
    print(f"  {r[1]:<6} {r[2]:>4} {r[3]:>7.1f} {delta:>8} {str(r[5]):>5} {rdelta:>7} {str(r[7]):>6}  {new_t:<20} {drop_t:<20}")

# Candidate state: candidatos near_breakout con mas dias de age
print(f"\n=== CANDIDATOS NEAR BREAKOUT — setup aging ===")
cs = conn.execute("""
    SELECT date, ticker, score, rank_universe, dist_sma20_pct,
           near_breakout, setup_age, status, sector_etf, pivot_dist_pct
    FROM candidate_state
    WHERE date = (SELECT MAX(date) FROM candidate_state)
      AND near_breakout = 1
    ORDER BY setup_age DESC, score DESC
    LIMIT 15
""").fetchall()
print(f"{'Ticker':<8} {'Score':>6} {'Rank':>5} {'Dist20%':>8} {'Age':>5} {'Status':<12} {'Sector':<8} {'PivDist%':>9}")
for r in cs:
    print(f"  {r[1]:<6} {r[2]:>6.1f} {r[3]:>5} {r[4]:>8.1f} {r[6]:>5} {r[7]:<12} {r[8]:<8} {str(r[9])[:8]:>9}")

# Señal de rotacion: sectores con rank_delta fuerte
print(f"\n=== SEÑAL ROTACION — rank_delta extremos (ultimos 5 dias) ===")
rot = conn.execute("""
    SELECT date, sector_etf, rank_today, rank_delta, score_mean, score_delta_5d
    FROM sector_cohort
    WHERE date >= DATE((SELECT MAX(date) FROM sector_cohort), '-7 days')
      AND ABS(COALESCE(rank_delta,0)) >= 2
    ORDER BY date DESC, ABS(COALESCE(rank_delta,0)) DESC
    LIMIT 20
""").fetchall()
if rot:
    for r in rot:
        arrow = "↑" if r[3] and r[3]>0 else "↓"
        print(f"  {r[0]} {r[1]:<6} rank={r[2]} {arrow}{abs(r[3]) if r[3] else 0} score={r[4]:.1f} delta={r[5]:.1f if r[5] else 'n/a'}")
else:
    print("  Sin movimientos de rank >= 2 en últimos 7 días")

conn.close()
