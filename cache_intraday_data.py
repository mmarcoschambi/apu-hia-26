#!/usr/bin/env python3
"""
Intraday Data Cacher
====================
Descarga y cachea datos intraday (5m) para el universo de trading.

YFinance permite:
- 60 días de datos intraday gratis
- Intervalos: 1m, 2m, 5m, 15m, 30m, 60m, 90m

Estrategia de Cache:
- Guarda últimos 60 días en SQLite
- Actualiza diariamente solo el día actual
- Compresión eficiente (solo 5min bars)

USO:
    # Cache todo el universo
    python3 cache_intraday_data.py --universe universe_tickers.txt
    
    # Cache tickers específicos
    python3 cache_intraday_data.py --tickers TSLA,NVDA,AAPL
    
    # Solo actualizar hoy
    python3 cache_intraday_data.py --update-today
"""

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import time
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntradayCacheManager:
    def __init__(self, db_path='data/intraday_cache.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Crea tabla para datos intraday"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intraday_5m (
                ticker TEXT NOT NULL,
                datetime TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                vwap REAL,
                PRIMARY KEY (ticker, datetime)
            )
        """)
        
        # Índices para queries rápidas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_datetime 
            ON intraday_5m(ticker, datetime DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_datetime 
            ON intraday_5m(datetime DESC)
        """)
        
        self.conn.commit()
        logger.info("✅ Database tables created/verified")
    
    def fetch_intraday(self, ticker, days=60, interval='5m'):
        """
        Descarga datos intraday de YFinance
        
        Args:
            ticker: Symbol
            days: Días históricos (max 60 para free)
            interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m
        """
        try:
            # YFinance period syntax
            if days <= 7:
                period = f'{days}d'
            elif days <= 60:
                period = '60d'
            else:
                period = '60d'  # Free tier limit
            
            df = yf.download(
                ticker, 
                period=period,
                interval=interval,
                progress=False
            )
            
            if df.empty:
                logger.warning(f"⚠️ {ticker}: No data returned")
                return pd.DataFrame()
            
            # Lowercase columns
            df.columns = [c.lower() for c in df.columns]
            
            # Calculate VWAP if not present
            if 'vwap' not in df.columns:
                if df['volume'].sum() > 0:
                    typical_price = (df['high'] + df['low'] + df['close']) / 3
                    df['vwap'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
                else:
                    df['vwap'] = (df['high'] + df['low'] + df['close']) / 3
            
            # Reset index to get datetime as column
            df = df.reset_index()
            df['ticker'] = ticker
            
            # Rename datetime column if needed
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'datetime'})
            
            return df[['ticker', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'vwap']]
            
        except Exception as e:
            logger.error(f"❌ {ticker}: {e}")
            return pd.DataFrame()
    
    def cache_ticker(self, ticker, days=60, replace=False):
        """
        Cachea datos intraday para un ticker
        
        Args:
            replace: Si True, borra datos existentes antes de insertar
        """
        df = self.fetch_intraday(ticker, days)
        
        if df.empty:
            return 0
        
        # Convert datetime to string for SQLite
        df['datetime'] = df['datetime'].astype(str)
        
        cursor = self.conn.cursor()
        
        if replace:
            cursor.execute("DELETE FROM intraday_5m WHERE ticker = ?", (ticker,))
        
        # Insert new data (ignore conflicts = update mode)
        df.to_sql('intraday_5m', self.conn, if_exists='append', index=False)
        self.conn.commit()
        
        return len(df)
    
    def update_today(self, ticker):
        """Actualiza solo el día actual (más rápido para uso diario)"""
        try:
            # Get today's data only
            df = yf.download(
                ticker,
                period='1d',
                interval='5m',
                progress=False
            )
            
            if df.empty:
                return 0
            
            df.columns = [c.lower() for c in df.columns]
            df = df.reset_index()
            df['ticker'] = ticker
            
            # Calculate VWAP
            if 'vwap' not in df.columns:
                typical_price = (df['high'] + df['low'] + df['close']) / 3
                df['vwap'] = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
            
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'datetime'})
            
            df['datetime'] = df['datetime'].astype(str)
            
            # Delete today's data and reinsert
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM intraday_5m WHERE ticker = ? AND date(datetime) = ?",
                (ticker, today)
            )
            
            df[['ticker', 'datetime', 'open', 'high', 'low', 'close', 'volume', 'vwap']].to_sql(
                'intraday_5m', self.conn, if_exists='append', index=False
            )
            self.conn.commit()
            
            return len(df)
            
        except Exception as e:
            logger.error(f"❌ {ticker}: {e}")
            return 0
    
    def get_cached_data(self, ticker, days=5):
        """Recupera datos cacheados"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT datetime, open, high, low, close, volume, vwap
            FROM intraday_5m
            WHERE ticker = ? AND datetime >= ?
            ORDER BY datetime
        """
        
        df = pd.read_sql_query(query, self.conn, params=(ticker, cutoff))
        
        if not df.empty:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
        
        return df
    
    def stats(self):
        """Estadísticas del cache"""
        cursor = self.conn.cursor()
        
        # Total rows
        cursor.execute("SELECT COUNT(*) FROM intraday_5m")
        total_rows = cursor.fetchone()[0]
        
        # Total tickers
        cursor.execute("SELECT COUNT(DISTINCT ticker) FROM intraday_5m")
        total_tickers = cursor.fetchone()[0]
        
        # Date range
        cursor.execute("SELECT MIN(datetime), MAX(datetime) FROM intraday_5m")
        date_range = cursor.fetchone()
        
        # Size
        import os
        size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
        
        print("\n" + "="*60)
        print("📊 INTRADAY CACHE STATS")
        print("="*60)
        print(f"Total Rows:     {total_rows:,}")
        print(f"Total Tickers:  {total_tickers:,}")
        print(f"Date Range:     {date_range[0]} → {date_range[1]}")
        print(f"Database Size:  {size_mb:.2f} MB")
        print("="*60 + "\n")
    
    def close(self):
        self.conn.close()


def load_universe_file(filepath):
    """Carga tickers desde archivo"""
    tickers = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                line_tickers = [t.strip() for t in line.split(',') if t.strip()]
                tickers.extend(line_tickers)
    return sorted(list(set(tickers)))


def main():
    parser = argparse.ArgumentParser(description='Cache intraday data for trading universe')
    parser.add_argument('--universe', type=str, help='Path to universe file (tickers)')
    parser.add_argument('--tickers', type=str, help='Comma-separated ticker list')
    parser.add_argument('--update-today', action='store_true', help='Only update today (faster)')
    parser.add_argument('--days', type=int, default=60, help='Days of history to cache (max 60)')
    parser.add_argument('--stats-only', action='store_true', help='Show stats and exit')
    parser.add_argument('--replace', action='store_true', help='Replace existing data')
    parser.add_argument('--limit', type=int, help='Limit number of tickers (testing)')
    
    args = parser.parse_args()
    
    print("🚀 Intraday Data Cacher")
    print("="*60)
    
    cache = IntradayCacheManager()
    
    try:
        # Show stats
        if args.stats_only:
            cache.stats()
            return
        
        # Load tickers
        if args.universe:
            tickers = load_universe_file(args.universe)
        elif args.tickers:
            tickers = [t.strip() for t in args.tickers.split(',')]
        else:
            print("❌ Must provide --universe or --tickers")
            return
        
        if args.limit:
            tickers = tickers[:args.limit]
        
        print(f"Processing {len(tickers)} tickers...")
        print()
        
        # Cache data
        total_rows = 0
        failed = []
        
        for ticker in tqdm(tickers, desc="Caching"):
            try:
                if args.update_today:
                    rows = cache.update_today(ticker)
                else:
                    rows = cache.cache_ticker(ticker, days=args.days, replace=args.replace)
                
                total_rows += rows
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed {ticker}: {e}")
                failed.append(ticker)
        
        print(f"\n✅ Caching completed!")
        print(f"   Total rows: {total_rows:,}")
        print(f"   Success: {len(tickers) - len(failed)}/{len(tickers)}")
        if failed:
            print(f"   Failed: {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")
        
        # Show final stats
        cache.stats()
        
    finally:
        cache.close()
    
    print("\n💡 Now you can use cached intraday data in your scanner!")
    print("   Example: cache.get_cached_data('TSLA', days=5)")


if __name__ == "__main__":
    main()
