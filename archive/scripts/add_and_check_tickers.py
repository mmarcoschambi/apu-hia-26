#!/usr/bin/env python3
"""
ADD AND CHECK TICKERS - Agregar tickers a SQLite y verificar si están en top líquidos
======================================================================================
Uso:
    python3 add_and_check_tickers.py APP PLTR NVDA
    python3 add_and_check_tickers.py --add-all APP PLTR NVDA  # Agregar a custom también
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import yfinance as yf

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.data.universe_manager import UniverseManager


class TickerManager:
    """Gestiona tickers en SQLite y verifica si están en top líquidos"""
    
    def __init__(self):
        self.db_path = "data/ticker_cache.db"
        self.manager = UniverseManager()
    
    def add_to_sqlite(self, ticker):
        """Agrega ticker a la base de datos SQLite"""
        try:
            # Obtener info del ticker
            stock = yf.Ticker(ticker)
            info = stock.info
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insertar o actualizar
            cursor.execute("""
                INSERT OR REPLACE INTO universe 
                (ticker, name, exchange, sector, industry, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ticker.upper(),
                info.get('longName', ''),
                info.get('exchange', ''),
                info.get('sector', ''),
                info.get('industry', ''),
                datetime.now().strftime('%Y-%m-%d')
            ))
            
            conn.commit()
            conn.close()
            
            return True, info
        
        except Exception as e:
            return False, str(e)
    
    def check_in_top(self, ticker):
        """Verifica si el ticker está en la lista de top líquidos"""
        top_tickers = self.manager.load_universe()
        is_in_top = ticker.upper() in [t.upper() for t in top_tickers]
        return is_in_top, len(top_tickers)
    
    def check_in_sqlite(self, ticker):
        """Verifica si el ticker existe en SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM universe WHERE ticker = ?", (ticker.upper(),))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None, result
    
    def get_ticker_info_sqlite(self, ticker):
        """Obtiene información del ticker desde SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ticker, name, exchange, sector, industry, last_updated 
            FROM universe WHERE ticker = ?
        """, (ticker.upper(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'ticker': result[0],
                'name': result[1],
                'exchange': result[2],
                'sector': result[3],
                'industry': result[4],
                'last_updated': result[5]
            }
        return None
    
    def count_tickers(self):
        """Cuenta tickers en SQLite y en top"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM universe")
        sqlite_count = cursor.fetchone()[0]
        conn.close()
        
        top_count = len(self.manager.load_universe())
        
        return sqlite_count, top_count


def print_header(text):
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80)


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 add_and_check_tickers.py [--add-all] TICKER1 TICKER2 ...")
        print("\nOpciones:")
        print("  --add-all    También agregar a la lista de top líquidos")
        print("\nEjemplos:")
        print("  python3 add_and_check_tickers.py APP PLTR")
        print("  python3 add_and_check_tickers.py --add-all APP PLTR")
        return
    
    # Parsear argumentos
    add_to_top = False
    tickers = []
    
    for arg in sys.argv[1:]:
        if arg == '--add-all':
            add_to_top = True
        else:
            tickers.append(arg.upper())
    
    if not tickers:
        print("❌ No se especificaron tickers")
        return
    
    print_header("🎯 AGREGAR Y VERIFICAR TICKERS")
    
    manager = TickerManager()
    
    # Mostrar estado inicial
    sqlite_count, top_count = manager.count_tickers()
    print(f"\n📊 Estado actual:")
    print(f"   • SQLite database: {sqlite_count} tickers")
    print(f"   • Top líquidos: {top_count} tickers")
    
    print(f"\n📝 Procesando {len(tickers)} ticker(s)...")
    
    results = []
    
    for ticker in tickers:
        print(f"\n{'─'*80}")
        print(f"🔍 Procesando: {ticker}")
        
        result = {
            'ticker': ticker,
            'in_sqlite_before': False,
            'in_top': False,
            'added_sqlite': False,
            'added_top': False,
            'info': None
        }
        
        # 1. Verificar si ya está en SQLite
        in_sqlite, sqlite_data = manager.check_in_sqlite(ticker)
        result['in_sqlite_before'] = in_sqlite
        
        if in_sqlite:
            print(f"   ✅ Ya existe en SQLite")
            result['info'] = manager.get_ticker_info_sqlite(ticker)
        else:
            print(f"   ➕ Agregando a SQLite...")
            success, info_or_error = manager.add_to_sqlite(ticker)
            
            if success:
                print(f"   ✅ Agregado a SQLite exitosamente")
                result['added_sqlite'] = True
                result['info'] = {
                    'name': info_or_error.get('longName', 'N/A'),
                    'exchange': info_or_error.get('exchange', 'N/A'),
                    'sector': info_or_error.get('sector', 'N/A'),
                    'industry': info_or_error.get('industry', 'N/A')
                }
            else:
                print(f"   ❌ Error: {info_or_error}")
                results.append(result)
                continue
        
        # 2. Verificar si está en top líquidos
        in_top, top_total = manager.check_in_top(ticker)
        result['in_top'] = in_top
        
        if in_top:
            print(f"   🌟 ESTÁ en top {top_total} líquidos")
        else:
            print(f"   ⚠️  NO está en top {top_total} líquidos")
            
            if add_to_top:
                print(f"   ➕ Agregando a top líquidos...")
                manager.manager.add_custom_tickers([ticker])
                result['added_top'] = True
        
        # Mostrar info
        if result['info']:
            print(f"\n   📋 Información:")
            print(f"      Nombre: {result['info'].get('name', 'N/A')}")
            print(f"      Exchange: {result['info'].get('exchange', 'N/A')}")
            print(f"      Sector: {result['info'].get('sector', 'N/A')}")
            print(f"      Industry: {result['info'].get('industry', 'N/A')}")
        
        results.append(result)
    
    # Resumen final
    print_header("📊 RESUMEN")
    
    sqlite_count_final, top_count_final = manager.count_tickers()
    
    print(f"\n📈 Estado final:")
    print(f"   • SQLite database: {sqlite_count_final} tickers (+{sqlite_count_final - sqlite_count})")
    print(f"   • Top líquidos: {top_count_final} tickers (+{top_count_final - top_count})")
    
    print(f"\n📋 Resultados por ticker:")
    for r in results:
        status_top = "✅ En top" if r['in_top'] else "❌ NO en top"
        status_sqlite = "✅ En DB" if (r['in_sqlite_before'] or r['added_sqlite']) else "❌ Error"
        
        print(f"   {r['ticker']:<8} {status_sqlite:<12} {status_top}")
    
    print("\n💡 Tip: Usa --add-all para agregar a top líquidos también")
    print()


if __name__ == "__main__":
    main()
