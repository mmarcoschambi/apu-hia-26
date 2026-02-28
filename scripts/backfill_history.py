import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import sys
import os

# Configuración
DB_PATH = 'data/ticker_cache.db'
YEARS_BACK = 5  # Cuántos años hacia atrás quieres descargar
MAX_WORKERS = 10 # Hilos paralelos (no subir mucho para no ser bloqueado por Yahoo)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)

def get_existing_tickers():
    """Obtiene todos los tickers listados en la tabla universe"""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT ticker FROM universe")
        tickers = [row[0] for row in cursor.fetchall()]
        return tickers
    except Exception as e:
        logger.error(f"Error leyendo universo: {e}")
        return []
    finally:
        conn.close()

def process_ticker(ticker, start_date, end_date):
    """Descarga, procesa y guarda datos para un ticker"""
    conn = get_db_connection()
    try:
        # Descarga
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        
        if df.empty:
            return ticker, False, "No data found"
        
        # Aplanar MultiIndex si existe (fix común de yfinance reciente)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Calcular métricas derivadas necesarias para tu sistema
        # Dollar Volume = Close * Volume
        df['dollar_volume'] = df['Close'] * df['Volume']
        
        # Rolling Dollar Volume (Liquidez promedio 20 días)
        df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=1).mean()
        
        # Reset index para tener la fecha como columna
        df = df.reset_index()
        
        # Insertar en DB
        records = []
        for _, row in df.iterrows():
            records.append((
                ticker,
                row['Date'].strftime('%Y-%m-%d'),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close']),
                int(row['Volume']),
                float(row['dollar_volume']) if pd.notna(row['dollar_volume']) else 0.0,
                float(row['rolling_dollar_vol_20']) if pd.notna(row['rolling_dollar_vol_20']) else 0.0
            ))
            
        conn.executemany('''
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', records)
        
        conn.commit()
        return ticker, True, f"Saved {len(records)} days"

    except Exception as e:
        return ticker, False, str(e)
    finally:
        conn.close()

def main():
    if not os.path.exists(DB_PATH):
        logger.error(f"Base de datos no encontrada en {DB_PATH}")
        return

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=YEARS_BACK * 365)).strftime('%Y-%m-%d')
    
    logger.info(f"🚀 Iniciando Backfill de Datos")
    logger.info(f"📅 Rango: {start_date} a {end_date} ({YEARS_BACK} años)")
    
    # 1. Prioridad: Índices de Mercado (CRÍTICOS para el sistema)
    indices = ['SPY', '^VIX', 'QQQ', 'IWM', 'DIA']
    logger.info("⚡ Actualizando Índices de Mercado primero...")
    
    for idx in indices:
        _, success, msg = process_ticker(idx, start_date, end_date)
        status = "✅" if success else "❌"
        logger.info(f"{status} {idx}: {msg}")

    # 2. Resto del Universo
    tickers = get_existing_tickers()
    # Filtrar índices que ya procesamos
    tickers = [t for t in tickers if t not in indices]
    
    logger.info(f"📦 Procesando {len(tickers)} acciones del universo...")
    
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_ticker, t, start_date, end_date): t for t in tickers}
        
        for i, future in enumerate(as_completed(future_to_ticker)):
            ticker, success, msg = future.result()
            
            if success:
                success_count += 1
            else:
                fail_count += 1
                logger.warning(f"❌ {ticker}: {msg}")
            
            # Log de progreso cada 50 tickers
            if (i + 1) % 50 == 0:
                logger.info(f"📊 Progreso: {i + 1}/{len(tickers)} completados (Errors: {fail_count})")

    logger.info("=" * 40)
    logger.info(f"🎉 FINALIZADO")
    logger.info(f"✅ Exitosos: {success_count + len(indices)}")
    logger.info(f"❌ Fallidos: {fail_count}")
    logger.info("=" * 40)

if __name__ == "__main__":
    main()
