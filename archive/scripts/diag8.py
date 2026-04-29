import sqlite3, pandas as pd

df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
conn = sqlite3.connect('data/ticker_cache.db')

results = []
for t in df['ticker'].unique():
    tdf = df[df['ticker']==t]
    dates = [str(d)[:10] for d in tdf['date'].tolist()]
    if not dates:
        continue
    found = conn.execute('SELECT COUNT(*) FROM daily_triad_rankings WHERE ticker=? AND date>=? AND date<=?', (t, dates[0], dates[-1])).fetchone()[0]
    total = len(dates)
    coverage_pct = found / total * 100
    results.append({'ticker': t, 'parquet_dates': total, 'triad_dates': found, 'coverage_pct': round(coverage_pct, 1)})

conn.close()
res = pd.DataFrame(results).sort_values('coverage_pct', ascending=False)
print('Coverage distribution:')
print(pd.cut(res['coverage_pct'], bins=[0,1,25,75,99,100], include_lowest=True).value_counts().sort_index().to_string())
print()
print('0% coverage (no data at all):', (res['coverage_pct'] == 0).sum(), 'tickers')
print('>=90% coverage:', (res['coverage_pct'] >= 90).sum(), 'tickers')
print()
print('Tickers con 0% coverage (no estan en daily_triad_rankings):')
zero = res[res['coverage_pct'] == 0]
print(zero['ticker'].tolist()[:40])
print('...(', len(zero), 'total)')
print()
print('Tickers con coverage parcial (1-99%):')
partial = res[(res['coverage_pct'] > 0) & (res['coverage_pct'] < 99)]
print(partial[['ticker','parquet_dates','triad_dates','coverage_pct']].to_string())
