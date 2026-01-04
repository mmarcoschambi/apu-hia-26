#!/usr/bin/env python3
"""
Script para poblar el cache SQLite con datos históricos usando OpenBB
Descarga datos históricos y calcula TODAS las métricas automáticamente:
- OHLCV básico
- Dollar volume (dollar_volume, rolling_dollar_vol_20)
- Volume metrics (avg_volume_20)
- ADR (adr_14, adr_pct_14)
- SMAs (sma_50, sma_200)
- Trend flags (price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned)
- Market cap (si está disponible)

Uso:
    python populate_historical_openbb.py --years 20
    python populate_historical_openbb.py --years 5 --tickers AAPL MSFT GOOGL
    python populate_historical_openbb.py --test  # Solo 10 tickers para prueba
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
from src.data.openbb_data import OpenBBData
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HistoricalDataPopulator:
    """Poblador de datos históricos con todas las métricas calculadas"""
    
    def __init__(self):
        self.cache = TickerCache()
        self.openbb = OpenBBData()
        
    def calculate_all_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula TODAS las métricas para un DataFrame de OHLCV
        
        Métricas calculadas:
        - dollar_volume: close * volume
        - rolling_dollar_vol_20: promedio móvil 20 días de dollar_volume
        - avg_volume_20: promedio móvil 20 días de volume
        - adr_14: Average Daily Range en $ (14 días)
        - adr_pct_14: Average Daily Range en % (14 días)
        - sma_50: Simple Moving Average 50 días
        - sma_200: Simple Moving Average 200 días
        - price_above_sma50: 1 si precio > SMA50, 0 si no
        - price_above_sma200: 1 si precio > SMA200, 0 si no
        - sma50_above_sma200: 1 si SMA50 > SMA200, 0 si no
        - trend_aligned: 1 si todas las condiciones anteriores son True
        """
        # Normalizar nombres de columnas
        df.columns = [c.lower() if isinstance(c, str) else str(c).lower() for c in df.columns]
        
        # 1. Dollar Volume
        df['dollar_volume'] = df['close'] * df['volume']
        df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20, min_periods=1).mean()
        
        # 2. Average Volume
        df['avg_volume_20'] = df['volume'].rolling(window=20, min_periods=1).mean()
        
        # 3. ADR (Average Daily Range)
        df['daily_range'] = df['high'] - df['low']
        df['daily_range_pct'] = (df['daily_range'] / df['low']) * 100
        df['adr_14'] = df['daily_range'].rolling(window=14, min_periods=1).mean()
        df['adr_pct_14'] = df['daily_range_pct'].rolling(window=14, min_periods=1).mean()
        
        # 4. SMAs
        df['sma_50'] = df['close'].rolling(window=50, min_periods=1).mean()
        df['sma_200'] = df['close'].rolling(window=200, min_periods=1).mean()
        
        # 5. Trend Flags
        df['price_above_sma50'] = (df['close'] > df['sma_50']).astype(int)
        df['price_above_sma200'] = (df['close'] > df['sma_200']).astype(int)
        df['sma50_above_sma200'] = (df['sma_50'] > df['sma_200']).astype(int)
        df['trend_aligned'] = (
            (df['price_above_sma50'] == 1) & 
            (df['sma50_above_sma200'] == 1)
        ).astype(int)
        
        # Eliminar columnas temporales
        df.drop(['daily_range', 'daily_range_pct'], axis=1, inplace=True)
        
        return df
    
    def populate_ticker(self, ticker: str, start_date: str, end_date: str) -> dict:
        """
        Descarga y procesa datos para un ticker específico
        
        Returns:
            dict con estadísticas del proceso
        """
        try:
            # Descargar datos históricos usando OpenBB
            logger.info(f"📥 {ticker:6} - Descargando desde OpenBB...")
            df = self.openbb.get_historical_data(
                symbol=ticker,
                start_date=start_date,
                end_date=end_date,
                interval="1d"
            )
            
            if df is None or df.empty:
                logger.warning(f"⚠️  {ticker:6} - Sin datos")
                return {'status': 'error', 'message': 'No data'}
            
            # Calcular todas las métricas
            df = self.calculate_all_metrics(df)
            
            # Insertar en base de datos
            rows_inserted = 0
            for date, row in df.iterrows():
                try:
                    # Preparar valores, reemplazar NaN con None
                    values = (
                        ticker,
                        date.strftime('%Y-%m-%d'),
                        float(row['open']) if not pd.isna(row['open']) else None,
                        float(row['high']) if not pd.isna(row['high']) else None,
                        float(row['low']) if not pd.isna(row['low']) else None,
                        float(row['close']) if not pd.isna(row['close']) else None,
                        int(row['volume']) if not pd.isna(row['volume']) else 0,
                        float(row['dollar_volume']) if not pd.isna(row['dollar_volume']) else None,
                        float(row['rolling_dollar_vol_20']) if not pd.isna(row['rolling_dollar_vol_20']) else None,
                        None,  # market_cap - se puede agregar después si está disponible
                        float(row['avg_volume_20']) if not pd.isna(row['avg_volume_20']) else None,
                        float(row['adr_14']) if not pd.isna(row['adr_14']) else None,
                        float(row['adr_pct_14']) if not pd.isna(row['adr_pct_14']) else None,
                        float(row['sma_50']) if not pd.isna(row['sma_50']) else None,
                        float(row['sma_200']) if not pd.isna(row['sma_200']) else None,
                        int(row['price_above_sma50']) if not pd.isna(row['price_above_sma50']) else 0,
                        int(row['price_above_sma200']) if not pd.isna(row['price_above_sma200']) else 0,
                        int(row['sma50_above_sma200']) if not pd.isna(row['sma50_above_sma200']) else 0,
                        int(row['trend_aligned']) if not pd.isna(row['trend_aligned']) else 0
                    )
                    
                    self.cache.conn.execute("""
                        INSERT OR REPLACE INTO ohlcv_cache 
                        (ticker, date, open, high, low, close, volume,
                         dollar_volume, rolling_dollar_vol_20, market_cap, avg_volume_20,
                         adr_14, adr_pct_14, sma_50, sma_200,
                         price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, values)
                    
                    rows_inserted += 1
                    
                except Exception as e:
                    logger.debug(f"Error insertando fila para {ticker} en {date}: {e}")
                    continue
            
            self.cache.conn.commit()
            
            first_date = df.index.min()
            last_date = df.index.max()
            
            logger.info(f"✅ {ticker:6} - {rows_inserted} días ({first_date.strftime('%Y-%m-%d')} a {last_date.strftime('%Y-%m-%d')})")
            
            return {
                'status': 'success',
                'ticker': ticker,
                'rows': rows_inserted,
                'first_date': first_date,
                'last_date': last_date
            }
            
        except Exception as e:
            logger.error(f"❌ {ticker:6} - Error: {e}")
            return {'status': 'error', 'ticker': ticker, 'message': str(e)}
    
    def check_existing_data(self, ticker: str, start_date: str) -> dict:
        """Verifica si el ticker ya tiene suficientes datos históricos"""
        cursor = self.cache.conn.execute("""
            SELECT MIN(date) as first_date, MAX(date) as last_date, COUNT(*) as days
            FROM ohlcv_cache
            WHERE ticker = ?
        """, (ticker,))
        
        row = cursor.fetchone()
        if row and row[0]:
            return {
                'has_data': True,
                'first_date': row[0],
                'last_date': row[1],
                'days': row[2]
            }
        
        return {'has_data': False}
    
    def populate_all(self, tickers: list, years_back: int = 20, delay: float = 0.3, skip_existing: bool = True):
        """
        Pobla datos históricos para una lista de tickers
        
        Args:
            tickers: Lista de símbolos a descargar
            years_back: Años de histórico a descargar
            delay: Segundos de pausa entre requests
            skip_existing: Si True, omite tickers que ya tienen datos completos
        """
        start_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')
        end_date = datetime.now().strftime('%Y-%m-%d')
        
        print("=" * 80)
        print(f"📊 DESCARGA DE DATOS HISTÓRICOS CON OPENBB")
        print("=" * 80)
        print(f"Tickers a procesar: {len(tickers)}")
        print(f"Período: {start_date} a {end_date} ({years_back} años)")
        print(f"Delay: {delay}s entre requests")
        print(f"Skip existing: {'Sí' if skip_existing else 'No'}")
        print("=" * 80 + "\n")
        
        stats = {
            'success': 0,
            'skipped': 0,
            'errors': 0,
            'total': len(tickers)
        }
        
        for idx, ticker in enumerate(tickers, 1):
            # Progress
            if idx % 10 == 0 or idx == len(tickers):
                print(f"\n📊 Progreso: {idx}/{len(tickers)} | ✅ {stats['success']} | ⏭️ {stats['skipped']} | ❌ {stats['errors']}")
            
            # Check if already has data
            if skip_existing:
                existing = self.check_existing_data(ticker, start_date)
                if existing['has_data']:
                    # Check if data is complete enough
                    first_date = pd.to_datetime(existing['first_date'])
                    days = existing['days']
                    
                    # Si tiene datos desde hace al menos (years_back - 1) años y al menos 1500 días, skip
                    cutoff_date = pd.to_datetime(start_date) + timedelta(days=365)
                    if first_date < cutoff_date and days >= (years_back * 250 * 0.75):  # 75% de días de trading esperados
                        logger.info(f"⏭️  {ticker:6} - Ya tiene datos completos ({days} días desde {first_date.strftime('%Y-%m-%d')})")
                        stats['skipped'] += 1
                        continue
            
            # Download and populate
            result = self.populate_ticker(ticker, start_date, end_date)
            
            if result['status'] == 'success':
                stats['success'] += 1
            else:
                stats['errors'] += 1
            
            # Rate limiting
            time.sleep(delay)
        
        # Summary
        print("\n" + "=" * 80)
        print("✅ DESCARGA COMPLETADA")
        print("=" * 80)
        print(f"Exitosos:  {stats['success']}")
        print(f"Omitidos:  {stats['skipped']} (ya tenían histórico completo)")
        print(f"Errores:   {stats['errors']}")
        print(f"Total:     {stats['total']}")
        print("=" * 80)
    
    def close(self):
        """Cierra conexiones"""
        self.cache.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Poblar cache con datos históricos de OpenBB')
    parser.add_argument('--years', type=int, default=20, help='Años de histórico (default: 20)')
    parser.add_argument('--delay', type=float, default=0.3, help='Delay entre requests (default: 0.3s)')
    parser.add_argument('--tickers', nargs='+', help='Lista específica de tickers (ej: AAPL MSFT GOOGL)')
    parser.add_argument('--test', action='store_true', help='Solo procesar primeros 10 tickers (test)')
    parser.add_argument('--no-skip', action='store_true', help='No omitir tickers con datos existentes')
    
    args = parser.parse_args()
    
    populator = HistoricalDataPopulator()
    
    try:
        # Determinar qué tickers procesar
        if args.tickers:
            # Lista específica de tickers
            tickers = args.tickers
            print(f"\n🎯 Procesando lista específica: {', '.join(tickers)}\n")
        elif args.test:
            # Modo test: primeros 10 tickers
            print("\n🧪 MODO TEST: Solo primeros 10 tickers\n")
            cursor = populator.cache.conn.execute("SELECT ticker FROM universe LIMIT 10")
            tickers = [row[0] for row in cursor.fetchall()]
        else:
            # Todos los tickers del universo
            cursor = populator.cache.conn.execute("SELECT ticker FROM universe ORDER BY ticker")
            tickers = [row[0] for row in cursor.fetchall()]
            
            print(f"\n⚠️  Esto descargará datos para {len(tickers)} tickers.")
            print(f"⏱️  Tiempo estimado: {len(tickers) * args.delay / 60:.1f} minutos")
            response = input("\n¿Continuar? (y/n): ")
            
            if response.lower() != 'y':
                print("❌ Cancelado")
                return
        
        # Ejecutar población
        populator.populate_all(
            tickers=tickers,
            years_back=args.years,
            delay=args.delay,
            skip_existing=not args.no_skip
        )
        
    finally:
        populator.close()


if __name__ == "__main__":
    main()
