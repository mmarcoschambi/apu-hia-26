import sqlite3

con = sqlite3.connect('/home/marcos/trade/momentum-v2/data/ticker_cache.db')
cur = con.cursor()
queries = {
    'db_min_max': "select min(date), max(date) from ohlcv_cache",
    'spy_min_max': "select min(date), max(date), count(*) from ohlcv_cache where ticker='SPY'",
    'vix_min_max': "select min(date), max(date), count(*) from ohlcv_cache where ticker='^VIX'",
    'vixy_min_max': "select min(date), max(date), count(*) from ohlcv_cache where ticker='VIXY'",
    'rows_2024_any': "select count(*) from ohlcv_cache where date between '2024-01-01' and '2024-12-31'",
    'tickers_2024_any': "select count(distinct ticker) from ohlcv_cache where date between '2024-01-01' and '2024-12-31'",
    'top_tickers_2024': "select ticker, count(*) c, min(date), max(date) from ohlcv_cache where date between '2024-01-01' and '2024-12-31' group by ticker order by c desc limit 15",
}
for key, q in queries.items():
    print(f'\n== {key} ==')
    try:
        rows = cur.execute(q).fetchall()
        for r in rows:
            print(r)
    except Exception as e:
        print('ERR', e)
con.close()
