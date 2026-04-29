import sqlite3, pandas as pd, re, sys
sys.path.insert(0, '/home/marcos/trade/momentum-v2')
df = pd.read_parquet('/home/marcos/trade/momentum-v2/data/screener_cache/triad_rts.parquet')
conn = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
covered_tickers = set(r[0] for r in conn.execute('SELECT DISTINCT ticker FROM daily_triad_rankings').fetchall())
rts_fail = df[df['reason'].str.startswith('RTS:', na=False)].copy()
import re
def parse_rts(r):
    m = re.search(r'RTS:\s*([0-9.]+)', str(r))
    return float(m.group(1)) if m else None
rts_fail['rv'] = rts_fail['reason'].map(parse_rts)
rv50_covered = rts_fail[(rts_fail['rv'] == 50.0) & (rts_fail['ticker'].isin(covered_tickers))]
print('rv=50 rows de tickers cubiertos:', len(rv50_covered))
genuine_50 = 0
no_data = 0
other = 0
for _, row in rv50_covered.head(100).iterrows():
    d = str(row['date'])[:10]
    t = row['ticker']
    r = conn.execute('SELECT rts_pct FROM daily_triad_rankings WHERE ticker=? AND date=?', (t, d)).fetchone()
    if r is None:
        no_data += 1
    elif abs(r[0] - 50.0) < 0.5:
        genuine_50 += 1
    else:
        other += 1
        print('DISCREPANCY', t, d, 'rv=50 but db_rts=', round(r[0],1))
print('Sample 100 -> genuine_50:', genuine_50, 'no_data:', no_data, 'discrepancies:', other)
rts_vals = []
for _, row in rts_fail[rts_fail['ticker'].isin(covered_tickers)].iterrows():
    d = str(row['date'])[:10]
    r = conn.execute('SELECT rts_pct FROM daily_triad_rankings WHERE ticker=? AND date=?', (row['ticker'], d)).fetchone()
    if r:
        rts_vals.append(r[0])
s = pd.Series(rts_vals)
print('N=', len(s))
print(s.describe().to_string())
print('Histogram bins 10:')
print(pd.cut(s, bins=list(range(0,101,10))).value_counts().sort_index().to_string())
conn.close()
