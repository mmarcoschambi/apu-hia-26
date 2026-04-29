import sqlite3, pandas as pd

df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
conn = sqlite3.connect('data/ticker_cache.db')

# Rango parquet vs triad_rankings para KLAC
klac_df = df[df['ticker']=='KLAC'].copy()
klac_dates = sorted([str(d)[:10] for d in klac_df['date'].tolist()])
print('KLAC parquet dates:', klac_dates[0], '->', klac_dates[-1], '| total:', len(klac_dates))

triad_range = conn.execute('SELECT MIN(date),MAX(date),COUNT(*) FROM daily_triad_rankings WHERE ticker=?', ('KLAC',)).fetchone()
print('KLAC triad_rankings:', triad_range)

# Cuantas fechas del parquet KLAC coinciden con triad_rankings?
klac_rts_fails = klac_df[klac_df['reason'].str.startswith('RTS:',na=False)]
fail_dates = [str(d)[:10] for d in klac_rts_fails['date'].tolist()][:10]
print('Sample RTS fail dates:')
for d in fail_dates:
    r = conn.execute('SELECT rts_pct FROM daily_triad_rankings WHERE ticker=? AND date=?', ('KLAC',d)).fetchone()
    print(f'  {d}: triad={r}')

# Overall coverage check para los 51 tickers cubiertos
covered = ['AMAT','AMD','AMZN','AVGO','BKNG','CDNS','COST','CSCO','FTNT','INTC','INTU','KLAC','LRCX','MAR','MELI','META','MSFT','MU','NFLX','NVDA','PANW','PCAR','PYPL','QCOM','SNPS','SPY','TSLA','TXN','VRTX']
print()
for t in covered[:10]:
    tdf = df[df['ticker']==t]
    pdates = [str(d)[:10] for d in tdf['date'].tolist()]
    if not pdates:
        continue
    found = conn.execute('SELECT COUNT(*) FROM daily_triad_rankings WHERE ticker=? AND date>=? AND date<=?', (t,pdates[0],pdates[-1])).fetchone()[0]
    total = len(pdates)
    print(f'{t}: parquet={total} dates, triad_coverage={found} ({found/total*100:.0f}%)')

conn.close()
