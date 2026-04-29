import json
m = json.load(open('data/screener_cache/triad_rts.meta.json'))
print('meta tickers:', len(m['tickers']), '| rows:', m['rows'], '| range:', m['start_date'], '->', m['end_date'])
