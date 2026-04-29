import sqlite3

TICKERS = ['AAL','AAPL','ABBV','ABNB','ABT','ACN','ADBE','ADI','ADP','ADSK',
           'AEE','AMAT','AMD','AMZN','AVGO','BKNG','CDNS','COST','CSCO','FTNT',
           'INTC','INTU','KLAC','LRCX','MAR','MELI','META','MSFT','MU','NFLX',
           'NVDA','PANW','PYPL','QCOM','SNPS','SPY','TSLA','TXN','VRTX']

conn = sqlite3.connect('data/ticker_cache.db')
print('Year | triad_cov | ohlcv_cov | missing_triad')
for y in [2019,2020,2021,2022,2023,2024]:
    s,e = str(y)+'-01-01', str(y)+'-12-31'
    t_rows = conn.execute('SELECT DISTINCT ticker FROM daily_triad_rankings WHERE date>=? AND date<=?',(s,e)).fetchall()
    t_set = set(r[0] for r in t_rows)
    o_rows = conn.execute('SELECT DISTINCT ticker FROM ohlcv_cache WHERE date>=? AND date<=?',(s,e)).fetchall()
    o_set = set(r[0] for r in o_rows)
    t_cov = len([t for t in TICKERS if t in t_set])
    o_cov = len([t for t in TICKERS if t in o_set])
    miss = [t for t in TICKERS if t not in t_set]
    print(y, '|', t_cov, '/', len(TICKERS), '|', o_cov, '/', len(TICKERS), '| missing:', miss[:6])
conn.close()
