#!/usr/bin/env python3
"""
SIMPLE DEBUG: Identificar diferencias específicas entre THOR y Advanced
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

TEST_TICKERS = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
TEST_PERIOD = ('2023-01-01', '2023-12-31')

print("="*70)
print("🔍 SIMPLE DEBUG: THOR vs Advanced")
print("="*70)

# Load data
print("\n📊 Loading data...")
thor = OptimizationEngineTHOR(tickers=TEST_TICKERS, start_date=TEST_PERIOD[0], end_date=TEST_PERIOD[1], use_float32=True, chunk_size=50)
print(f"   THOR: {thor.close.shape}")

advanced = AdvancedVectorBTEngine(
    universe=TEST_TICKERS, start_date=TEST_PERIOD[0], end_date=TEST_PERIOD[1],
    min_rvol=2.0, min_adr=2.5, max_dist_sma20=12.5, min_consolidation_days=10,
    max_stop_pct=7.0, risk_dollars=150,
    require_spy_above_sma50=False, use_adaptive_filtering=False,
    use_earnings_calendar=False, use_trailing_stop=False,
    use_market_regime_filter=False, use_dynamic_thresholds=False,
    require_positive_rs=False, use_rs_percentile=False, use_sma50_atr_filter=False,
    rvol_danger=3.0, rvol_warning=2.0, rvol_danger_size=30, rvol_warning_size=65,
)
advanced.load_data()
print(f"   Advanced: {advanced.close.shape}")

# Common data
common_tickers = list(set(thor.close.columns) & set(advanced.close.columns))
common_dates = sorted(set(thor.close.index) & set(advanced.close.index))
print(f"   Common: {len(common_tickers)} tickers, {len(common_dates)} dates")

# Run backtests
print("\n📊 Running backtests...")
params_thor = {
    'signal_type': 'any', 'min_rvol': 2.0, 'min_adr': 2.5, 'risk_dollars': 150,
    'max_dist_sma20': 12.5, 'min_consolidation_days': 10, 'max_stop_pct': 7.0,
    'tp1_r': 1.5, 'tp2_r': 3.0, 'rvol_warning_size': 0.65, 'rvol_danger_size': 0.30, 'use_phases': True,
}
result_thor = thor.backtest(params_thor)
result_advanced = advanced.run_backtest()

# Results
print(f"\n   {'Metric':<15} | {'THOR':<12} | {'Advanced':<12} | {'Diff':<10}")
print(f"   {'-'*55}")
print(f"   {'Sharpe':<15} | {result_thor['sharpe_ratio']:<12.3f} | {result_advanced['sharpe_ratio']:<12.3f} | {abs(result_thor['sharpe_ratio']-result_advanced['sharpe_ratio']):<10.3f}")
print(f"   {'Trades':<15} | {result_thor['total_trades']:<12.0f} | {result_advanced['total_trades']:<12.0f} | {abs(result_thor['total_trades']-result_advanced['total_trades']):<10.0f}")
print(f"   {'Win Rate %':<15} | {result_thor['win_rate_pct']:<12.1f} | {result_advanced['win_rate']*100:<12.1f} | {abs(result_thor['win_rate_pct']-result_advanced['win_rate']*100):<10.1f}")

# Convergence check
sharpe_diff = abs(result_thor['sharpe_ratio'] - result_advanced['sharpe_ratio'])
trades_diff = abs(result_thor['total_trades'] - result_advanced['total_trades'])

print("\n" + "="*70)
if sharpe_diff < 0.2 and trades_diff <= 2:
    print("✅ CONVERGED")
else:
    print("❌ NOT CONVERGED")
    print(f"\nKEY DIFFERENCES:")
    print("1. THOR: Requires consolidation_days >= 10")
    print("2. Advanced: Does NOT require consolidation_days in baseline logic")
    print("3. THOR: vol >= 200k threshold")
    print("4. Advanced: vol >= 300k threshold (in __init__)")
