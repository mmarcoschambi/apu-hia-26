import sqlite3, pandas as pd

TICKERS = ['AAL','AAPL','ABBV','ABNB','ABT','ACN','ADBE','ADI','ADP','ADSK',
           'AEE','AMAT','AMD','AMZN','AVGO','BKNG','CDNS','COST','CSCO','FTNT',
           'INTC','INTU','KLAC','LRCX','MAR','MELI','META','MSFT','MU','NFLX',
           'NVDA','PANW','PYPL','QCOM','SNPS','SPY','TSLA','TXN','VRTX']

conn = sqlite3.connect('data/ticker_cache.db')

# Coverage por año en daily_triad_rankings
years = [2019, 2020, 2021, 2022, 2023, 2024]
print('Coverage de daily_triad_rankings por año (tickers con datos):')
print(f'  {
