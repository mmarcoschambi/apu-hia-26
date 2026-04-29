#!/usr/bin/env python3
"""
Headless Backtest Runner for Dashboard Integration (OpenBB Version)
"""
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.triad_openbb import TriadOpenBB
from src.utils.risk_manager import RiskManager

def load_watchlist(json_path):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        symbols = []
        for cat in data.values():
            symbols.extend(cat)
        return list(set(symbols))
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return ['AAPL', 'MSFT', 'TSLA', 'NVDA']

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--watchlist', default='config/watchlist.json')
    parser.add_argument('--stop_loss', type=float, default=None, help="Fixed Stop Loss %")
    
    # Risk Management Arguments
    parser.add_argument('--account_equity', type=float, default=100000.0)
    parser.add_argument('--risk_fraction', type=float, default=0.005) # 0.5%
    parser.add_argument('--max_exposure', type=float, default=0.25) # 25%

    args = parser.parse_args()

    print(f"Starting OpenBB backtest from {args.start} to {args.end}")
    if args.stop_loss:
        print(f"Using Fixed Stop Loss: {args.stop_loss}%")
    
    print(f"Risk Config: Equity=${args.account_equity:,.0f}, Risk={args.risk_fraction*100}%, MaxExp={args.max_exposure*100}%")

    symbols = load_watchlist(args.watchlist)
    total_symbols = len(symbols)
    print(f"Loaded {total_symbols} symbols from watchlist.")

    # Initialize Risk Manager
    risk_manager = RiskManager(
        account_equity=args.account_equity,
        risk_fraction=args.risk_fraction,
        max_exposure_fraction=args.max_exposure
    )

    # Initialize OpenBB Triad system
    triad = TriadOpenBB()
    all_results = []
    
    # Iterate manually to report progress to Streamlit
    for i, symbol in enumerate(symbols):
        print(f"__PROGRESS__{i+1}/{total_symbols}__{symbol}")
        try:
            res = triad.backtest_with_openbb(
                [symbol], 
                args.start, 
                args.end, 
                stop_loss_pct=args.stop_loss,
                risk_manager=risk_manager
            )
            if not res.empty:
                all_results.append(res)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        if 'entry_date' in combined.columns:
            combined['entry_date'] = pd.to_datetime(combined['entry_date'])
        if 'exit_date' in combined.columns:
            combined['exit_date'] = pd.to_datetime(combined['exit_date'])
            
        combined.to_csv('backtest_results.csv', index=False)
        print(f"✅ Successfully saved {len(combined)} trades to backtest_results.csv")
    else:
        print("No trades found in the specified period.")
        pd.DataFrame(columns=[
            'entry_date', 'exit_date', 'entry_price', 'exit_price', 
            'returns_pct', 'is_profitable', 'signal_type', 
            'signal_reason', 'symbol', 'shares', 'position_value', 'monetary_risk'
        ]).to_csv('backtest_results.csv', index=False)

if __name__ == "__main__":
    main()
