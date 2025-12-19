#!/usr/bin/env python3
"""
Example: Using OpenBB for Triad Momentum Analysis
"""
import sys
from pathlib import Path
import pandas as pd
import subprocess
import os

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.triad_openbb import TriadOpenBB


def main():
    """
    Main example - demonstrates OpenBB integration with Triad system
    """
    # Initialize Triad with OpenBB
    triad_openbb = TriadOpenBB()

    # Example symbols to analyze
    symbols = ['LUNR', 'MU', 'ALM', 'AFRM', 'SNDK', 'WDC', 'SUZ', 'LITE', 'RKLB', 'LRCX', 'RIVN', 'SBUX', 'STX', 'RDDT', 'PLTR', 'SHOP', 'GEV', 'TSLA', 'ORLA', 'COHR', 'AEO']

    print(f"\n{'='*80}")
    print(f"TRIAD OPENBB ANALYSIS - {len(symbols)} symbols")
    print(f"{'='*80}\n")

    # Calculate AVWAP and ATH for each symbol
    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        result = triad_openbb.calculate_avwap_ath(symbol)

        if result:
            print(f"  AVWAP: ${result['avwap']:.2f}")
            print(f"  ATH: ${result['ath']:.2f} on {result['ath_date']}")
            print(f"  Current: ${result['current_price']:.2f}")
            print(f"  Distance to ATH: {result['ath_distance_pct']:.2f}%")
            print(f"  Data points: {result['data_available']}")
        else:
            print(f"  No data available for {symbol}")
        print()

    # Example backtesting
    print(f"{'='*80}")
    print("BACKTESTING EXAMPLE")
    print(f"{'='*80}\n")

    # Backtest the same symbols we analyzed individually
    start_date = "2024-01-01"
    end_date = "2024-12-19"

    backtest_results = triad_openbb.backtest_with_openbb(symbols, start_date, end_date)

    if not backtest_results.empty:
        print("Backtest Results:")
        print(backtest_results.head(10))  # Show first 10 results
        print(f"\nTotal trades: {len(backtest_results)}")
        print(f"Win rate: {(backtest_results['is_profitable'].sum() / len(backtest_results) * 100):.2f}%")
        print(f"Average return: {backtest_results['returns_pct'].mean():.2f}%")

        # Save results to CSV for the dashboard
        backtest_results.to_csv('backtest_results.csv', index=False)
        print(f"\nBacktest results saved to backtest_results.csv")

        # Ask user if they want to open the dashboard
        response = input("\nDo you want to open the backtest dashboard? (y/n): ")
        if response.lower() in ['y', 'yes', 's', 'si']:
            try:
                # Try to open the dashboard using the provided script
                subprocess.run(['./open_dashboard.sh'], check=True)
            except subprocess.CalledProcessError:
                # If the script fails, try to open the HTML file directly with a browser
                try:
                    subprocess.run(['firefox', 'backtest_dashboard.html'], check=True)
                except subprocess.CalledProcessError:
                    try:
                        subprocess.run(['google-chrome', 'backtest_dashboard.html'], check=True)
                    except subprocess.CalledProcessError:
                        print("Could not open the dashboard. Please open backtest_dashboard.html manually.")
    else:
        print("No backtest results available")


if __name__ == "__main__":
    main()
