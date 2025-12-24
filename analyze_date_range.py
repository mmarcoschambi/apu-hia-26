#!/usr/bin/env python3
"""
DATE RANGE ANALYZER - Analiza el rango de fechas disponible en cache
====================================================================
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.cache_manager import CacheManager
import pandas as pd


def analyze_date_coverage():
    """Analiza la cobertura de fechas en el cache"""
    cache = CacheManager()
    
    info = cache.get_cache_info()
    
    if len(info) == 0:
        return None, None, []
    
    info['first_date'] = pd.to_datetime(info['first_date'])
    info['last_date'] = pd.to_datetime(info['last_date'])
    
    # Fecha más temprana y más reciente en todo el cache
    global_start = info['first_date'].min()
    global_end = info['last_date'].max()
    
    # Tickers con mejor cobertura
    info['days_coverage'] = (info['last_date'] - info['first_date']).dt.days
    top_coverage = info.nlargest(10, 'days_coverage')[['ticker', 'first_date', 'last_date', 'days_coverage']]
    
    return global_start, global_end, top_coverage


def main():
    print("\n" + "="*80)
    print("📅 DATE RANGE ANALYZER")
    print("="*80)
    
    global_start, global_end, top_coverage = analyze_date_coverage()
    
    if global_start is None:
        print("\n❌ No hay datos en el cache")
        print("   Ejecuta el scanner o backtest para poblar el cache")
        return
    
    print(f"\n{'='*80}")
    print("RANGO GLOBAL DE FECHAS")
    print(f"{'='*80}")
    print(f"Fecha más temprana: {global_start.strftime('%Y-%m-%d')}")
    print(f"Fecha más reciente:  {global_end.strftime('%Y-%m-%d')}")
    print(f"Total días cubiertos: {(global_end - global_start).days:,}")
    
    print(f"\n{'='*80}")
    print("TOP 10 TICKERS CON MAYOR COBERTURA")
    print(f"{'='*80}")
    print(f"{'Ticker':<8} {'First Date':<12} {'Last Date':<12} {'Days':>8}")
    print("-"*80)
    
    for _, row in top_coverage.iterrows():
        print(f"{row['ticker']:<8} {row['first_date'].strftime('%Y-%m-%d'):<12} "
              f"{row['last_date'].strftime('%Y-%m-%d'):<12} {row['days_coverage']:>8,}")
    
    print(f"\n{'='*80}")
    print("RECOMENDACIÓN PARA BACKTEST")
    print(f"{'='*80}")
    print(f"Puedes hacer backtest desde: {global_start.strftime('%Y-%m-%d')}")
    print(f"                     hasta:  {global_end.strftime('%Y-%m-%d')}")
    print(f"\nEjemplo:")
    print(f"  python backtest_dynamic_universe.py --start {global_start.strftime('%Y-%m-%d')} --end {global_end.strftime('%Y-%m-%d')}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
