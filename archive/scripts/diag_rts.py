import sys, sqlite3
sys.path.insert(0, '/home/marcos/trade/momentum-v2')

# Test 1: get_triad_metrics funciona?
from src.data.triad_rankings import get_triad_metrics
r = get_triad_metrics('KLAC', '2024-06-03')
print('KLAC 2024-06-03:', r)

r2 = get_triad_metrics('KLAC')
print('KLAC latest:', r2)

# Test 2: que fechas tiene KLAC en daily_triad_rankings?
conn = sqlite3.connect('data/ticker_cache.db')
dates = conn.execute('SELECT date, rts_pct, as_5d_pct FROM daily_triad_rankings WHERE ticker=? ORDER BY date DESC LIMIT 5', ('KLAC',)).fetchall()
print('KLAC dates sample:', dates)

# Test 3: el parquet tiene scan_date para KLAC?
import pandas as pd
df = pd.read_parquet('data/screener_cache/triad_rts.parquet')
klac = df[df['ticker']=='KLAC']
print('KLAC parquet rows:', len(klac))
print('KLAC passed:', klac['passed'].sum())
print('Sample reasons:', klac[klac['passed']==True]['reason'].head(3).tolist())
print('KLAC fail reasons:', klac[klac['passed']==False]['reason'].value_counts().head(5).to_string())

# Test 4: cross-check de una fecha donde KLAC paso
if klac['passed'].any():
    passed_row = klac[klac['passed']==True].iloc[0]
    date_str = str(passed_row['date'])[:10]
    print(f'KLAC passed on {date_str}, checking triad_rankings...')
    r3 = get_triad_metrics('KLAC', date_str)
    print('triad_metrics for that date:', r3)

conn.close()
