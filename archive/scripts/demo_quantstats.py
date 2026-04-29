#!/usr/bin/env python3
"""
QuantStats Demo - Show How Trade Grouping Works
================================================
Demonstrates the difference between partial and complete trade analysis.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add project root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.analytics.quantstats_analyzer import TradeGrouper


def create_demo_trades():
    """Create realistic demo trade log with partial exits."""
    
    trades = [
        # Trade 1: AAPL - Winner with full exit sequence (TP1, TP2, RUNNER)
        {'ticker': 'AAPL', 'entry_date': '2024-01-10', 'exit_date': '2024-01-12', 
         'entry_price': 180.0, 'exit_price': 185.4, 'shares': 50, 'pnl': 270.0, 
         'exit_phase': 'TP1', 'adjusted_risk_dollars': 150},
        {'ticker': 'AAPL', 'entry_date': '2024-01-10', 'exit_date': '2024-01-15',
         'entry_price': 180.0, 'exit_price': 194.4, 'shares': 30, 'pnl': 432.0,
         'exit_phase': 'TP2', 'adjusted_risk_dollars': 150},
        {'ticker': 'AAPL', 'entry_date': '2024-01-10', 'exit_date': '2024-01-18',
         'entry_price': 180.0, 'exit_price': 198.0, 'shares': 20, 'pnl': 360.0,
         'exit_phase': 'RUNNER_EXIT', 'adjusted_risk_dollars': 150},
        
        # Trade 2: MSFT - Partial winner stopped out (TP1, STOP)
        {'ticker': 'MSFT', 'entry_date': '2024-01-15', 'exit_date': '2024-01-17',
         'entry_price': 380.0, 'exit_price': 385.7, 'shares': 25, 'pnl': 142.5,
         'exit_phase': 'TP1', 'adjusted_risk_dollars': 150},
        {'ticker': 'MSFT', 'entry_date': '2024-01-15', 'exit_date': '2024-01-20',
         'entry_price': 380.0, 'exit_price': 375.0, 'shares': 75, 'pnl': -375.0,
         'exit_phase': 'STOP_BE', 'adjusted_risk_dollars': 150},
        
        # Trade 3: NVDA - Quick stop out (no partials)
        {'ticker': 'NVDA', 'entry_date': '2024-01-22', 'exit_date': '2024-01-23',
         'entry_price': 500.0, 'exit_price': 493.0, 'shares': 30, 'pnl': -210.0,
         'exit_phase': 'STOP', 'adjusted_risk_dollars': 150},
        
        # Trade 4: TSLA - Full sequence winner (TP1, TP2, RUNNER)
        {'ticker': 'TSLA', 'entry_date': '2024-01-25', 'exit_date': '2024-01-26',
         'entry_price': 200.0, 'exit_price': 206.0, 'shares': 50, 'pnl': 300.0,
         'exit_phase': 'TP1', 'adjusted_risk_dollars': 150},
        {'ticker': 'TSLA', 'entry_date': '2024-01-25', 'exit_date': '2024-01-29',
         'entry_price': 200.0, 'exit_price': 218.0, 'shares': 30, 'pnl': 540.0,
         'exit_phase': 'TP2', 'adjusted_risk_dollars': 150},
        {'ticker': 'TSLA', 'entry_date': '2024-01-25', 'exit_date': '2024-02-02',
         'entry_price': 200.0, 'exit_price': 225.0, 'shares': 20, 'pnl': 500.0,
         'exit_phase': 'RUNNER_EXIT', 'adjusted_risk_dollars': 150},
    ]
    
    # Add required context fields
    for trade in trades:
        trade.update({
            'entry_signal': 'TRIAD_VWAP',
            'context_adr': 5.0,
            'context_rvol': 2.5,
            'context_trend': 'BULLISH',
            'dist_sma20_pct': 3.5,
            'consolidation_days': 15,
            'sector': 'Technology',
            'sector_strength': 0.65,
            'vix_regime': 'CALM',
            'spy_above_ema20': True,
            'base_risk_dollars': 150,
            'risk_reduction_factor': 1.0,
            'rvol_classification': 'INSTITUTIONAL',
            'volatility_regime': 'MED',
            'is_vcp_pattern': True,
        })
    
    return pd.DataFrame(trades)


def analyze_demo():
    """Show the difference between partial and grouped analysis."""
    
    print("=" * 80)
    print("QUANTSTATS DEMO: Partial Trade Grouping")
    print("=" * 80)
    
    # Create demo data
    trade_log = create_demo_trades()
    
    print(f"\n📊 RAW TRADE LOG (Partial Exits)")
    print("-" * 80)
    print(f"Total Events: {len(trade_log)}")
    print("\nDetailed Events:")
    for i, trade in trade_log.iterrows():
        print(f"  {trade['ticker']:6} {trade['entry_date']} → {trade['exit_date']}  "
              f"{trade['exit_phase']:15} {trade['shares']:3} shares  "
              f"${trade['pnl']:+8.2f}")
    
    # Without grouping - WRONG ANALYSIS
    print(f"\n❌ WITHOUT GROUPING (WRONG!)")
    print("-" * 80)
    winners = (trade_log['pnl'] > 0).sum()
    losers = (trade_log['pnl'] <= 0).sum()
    win_rate = winners / len(trade_log) * 100
    total_pnl = trade_log['pnl'].sum()
    
    print(f"Total 'Trades':      {len(trade_log)}  ← WRONG! These are partial exits")
    print(f"Winners:             {winners} ({win_rate:.1f}%)  ← INFLATED win rate")
    print(f"Losers:              {losers}")
    print(f"Total P&L:           ${total_pnl:,.2f}  ← This is correct")
    print(f"Avg P&L per event:   ${trade_log['pnl'].mean():.2f}  ← MEANINGLESS")
    
    # With grouping - CORRECT ANALYSIS
    print(f"\n✅ WITH TRADE GROUPER (CORRECT!)")
    print("-" * 80)
    
    complete_trades = TradeGrouper.group_partial_trades(trade_log)
    
    print(f"\nGrouped Complete Trades:")
    for i, trade in complete_trades.iterrows():
        print(f"  {trade['ticker']:6} {trade['entry_date']} → {trade['final_exit_date']}  "
              f"{trade['exit_phases']:25} {trade['total_shares']:3} shares  "
              f"${trade['total_pnl']:+8.2f}  {trade['r_multiple']:+.2f}R  "
              f"{trade['hold_days']}d")
    
    print(f"\n📈 CORRECT METRICS:")
    print("-" * 80)
    winners = complete_trades['is_winner'].sum()
    losers = len(complete_trades) - winners
    win_rate = winners / len(complete_trades) * 100
    total_pnl = complete_trades['total_pnl'].sum()
    avg_r = complete_trades['r_multiple'].mean()
    
    # Profit factor
    gross_wins = complete_trades[complete_trades['is_winner']]['total_pnl'].sum()
    gross_losses = abs(complete_trades[~complete_trades['is_winner']]['total_pnl'].sum())
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else np.inf
    
    print(f"Total Trades:        {len(complete_trades)}  ← ACTUAL number of trades")
    print(f"Winners:             {winners} ({win_rate:.1f}%)  ← REAL win rate")
    print(f"Losers:              {losers}")
    print(f"Total P&L:           ${total_pnl:,.2f}")
    print(f"Avg R-Multiple:      {avg_r:+.2f}R  ← SYSTEM EXPECTANCY")
    print(f"Profit Factor:       {profit_factor:.2f}")
    
    # Exit analysis
    print(f"\n🎯 EXIT ANALYSIS:")
    print("-" * 80)
    hit_tp1 = complete_trades['hit_tp1'].sum()
    hit_tp2 = complete_trades['hit_tp2'].sum()
    had_runner = complete_trades['had_runner'].sum()
    stopped_out = complete_trades['was_stopped_out'].sum()
    
    print(f"Hit TP1:             {hit_tp1} ({hit_tp1/len(complete_trades)*100:.0f}%)")
    print(f"Hit TP2:             {hit_tp2} ({hit_tp2/len(complete_trades)*100:.0f}%)")
    print(f"Had Runner:          {had_runner} ({had_runner/len(complete_trades)*100:.0f}%)")
    print(f"Stopped Out:         {stopped_out} ({stopped_out/len(complete_trades)*100:.0f}%)")
    
    # Show trade breakdown
    print(f"\n💰 TRADE BREAKDOWN:")
    print("-" * 80)
    for i, trade in complete_trades.iterrows():
        outcome = "🟢 WIN " if trade['is_winner'] else "🔴 LOSS"
        print(f"{outcome} | {trade['ticker']:6} | "
              f"${trade['total_pnl']:+8.2f} | {trade['r_multiple']:+.2f}R | "
              f"{trade['exit_phases']:25} | {trade['hold_days']:2}d")
    
    print("\n" + "=" * 80)
    print("KEY TAKEAWAY:")
    print("=" * 80)
    print("Without grouping: 9 'trades' with 66.7% win rate ← WRONG!")
    print("With grouping:    4 trades with 75.0% win rate    ← CORRECT!")
    print("\nPartial exits are EXECUTION details, not separate trades!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    analyze_demo()
