#!/usr/bin/env python3
"""
Export Complete Trades
======================
Exports the latest trade_log.csv as complete trades (grouped partial exits).

Usage:
    python3 scripts/optimization/export_complete_trades.py
    python3 scripts/optimization/export_complete_trades.py --input custom_log.csv
"""

import pandas as pd
from pathlib import Path
import sys
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.analytics.quantstats_analyzer import TradeGrouper


def main():
    parser = argparse.ArgumentParser(description='Export complete trades')
    parser.add_argument('--input', type=str, default='outputs/backtests/trade_log.csv',
                       help='Input trade log CSV')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file (default: outputs/backtests/complete_trades.csv)')
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)
    
    # Load trade log
    print(f"📂 Loading: {input_path}")
    trade_log = pd.read_csv(input_path)
    print(f"   Raw events: {len(trade_log)}")
    
    # Group into complete trades
    print("\n🔄 Grouping partial exits into complete trades...")
    complete_trades = TradeGrouper.group_partial_trades(trade_log)
    
    if complete_trades.empty:
        print("❌ No trades to export")
        sys.exit(1)
    
    print(f"   ✅ Complete trades: {len(complete_trades)}")
    print(f"   Winners: {complete_trades['is_winner'].sum()} ({complete_trades['is_winner'].sum()/len(complete_trades)*100:.1f}%)")
    print(f"   Total PnL: ${complete_trades['total_pnl'].sum():,.2f}")
    print(f"   Avg R: {complete_trades['r_multiple'].mean():.2f}R")
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_path = Path('outputs/backtests/complete_trades.csv')
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save
    complete_trades.to_csv(output_path, index=False)
    print(f"\n💾 Exported to: {output_path}")
    print(f"   Columns: {len(complete_trades.columns)}")
    print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")
    
    # Quick stats
    print("\n📊 Quick Stats:")
    print(f"   Hold Days (avg): {complete_trades['hold_days'].mean():.1f}")
    print(f"   Stopped Out: {complete_trades['was_stopped_out'].sum()} ({complete_trades['was_stopped_out'].sum()/len(complete_trades)*100:.0f}%)")
    print(f"   Hit TP1: {complete_trades['hit_tp1'].sum()} ({complete_trades['hit_tp1'].sum()/len(complete_trades)*100:.0f}%)")
    print(f"   Hit TP2: {complete_trades['hit_tp2'].sum()} ({complete_trades['hit_tp2'].sum()/len(complete_trades)*100:.0f}%)")
    print(f"   Had Runner: {complete_trades['had_runner'].sum()} ({complete_trades['had_runner'].sum()/len(complete_trades)*100:.0f}%)")
    
    print(f"\n✅ Done! Use this file with optimization scripts:")
    print(f"   python3 scripts/optimization/range_finder.py --file {output_path}")
    print(f"   python3 scripts/optimization/optimize_parameters.py --file {output_path}")


if __name__ == '__main__':
    main()
