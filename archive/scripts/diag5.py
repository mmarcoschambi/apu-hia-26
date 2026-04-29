import sys
sys.path.insert(0, '.')
from src.data.market_data import MarketDataProvider

mdp = MarketDataProvider()

# Simular exactamente lo que hace build_for_combo para KLAC
import pandas as pd
buffer_start = (pd.to_datetime('2022-01-01') - pd.Timedelta(days=365)).strftime('%Y-%m-%d')
df = mdp.get_daily_data('KLAC', start_date=buffer_start, end_date='2024-12-31', offline=True)
print('KLAC data shape:', df.shape if df is not None else None)
print('KLAC columns:', list(df.columns) if df is not None and not df.empty else 'EMPTY')
print('KLAC index type:', type(df.index))
print('KLAC index sample:', df.index[-3:].tolist() if df is not None and not df.empty else None)
print('KLAC dtypes:')
if df is not None and not df.empty:
    print(df.dtypes)

# Ahora correr el screener sobre un slice exacto con scan_date
if df is not None and not df.empty:
    import logging
    logging.disable(logging.CRITICAL)
    from src.screeners.triad_rts import TriadRTSScreener
    screener = TriadRTSScreener()
    
    # Slice hasta 2024-10-10 (fecha que sabemos tiene rts_pct=54 en daily_triad_rankings)
    target_date = pd.to_datetime('2024-10-10')
    hist = df[df.index <= target_date]
    print()
    print('Hist slice rows:', len(hist), '| last date:', hist.index[-1])
    
    result = screener.scan('KLAC', hist, scan_date='2024-10-10')
    print('Result passed:', result.passed)
    print('Result reason:', result.reason)
    print('rts_pct in metrics:', result.metrics.get('rts_pct'))
    print('as_5d_pct in metrics:', result.metrics.get('as_5d_pct'))
