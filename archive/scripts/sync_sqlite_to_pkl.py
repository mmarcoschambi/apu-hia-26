#!/usr/bin/env python3
"""
Script para sincronizar datos desde SQLite a archivos Pickle (.pkl)
y asegurar que ambos sistemas tengan los mismos datos para las pruebas de velocidad.
"""
import sys
from pathlib import Path
import pandas as pd
import time
import os
import pickle

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.data.ticker_cache import TickerCache

def sync_data():
    print("="*60)
    print("🔄 SINCRONIZACIÓN: SQLite -> Pickle (.pkl)")
    print("="*60)
    
    cache = TickerCache()
    cache_dir = Path("data/cache")
    cache_dir.mkdir(exist_ok=True)
    
    # 1. Obtener todos los tickers en SQLite
    print("🔍 Leyendo tickers disponibles en SQLite...")
    cursor = cache.conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache")
    tickers = [row[0] for row in cursor.fetchall()]
    print(f"✅ Se encontraron {len(tickers)} tickers en la base de datos.")
    
    start_time = time.time()
    synced_count = 0
    error_count = 0
    
    for i, ticker in enumerate(tickers):
        try:
            # Leer de SQLite
            query = """
                SELECT date, open, high, low, close, volume 
                FROM ohlcv_cache 
                WHERE ticker = ? 
                ORDER BY date
            """
            df = pd.read_sql_query(query, cache.conn, params=(ticker,))
            
            if df.empty:
                continue
                
            # Formatear DataFrame igual que el cache pickle antiguo
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.columns = [c.capitalize() for c in df.columns] # Open, High...
            
            # Guardar como Pickle
            pkl_path = cache_dir / f"{ticker}.pkl"
            with open(pkl_path, 'wb') as f:
                pickle.dump(df, f)
            
            synced_count += 1
            
            # Progreso
            if i % 100 == 0:
                print(f"   ⏳ Procesados {i}/{len(tickers)}...")
                
        except Exception as e:
            print(f"❌ Error con {ticker}: {e}")
            error_count += 1

    total_time = time.time() - start_time
    print("-" * 60)
    print(f"✅ Sincronización completada en {total_time:.2f} segundos.")
    print(f"📦 Archivos creados/actualizados: {synced_count}")
    print(f"⚠️ Errores: {error_count}")

if __name__ == "__main__":
    sync_data()
