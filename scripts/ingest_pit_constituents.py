#!/usr/bin/env python3
"""
scripts/ingest_pit_constituents.py
Ingesta del CSV de constituyentes PIT de QuantConnect a la base SQLite local.
"""

import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
CSV_PATH = PROJECT_ROOT / "quantconnect" / "sp500_pit_2019_2024.csv"

def ingest_pit_data():
    if not CSV_PATH.exists():
        print(f"❌ Archivo no encontrado en: {CSV_PATH}")
        print("Asegúrate de que el CSV esté en la ruta correcta.")
        return

    print(f"📖 Leyendo datos de membresía PIT desde {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    # Limpieza de datos
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["ticker"] = df["ticker"].str.upper().str.strip()
    
    print(f"📊 Registros leídos del CSV: {len(df)}")
    print(f"   Tickers únicos: {df['ticker'].nunique()}")
    print(f"   Rango de fechas: {df['date'].min()} -> {df['date'].max()}")

    # Conectar a SQLite
    print(f"💾 Conectando a la base de datos: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Crear la tabla si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pit_constituents (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            index_member TEXT,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()
    
    # Insertar en lotes
    print("💾 Insertando/reemplazando registros en SQLite...")
    records = df[["date", "ticker", "index_member"]].values.tolist()
    
    cursor.executemany(
        "INSERT OR REPLACE INTO pit_constituents (date, ticker, index_member) VALUES (?, ?, ?)",
        records
    )
    conn.commit()
    
    # Obtener estadísticas de la tabla
    total_db = cursor.execute("SELECT COUNT(*) FROM pit_constituents").fetchone()[0]
    dates_count = cursor.execute("SELECT COUNT(DISTINCT date) FROM pit_constituents").fetchone()[0]
    conn.close()
    
    print("✅ Ingestión completada con éxito.")
    print(f"   - Total registros en DB (pit_constituents): {total_db}")
    print(f"   - Fechas mensuales de corte registradas: {dates_count}")

if __name__ == "__main__":
    ingest_pit_data()
