#!/usr/bin/env python3
"""
Debug Signal Detection
----------------------
Compare what data each engine is seeing for breakout detection.
"""

import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, '.')

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from config.advanced_engine_modes import get_engine_kwargs

def main():
    ticker = 'NVDA'
    start = '2019-01-01'
    end = '2019-12-31'
    
    print(f"=" * 80)
    print(f"🔍 DEBUG SIGNAL DETECTION: {ticker}")
    print(f"=" * 80)
    print(f"Period: {start} to {end}\n")
    
    # Get convergence config
    convergence_config = get_engine_kwargs(
        mode='convergence',
        universe=[ticker],
        start_date=start,
        end_date=end,
        initial_capital=100000
    )
    
    print("Configuration:")
    print(f"  min_rvol: {convergence_config['min_rvol']}")
    print(f"  min_adr: {convergence_config['min_adr']}")
    print(f"  max_dist_sma20: {convergence_config['max_dist_sma20']}")
    print(f"  signal_type: {convergence_config['signal_type']}")
    print()
    
    # Run THOR
    print("-" * 60)
    print("THOR ENGINE")
    print("-" * 60)
    
    thor = OptimizationEngineTHOR(
        tickers=[ticker],
        start_date=start,
        end_date=end,
        initial_capital=100000
    )
    
    thor_params = {
        'signal_type': convergence_config['signal_type'],
        'min_rvol': convergence_config['min_rvol'],
        'min_adr': convergence_config['min_adr'],
        'risk_dollars': convergence_config['risk_dollars'],
        'max_dist_sma20': convergence_config['max_dist_sma20'],
        'tp1_r': convergence_config['tp1_r'],
        'tp2_r': convergence_config['tp2_r'],
        'max_stop_pct': convergence_config['max_stop_pct'] / 100.0,
        'min_dollar_volume': convergence_config['min_dollar_volume'],
        'min_consolidation_days': convergence_config['min_consolidation_days'],
        'use_phases': True
    }
    
    thor_result = thor.backtest(thor_params)
    
    print(f"  Unique entries: {thor_result.get('unique_entries', 0)}")
    print(f"  All exits: {thor_result.get('all_exits', 0)}")
    print()
    
    # Run Advanced
    print("-" * 60)
    print("ADVANCED ENGINE")
    print("-" * 60)
    
    adv = AdvancedVectorBTEngine(**convergence_config)
    adv_result = adv.run_backtest()
    
    if 'trades' in adv_result and not adv_result['trades'].empty:
        trades = adv_result['trades']
        print(f"  Total trades (all exits): {len(trades)}")
        
        # Filter by date
        trades['entry_date_dt'] = pd.to_datetime(trades['entry_date'])
        in_range = trades[
            (trades['entry_date_dt'] >= start) &
            (trades['entry_date_dt'] <= end)
        ]
        
        # Count unique entries
        unique_entries = in_range.groupby(['entry_date', 'symbol']).ngroups
        print(f"  Unique entries (in range): {unique_entries}")
        
        print(f"\n  All entry dates found:")
        start_dt = pd.to_datetime(start)
        end_dt = pd.to_datetime(end)
        for entry_date in sorted(pd.to_datetime(trades['entry_date']).unique()):
            trades_on_date = trades[pd.to_datetime(trades['entry_date']) == entry_date]
            phases = ','.join(sorted(trades_on_date['exit_phase'].unique()))
            in_range_mark = "✓" if entry_date >= start_dt and entry_date <= end_dt else "✗"
            print(f"    {in_range_mark} {entry_date.date()} ({len(trades_on_date)} exits: {phases})")
    else:
        print("  No trades found")
    
    print()
    print("=" * 80)
    print("CONCLUSION:")
    print("=" * 80)
    thor_count = thor_result.get('unique_entries', 0)
    if 'trades' in adv_result and not adv_result['trades'].empty:
        adv_in_range = adv_result['trades'][
            (pd.to_datetime(adv_result['trades']['entry_date']) >= start) &
            (pd.to_datetime(adv_result['trades']['entry_date']) <= end)
        ]
        adv_count = adv_in_range.groupby(['entry_date', 'symbol']).ngroups
    else:
        adv_count = 0
    
    diff = abs(thor_count - adv_count)
    diff_pct = (diff / max(thor_count, 1)) * 100
    
    print(f"  THOR found:     {thor_count} unique entries")
    print(f"  Advanced found: {adv_count} unique entries")
    print(f"  Difference:     {diff} ({diff_pct:.1f}%)")
    
    if diff_pct > 15:
        print(f"\n  ⚠️  Divergence > 15% - engines are detecting different signals")
        print(f"     This suggests differences in breakout logic, filters, or indicator calculation")
    else:
        print(f"\n  ✓ Within tolerance (<15%)")

if __name__ == "__main__":
    main()
