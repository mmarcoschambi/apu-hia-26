#!/usr/bin/env python3
"""
UPDATE 2025 PRIORITY UNIVERSE
=============================
Actualiza la data de 2024-2026 PRIORIZANDO:
1. S&P 500 (Base sólida)
2. Top 500 Liquidez (Momentum candidates)

Evita duplicados y asegura que la "gasolina" para el backtest sea de alto octanaje.
"""

import sys
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache
from populate_historical_openbb import process_ticker # Importamos la función core
from yahoo_fin import stock_info as si

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("UpdatePriority")

def get_sp500_tickers():
    print("🌎 Fetching S&P 500 list (Wikipedia Fallback)...")
    try:
        # Intento directo con pandas y Wikipedia (más estable que yahoo_fin)
        import pandas as pd
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        tickers = [t.replace('.', '-') for t in tickers]
        print(f"   ✅ S&P 500: {len(tickers)} tickers found via Wikipedia.")
        return set(tickers)
    except Exception as e:
        print(f"   ⚠️ Wikipedia failed ({e}). Trying local file...")
        try:
            # Fallback local
            with open('sp500_tickers_since_2014.txt', 'r') as f:
                content = f.read()
                # Asumiendo formato simple o JSON, intentamos split básico
                tickers = [t.strip().replace('.', '-') for t in content.replace(',', ' ').split() if t.strip()]
            print(f"   ✅ S&P 500: {len(tickers)} tickers found via local file.")
            return set(tickers)
        except Exception as e2:
            print(f"   ❌ All methods failed: {e2}")
            return set()

def get_top_liquid_tickers(limit=500):
    print(f"💧 Fetching Top {limit} Liquid Tickers from Local DB...")
    cache = TickerCache()
    
    # Buscar fecha reciente
    try:
        date_query = "SELECT MAX(date) FROM ohlcv_cache WHERE rolling_dollar_vol_20 IS NOT NULL"
        recent_date = cache.conn.execute(date_query).fetchone()[0]
    except:
        recent_date = None
    
    if not recent_date:
        print("   ⚠️ No recent liquidity data found. Using broad universe.")
        return set()
        
    print(f"   📅 Reference Date: {recent_date}")
    
    # Bajamos requisitos para llenar el cupo
    tickers = cache.get_active_tickers(
        sort_by='liquidity',
        limit=limit,
        date_filter=recent_date,
        min_price=2.0,            # Más permisivo
        min_rolling_dollar_vol=1000000 # 1M en vez de 5M para capturar más
    )
    
    print(f"   ✅ Liquid Tickers: {len(tickers)} tickers found.")
    return set(tickers)

def main():
    start_time = datetime.now()
    
    # 1. Gather Universe
    sp500 = get_sp500_tickers()
    liquid = get_top_liquid_tickers(limit=500)
    
    if not sp500 and not liquid:
        print("❌ CRITICAL: No tickers found. Aborting.")
        return

    # 2. Merge & Deduplicate
    priority_universe = list(sp500.union(liquid))
    priority_universe.sort()
    
    print("\n" + "="*50)
    print(f"🚀 UPDATING PRIORITY UNIVERSE ({len(priority_universe)} Tickers)")
    print("="*50)
    print("   • Range: 2024 - 2026 (Live)")
    print("   • Sources: S&P 500 + Top Liquidity")
    print("-" * 50)
    
    # 3. Process
    cache = TickerCache()
    # Forzamos descarga desde 2024 para cubrir cualquier gap reciente y obtener 2025/2026 completo
    start_date = "2024-01-01" 
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    success_count = 0
    error_count = 0
    
    # Usamos tqdm si está instalado, si no loop normal
    try:
        from tqdm import tqdm
        iterator = tqdm(priority_universe)
    except ImportError:
        iterator = priority_universe

    for ticker in iterator:
        try:
            # Reutilizamos la lógica robusta de populate_historical_openbb
            # Nota: process_ticker espera (ticker, start_date, end_date, cache_instance, force_download)
            # Pero como no importamos la firma exacta, voy a llamar directamente a cache.get_ohlcv
            # que es lo que hace process_ticker internamente, pero asegurando el force refresh implícito
            # al pedir una fecha final 'hoy' que probablemente no está en cache.
            
            # Sin embargo, para asegurar calculo de métricas, mejor usamos la lógica completa.
            # Como process_ticker no es facil de importar aislada (dependencias globales),
            # usaremos cache.get_ohlcv directamente que ya calculamos las metricas en el step anterior.
            
            # TRUCO: cache.get_ohlcv ya descarga y calcula si falta data.
            # Al pedir hasta HOY, forzará la actualización de 2025.
            
            df = cache.get_ohlcv(ticker, start_date=start_date, end_date=end_date)
            
            if df is not None and not df.empty:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            error_count += 1
            # print(f"Error {ticker}: {e}")

    print("\n" + "="*50)
    print("🏁 UPDATE COMPLETE")
    print(f"   ✅ Updated: {success_count}")
    print(f"   ❌ Failed:  {error_count}")
    print(f"   ⏱️  Time:    {datetime.now() - start_time}")

if __name__ == "__main__":
    main()
