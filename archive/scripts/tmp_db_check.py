import sqlite3
from pathlib import Path
p = Path('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
con = sqlite3.connect(p)
cur = con.cursor()
queries = [
    "select count(*) from ohlcv_cache",
    "select min(date), max(date) from ohlcv_cache",
    "select count(*) from ohlcv_cache where ticker='SPY'",
    "select count(*) from ohlcv_cache where ticker='^VIX'",
    "select count(*) from ohlcv_cache where ticker='VIXY'",
    "select ticker, count(*) c, min(date), max(date) from ohlcv_cache where upper(ticker) like '%SPY%' group by ticker order by c desc limit 20",
    "select ticker, count(*) c, min(date), max(date) from ohlcv_cache where upper(ticker) like '%VIX%' group by ticker order by c desc limit 20",
]
for q in queries:
    print('\nQ:', q)
    rows = cur.execute(q).fetchall()
    for r in rows:
        print(r)
con.close()
