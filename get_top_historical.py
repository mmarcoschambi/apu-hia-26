import sqlite3
import pandas as pd
import argparse
import os

# Configuración
DB_PATH = 'data/ticker_cache.sqlite'

def get_top_historical(year, month, limit=50):
    if not os.path.exists(DB_PATH):
        print(f"❌ No se encontró la base de datos en: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    
    # Construir fechas de inicio y fin del mes
    start_date = f"{year}-{month:02d}-01"
    # Truco rápido para fin de mes: tomar el día 1 del mes siguiente y restar un día, 
    # o simplemente usar strings hasta el 31 (SQLite maneja strings de fecha, si no existe el 31 no pasa nada en range)
    # Forma más segura en string comparison:
    end_date = f"{year}-{month:02d}-31" 

    print(f"🔍 Analizando liquidez histórica para: {year}-{month:02d}...")

    query = f"""
    SELECT 
        h.ticker,
        u.sector,
        COUNT(h.date) as days_traded,
        AVG(h.close) as avg_price,
        AVG(h.close * h.volume) as avg_dollar_vol
    FROM ohlcv_cache h
    LEFT JOIN universe u ON h.ticker = u.ticker
    WHERE h.date BETWEEN '{start_date}' AND '{end_date}'
    GROUP BY h.ticker
    HAVING days_traded > 10  -- Filtrar tickers que cotizaron la mayoría del mes
    ORDER BY avg_dollar_vol DESC
    LIMIT {limit};
    """

    try:
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("⚠️ No se encontraron datos para esa fecha.")
        else:
            # Formatear para leer mejor
            df['avg_dollar_vol_M'] = df['avg_dollar_vol'] / 1_000_000
            df['avg_price'] = df['avg_price'].round(2)
            
            print(f"\n🏆 TOP {limit} LIQUIDEZ ({year}-{month:02d})")
            print("-" * 65)
            print(f"{ 'Ticker':<8} {'Sector':<20} {'Precio Prom':<12} {'$Vol (M/día)':<15}")
            print("-" * 65)
            
            for index, row in df.iterrows():
                sector = str(row['sector'])[:18] if row['sector'] else "N/A"
                print(f"{row['ticker']:<8} {sector:<20} ${row['avg_price']:<11.2f} ${row['avg_dollar_vol_M']:<14.1f}M")
            
            print("-" * 65)
            
            # Opción para exportar
            # df.to_csv(f"top_liquid_{year}_{month}.csv", index=False)

    except Exception as e:
        print(f"Error ejecutando query: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Obtener Top Tickers por Liquidez Histórica')
    parser.add_argument('year', type=int, help='Año (ej. 2023)')
    parser.add_argument('month', type=int, help='Mes (1-12)')
    parser.add_argument('--limit', type=int, default=50, help='Cantidad de resultados')
    
    args = parser.parse_args()
    get_top_historical(args.year, args.month, args.limit)
