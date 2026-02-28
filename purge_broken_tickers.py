import sqlite3
from pathlib import Path
import sys

def purge_db():
    db_path = 'data/ticker_cache.db'
    if not Path(db_path).exists():
        print("❌ No se encontró la base de datos.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🧹 INICIANDO LIMPIEZA DE BASE DE DATOS...")
    
    # 1. Identificar Penny Stocks (Promedio < $2)
    print("🔍 Buscando Penny Stocks (< $2)...")
    query_penny = """
        SELECT ticker 
        FROM ohlcv_cache 
        GROUP BY ticker 
        HAVING AVG(close) < 2.0
    """
    cursor.execute(query_penny)
    pennies = [r[0] for r in cursor.fetchall()]
    
    # 2. Identificar Data Insuficiente (< 100 días) - Subí el estándar a 100
    print("🔍 Buscando tickers con data insuficiente (< 100 días)...")
    query_thin = """
        SELECT ticker 
        FROM ohlcv_cache 
        GROUP BY ticker 
        HAVING COUNT(*) < 100
    """
    cursor.execute(query_thin)
    thins = [r[0] for r in cursor.fetchall()]
    
    bad_tickers = set(pennies + thins)
    
    # Proteger tickers clave (Índices y Sectores Críticos)
    whitelist = [
        'SPY', 'QQQ', 'IWM', 'DIA', 'VIX', '^VIX', '^GSPC', '^IXIC', '^RUT',
        'XLK', 'XLE', 'XLF', 'XLY', 'XLI', 'XLP', 'XLV', 'XLB', 'XLU', 'XLRE', 'XLC',
        'SMH', 'IGV', 'IBB', 'XBI', 'KRE', 'KBE', 'XRT'
    ]
    for t in whitelist:
        if t in bad_tickers:
            bad_tickers.remove(t)
    
    print(f"\n📉 Se encontraron {len(bad_tickers)} tickers 'basura'.")
    print(f"   • {len(pennies)} son Penny Stocks (< $2)")
    print(f"   • {len(thins)} tienen data insuficiente (< 100 días)")
    
    if not bad_tickers:
        print("✅ Tu base de datos está limpia.")
        conn.close()
        return

    print(f"Ejemplos a borrar: {list(bad_tickers)[:10]} ...")
    
    # En entorno no interactivo, pedimos confirmación segura
    if sys.stdin.isatty():
        confirm = input("¿Eliminar estos tickers de la base de datos? (s/n): ")
    else:
        print("⚠️ Modo no interactivo: Ejecuta manualmente para confirmar borrado.")
        confirm = 'n'

    if confirm.lower() == 's':
        print("🔥 Eliminando...")
        placeholders = ','.join('?' for _ in bad_tickers)
        
        # Borrar de OHLCV
        conn.execute(f"DELETE FROM ohlcv_cache WHERE ticker IN ({placeholders})", list(bad_tickers))
        
        # Borrar de Universe (si existe)
        try:
            conn.execute(f"DELETE FROM universe WHERE ticker IN ({placeholders})", list(bad_tickers))
        except:
            pass
            
        conn.commit()
        print("✨ Limpieza completada.")
        
        print("🗜️  Compactando base de datos (VACUUM)...")
        conn.execute("VACUUM")
        print("✅ Base de datos optimizada.")
    else:
        print("Operación cancelada.")
    
    conn.close()

if __name__ == "__main__":
    purge_db()