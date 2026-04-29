import sys
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Configurar paths
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.ticker_cache import TickerCache
from populate_historical_openbb import calculate_metrics

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def download_and_store(ticker, years=20):
    cache = TickerCache()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years*365)
    
    logger.info(f"🚀 Descargando {ticker} desde {start_date.date()} hasta {end_date.date()}...")
    
    # Descargar (auto_adjust=True es clave para SPY)
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    
    if df.empty:
        logger.error(f"❌ No se pudo descargar data para {ticker}")
        return
    
    # Manejo de MultiIndex si yfinance lo devuelve
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Calcular métricas (reusando tu lógica de populate_historical_openbb)
    logger.info(f"📊 Calculando métricas técnicas para {ticker}...")
    df = calculate_metrics(df)
    
    # Guardar en base de datos
    logger.info(f"💾 Guardando {len(df)} registros en la base de datos...")
    
    data_to_insert = []
    for date, row in df.iterrows():
        if pd.isna(row['Close']): continue
        
        def get_val(key):
            val = row.get(key)
            return float(val) if pd.notna(val) else None

        data_to_insert.append((
            ticker, date.strftime('%Y-%m-%d'), get_val('Open'), get_val('High'),
            get_val('Low'), get_val('Close'), int(row.get('Volume', 0)),
            get_val('dollar_volume'), get_val('rolling_dollar_vol_20'), get_val('avg_volume_20'),
            get_val('adr_14'), get_val('adr_pct_14'), get_val('sma_50'), get_val('sma_200'),
            int(row.get('price_above_sma50', 0)), int(row.get('price_above_sma200', 0)),
            int(row.get('sma50_above_sma200', 0)), int(row.get('trend_aligned', 0)),
            get_val('ema_8'), get_val('ema_21')
        ))
    
    try:
        cache.conn.executemany('''
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, 
             dollar_volume, rolling_dollar_vol_20, avg_volume_20,
             adr_14, adr_pct_14, sma_50, sma_200,
             price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned,
             ema_8, ema_21)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_to_insert)
        cache.conn.commit()
        logger.info(f"✅ {ticker} actualizado correctamente.")
    except Exception as e:
        logger.error(f"❌ Error al guardar en DB: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Descargar datos de mercado')
    parser.add_argument('--tickers', type=str, help='Lista de tickers separados por coma')
    parser.add_argument('--years', type=int, default=20, help='Años de historia a descargar')
    args = parser.parse_args()

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(',')]
        for ticker in tickers:
            download_and_store(ticker, years=args.years)
    else:
        # Defaults si no hay argumentos
        download_and_store("SPY", years=args.years)
        download_and_store("^VIX", years=args.years)
    
    print("\n✨ Proceso terminado.")
