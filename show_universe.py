#!/usr/bin/env python3
"""
UNIVERSE INFO - Muestra información del universo de trading
===========================================================
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from live_scanner import get_universe, get_sp500_tickers, get_nasdaq100_tickers


def main():
    print("\n" + "="*80)
    print("🌎 TRADING UNIVERSE INFO")
    print("="*80)
    
    print("\nDownloading universe lists...")
    
    sp500 = get_sp500_tickers()
    nasdaq100 = get_nasdaq100_tickers()
    universe = get_universe()
    
    # Calcular overlap
    overlap = set(sp500) & set(nasdaq100)
    
    print(f"\n{'='*80}")
    print("UNIVERSE BREAKDOWN")
    print(f"{'='*80}")
    print(f"S&P 500:              {len(sp500):>4} tickers")
    print(f"NASDAQ 100:           {len(nasdaq100):>4} tickers")
    print(f"Overlap (in both):    {len(overlap):>4} tickers")
    print(f"{'='*40}")
    print(f"TOTAL UNIQUE:         {len(universe):>4} tickers")
    
    # Mostrar algunos ejemplos del overlap
    print(f"\n{'='*80}")
    print("EXAMPLES OF OVERLAP (in both S&P 500 and NASDAQ 100)")
    print(f"{'='*80}")
    overlap_list = sorted(list(overlap))[:20]
    for i in range(0, len(overlap_list), 10):
        print("  " + ", ".join(overlap_list[i:i+10]))
    
    if len(overlap_list) < len(overlap):
        print(f"  ... and {len(overlap) - len(overlap_list)} more")
    
    # S&P 500 exclusivos
    sp500_only = set(sp500) - set(nasdaq100)
    print(f"\n{'='*80}")
    print(f"S&P 500 ONLY ({len(sp500_only)} tickers) - First 20 examples:")
    print(f"{'='*80}")
    sp500_only_list = sorted(list(sp500_only))[:20]
    for i in range(0, len(sp500_only_list), 10):
        print("  " + ", ".join(sp500_only_list[i:i+10]))
    
    # NASDAQ 100 exclusivos
    nasdaq_only = set(nasdaq100) - set(sp500)
    print(f"\n{'='*80}")
    print(f"NASDAQ 100 ONLY ({len(nasdaq_only)} tickers) - All examples:")
    print(f"{'='*80}")
    nasdaq_only_list = sorted(list(nasdaq_only))
    for i in range(0, len(nasdaq_only_list), 10):
        print("  " + ", ".join(nasdaq_only_list[i:i+10]))
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"When you run live_scanner.py, it will scan all {len(universe)} unique tickers")
    print(f"This includes the largest and most liquid stocks from both indices")
    print(f"\nEstimated scan time:")
    print(f"  - First time (download): 30-60 minutes")
    print(f"  - With cache: 5-10 minutes")
    print(f"  - With multiprocessing ({import_multiprocessing().cpu_count()-1} cores): Even faster")
    print("="*80 + "\n")


def import_multiprocessing():
    from multiprocessing import cpu_count
    class MP:
        @staticmethod
        def cpu_count():
            return cpu_count()
    return MP()


if __name__ == "__main__":
    main()
