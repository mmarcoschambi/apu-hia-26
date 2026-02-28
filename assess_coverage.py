import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "data/ticker_cache.db"

def main():
    if not Path(DB_PATH).exists():
        print("No database found.")
        return

    conn = sqlite3.connect(DB_PATH)
    
    print("⏳ Consultando estadísticas de la base de datos...")
    # Get min and max date for each ticker
    query = "SELECT ticker, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as count FROM ohlcv_cache GROUP BY ticker"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print("Database is empty.")
        return

    df['start_date'] = pd.to_datetime(df['start_date'])
    df['end_date'] = pd.to_datetime(df['end_date'])
    
    print(f"📊 Total tickers con data: {len(df)}")
    
    # Start Date Analysis
    print("\n--- COBERTURA HISTÓRICA (INICIO) ---")
    print(f"✅ Tickers con data PRE-2020: {len(df[df['start_date'] < '2020-01-01'])}")
    print(f"⚠️ Tickers que inician en 2020: {len(df[(df['start_date'] >= '2020-01-01') & (df['start_date'] < '2021-01-01')])}")
    print(f"⚠️ Tickers que inician en 2021: {len(df[(df['start_date'] >= '2021-01-01') & (df['start_date'] < '2022-01-01')])}")
    print(f"❌ Tickers muy recientes (post-2022): {len(df[df['start_date'] >= '2022-01-01'])}")

    # End Date Analysis
    print("\n--- ACTUALIDAD DE LA DATA (FIN) ---")
    print(f"✅ Data hasta 2026 (Live): {len(df[df['end_date'] >= '2026-01-01'])}")
    print(f"✅ Data hasta 2025: {len(df[(df['end_date'] >= '2025-01-01') & (df['end_date'] < '2026-01-01')])}")
    print(f"⚠️ Data congelada en 2024: {len(df[(df['end_date'] >= '2024-01-01') & (df['end_date'] < '2025-01-01')])}")
    print(f"❌ Data obsoleta (pre-2024): {len(df[df['end_date'] < '2024-01-01'])}")

    # Overall Range
    min_global = df['start_date'].min()
    max_global = df['end_date'].max()
    print(f"\n📅 Rango Global Disponible: {min_global.date()} -> {max_global.date()}")
    
    # Top liquid tickers check (sample)
    print("\n--- MUESTRA: Top 5 Tickers más largos ---")
    print(df.sort_values('count', ascending=False).head(5)[['ticker', 'start_date', 'end_date', 'count']])

if __name__ == "__main__":
    main()
