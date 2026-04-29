import sys, sqlite3
sys.path.insert(0, '.')
from src.data.triad_rankings import get_triad_metrics
from src.screeners.triad_rts import TriadRTSScreener
from src.data.market_data import MarketDataProvider

# Test directo de get_triad_metrics para fechas que sabemos que existen
r = get_triad_metrics('KLAC', '2024-10-10')
print('get_triad_metrics KLAC 2024-10-10:', r)

# Simular exactamente lo que hace el screener durante el rebuild
mdp = MarketDataProvider()
df = mdp.get_ohlcv('KLAC', '2022-01-01', '2024-12-31', offline=True)
if df is not None and not df.empty:
    print('KLAC data loaded, rows:', len(df))
    hist = df.loc[:df.index[df.index <= '2024-10-10'][-1]]
    screener = TriadRTSScreener()
    import logging
    logging.basicConfig(level=logging.DEBUG)
    result = screener.scan('KLAC', hist, scan_date='2024-10-10')
    print('Result:', result.passed, result.reason)
    print('Metrics rts_pct:', result.metrics.get('rts_pct'))
else:
    print('No KLAC data')
