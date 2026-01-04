"""
Populate Historical Market Cap & Average Volume
================================================
Este script agrega y puebla columnas históricas en ticker_cache.db
para eliminar el cuello de botella de requests en tiempo real.

IMPORTANTE: 
- Market Cap = Close Price × Shares Outstanding (se calcula por día)
- Average Volume = Rolling 20-day average (ya lo tienes en rolling_dollar_vol_20)
- Shares Outstanding: se obtiene UNA VEZ por ticker (cambios raros)

USO:
    python populate_historical_fundamentals.py --years 2020,2021,2022,2023,2024
    python populate_historical_fundamentals.py --all  # Todos los años disponibles
"""

import sqlite3
import pandas as pd
import yfinance as yf
from datetime import datetime
import time
from tqdm import tqdm
import argparse

class HistoricalFundamentalsPopulator:
    def __init__(self, db_path='data/ticker_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.shares_cache = {}  # Cache de shares outstanding por ticker
        
    def add_columns(self):
        """Agrega las columnas necesarias si no existen"""
        cursor = self.conn.cursor()
        
        # Check if columns exist
        cursor.execute("PRAGMA table_info(ohlcv_cache)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'market_cap' not in columns:
            print("➕ Agregando columna 'market_cap'...")
            cursor.execute("ALTER TABLE ohlcv_cache ADD COLUMN market_cap REAL")
            self.conn.commit()
            print("✅ Columna 'market_cap' agregada")
        else:
            print("✓ Columna 'market_cap' ya existe")
            
        if 'avg_volume_20' not in columns:
            print("➕ Agregando columna 'avg_volume_20'...")
            cursor.execute("ALTER TABLE ohlcv_cache ADD COLUMN avg_volume_20 REAL")
            self.conn.commit()
            print("✅ Columna 'avg_volume_20' agregada")
        else:
            print("✓ Columna 'avg_volume_20' ya existe")
            
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_date 
            ON ohlcv_cache(ticker, date)
        """)
        self.conn.commit()
        print("✅ Índices creados/verificados")
    
    def get_shares_outstanding(self, ticker):
        """Obtiene shares outstanding para un ticker (con cache)"""
        if ticker in self.shares_cache:
            return self.shares_cache[ticker]
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Intentar obtener shares outstanding
            shares = info.get('sharesOutstanding', None)
            
            # Fallback: usar impliedSharesOutstanding
            if shares is None or shares == 0:
                shares = info.get('impliedSharesOutstanding', None)
            
            # Fallback 2: Calcular desde market cap actual
            if shares is None or shares == 0:
                current_mcap = info.get('marketCap', None)
                current_price = info.get('currentPrice', None)
                if current_mcap and current_price and current_price > 0:
                    shares = current_mcap / current_price
            
            self.shares_cache[ticker] = shares
            return shares
            
        except Exception as e:
            print(f"  ⚠️ Error obteniendo shares para {ticker}: {e}")
            self.shares_cache[ticker] = None
            return None
    
    def calculate_avg_volume_20(self, ticker, date):
        """Calcula promedio de volumen últimos 20 días"""
        query = """
            SELECT volume 
            FROM ohlcv_cache 
            WHERE ticker = ? AND date <= ? 
            ORDER BY date DESC 
            LIMIT 20
        """
        cursor = self.conn.cursor()
        cursor.execute(query, (ticker, date))
        volumes = [row[0] for row in cursor.fetchall()]
        
        if len(volumes) >= 10:  # Al menos 10 días de data
            return sum(volumes) / len(volumes)
        return None
    
    def populate_ticker(self, ticker, years=None, force_update=False):
        """Puebla market cap y avg volume para un ticker específico"""
        # Get shares outstanding
        shares = self.get_shares_outstanding(ticker)
        
        if shares is None or shares == 0:
            print(f"  ⚠️ {ticker}: No se pudo obtener shares outstanding, saltando...")
            return 0
        
        # Build query with year filter
        where_clause = "ticker = ?"
        params = [ticker]
        
        if years:
            year_conditions = " OR ".join([f"strftime('%Y', date) = ?" for _ in years])
            where_clause += f" AND ({year_conditions})"
            params.extend([str(year) for year in years])
        
        if not force_update:
            where_clause += " AND (market_cap IS NULL OR avg_volume_20 IS NULL)"
        
        # Get rows to update
        query = f"SELECT date, close, volume FROM ohlcv_cache WHERE {where_clause} ORDER BY date"
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            return 0
        
        # Prepare updates
        updates = []
        for date, close, volume in rows:
            market_cap = close * shares if close and shares else None
            
            # Calculate avg_volume_20 (solo si no existe o force_update)
            avg_vol = self.calculate_avg_volume_20(ticker, date)
            
            updates.append((market_cap, avg_vol, ticker, date))
        
        # Batch update
        cursor.executemany("""
            UPDATE ohlcv_cache 
            SET market_cap = ?, avg_volume_20 = ?
            WHERE ticker = ? AND date = ?
        """, updates)
        
        self.conn.commit()
        return len(updates)
    
    def populate_all(self, years=None, force_update=False, limit_tickers=None):
        """Puebla todas las columnas para todos los tickers"""
        # Get unique tickers
        where_clause = ""
        params = []
        
        if years:
            year_conditions = " OR ".join([f"strftime('%Y', date) = ?" for _ in years])
            where_clause = f"WHERE {year_conditions}"
            params = [str(year) for year in years]
        
        query = f"SELECT DISTINCT ticker FROM ohlcv_cache {where_clause} ORDER BY ticker"
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        tickers = [row[0] for row in cursor.fetchall()]
        
        if limit_tickers:
            tickers = tickers[:limit_tickers]
        
        print(f"\n📊 Poblando datos para {len(tickers)} tickers...")
        if years:
            print(f"   Años: {', '.join(map(str, years))}")
        print(f"   Force update: {force_update}")
        print()
        
        total_updated = 0
        failed = []
        
        for ticker in tqdm(tickers, desc="Procesando tickers"):
            try:
                updated = self.populate_ticker(ticker, years, force_update)
                total_updated += updated
                
                # Rate limiting para no saturar Yahoo Finance
                if updated > 0:
                    time.sleep(0.1)  # 100ms entre requests
                    
            except Exception as e:
                print(f"\n❌ Error con {ticker}: {e}")
                failed.append(ticker)
                continue
        
        print(f"\n✅ Población completada!")
        print(f"   Total rows actualizadas: {total_updated:,}")
        print(f"   Tickers exitosos: {len(tickers) - len(failed)}")
        if failed:
            print(f"   ⚠️ Tickers fallidos: {len(failed)}")
            print(f"   Fallidos: {', '.join(failed[:10])}{'...' if len(failed) > 10 else ''}")
    
    def verify_population(self, years=None):
        """Verifica el estado de población de las columnas"""
        where_clause = ""
        params = []
        
        if years:
            year_conditions = " OR ".join([f"strftime('%Y', date) = ?" for _ in years])
            where_clause = f"WHERE {year_conditions}"
            params = [str(year) for year in years]
        
        query = f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN market_cap IS NOT NULL THEN 1 ELSE 0 END) as mcap_filled,
                SUM(CASE WHEN avg_volume_20 IS NOT NULL THEN 1 ELSE 0 END) as avgvol_filled,
                COUNT(DISTINCT ticker) as total_tickers
            FROM ohlcv_cache
            {where_clause}
        """
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        total, mcap_filled, avgvol_filled, total_tickers = row
        
        print("\n" + "="*60)
        print("📊 ESTADO DE POBLACIÓN")
        print("="*60)
        if years:
            print(f"Años analizados: {', '.join(map(str, years))}")
        print(f"Total rows:       {total:,}")
        print(f"Total tickers:    {total_tickers:,}")
        print(f"Market Cap:       {mcap_filled:,} / {total:,} ({mcap_filled/total*100:.1f}%)")
        print(f"Avg Volume 20:    {avgvol_filled:,} / {total:,} ({avgvol_filled/total*100:.1f}%)")
        print("="*60 + "\n")
    
    def close(self):
        """Cierra la conexión"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Poblar fundamentales históricos en ticker_cache.db')
    parser.add_argument('--years', type=str, help='Años a procesar (ej: 2020,2021,2022)')
    parser.add_argument('--all', action='store_true', help='Procesar todos los años')
    parser.add_argument('--force', action='store_true', help='Forzar actualización de datos existentes')
    parser.add_argument('--verify-only', action='store_true', help='Solo verificar estado sin poblar')
    parser.add_argument('--limit', type=int, help='Limitar número de tickers (para testing)')
    
    args = parser.parse_args()
    
    years = None
    if args.years:
        years = [int(y.strip()) for y in args.years.split(',')]
    
    print("🚀 Historical Fundamentals Populator")
    print("="*60)
    
    populator = HistoricalFundamentalsPopulator()
    
    try:
        # Add columns if needed
        populator.add_columns()
        
        # Verify current state
        populator.verify_population(years)
        
        if not args.verify_only:
            # Populate
            populator.populate_all(
                years=years, 
                force_update=args.force,
                limit_tickers=args.limit
            )
            
            # Verify again
            populator.verify_population(years)
        
    finally:
        populator.close()
    
    print("\n✅ Proceso completado!")
    print("\n💡 Ahora puedes usar --offline en tus backtests sin delays:")
    print("   python backtest_runner.py --offline --start 2020-01-01 --end 2020-12-31")


if __name__ == "__main__":
    main()
