#!/usr/bin/env python3
"""
CACHE INSPECTOR - Verifica qué datos tienes y qué te falta
============================================================

Este script te muestra:
- Qué tickers tienes en cache
- Rangos de fechas disponibles
- Gaps en los datos
- Tamaño del cache
- Calidad de los datos
"""

import os
import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import json

# Añadir src al path
sys.path.append(str(Path(__file__).parent))

from src.data.market_data import MarketDataProvider

class CacheInspector:
    """Inspecciona el estado del cache de datos"""
    
    def __init__(self):
        self.data_provider = MarketDataProvider()
        # El cache está en ./data/cache en el proyecto
        self.cache_dir = Path('./data/cache')
        
    def get_cache_stats(self):
        """Obtiene estadísticas generales del cache"""
        if not self.cache_dir.exists():
            return {
                'exists': False,
                'total_files': 0,
                'total_size_mb': 0,
                'tickers': []
            }
        
        files = list(self.cache_dir.glob('*.pkl'))
        total_size = sum(f.stat().st_size for f in files)
        
        # Extraer tickers de los nombres de archivo
        tickers = set()
        for f in files:
            # Formato: TICKER_daily.pkl o TICKER_earnings.pkl
            parts = f.stem.split('_')
            if len(parts) >= 2 and parts[1] == 'daily':
                tickers.add(parts[0])
        
        return {
            'exists': True,
            'total_files': len(files),
            'total_size_mb': total_size / (1024 * 1024),
            'tickers': sorted(tickers),
            'cache_dir': str(self.cache_dir.absolute())
        }
    
    def inspect_ticker(self, ticker):
        """Inspecciona datos disponibles para un ticker específico"""
        print(f"\n{'='*80}")
        print(f"📊 INSPECTING: {ticker}")
        print(f"{'='*80}")
        
        results = {
            'ticker': ticker,
            'daily': None,
            'intraday': None
        }
        
        # 1. Datos DAILY
        daily_file = self.cache_dir / f"{ticker}_daily.pkl"
        if daily_file.exists():
            try:
                import pickle
                with open(daily_file, 'rb') as f:
                    df = pickle.load(f)
                
                if isinstance(df, pd.DataFrame) and not df.empty:
                    first_date = df.index.min()
                    last_date = df.index.max()
                    total_days = len(df)
                    
                    # Calcular gaps
                    date_range = pd.date_range(first_date, last_date, freq='B')
                    expected_days = len(date_range)
                    missing_days = expected_days - total_days
                    completeness = (total_days / expected_days) * 100 if expected_days > 0 else 0
                    
                    results['daily'] = {
                        'exists': True,
                        'first_date': first_date,
                        'last_date': last_date,
                        'total_days': total_days,
                        'missing_days': missing_days,
                        'completeness': completeness,
                        'size_mb': daily_file.stat().st_size / (1024 * 1024),
                        'age_days': (datetime.now() - datetime.fromtimestamp(daily_file.stat().st_mtime)).days
                    }
                    
                    print(f"\n✅ DAILY DATA:")
                    print(f"   File: {daily_file.name}")
                    print(f"   Range: {first_date.date()} → {last_date.date()}")
                    print(f"   Total bars: {total_days}")
                    print(f"   Missing days: {missing_days} ({100-completeness:.1f}%)")
                    print(f"   Completeness: {completeness:.1f}%")
                    print(f"   Size: {results['daily']['size_mb']:.2f} MB")
                    print(f"   Last updated: {results['daily']['age_days']} days ago")
                    
                    # Columnas disponibles
                    print(f"   Columns: {', '.join(df.columns)}")
                    
                    # Últimos 5 datos
                    print(f"\n   Last 5 bars:")
                    print(df.tail(5)[['Open', 'High', 'Low', 'Close', 'Volume']].to_string())
                else:
                    print(f"\n❌ DAILY DATA: Empty dataframe")
                    results['daily'] = {'exists': True, 'error': 'Empty dataframe'}
                
            except Exception as e:
                print(f"\n❌ DAILY DATA: Error reading - {e}")
                results['daily'] = {'exists': True, 'error': str(e)}
        else:
            print(f"\n❌ DAILY DATA: Not in cache")
            results['daily'] = {'exists': False}
        
        return results
    
    def check_backtest_readiness(self, start_date, end_date, tickers):
        """Verifica si tienes datos suficientes para un backtest"""
        print(f"\n{'='*80}")
        print(f"🔍 BACKTEST READINESS CHECK")
        print(f"{'='*80}")
        print(f"Period: {start_date} → {end_date}")
        print(f"Tickers to check: {len(tickers)}")
        print(f"{'='*80}\n")
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        ready = []
        missing = []
        incomplete = []
        
        import pickle
        
        for ticker in tickers:
            daily_file = self.cache_dir / f"{ticker}_daily.pkl"
            
            if not daily_file.exists():
                missing.append(ticker)
                continue
            
            try:
                with open(daily_file, 'rb') as f:
                    df = pickle.load(f)
                
                if not isinstance(df, pd.DataFrame) or df.empty:
                    missing.append(ticker)
                    continue
                
                first_date = df.index.min()
                last_date = df.index.max()
                
                # Verificar si cubre el rango
                if first_date <= start_dt and last_date >= end_dt:
                    ready.append(ticker)
                else:
                    incomplete.append({
                        'ticker': ticker,
                        'has': f"{first_date.date()} → {last_date.date()}",
                        'needs': f"{start_date} → {end_date}"
                    })
            except Exception as e:
                missing.append(ticker)
        
        # Reporte
        print(f"✅ READY: {len(ready)}/{len(tickers)} ({len(ready)/len(tickers)*100:.1f}%)")
        print(f"⚠️  INCOMPLETE: {len(incomplete)}")
        print(f"❌ MISSING: {len(missing)}")
        
        if incomplete:
            print(f"\n⚠️  INCOMPLETE TICKERS:")
            for item in incomplete[:10]:  # Mostrar solo primeros 10
                print(f"   {item['ticker']}: Has {item['has']}, needs {item['needs']}")
            if len(incomplete) > 10:
                print(f"   ... and {len(incomplete)-10} more")
        
        if missing:
            print(f"\n❌ MISSING TICKERS:")
            print(f"   {', '.join(missing[:20])}")
            if len(missing) > 20:
                print(f"   ... and {len(missing)-20} more")
        
        return {
            'total': len(tickers),
            'ready': len(ready),
            'incomplete': len(incomplete),
            'missing': len(missing),
            'ready_pct': (len(ready)/len(tickers)*100) if tickers else 0
        }
    
    def download_missing(self, ticker, start_date=None, end_date=None):
        """Descarga datos faltantes para un ticker"""
        print(f"\n📥 Downloading {ticker}...")
        
        if not start_date:
            start_date = "2020-01-01"
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            # Usar el data provider que ya tiene cache
            df = self.data_provider.get_daily_data(
                ticker,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty:
                print(f"   ✅ Downloaded {len(df)} bars")
                print(f"   Range: {df.index.min().date()} → {df.index.max().date()}")
                return True
            else:
                print(f"   ❌ No data returned")
                return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    def summary(self):
        """Muestra resumen general del cache"""
        stats = self.get_cache_stats()
        
        print(f"\n{'='*80}")
        print(f"📦 CACHE SUMMARY")
        print(f"{'='*80}")
        
        if not stats['exists']:
            print(f"\n❌ NO CACHE FOUND")
            print(f"   Expected location: {self.cache_dir}")
            print(f"   Run a backtest first to populate cache")
            return
        
        print(f"\n📁 Cache directory: {stats['cache_dir']}")
        print(f"📊 Total files: {stats['total_files']}")
        print(f"💾 Total size: {stats['total_size_mb']:.2f} MB")
        print(f"📈 Tickers cached: {len(stats['tickers'])}")
        
        if stats['tickers']:
            print(f"\n🎯 Sample tickers:")
            sample = stats['tickers'][:20]
            for i in range(0, len(sample), 10):
                print(f"   {', '.join(sample[i:i+10])}")
            
            if len(stats['tickers']) > 20:
                print(f"   ... and {len(stats['tickers'])-20} more")
        
        print(f"\n{'='*80}")
        
        return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Inspect market data cache')
    parser.add_argument('--ticker', type=str, help='Inspect specific ticker')
    parser.add_argument('--check-backtest', nargs=3, metavar=('START', 'END', 'TICKERS_FILE'),
                       help='Check readiness for backtest')
    parser.add_argument('--download', type=str, help='Download missing data for ticker')
    parser.add_argument('--start', type=str, default='2020-01-01', help='Start date for download')
    parser.add_argument('--end', type=str, help='End date for download (default: today)')
    
    args = parser.parse_args()
    
    inspector = CacheInspector()
    
    if args.ticker:
        # Inspeccionar ticker específico
        inspector.inspect_ticker(args.ticker)
    
    elif args.check_backtest:
        # Verificar si estamos listos para un backtest
        start, end, tickers_file = args.check_backtest
        
        # Leer lista de tickers
        if tickers_file.endswith('.json'):
            with open(tickers_file) as f:
                data = json.load(f)
                if isinstance(data, list):
                    tickers = data
                elif isinstance(data, dict) and 'tickers' in data:
                    tickers = data['tickers']
                else:
                    print(f"❌ Invalid JSON format")
                    return
        else:
            # Asumir que es una lista de tickers separados por coma
            tickers = tickers_file.split(',')
        
        inspector.check_backtest_readiness(start, end, tickers)
    
    elif args.download:
        # Descargar datos para un ticker
        end_date = args.end or datetime.now().strftime('%Y-%m-%d')
        inspector.download_missing(args.download, args.start, end_date)
    
    else:
        # Mostrar resumen general
        inspector.summary()
        
        print(f"\n💡 USAGE EXAMPLES:")
        print(f"   ./inspect_cache.py                           # General summary")
        print(f"   ./inspect_cache.py --ticker AAPL             # Inspect specific ticker")
        print(f"   ./inspect_cache.py --download AAPL           # Download missing data")
        print(f"   ./inspect_cache.py --download AAPL --start 2020-01-01")


if __name__ == "__main__":
    main()
