#!/usr/bin/env python3
"""
Benchmark de Velocidad: SQLite vs Pickle
Mide el tiempo de lectura masiva de datos históricos.
"""
import sys
from pathlib import Path
import pandas as pd
import time
import random
import pickle
import sqlite3
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.data.ticker_cache import TickerCache

def run_benchmark():
    cache = TickerCache()
    cache_dir = Path("data/cache")
    
    # Obtener lista de tickers disponibles en ambos formatos
    print("🔍 Buscando tickers comunes...")
    sqlite_tickers = [r[0] for r in cache.conn.execute("SELECT DISTINCT ticker FROM ohlcv_cache").fetchall()]
    pkl_files = list(cache_dir.glob("*.pkl"))
    pkl_tickers = [f.stem for f in pkl_files]
    
    common_tickers = list(set(sqlite_tickers) & set(pkl_tickers))
    print(f"📊 Tickers disponibles para test: {len(common_tickers)}")
    
    if len(common_tickers) < 10:
        print("❌ No hay suficientes datos sincronizados. Corre 'sync_sqlite_to_pkl.py' primero.")
        return

    # Seleccionar muestra aleatoria
    sample_size = min(500, len(common_tickers))
    test_tickers = random.sample(common_tickers, sample_size)
    
    print(f"🧪 Iniciando prueba con {sample_size} tickers aleatorios...")
    print("=" * 60)

    # --- TEST 1: SQLITE ---
    print("\n🗄️  TEST SQLITE (Lectura secuencial)...")
    start_sql = time.time()
    rows_sql = 0
    
    # Pre-conectar para ser justos (simulando app abierta)
    conn = sqlite3.connect(cache.db_path)
    
    for ticker in test_tickers:
        query = "SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker = ?"
        # Usamos pandas read_sql que es lo estándar en data science
        df = pd.read_sql_query(query, conn, params=(ticker,))
        rows_sql += len(df)
        
    time_sql = time.time() - start_sql
    print(f"⏱️  Tiempo: {time_sql:.4f} seg")
    print(f"📈 Velocidad: {sample_size / time_sql:.1f} tickers/seg")

    # --- TEST 2: PICKLE ---
    print("\n🥒 TEST PICKLE (Lectura secuencial)...")
    start_pkl = time.time()
    rows_pkl = 0
    
    for ticker in test_tickers:
        pkl_path = cache_dir / f"{ticker}.pkl"
        with open(pkl_path, 'rb') as f:
            df = pickle.load(f)
            rows_pkl += len(df)
            
    time_pkl = time.time() - start_pkl
    print(f"⏱️  Tiempo: {time_pkl:.4f} seg")
    print(f"📈 Velocidad: {sample_size / time_pkl:.1f} tickers/seg")

    # --- RESULTADOS ---
    print("\n" + "=" * 60)
    print("🏆 RESULTADOS FINALES")
    print("=" * 60)
    
    faster = "PICKLE" if time_pkl < time_sql else "SQLITE"
    ratio = time_sql / time_pkl if time_pkl < time_sql else time_pkl / time_sql
    
    print(f"Ganador: {faster}")
    print(f"Diferencia: {ratio:.1f}x veces más rápido")
    
    print("\nConclusión:")
    if faster == "PICKLE":
        print("✅ Confirmado: Pickle es superior para cargas masivas (Backtesting).")
    else:
        print("⚠️ Sorpresa: SQLite fue más rápido (raro, pero posible en SSDs nvme rápidos con caché de OS).")

if __name__ == "__main__":
    run_benchmark()
