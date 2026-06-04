import sqlite3
import yfinance as yf
import pandas as pd
from pathlib import Path
import logging
import time
from typing import List, Dict

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = Path("data/ticker_cache.db")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def ensure_universe_table():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS universe (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT,
            sector TEXT,
            industry TEXT,
            last_updated DATE
        )
    """)
    conn.commit()
    conn.close()

def sync_tickers_from_rankings():
    """Inserta tickers de daily_rs_rankings que no estén en universe."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    logger.info("Sincronizando tickers desde daily_rs_rankings...")
    cursor.execute("""
        INSERT OR IGNORE INTO universe (ticker)
        SELECT DISTINCT ticker FROM daily_rs_rankings
    """)
    
    rows_added = cursor.rowcount
    conn.commit()
    conn.close()
    logger.info(f"Se añadieron {rows_added} nuevos tickers a la tabla universe.")

def populate_sectors_batch(batch_size=50):
    """Puebla sector e industria usando yfinance en lotes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Obtener tickers que no tienen sector
    cursor.execute("SELECT ticker FROM universe WHERE sector IS NULL OR sector = ''")
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not tickers:
        logger.info("No hay tickers pendientes de sector/industria.")
        return

    logger.info(f"Poblando {len(tickers)} tickers. Usando lotes de {batch_size}.")
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        logger.info(f"Procesando lote {i//batch_size + 1}/{(len(tickers)-1)//batch_size + 1} ({len(batch)} tickers)...")
        
        # yfinance no permite bajar 'info' en batch de forma eficiente para campos específicos
        # pero podemos intentar optimizar o simplemente iterar con cuidado.
        for ticker in batch:
            try:
                t = yf.Ticker(ticker)
                info = t.info
                
                sector = info.get('sector')
                industry = info.get('industry')
                name = info.get('longName')
                exchange = info.get('exchange')
                
                if sector or industry:
                    conn = get_db_connection()
                    conn.execute("""
                        UPDATE universe 
                        SET sector = ?, industry = ?, name = ?, exchange = ?, last_updated = CURRENT_DATE
                        WHERE ticker = ?
                    """, (sector, industry, name, exchange, ticker))
                    conn.commit()
                    conn.close()
                    logger.info(f"✅ {ticker}: {sector} | {industry}")
                else:
                    logger.warning(f"⚠️ {ticker}: No se encontró información.")
                    # Marcar como 'Unknown' para no reintentar infinitamente hoy
                    conn = get_db_connection()
                    conn.execute("UPDATE universe SET sector = 'Unknown', last_updated = CURRENT_DATE WHERE ticker = ?", (ticker,))
                    conn.commit()
                    conn.close()
                
            except Exception as e:
                logger.error(f"❌ Error procesando {ticker}: {e}")
                time.sleep(1) # Pequeña pausa si hay error de rate limit
        
        # Pausa entre lotes para evitar bloqueos de yfinance
        time.sleep(2)

def main():
    if not DB_PATH.exists():
        logger.error(f"No se encontró la base de datos en {DB_PATH}")
        return

    ensure_universe_table()
    sync_tickers_from_rankings()
    
    # Opcional: Podríamos meter aquí la Opción C (hardcode) si quisiéramos rapidez inicial
    # Pero vamos a intentar el batch primero.
    populate_sectors_batch(batch_size=20)

if __name__ == "__main__":
    main()
