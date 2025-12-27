#!/usr/bin/env python3
"""
Quick script to populate historical cache with 10 years of data
Optimized version with better progress tracking
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

def main():
    cache = TickerCache()
    
    # Get all tickers
    cursor = cache.conn.execute("SELECT ticker FROM universe ORDER BY ticker")
    all_tickers = [row[0] for row in cursor.fetchall()]
    
    start_date = (datetime.now() - timedelta(days=10*365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print("=" * 70)
    print(f"📊 POBLACIÓN DE CACHE HISTÓRICO (10 AÑOS)")
    print("=" * 70)
    print(f"Total tickers: {len(all_tickers)}")
    print(f"Período: {start_date} a {end_date}")
    print(f"Tiempo estimado: ~{len(all_tickers) * 0.5 / 60:.0f} minutos")
    print("=" * 70)
    print("\n🚀 Iniciando descarga...\n")
    
    # Check existing cache
    cursor = cache.conn.execute("""
        SELECT ticker, MIN(date) as first_date, COUNT(*) as days
        FROM ohlcv_cache
        GROUP BY ticker
    """)
    
    cached_info = {}
    for row in cursor.fetchall():
        cached_info[row[0]] = {'first_date': row[1], 'days': row[2]}
    
    success = 0
    skip = 0
    error = 0
    
    start_time = time.time()
    
    for idx, ticker in enumerate(all_tickers, 1):
        # Progress every 50 tickers
        if idx % 50 == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed
            remaining = (len(all_tickers) - idx) / rate
            print(f"\n📊 Progreso: {idx}/{len(all_tickers)} ({idx/len(all_tickers)*100:.1f}%) | ✅ {success} | ⏭️ {skip} | ❌ {error}")
            print(f"   ⏱️  Tiempo: {elapsed/60:.1f}min | ETA: {remaining/60:.1f}min")
        
        # Check if already has good data
        if ticker in cached_info:
            first = pd.to_datetime(cached_info[ticker]['first_date'])
            days = cached_info[ticker]['days']
            
            if first < pd.to_datetime(start_date) + timedelta(days=365) and days >= 1500:
                if idx % 50 == 1:  # Only print occasionally
                    print(f"⏭️  {ticker:6} - Ya tiene {days} días desde {first.strftime('%Y-%m-%d')}")
                skip += 1
                continue
        
        try:
            # Download
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
            if data.empty:
                if idx % 50 == 1:
                    print(f"⚠️  {ticker:6} - Sin datos")
                error += 1
                continue
            
            # Process
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] if isinstance(col, tuple) else col for col in data.columns]
            
            data = data.reset_index()
            data.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in data.columns]
            
            # Insert
            for _, row in data.iterrows():
                try:
                    cache.conn.execute("""
                        INSERT OR REPLACE INTO ohlcv_cache 
                        (ticker, date, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker,
                        pd.to_datetime(row['date']).strftime('%Y-%m-%d'),
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    ))
                except:
                    pass
            
            cache.conn.commit()
            
            if idx % 50 == 1 or len(data) > 2000:  # Print occasionally or if good data
                first = data['date'].min()
                last = data['date'].max()
                years = (last - first).days / 365.25
                print(f"✅ {ticker:6} - {len(data)} días ({years:.1f} años)")
            
            success += 1
            time.sleep(0.3)  # Rate limit
            
        except Exception as e:
            if idx % 50 == 1:
                print(f"❌ {ticker:6} - Error: {str(e)[:50]}")
            error += 1
    
    cache.close()
    
    total_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("✅ DESCARGA COMPLETADA")
    print("=" * 70)
    print(f"Exitosos:  {success:,}")
    print(f"Omitidos:  {skip:,} (ya tenían histórico)")
    print(f"Errores:   {error:,}")
    print(f"Total:     {len(all_tickers):,}")
    print(f"Tiempo:    {total_time/60:.1f} minutos")
    print("=" * 70)

if __name__ == "__main__":
    print("\n⚠️  Esto descargará ~10 años de datos para 5000+ tickers")
    print("⏱️  Tiempo estimado: 30-45 minutos")
    print("💾 Espacio: ~500MB adicionales")
    
    response = input("\n¿Continuar? (y/n): ")
    
    if response.lower() == 'y':
        main()
    else:
        print("❌ Cancelado")
