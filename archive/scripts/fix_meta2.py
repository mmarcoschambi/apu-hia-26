import json
from pathlib import Path

tickers = ['AAL','AAPL','ABBV','ABNB','ABT','ACN','ADBE','ADI','ADP','ADSK',
           'AEE','AMAT','AMD','AMZN','AVGO','BKNG','CDNS','COST','CSCO','FTNT',
           'INTC','INTU','KLAC','LRCX','MAR','MELI','META','MSFT','MU','NFLX',
           'NVDA','PANW','PYPL','QCOM','SNPS','SPY','TSLA','TXN','VRTX']

meta = {
    'screener_name': 'triad_rts',
    'start_date': '2020-01-01',
    'end_date': '2024-12-31',
    'tickers': tickers,
    'rows': 0
}
p = Path('data/screener_cache/triad_rts.meta.json')
p.write_text(json.dumps(meta, indent=2))
print('Meta updated:', len(tickers), 'tickers | 2020-01-01 -> 2024-12-31')
