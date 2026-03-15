import subprocess, sys
files = [
    '/home/marcos/trade/momentum-v2/src/backtest/vectorbt_engine_advanced.py',
    '/home/marcos/trade/momentum-v2/optimize_3tier.py',
    '/home/marcos/trade/momentum-v2/src/validation/research_gate.py',
]
keywords = ['random', 'shuffle', '.sample(', 'np.random', 'set()', 'dict()', 'os.environ']
print('=== FUENTES DE NO DETERMINISMO ===')
for fpath in files:
    fname = fpath.split('/')[-1]
    with open(fpath) as f: content = f.readlines()
    hits = [(i+1, l.rstrip()) for i,l in enumerate(content)
            if any(k in l for k in keywords) and not l.strip().startswith('#')]
    if hits:
        print(f'\\n{fname}:')
        for lineno, line in hits[:15]: print(f'  {lineno}: {line}')
print('\\n=== BASELINE TRADE COUNT (2 runs rapidos) ===')
print('Chequeando si el universo cambia entre runs...')
import sqlite3
conn = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
rows1 = conn.execute('SELECT DISTINCT ticker FROM ohlcv_cache GROUP BY ticker HAVING COUNT(*)>800 ORDER BY ticker LIMIT 80').fetchall()
print(f'Universo con LIMIT 80: {len(rows1)} tickers -> {rows1[0][0]}..{rows1[-1][0]}')
rows2 = conn.execute('SELECT DISTINCT ticker FROM ohlcv_cache WHERE ticker IN (SELECT ticker FROM ohlcv_cache GROUP BY ticker HAVING COUNT(*)>800) ORDER BY ticker').fetchall()
print(f'Universo completo >800 dias: {len(rows2)} tickers')
conn.close()
