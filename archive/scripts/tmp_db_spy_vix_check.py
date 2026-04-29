import sqlite3
con = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
cur = con.cursor()
checks = [
    ("SPY count", "select count(*) from ohlcv_cache where ticker='SPY'"),
    ("^VIX count", "select count(*) from ohlcv_cache where ticker='^VIX'"),
    ("VIXY count", "select count(*) from ohlcv_cache where ticker='VIXY'"),
    ("SPY sample", "select date, close from ohlcv_cache where ticker='SPY' order by date desc limit 5"),
    ("VIX sample", "select date, close from ohlcv_cache where ticker='^VIX' order by date desc limit 5"),
]
for name, q in checks:
    print(f'\\n-- {name} --')
    try:
        rows = cur.execute(q).fetchall()
        print(rows[:10])
    except Exception as e:
        print('ERROR:', e)

print('\\n-- integrity_check --')
try:
    rows = cur.execute('PRAGMA integrity_check').fetchmany(10)
    print(rows)
except Exception as e:
    print('ERROR:', e)

con.close()
