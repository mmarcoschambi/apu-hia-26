import sqlite3
import pandas as pd
from datetime import datetime

db_path = 'data/ticker_cache.db'

print(f"--- Diagnóstico de Datos 2020 en {db_path} ---")

try:
    conn = sqlite3.connect(db_path)
    
    # 1. Contar registros totales en 2020
    query_count = """
    SELECT COUNT(*) 
    FROM ohlcv_cache 
    WHERE date >= '2020-01-01' AND date <= '2020-12-31'
    """
    cursor = conn.execute(query_count)
    count = cursor.fetchone()[0]
    print(f"Registros totales en 2020: {count}")
    
    if count == 0:
        print("❌ NO HAY DATOS PARA 2020 EN ABSOLUTO.")
        
        # Verificar rango total disponible
        cursor = conn.execute("SELECT MIN(date), MAX(date) FROM ohlcv_cache")
        min_date, max_date = cursor.fetchone()
        print(f"Rango disponible en DB: {min_date} a {max_date}")
        
    else:
        print("✅ Hay datos para 2020.")
        
        # 2. Ver qué tickers tienen datos en 2020
        query_tickers = """
        SELECT ticker, COUNT(*) as days
        FROM ohlcv_cache
        WHERE date >= '2020-01-01' AND date <= '2020-12-31'
        GROUP BY ticker
        ORDER BY days DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query_tickers, conn)
        print("\nTop 10 tickers con más datos en 2020:")
        print(df)
        
        # 3. Verificar SPY específicamente (usado para regime filter)
        query_spy = """
        SELECT COUNT(*) 
        FROM ohlcv_cache 
        WHERE ticker = 'SPY' AND date >= '2020-01-01' AND date <= '2020-12-31'
        """
        cursor = conn.execute(query_spy)
        spy_count = cursor.fetchone()[0]
        print(f"\nDatos de SPY en 2020: {spy_count} días")

    conn.close()

except Exception as e:
    print(f"Error accediendo a la DB: {e}")
