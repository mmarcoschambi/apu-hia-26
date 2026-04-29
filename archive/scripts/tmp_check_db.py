import sqlite3
con = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
cur = con.cursor()
queries = [
    "select count(*) from ohlcv_cache where ticker='SPY'",
    "select count(*) from ohlcv_cache where ticker='^VIX'",
    "select min(date), max(date) from ohlcv_cache where ticker='SPY'",
    "select min(date), max(date) from ohlcv_cache where ticker='^VIX'",
]
for q in queries:
    try:
        print(q, cur.execute(q).fetchone())
    except Exception as e:
        print(q, 'ERR', e)
try:
    print('integrity', cur.execute('PRAGMA integrity_check').fetchmany(5))
except Exception as e:
    print('integrity ERR', e)
con.close()
