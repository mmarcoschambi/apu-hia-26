#!/usr/bin/env python3
"""
POPULATE HISTORICAL DATA (OPENBB VERSION)
=========================================
Script recomendado para poblar la base de datos con datos históricos y métricas calculadas.
Reemplaza scripts antiguos.

Uso:
    python populate_historical_openbb.py --help
    python populate_historical_openbb.py --test
    python populate_historical_openbb.py --tickers AAPL MSFT
    python populate_historical_openbb.py --years 2
"""

import sys
import argparse
import time
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm

# Configurar path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.universe_manager import UniverseManager
from src.data.ticker_cache import TickerCache
from config.settings import DATA_SOURCE, OPENBB_PROVIDER

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/populate_db.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def calculate_metrics(df):
    """Calcula todas las métricas técnicas necesarias"""
    if df.empty:
        return df

    # 1. Dollar Volume
    df['dollar_volume'] = df['Close'] * df['Volume']
    df['rolling_dollar_vol_20'] = df['dollar_volume'].rolling(window=20).mean()
    df['avg_volume_20'] = df['Volume'].rolling(window=20).mean()

    # 2. Moving Averages
    df['sma_50'] = df['Close'].rolling(window=50).mean()
    df['sma_200'] = df['Close'].rolling(window=200).mean()
    
    # EMAs (para uso futuro)
    df['ema_8'] = df['Close'].ewm(span=8, adjust=False).mean()
    df['ema_21'] = df['Close'].ewm(span=21, adjust=False).mean()

    # 3. ADR (Average Daily Range)
    # Range diario en %
    df['high_low_pct'] = (df['High'] - df['Low']) / df['Low']
    # ADR 14 días (promedio del rango %)
    df['adr_pct_14'] = df['high_low_pct'].rolling(window=14).mean() * 100
    # ADR en $ (promedio del rango absoluto)
    df['range_abs'] = df['High'] - df['Low']
    df['adr_14'] = df['range_abs'].rolling(window=14).mean()

    # 4. Trend Flags
    # Se calculan solo si tenemos SMAs válidas
    df['price_above_sma50'] = (df['Close'] > df['sma_50']).astype(int)
    df['price_above_sma200'] = (df['Close'] > df['sma_200']).astype(int)
    df['sma50_above_sma200'] = (df['sma_50'] > df['sma_200']).astype(int)
    
    # Trend Aligned: Precio > SMA50 > SMA200
    df['trend_aligned'] = (
        (df['price_above_sma50'] == 1) & 
        (df['sma50_above_sma200'] == 1)
    ).astype(int)

    # Limpieza de columnas temporales
    df.drop(columns=['high_low_pct', 'range_abs'], inplace=True, errors='ignore')

    return df

def fetch_data(ticker, start_date, end_date):
    """Descarga datos usando OpenBB o yfinance como fallback"""
    
    # Handle VIX alias
    if ticker == "VIX":
        ticker = "^VIX"
        
    try:
        # Intentar OpenBB solo si está configurado
        if DATA_SOURCE == "openbb":
            try:
                from openbb import obb
                # logger.info(f"Fetching {ticker} via OpenBB...")
                result = obb.equity.price.historical(
                    symbol=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    interval="1d",
                    provider=OPENBB_PROVIDER
                )
                if result and hasattr(result, 'to_df'):
                    df = result.to_df()
                    if not df.empty:
                        # Normalizar columnas
                        df.rename(columns={
                            'open': 'Open', 'high': 'High', 'low': 'Low', 
                            'close': 'Close', 'volume': 'Volume'
                        }, inplace=True)
                        return df
            except Exception as e:
                logger.warning(f"OpenBB failed for {ticker}: {e}")

        # Fallback a yfinance (Directo)
        import yfinance as yf
        
        # Helper to try download
        def try_download(symbol):
            try:
                # auto_adjust=True es CRÍTICO para manejar splits correctamente
                d = yf.download(symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                return d
            except TypeError:
                # Catch "NoneType is not subscriptable" inside yfinance
                return pd.DataFrame()
            except Exception:
                return pd.DataFrame()

        df = try_download(ticker)
        
        # Fallback for international tickers: Try replacing last '-' with '.'
        # Example: 005930-KS -> 005930.KS
        if (df.empty or len(df) == 0) and '-' in ticker:
            alt_ticker = ticker.rsplit('-', 1)
            alt_ticker = '.'.join(alt_ticker)
            logger.info(f"Retry with alternate ticker: {alt_ticker}")
            df = try_download(alt_ticker)

        return df

    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()

def process_ticker(ticker, cache, start_date, end_date, force=False):
    """Procesa un ticker individual: descarga, calcula, guarda"""
    
    # Verificar si ya está actualizado (opcional, por simplicidad descargamos por ahora)
    # En una implementación más avanzada, chequearíamos la última fecha en DB
    
    # 1. Descargar
    df = fetch_data(ticker, start_date, end_date)
    
    if df.empty or len(df) < 50: # Necesitamos al menos 50 días para SMA50
        logger.warning(f"Insufficient data for {ticker}")
        return False

    # 2. Calcular Métricas
    df = calculate_metrics(df)
    
    # 3. Guardar en SQLite
    try:
        # Iterar e insertar (eficiente con transacciones batch)
        # Usamos el método execute de la conexión para mayor control
        conn = cache.conn
        
        # Preparar datos
        data_to_insert = []
        for date, row in df.iterrows():
            if pd.isna(row['Close']): continue
            
            # Helper para safe float
            def get_val(key, default=None):
                val = row.get(key, default)
                return float(val) if pd.notna(val) else None

            data_to_insert.append((
                ticker,
                date.strftime('%Y-%m-%d'),
                get_val('Open'),
                get_val('High'),
                get_val('Low'),
                get_val('Close'),
                int(row['Volume']) if pd.notna(row['Volume']) else 0,
                get_val('dollar_volume'),
                get_val('rolling_dollar_vol_20'),
                get_val('avg_volume_20'),
                get_val('adr_14'),
                get_val('adr_pct_14'),
                get_val('sma_50'),
                get_val('sma_200'),
                get_val('price_above_sma50'),
                get_val('price_above_sma200'),
                get_val('sma50_above_sma200'),
                get_val('trend_aligned'),
                get_val('ema_8'),
                get_val('ema_21')
            ))
        
        # Ejecutar Batch Insert
        conn.executemany('''
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, 
             dollar_volume, rolling_dollar_vol_20, avg_volume_20,
             adr_14, adr_pct_14, sma_50, sma_200,
             price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned,
             ema_8, ema_21)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        
        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Error saving {ticker}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Poblar base de datos histórica con métricas')
    parser.add_argument('--test', action='store_true', help='Modo prueba (10 tickers)')
    parser.add_argument('--tickers', nargs='+', help='Lista específica de tickers')
    parser.add_argument('--years', type=int, default=2, help='Años de historia a descargar')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay entre requests')
    parser.add_argument('--no-skip', action='store_true', help='No saltar tickers existentes (forzar update)')
    
    args = parser.parse_args()
    
    # 1. Inicializar
    cache = TickerCache()
    manager = UniverseManager()
    
    # Asegurar que la tabla tenga todas las columnas
    # (El script TickerCache original podría no tener todas las columnas de métricas en create table)
    # Hacemos una migración al vuelo si es necesario
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN adr_pct_14 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN sma_50 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN sma_200 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN trend_aligned INTEGER")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN price_above_sma50 INTEGER")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN price_above_sma200 INTEGER")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN sma50_above_sma200 INTEGER")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN avg_volume_20 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN adr_14 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN market_cap REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN ema_8 REAL")
    except:
        pass
    try:
        cache.conn.execute("ALTER TABLE ohlcv_cache ADD COLUMN ema_21 REAL")
    except:
        pass

    
    # 2. Definir universo
    if args.tickers:
        tickers = args.tickers
        print(f"🎯 Procesando {len(tickers)} tickers específicos")
    elif args.test:
        universe = manager.load_universe()
        if not universe:
            universe = manager.build_universe()
        tickers = universe[:10]
        print(f"🧪 Modo TEST: Procesando {len(tickers)} tickers")
    else:
        universe = manager.load_universe()
        if not universe:
            universe = manager.build_universe()
        tickers = universe
        print(f"🚀 Procesando universo completo: {len(tickers)} tickers")

    # 3. Definir fechas
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=args.years*365)).strftime('%Y-%m-%d')
    
    print(f"📅 Rango: {start_date} -> {end_date}")
    print(f"⏱️  Delay: {args.delay}s")
    
    # 4. Loop principal
    success_count = 0
    error_count = 0
    
    pbar = tqdm(tickers)
    for ticker in pbar:
        pbar.set_description(f"Procesando {ticker}")
        
        try:
            if process_ticker(ticker, cache, start_date, end_date):
                success_count += 1
            else:
                error_count += 1
            
            time.sleep(args.delay)
            
        except KeyboardInterrupt:
            print("\n🛑 Interrumpido por usuario")
            break
        except Exception as e:
            logger.error(f"Critical error on {ticker}: {e}")
            error_count += 1

    print("\n" + "="*50)
    print("✅ PROCESO COMPLETADO")
    print(f"Total procesados: {success_count}")
    print(f"Errores: {error_count}")
    print("="*50)

if __name__ == "__main__":
    main()
