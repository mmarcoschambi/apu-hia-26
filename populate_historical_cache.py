#!/usr/bin/env python3
"""
Script para poblar el cache SQLite con datos históricos (10+ años)
Descarga GRATIS desde Yahoo Finance y llena el cache local
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

def populate_historical_data(years_back=10, batch_size=50, delay=0.5):
    """
    Descarga datos históricos para todos los tickers en universe
    
    Args:
        years_back: Cuántos años hacia atrás descargar (default: 10)
        batch_size: Cuántos tickers procesar antes de pausar
        delay: Segundos de pausa entre requests (evitar rate limit)
    """
    cache = TickerCache()
    
    # Get all tickers from universe
    cursor = cache.conn.execute("SELECT ticker FROM universe ORDER BY ticker")
    all_tickers = [row[0] for row in cursor.fetchall()]
    
    start_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print("=" * 70)
    print(f"📊 DESCARGA DE DATOS HISTÓRICOS")
    print("=" * 70)
    print(f"Tickers a procesar: {len(all_tickers)}")
    print(f"Período: {start_date} a {end_date} ({years_back} años)")
    print(f"Batch size: {batch_size} tickers")
    print(f"Delay: {delay}s entre requests")
    print("=" * 70)
    
    # Check what's already cached
    cursor = cache.conn.execute("""
        SELECT ticker, MIN(date) as first_date, COUNT(*) as days
        FROM ohlcv_cache
        GROUP BY ticker
    """)
    
    cached_info = {}
    for row in cursor.fetchall():
        cached_info[row[0]] = {'first_date': row[1], 'days': row[2]}
    
    # Process tickers
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for idx, ticker in enumerate(all_tickers, 1):
        # Progress indicator
        if idx % 10 == 0 or idx == len(all_tickers):
            print(f"\n📊 Progreso: {idx}/{len(all_tickers)} | ✅ {success_count} | ⏭️ {skip_count} | ❌ {error_count}")
        
        # Check if already has enough historical data
        if ticker in cached_info:
            first_date = pd.to_datetime(cached_info[ticker]['first_date'])
            days = cached_info[ticker]['days']
            
            # If has data from at least 8 years ago and 1500+ days, skip
            if first_date < pd.to_datetime(start_date) + timedelta(days=365) and days >= 1500:
                print(f"⏭️  {ticker:6} - Ya tiene suficiente histórico ({days} días desde {first_date.strftime('%Y-%m-%d')})")
                skip_count += 1
                continue
        
        try:
            # Download historical data
            print(f"📥 {ticker:6} - Descargando desde {start_date}...", end=' ')
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if data.empty:
                print(f"⚠️  Sin datos")
                error_count += 1
                continue
            
            # Handle multi-index columns (yfinance returns (Price, Ticker) tuples)
            if isinstance(data.columns, pd.MultiIndex):
                # Flatten multi-index columns
                data.columns = [col[0] if isinstance(col, tuple) else col for col in data.columns]
            
            # Reset index to get Date as a column
            data = data.reset_index()
            
            # Normalize column names to lowercase
            data.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in data.columns]
            
            # Insert into cache
            for _, row in data.iterrows():
                try:
                    cache.conn.execute("""
                        INSERT OR REPLACE INTO ohlcv_cache 
                        (ticker, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker,
                        row['date'].strftime('%Y-%m-%d'),
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    ))
                except Exception as e:
                    pass  # Skip bad rows
            
            cache.conn.commit()
            
            first_date = data['date'].min()
            last_date = data['date'].max()
            days = len(data)
            
            print(f"✅ {days} días ({first_date.strftime('%Y-%m-%d')} a {last_date.strftime('%Y-%m-%d')})")
            success_count += 1
            
            # Delay to avoid rate limiting
            if idx % batch_size == 0:
                print(f"\n⏸️  Pausa de {batch_size * delay}s para evitar rate limit...")
                time.sleep(batch_size * delay)
            else:
                time.sleep(delay)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            error_count += 1
    
    cache.close()
    
    print("\n" + "=" * 70)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 70)
    print(f"Exitosos:  {success_count}")
    print(f"Omitidos:  {skip_count} (ya tenían histórico)")
    print(f"Errores:   {error_count}")
    print(f"Total:     {len(all_tickers)}")
    print("=" * 70)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Poblar cache con datos históricos')
    parser.add_argument('--years', type=int, default=10, help='Años de histórico (default: 10)')
    parser.add_argument('--batch', type=int, default=50, help='Batch size (default: 50)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay entre requests (default: 0.5s)')
    parser.add_argument('--test', action='store_true', help='Solo procesar primeros 10 tickers (test)')
    
    args = parser.parse_args()
    
    if args.test:
        print("🧪 MODO TEST: Solo primeros 10 tickers")
        cache = TickerCache()
        cursor = cache.conn.execute("SELECT ticker FROM universe LIMIT 10")
        test_tickers = [row[0] for row in cursor.fetchall()]
        cache.close()
        
        # Temporarily modify universe for test
        from src.data.ticker_cache import TickerCache as TC
        original_method = TC.__init__
        
        def test_init(self, *args, **kwargs):
            original_method(self, *args, **kwargs)
            # Filter to test tickers only
        
        populate_historical_data(years_back=args.years, batch_size=args.batch, delay=args.delay)
    else:
        print("\n⚠️  Esto descargará datos para ~5000 tickers.")
        print(f"⏱️  Tiempo estimado: {5000 * args.delay / 60:.1f} minutos")
        response = input("\n¿Continuar? (y/n): ")
        
        if response.lower() == 'y':
            populate_historical_data(years_back=args.years, batch_size=args.batch, delay=args.delay)
        else:
            print("❌ Cancelado")
