import pandas as pd
df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
print('rows:', len(df), '| passed:', df['passed'].sum(), '| tickers:', df['ticker'].nunique(), '| dates:', df['date'].nunique())
print('date range:', df['date'].min(), '->', df['date'].max())
rts_fail = df[df['reason'].str.startswith('RTS:', na=False)]
import re
def parse_rts(r):
    m = re.search(r'RTS:\s*([0-9.]+)', str(r))
    return float(m.group(1)) if m else None
rts_fail = rts_fail.copy()
rts_fail['rv'] = rts_fail['reason'].map(parse_rts)
valid = rts_fail['rv'].dropna()
print('RTS fails:', len(valid), '| all_50:', (valid==50).sum(), '| real_values:', (valid!=50).sum())
if len(valid) > 0:
    print('RTS quantiles:', valid.quantile([.1,.25,.5,.75,.9]).to_dict())
