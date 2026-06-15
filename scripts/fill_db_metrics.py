#!/usr/bin/env python3
"""
Script de Mantenimiento: fill_db_metrics.py
-------------------------------------------
Rellena los valores nulos (None) de indicadores técnicos en la base de datos SQLite.
NO descarga datos de internet. Solo calcula matemáticas sobre los precios existentes.

Métricas que actualiza:
- Dollar Volume
- Rolling Dollar Volume (20d)
- SMA 20
- SMA 50
- ADR % (20d)
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def calculate_metrics(df):
    """Calcula indicadores técnicos básicos"""
    df = df.sort_values('date').copy()
    
    # 1. Dollar Volume
    df['dollar_volume'] = df['close'] * df['volume']
    df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20).mean()
    
    # 2. SMAs
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()
    df['sma100'] = df['close'].rolling(window=100).mean()
    df['sma200'] = df['close'].rolling(window=200).mean()
    
    # 3. ADR % (20 days)
    # ADR = (High - Low) / Low
    df['daily_range_pct'] = ((df['high'] - df['low']) / df['low']) * 100
    df['adr_pct_20'] = df['daily_range_pct'].rolling(window=20).mean()
    
    return df

def main():
    db_path = "data/ticker_cache.db"
    if not Path(db_path).exists():
        print("❌ No se encontró la base de datos.")
        return

    print(f"🔌 Conectando a {db_path}...")
    conn = sqlite3.connect(db_path, timeout=30.0)
    
    # --- MIGRACIÓN AUTOMÁTICA ---
    cursor = conn.execute("PRAGMA table_info(ohlcv_cache)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    for col in ["sma20", "sma50", "sma100", "sma200", "adr_pct_20"]:
        if col not in existing_cols:
            print(f"🔧 Migrando: Añadiendo columna {col}...")
            conn.execute(f"ALTER TABLE ohlcv_cache ADD COLUMN {col} REAL")
    conn.commit()
    # ----------------------------

    # Optimización de escritura
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')

    # Obtener tickers que tienen datos pero les faltan métricas (ej. sma200 es null)
    print("🔍 Buscando tickers con métricas incompletas...")
    cursor = conn.execute("""
        SELECT DISTINCT ticker 
        FROM ohlcv_cache 
        WHERE sma200 IS NULL OR adr_pct_20 IS NULL
    """)
    tickers_to_update = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Tickers a actualizar: {len(tickers_to_update)}")
    
    if not tickers_to_update:
        print("✅ La base de datos ya está optimizada. No se requieren cambios.")
        return

    start_time = time.time()
    updated_count = 0
    
    for i, ticker in enumerate(tickers_to_update):
        try:
            # Leer datos RAW
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker = ? ORDER BY date",
                conn,
                params=(ticker,)
            )
            
            if df.empty or len(df) < 20: # Need at least some days
                continue
                
            # Calcular
            df = calculate_metrics(df)
            
            # Preparar datos para update masivo
            updates = []
            for _, row in df.iterrows():
                # Actualizar si tenemos al menos SMA20 (el más básico)
                if pd.notna(row['sma20']): 
                    updates.append((
                        row['dollar_volume'],
                        row['rolling_dollar_vol_20'],
                        row['sma20'],
                        row['sma50'],
                        row['sma100'],
                        row['sma200'],
                        row['adr_pct_20'],
                        ticker,
                        row['date']
                    ))
            
            if updates:
                conn.executemany("""
                    UPDATE ohlcv_cache 
                    SET dollar_volume = ?, 
                        rolling_dollar_vol_20 = ?,
                        sma20 = ?,
                        sma50 = ?,
                        sma100 = ?,
                        sma200 = ?,
                        adr_pct_20 = ?
                    WHERE ticker = ? AND date = ?
                """, updates)
                
            updated_count += 1
            
            if i % 10 == 0:
                print(f"   ⏳ Procesando {i+1}/{len(tickers_to_update)}: {ticker} ({len(updates)} filas act.)")
                conn.commit() # Commit parcial
                
        except Exception as e:
            print(f"❌ Error en {ticker}: {e}")

    conn.commit()
    conn.close()
    
    duration = time.time() - start_time
    print("="*60)
    print(f"✅ PROCESO COMPLETADO")
    print(f"   Tickers actualizados: {updated_count}")
    print(f"   Tiempo total: {duration:.1f} segundos")
    print("="*60)

if __name__ == "__main__":
    main()
