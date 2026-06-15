import logging
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '/home/marcos/trade/momentum-v2')

logging.basicConfig(level=logging.WARNING)
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.pit_universe import PointInTimeUniverse

def freq_check():
    pit = PointInTimeUniverse()
    universe = pit.get_active_tickers("2022-01-01")

    configs = [
        dict(name='60d/50%',        pole_days=60,  pole_ret=0.50, vol_ratio=0.75),
        dict(name='60d/50%_novol',  pole_days=60,  pole_ret=0.50, vol_ratio=9.99),
        dict(name='120d/50%',       pole_days=120, pole_ret=0.50, vol_ratio=0.75),
        dict(name='120d/50%_novol', pole_days=120, pole_ret=0.50, vol_ratio=9.99),
        dict(name='120d/40%',       pole_days=120, pole_ret=0.40, vol_ratio=0.75),
        dict(name='120d/40%_novol', pole_days=120, pole_ret=0.40, vol_ratio=9.99),
    ]

    print('Loading data once...')
    engine = AdvancedVectorBTEngine(
        universe=universe, start_date='2022-01-01', end_date='2024-06-30',
        signal_type='htf', htf_pole_ret=0.50, htf_pole_days=60,
        htf_flag_correction=0.12, htf_vol_ratio=0.75, htf_breakout_days=20,
        htf_min_trend_intensity=0.0, offline_mode=True
    )
    engine.load_data()

    close  = engine.close
    high   = engine.high
    volume = engine.volume
    n_days = close.shape[0]
    years  = n_days / 252

    print(f'Universe: {close.shape[1]} tickers | {n_days} days ({years:.1f} yr)')
    print(f"{'Config':<22} {'Pole':>6} {'Flag':>6} {'Vol':>6} {'BO':>6} {'Final':>7} {'per/yr':>7}")
    print('-'*65)

    for cfg in configs:
        pole_days = cfg['pole_days']
        pole_ret  = cfg['pole_ret']
        vol_ratio = cfg['vol_ratio']
        bo_days   = 20

        ret_pole   = (close / close.shift(pole_days) - 1).fillna(0)
        pole_mask  = ret_pole >= pole_ret

        flag_high   = high.rolling(bo_days).max().shift(1)
        close_prev  = close.shift(1)  # precio ayer -> mide flag antes del BO
        correction  = (flag_high - close_prev) / flag_high.replace(0, np.nan)
        flag_mask   = (correction.fillna(1.0) < 0.12) & (correction.fillna(1.0) >= 0)

        vol_flag   = volume.rolling(20).mean()
        vol_pole   = volume.rolling(20).mean().shift(pole_days // 2)
        vol_mask   = vol_flag < vol_ratio * vol_pole.fillna(vol_flag)

        bo_mask    = close > flag_high

        final = pole_mask & flag_mask & vol_mask & bo_mask

        p = int(pole_mask.sum().sum())
        f = int(flag_mask.sum().sum())
        v = int(vol_mask.sum().sum())
        b = int(bo_mask.sum().sum())
        n = int(final.sum().sum())

        print(f"{cfg['name']:<22} {p:>6} {f:>6} {v:>6} {b:>6} {n:>7} {n/years:>7.1f}")

if __name__ == '__main__':
    freq_check()
