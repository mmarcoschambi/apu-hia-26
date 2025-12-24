#!/usr/bin/env python3
"""
CACHE INSPECTOR - Inspecciona y visualiza el cache
==================================================
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.cache_manager import CacheManager
import pandas as pd


def main():
    cache = CacheManager()
    
    print("\n" + "="*80)
    print("📊 CACHE INSPECTOR")
    print("="*80)
    
    # Estadísticas generales
    stats = cache.get_cache_stats()
    
    print(f"\n{'='*80}")
    print("ESTADÍSTICAS GENERALES")
    print(f"{'='*80}")
    print(f"Total Tickers en Cache: {stats['total_tickers']:,}")
    print(f"Total Registros: {stats['total_records']:,}")
    print(f"Rango de Fechas: {stats['date_range'][0]} → {stats['date_range'][1]}")
    print(f"Tamaño de DB: {stats['db_size_mb']:.2f} MB")
    
    # Información detallada
    info = cache.get_cache_info()
    
    if len(info) > 0:
        print(f"\n{'='*80}")
        print("DETALLE POR TICKER (primeros 50)")
        print(f"{'='*80}")
        print(f"{'Ticker':<8} {'First Date':<12} {'Last Date':<12} {'Records':>8} {'Last Updated':<20}")
        print("-"*80)
        
        for _, row in info.head(50).iterrows():
            print(f"{row['ticker']:<8} {row['first_date']:<12} {row['last_date']:<12} "
                  f"{row['record_count']:>8,} {row['last_updated']:<20}")
        
        if len(info) > 50:
            print(f"\n... y {len(info) - 50} tickers más")
        
        # Estadísticas de cobertura
        print(f"\n{'='*80}")
        print("ANÁLISIS DE COBERTURA")
        print(f"{'='*80}")
        
        info['first_date'] = pd.to_datetime(info['first_date'])
        info['last_date'] = pd.to_datetime(info['last_date'])
        info['days_coverage'] = (info['last_date'] - info['first_date']).dt.days
        
        print(f"Días promedio de cobertura: {info['days_coverage'].mean():.0f}")
        print(f"Ticker con más historia: {info.loc[info['days_coverage'].idxmax(), 'ticker']} "
              f"({info['days_coverage'].max():.0f} días)")
        print(f"Ticker con menos historia: {info.loc[info['days_coverage'].idxmin(), 'ticker']} "
              f"({info['days_coverage'].min():.0f} días)")
        
        # Actualización reciente
        info['last_updated'] = pd.to_datetime(info['last_updated'])
        recent = info[info['last_updated'] > pd.Timestamp.now() - pd.Timedelta(days=1)]
        
        print(f"\nTickers actualizados en las últimas 24h: {len(recent)}")
    
    else:
        print("\n❌ El cache está vacío")
        print("   Ejecuta el backtest para llenar el cache")
    
    print("\n" + "="*80)
    print("COMANDOS ÚTILES")
    print("="*80)
    print("# Limpiar cache de un ticker:")
    print("  python -c \"from src.data.cache_manager import CacheManager; CacheManager().clear_ticker('AAPL')\"")
    print("\n# Limpiar todo el cache:")
    print("  python -c \"from src.data.cache_manager import CacheManager; CacheManager().clear_all()\"")
    print("\n# Optimizar DB (liberar espacio):")
    print("  python -c \"from src.data.cache_manager import CacheManager; CacheManager().vacuum()\"")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
