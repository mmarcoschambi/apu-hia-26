import json
m = json.load(open('data/screener_cache/triad_rts.meta.json'))
print('tickers:', len(m['tickers']), m['tickers'][:5])
print('range:', m['start_date'], '->', m['end_date'])
print()
# Show what rebuild_screener_cache.py is doing now
src = open('rebuild_screener_cache.py').read()
idx = src.find('def get_universe_and_dates')
print('--- get_universe_and_dates ---')
print(src[idx:idx+600])
print()
idx2 = src.find('tickers, start_date, end_date = get_universe')
print('--- call site ---')
print(src[idx2:idx2+120])
