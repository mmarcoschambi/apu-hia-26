#!/usr/bin/env python3
"""
CACHE MANAGER - Sistema de Cache Persistente
===========================================
Cache que sobrevive entre sesiones usando SQLite
"""

import sqlite3
import pandas as pd
import pickle
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Gestiona cache persistente de datos de mercado"""
    
    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "market_cache.db"
        self._init_db()
    
    def _init_db(self):
        """Inicializa la base de datos SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla para datos históricos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_data (
                ticker TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                updated_at TEXT,
                PRIMARY KEY (ticker, date)
            )
        """)
        
        # Tabla para metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                ticker TEXT PRIMARY KEY,
                first_date TEXT,
                last_date TEXT,
                last_updated TEXT,
                record_count INTEGER
            )
        """)
        
        # Índices para búsqueda rápida
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_date 
            ON price_data(ticker, date)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Cache database initialized at {self.db_path}")
    
    def get_cached_data(self, ticker, start_date, end_date):
        """
        Obtiene datos del cache
        Returns: DataFrame o None si no hay datos completos
        """
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT date, open, high, low, close, volume
            FROM price_data
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date
        """
        
        df = pd.read_sql_query(
            query,
            conn,
            params=(ticker, start_date, end_date),
            parse_dates=['date']
        )
        
        conn.close()
        
        if len(df) == 0:
            return None
        
        df.set_index('date', inplace=True)
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        return df
    
    def save_to_cache(self, ticker, df):
        """Guarda datos en el cache"""
        if df is None or len(df) == 0:
            return
        
        conn = sqlite3.connect(self.db_path)
        
        # Preparar datos
        df_reset = df.reset_index()
        df_reset['ticker'] = ticker
        df_reset['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Renombrar columnas para coincidir con la DB
        df_reset.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'ticker', 'updated_at']
        
        # Insertar o actualizar usando una tabla temporal para manejar duplicados
        df_reset.to_sql('temp_price_data', conn, if_exists='replace', index=False)
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO price_data 
            (ticker, date, open, high, low, close, volume, updated_at)
            SELECT ticker, date, open, high, low, close, volume, updated_at 
            FROM temp_price_data
        """)
        cursor.execute("DROP TABLE temp_price_data")
        
        # Actualizar metadata
        cursor.execute("""
            INSERT OR REPLACE INTO cache_metadata 
            (ticker, first_date, last_date, last_updated, record_count)
            VALUES (?, ?, ?, ?, ?)
        """, (
            ticker,
            df_reset['date'].min(),
            df_reset['date'].max(),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            len(df_reset)
        ))
        
        conn.commit()
        conn.close()
        logger.debug(f"Cached {len(df)} records for {ticker}")
    
    def get_cache_info(self):
        """Obtiene información del cache"""
        conn = sqlite3.connect(self.db_path)
        
        df = pd.read_sql_query("""
            SELECT 
                ticker,
                first_date,
                last_date,
                last_updated,
                record_count
            FROM cache_metadata
            ORDER BY ticker
        """, conn)
        
        conn.close()
        return df
    
    def get_cache_stats(self):
        """Estadísticas generales del cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total tickers
        cursor.execute("SELECT COUNT(DISTINCT ticker) FROM price_data")
        total_tickers = cursor.fetchone()[0]
        
        # Total registros
        cursor.execute("SELECT COUNT(*) FROM price_data")
        total_records = cursor.fetchone()[0]
        
        # Rango de fechas
        cursor.execute("SELECT MIN(date), MAX(date) FROM price_data")
        date_range = cursor.fetchone()
        
        # Tamaño del archivo
        db_size_mb = self.db_path.stat().st_size / (1024 * 1024)
        
        conn.close()
        
        return {
            'total_tickers': total_tickers,
            'total_records': total_records,
            'date_range': date_range,
            'db_size_mb': db_size_mb
        }
    
    def clear_ticker(self, ticker):
        """Elimina datos de un ticker específico"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM price_data WHERE ticker = ?", (ticker,))
        cursor.execute("DELETE FROM cache_metadata WHERE ticker = ?", (ticker,))
        
        conn.commit()
        conn.close()
        logger.info(f"Cleared cache for {ticker}")
    
    def clear_all(self):
        """Limpia todo el cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM price_data")
        cursor.execute("DELETE FROM cache_metadata")
        
        conn.commit()
        conn.close()
        logger.info("Cleared all cache")
    
    def vacuum(self):
        """Optimiza la base de datos (libera espacio)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("VACUUM")
        conn.close()
        logger.info("Database vacuumed")
