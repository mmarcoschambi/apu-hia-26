import sys, logging
sys.path.insert(0, '/home/marcos/trade/momentum-v2')
logging.basicConfig(level=logging.WARNING)

import pandas as pd
import numpy as np
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.pit_universe import PointInTimeUniverse

pit = PointInTimeUniverse()
universe = pit.get_active_tickers("2022-01-01")

engine = AdvancedVectorBTEngine(
    universe=universe, start_date='2022-01-01', end_date='2024-06-30',
    signal_type='htf', htf_pole_ret=0.50, htf_pole_days=60,
    htf_flag_correction=0.12, htf_vol_ratio=9.99, htf_breakout_days=20,
    htf_min_trend_intensity=0.0, offline_mode=True
)
engine.load_data()

close  = engine.close
high   = engine.high

# Analizar NVDA
ticker = 'NVDA' if 'NVDA' in close.columns else close.columns[0]
print(f"Diagnostico sobre {ticker}")

c = close[ticker]
h = high[ticker]

# Polo 120d
pole_days = 120
ret_pole = (c / c.shift(pole_days) - 1).fillna(0)
pole_mask = ret_pole >= 0.50

# Flag high
bo_days = 20
flag_high = h.rolling(bo_days).max().shift(1)
correction = (flag_high - c) / flag_high.replace(0, np.nan)
flag_mask = (correction.fillna(1.0) < 0.12) & (correction.fillna(1.0) >= 0)

# BO
bo_mask = c > flag_high

# Donde el polo se cumple
pole_dates = pole_mask[pole_mask].index
print(f"Dias con polo activo: {len(pole_dates)}")
if len(pole_dates) > 0:
    print("Primeros 5 dias con polo:")
    for d in pole_dates[:5]:
        print(f"  {d.date()} ret120d={ret_pole[d]:.1%} close={c[d]:.2f} flag_high={flag_high.get(d, float('nan')):.2f} corr={correction.get(d, float('nan')):.3f} bo={bo_mask.get(d, False)} flag={flag_mask.get(d, False)}")

# Donde polo & flag & bo se cumplen sin vol
combined = pole_mask & flag_mask & bo_mask
print(f"\nPolo & Flag & BO combinados: {combined.sum()}")
print(f"Polo solo: {pole_mask.sum()}, Flag solo: {flag_mask.sum()}, BO solo: {bo_mask.sum()}")

# Ver si hay solapamiento manual
overlap_pf = pole_mask & flag_mask
print(f"Polo & Flag: {overlap_pf.sum()}")
overlap_pb = pole_mask & bo_mask
print(f"Polo & BO: {overlap_pb.sum()}")
