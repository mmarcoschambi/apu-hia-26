"""Repro mínimo v2: tracebacks completos por variante."""
import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.backtest.numba_core import simulate_fast_core  # noqa: E402


def build(open_day2_t1):
    n_days, n_t = 5, 2

    def f(v):
        return np.full((n_days, n_t), v, dtype=np.float32)

    close = f(100.0)
    high = f(100.0)
    low = f(100.0)
    open_arr = f(100.0)
    open_arr[2, 1] = open_day2_t1

    volume = f(1_000_000.0)
    entries = np.zeros((n_days, n_t), dtype=np.float32)
    entries[1, 1] = 1.0

    atr = f(1.0)
    sma20 = f(100.0)
    ema10 = f(100.0)
    ema8 = f(100.0)
    ema21 = f(100.0)
    adr = f(5.0)
    rvol = f(1.0)
    sector_mult = f(1.0)
    score = f(0.5)

    spy_close = np.full(n_days, 100.0, dtype=np.float32)
    spy_sma50 = np.full(n_days, 100.0, dtype=np.float32)

    return dict(
        close_arr=close,
        high_arr=high,
        low_arr=low,
        open_arr=open_arr,
        volume_arr=volume,
        entries_arr=entries,
        atr_arr=atr,
        sma20_arr=sma20,
        ema10_arr=ema10,
        ema8_arr=ema8,
        ema21_arr=ema21,
        adr_arr=adr,
        rvol_arr=rvol,
        sector_multiplier_arr=sector_mult,
        entry_score_arr=score,
        spy_close_arr=spy_close,
        spy_sma50_arr=spy_sma50,
        initial_capital=100000.0,
        tp1_r=2.0,
        tp2_r=4.0,
        tp1_pct=0.5,
        tp2_pct=0.3,
        runner_pct=0.2,
        risk_pct_per_trade=0.01,
        max_exposure_pct=0.25,
        be_threshold_r=1.0,
        use_trailing_stop=True,
        max_stop_pct=0.1,
        risk_dollars=500.0,
        use_fixed_dollar_risk=True,
        use_atr_stop=False,
        atr_stop_multiplier=2.0,
        atr_trailing_multiplier=2.0,
        fee_rate=0.001,
        slippage_rate=0.001,
        stop_mode=0,
        sizing_mode=0,
        max_position_pct=0.25,
    )


if __name__ == "__main__":
    for label, val in [("open_normal", 100.0), ("open_zero", 0.0), ("open_nan", np.nan)]:
        print(f"===== {label} =====")
        try:
            eq, tr = simulate_fast_core(**build(val))
            n_trades = int((tr[:, 0] > 0).sum()) if tr.shape[0] else 0
            print(f"OK equity[-1]={eq[-1]:.2f} trades={n_trades}")
        except Exception:
            traceback.print_exc()
        print()
