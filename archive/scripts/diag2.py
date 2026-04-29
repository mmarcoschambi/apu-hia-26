import sqlite3, pandas as pd

df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
parquet_tickers = set(df['ticker'].unique())
print('Tickers en parquet actual:', len(parquet_tickers))

conn = sqlite3.connect('data/ticker_cache.db')
db_tickers = set(r[0] for r in conn.execute('SELECT DISTINCT ticker FROM daily_triad_rankings').fetchall())

covered = parquet_tickers & db_tickers
missing = parquet_tickers - db_tickers
print('Con cobertura en daily_triad_rankings:', len(covered))
print('SIN cobertura (fallback inevitable):', len(missing))
print('Missing tickers:', sorted(missing))

# De los que SI tienen cobertura, cuantos pasan vs fallan RTS?
rts_fail = df[df['reason'].str.startswith('RTS:', na=False)]
rts_fail_covered = rts_fail[rts_fail['ticker'].isin(covered)]
rts_fail_missing = rts_fail[rts_fail['ticker'].isin(missing)]
print()
print('RTS fails de tickers CON cobertura:', len(rts_fail_covered))
print('RTS fails de tickers SIN cobertura:', len(rts_fail_missing))

# Para los cubiertos que fallan RTS, cual es el valor real?
import re
def parse_rts(r):
    m = re.search(r'RTS:\s*([0-9.]+)', str(r))
    return float(m.group(1)) if m else None
rts_fail_covered['rv'] = rts_fail_covered['reason'].map(parse_rts)
print()
print('Distribucion RTS real (tickers cubiertos):')
print(rts_fail_covered['rv'].value_counts().sort_index().to_string())

conn.close()
