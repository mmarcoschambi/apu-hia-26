#!/usr/bin/env python3
"""
Script para generar lista de tickers filtrando contra la base de datos existente.
NO descarga precios, solo genera el archivo de texto con tickers faltantes.

Autor: Script para momentum-v2
Fecha: 2026-02-11
"""

import pandas as pd
from pathlib import Path
import sys
import os

# Añadir el directorio raíz al path para importar src
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.data.ticker_cache import TickerCache

class TickerCollector:
    def __init__(self, output_dir="data"):
        self.output_dir = Path(output_dir)
        self.constituents_dir = self.output_dir / "constituents"
        self.constituents_dir.mkdir(exist_ok=True)
        
        # Inicializar TickerCache para consultar la DB
        self.ticker_cache = TickerCache()
        print(f"✅ Conectado a base de datos: {self.ticker_cache.db_path}")

    def get_existing_tickers(self):
        """Obtiene todos los tickers que ya tienen datos en la ohlcv_cache"""
        print("🔍 Consultando tickers existentes en la base de datos...")
        try:
            query = "SELECT DISTINCT ticker FROM ohlcv_cache"
            cursor = self.ticker_cache.conn.execute(query)
            existing = {row[0] for row in cursor.fetchall()}
            print(f"   Total en DB: {len(existing)}")
            return existing
        except Exception as e:
            print(f"❌ Error consultando DB: {e}")
            return set()

    def get_qqq_constituents(self):
        """Descarga componentes actuales del QQQ desde StockAnalysis.com"""
        print("\n📊 Obteniendo componentes del QQQ desde StockAnalysis...")
        url = "https://stockanalysis.com/etf/qqq/holdings/"
        try:
            tables = pd.read_html(url)
            holdings_table = max(tables, key=len)
            if 'Symbol' in holdings_table.columns:
                tickers = holdings_table['Symbol'].tolist()
                print(f"✅ QQQ: {len(tickers)} componentes encontrados")
                return set(tickers)
        except Exception as e:
            print(f"⚠️ Error descargando QQQ (usando backup): {e}")
            
        # Backup list if download fails
        backup = [
            'NVDA', 'AAPL', 'MSFT', 'AVGO', 'AMZN', 'GOOGL', 'GOOG', 'TSLA', 
            'META', 'NFLX', 'COST', 'PLTR', 'AMD', 'CSCO', 'MU', 'TMUS', 
            'AMAT', 'ISRG', 'PEP', 'APP', 'LRCX', 'LIN', 'SHOP', 'INTC', 
            'QCOM', 'BKNG', 'TXN', 'ADBE', 'INTU', 'HON'
        ]
        return set(backup)

    def get_russell2000_liquid(self):
        """Lista curada de small caps con buena liquidez"""
        print("📊 Obteniendo lista curada de Russell 2000 (Liquid)...")
        liquid_small_caps = [
            'PLTR', 'RBLX', 'COIN', 'HOOD', 'SOFI', 'OPEN', 'RIVN', 'LCID',
            'UPST', 'AFRM', 'DOCS', 'ZS', 'DDOG', 'NET', 'CRWD', 'PATH',
            'U', 'SNOW', 'MDB', 'FROG', 'BILL', 'IOT', 'SRRK', 'WOLF',
            'RXRX', 'BMRN', 'VRTX', 'IONS', 'TECH', 'ALGN', 'HOLX', 'PODD',
            'LMAT', 'INCY', 'EXAS', 'IRTC', 'ARVN', 'KRYS', 'BPMC', 'RARE',
            'CELH', 'CAVA', 'ONON', 'ELF', 'SHAK', 'DNUT', 'BROS', 'WH',
            'WING', 'TXRH', 'CHDN', 'CARG', 'HIMS', 'FIGS', 'LFVN', 'RH',
            'FTAI', 'CVNA', 'ASTS', 'SMCI', 'EYE', 'RELY', 'VST', 'CEG',
            'NRG', 'CWEN', 'AES', 'JKS', 'ENPH', 'SEDG', 'RUN', 'NOVA',
            'AFRM', 'LPLA', 'VIRT', 'IBKR', 'SF', 'ALLY', 'SOFI', 'NAVI',
            'EWBC', 'WAL', 'FHN', 'SNV', 'ZION', 'CMA', 'KEY', 'CFG'
        ]
        print(f"✅ Russell 2000: {len(liquid_small_caps)} tickers curados")
        return set(liquid_small_caps)

    def process(self):
        # 1. Obtener tickers de diversas fuentes
        qqq_tickers = self.get_qqq_constituents()
        iwm_tickers = self.get_russell2000_liquid()
        
        all_collected = qqq_tickers.union(iwm_tickers)
        print(f"\n📈 Total tickers recolectados: {len(all_collected)}")
        
        # 2. Obtener lo que ya tenemos en DB
        existing = self.get_existing_tickers()
        
        # 3. Filtrar
        missing = sorted(list(all_collected - existing))
        
        # 4. Guardar resultado
        output_file = self.output_dir / "new_tickers.txt"
        with open(output_file, "w") as f:
            f.write(", ".join(missing))
            
        print("\n" + "=" * 50)
        print(f"✅ PROCESO COMPLETADO")
        print(f"📊 Resumen:")
        print(f"   - Tickers Recolectados: {len(all_collected)}")
        print(f"   - Ya en Base de Datos: {len(existing)}")
        print(f"   - NUEVOS (Faltantes):  {len(missing)}")
        print(f"\n📝 Lista guardada en: {output_file}")
        print("=" * 50)
        
        if missing:
            print(f"Muestra: {', '.join(missing[:10])}...")

if __name__ == "__main__":
    collector = TickerCollector()
    collector.process()
