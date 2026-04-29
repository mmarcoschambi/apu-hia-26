#!/usr/bin/env python3
"""
Debug UI Metrics Discrepancy
============================
Checks if TradeGrouper is working correctly and why UI shows inflated numbers.
"""

import pandas as pd
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.analytics.quantstats_analyzer import TradeGrouper

def diagnose_trade_grouping():
    """Check if trade grouping logic is working"""
    
    print("=" * 80)
    print("🔍 DIAGNOSING TRADE GROUPING BUG")
    print("=" * 80)
    print()
    
    # Load the CSV that UI uses
    csv_file = "outputs/backtests/partial_exits.csv"
    
    if not Path(csv_file).exists():
        print(f"❌ CSV not found: {csv_file}")
        print("Run a backtest first in Streamlit to generate data")
        return
    
    print(f"📁 Loading: {csv_file}")
    df = pd.read_csv(csv_file)
    print(f"📊 Raw CSV rows (exit events): {len(df)}")
    print()
    
    # Show columns
    print("📋 Columns available:")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i:2d}. {col}")
    print()
    
    # Check what columns TradeGrouper needs
    required_cols = ['ticker', 'entry_date', 'exit_phase']
    print("🔍 Checking required columns for TradeGrouper:")
    for col in required_cols:
        exists = col in df.columns
        status = "✅" if exists else "❌"
        print(f"  {status} {col}")
    print()
    
    # Map columns if needed
    print("🔧 Column mapping:")
    if 'symbol' in df.columns and 'ticker' not in df.columns:
        print("  • symbol → ticker")
        df['ticker'] = df['symbol']
    
    if 'exit_phase' not in df.columns:
        if 'phase' in df.columns:
            print("  • phase → exit_phase")
            df['exit_phase'] = df['phase']
        elif 'reason' in df.columns:
            print("  • reason → exit_phase (extracting)")
            df['exit_phase'] = df['reason'].str.split(':').str[0]
    
    if 'pnl' not in df.columns and 'Result' in df.columns:
        print("  • Result → pnl")
        df['pnl'] = df['Result']
    print()
    
    # Now try grouping
    print("=" * 80)
    print("🧪 ATTEMPTING TO GROUP TRADES")
    print("=" * 80)
    print()
    
    try:
        grouped = TradeGrouper.group_partial_trades(df)
        
        print(f"✅ Grouping successful!")
        print(f"   📊 Complete trades: {len(grouped)}")
        print(f"   📤 Exit events: {len(df)}")
        print(f"   📉 Compression ratio: {len(df)/len(grouped):.2f}x")
        print()
        
        # Show examples
        print("🔍 Example trades with multiple exits:")
        multi_exit_trades = grouped[grouped['exit_phases'].str.contains(',')].head(5)
        
        if not multi_exit_trades.empty:
            for idx, row in multi_exit_trades.iterrows():
                ticker = row['ticker']
                entry_date = row['entry_date']
                phases = row['exit_phases']
                pnl = row['total_pnl']
                
                print(f"\n  📌 {ticker} @ {entry_date}")
                print(f"     Phases: {phases}")
                print(f"     Total PnL: ${pnl:,.2f}")
                
                # Show individual exits
                individual = df[(df['ticker'] == ticker) & (df['entry_date'] == entry_date)]
                for _, exit_row in individual.iterrows():
                    print(f"       - {exit_row['exit_phase']}: ${exit_row['pnl']:,.2f}")
        else:
            print("  ⚠️ No trades with multiple exits found!")
            print("  This might be expected if all trades hit stop immediately.")
        
        print()
        print("=" * 80)
        print("📊 METRICS COMPARISON")
        print("=" * 80)
        print()
        
        # Original metrics (counting each exit separately)
        original_trades = len(df)
        original_winners = len(df[df['pnl'] > 0])
        original_losers = len(df[df['pnl'] <= 0])
        original_win_rate = (original_winners / original_trades * 100) if original_trades > 0 else 0
        original_pnl = df['pnl'].sum()
        
        # Grouped metrics (correct)
        grouped_trades = len(grouped)
        grouped_winners = len(grouped[grouped['total_pnl'] > 0])
        grouped_losers = len(grouped[grouped['total_pnl'] <= 0])
        grouped_win_rate = (grouped_winners / grouped_trades * 100) if grouped_trades > 0 else 0
        grouped_pnl = grouped['total_pnl'].sum()
        
        print("📊 ORIGINAL (Counting each exit separately):")
        print(f"   Total Trades: {original_trades}")
        print(f"   Winners: {original_winners} ({original_win_rate:.1f}%)")
        print(f"   Losers: {original_losers}")
        print(f"   Total PnL: ${original_pnl:,.2f}")
        print()
        
        print("📊 GROUPED (Correct complete trades):")
        print(f"   Total Trades: {grouped_trades}")
        print(f"   Winners: {grouped_winners} ({grouped_win_rate:.1f}%)")
        print(f"   Losers: {grouped_losers}")
        print(f"   Total PnL: ${grouped_pnl:,.2f}")
        print()
        
        print("⚠️  DISCREPANCY:")
        print(f"   Trade count inflation: +{original_trades - grouped_trades} trades")
        print(f"   Win rate inflation: +{original_win_rate - grouped_win_rate:.1f}%")
        print(f"   PnL difference: ${original_pnl - grouped_pnl:,.2f}")
        print()
        
        # Check hold days
        if 'hold_days' in grouped.columns:
            avg_hold = grouped['hold_days'].mean()
            print(f"📅 Average hold time: {avg_hold:.1f} days")
            
            scalps = len(grouped[grouped['hold_days'] < 3])
            swings = len(grouped[(grouped['hold_days'] >= 3) & (grouped['hold_days'] < 10)])
            positions = len(grouped[grouped['hold_days'] >= 10])
            
            print(f"   Scalps (<3d): {scalps}")
            print(f"   Swings (3-10d): {swings}")
            print(f"   Positions (>10d): {positions}")
        else:
            print("⚠️ hold_days column missing!")
        
        print()
        print("=" * 80)
        print("🔍 ROOT CAUSE ANALYSIS")
        print("=" * 80)
        print()
        
        # Check if UI is actually using grouped trades
        if original_trades == grouped_trades:
            print("❌ PROBLEM: No grouping is happening!")
            print("   • UI is counting each exit separately")
            print("   • TradeGrouper is not being called")
            print("   • Check app.py lines 2480-2545")
        else:
            print("✅ Grouping is working correctly in this script")
            print("⚠️  BUT UI still shows inflated numbers!")
            print()
            print("🔍 Possible causes:")
            print("   1. UI is showing 'df_filtered' instead of 'complete_trades'")
            print("   2. use_complete_metrics flag is False")
            print("   3. TradeGrouper.group_partial_trades() is failing silently")
            print("   4. Column names mismatch in app.py")
            print()
            print("📝 Check app.py line 2585-2608:")
            print("   • Is use_complete_metrics = True?")
            print("   • Is display_trades using complete_trades count?")
        
    except Exception as e:
        print(f"❌ Grouping failed: {e}")
        import traceback
        traceback.print_exc()
        
        print()
        print("🔍 Diagnosis:")
        print("   • TradeGrouper cannot process this data")
        print("   • Missing required columns or data format issue")
        print("   • UI falls back to ungrouped metrics")

if __name__ == "__main__":
    diagnose_trade_grouping()
