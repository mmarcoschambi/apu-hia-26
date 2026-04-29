import pandas as pd, sqlite3
df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
print('Parquet date range:', df['date'].min(), '->', df['date'].max())
klac = df[df['ticker']=='KLAC']
print('KLAC range:', klac['date'].min(), '->', klac['date'].max())
rts_fail = df[df['reason'].str.startswith('RTS:', na=False)]
print('RTS fail date range:', rts_fail['date'].min(), '->', rts_fail['date'].max())
conn = sqlite3.connect('data/ticker_cache.db')
r = conn.execute('SELECT MIN(date),MAX(date) FROM daily_triad_rankings WHERE ticker=?', ('KLAC',)).fetchone()
print('KLAC in daily_triad_rankings:', r)
rv50_fail = rts_fail[rts_fail['reason']=='RTS: 50 < 70.0']
print('RTS fail rv=50 date range:', rv50_fail['date'].min(), '->', rv50_fail['date'].max())
sample_dates = rv50_fail[rv50_fail['ticker']=='KLAC']['date'].head(5).tolist()
print('KLAC rv=50 sample dates:', [str(d)[:10] for d in sample_dates])
for d in [str(x)[:10] for x in sample_dates]:
    r2 = conn.execute('SELECT rts_pct FROM daily_triad_rankings WHERE ticker=? AND date=?', ('KLAC', d)).fetchone()
    print(' ', d, '->', r2)
conn.close()
