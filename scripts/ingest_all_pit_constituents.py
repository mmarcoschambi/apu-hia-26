#!/usr/bin/env python3
"""
scripts/ingest_all_pit_constituents.py
Detecta de forma dinámica, limpia e ingesta todos los archivos de constituyentes PIT
(*_pit_2019_2024.csv) presentes en quantconnect/ bajo el esquema multi-índice.
"""

import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
QUANTCONNECT_DIR = PROJECT_ROOT / "quantconnect"

def ingest_all():
    if not QUANTCONNECT_DIR.exists():
        print(f"❌ Carpeta no encontrada: {QUANTCONNECT_DIR}")
        return

    print("🔌 Conectando a la base de datos SQLite...")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 1. Re-crear la tabla con el esquema multi-índice
    print("🧹 Limpiando tabla pit_constituents para carga masiva...")
    cursor.execute("DROP TABLE IF EXISTS pit_constituents")
    cursor.execute("""
        CREATE TABLE pit_constituents (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            index_member TEXT NOT NULL,
            PRIMARY KEY (date, ticker, index_member)
        )
    """)
    conn.commit()

    total_ingested = 0

    # 2. Escanear dinámicamente todos los archivos *_pit_2019_2024.csv en la carpeta
    csv_files = sorted(QUANTCONNECT_DIR.glob("*_pit_2019_2024.csv"))
    
    if not csv_files:
        print(f"⚠️ No se encontraron archivos *_pit_2019_2024.csv en {QUANTCONNECT_DIR}")
        conn.close()
        return

    print(f"📂 Se detectaron {len(csv_files)} archivos de constituyentes para procesar.")

    for file_path in csv_files:
        filename = file_path.name
        
        # Extraer el prefijo (ej: "sp500_pit_2019_2024.csv" -> "sp500")
        # Estandarizar nombre: e.g. "sp500" -> "SP500", "iwb" -> "RUSSELL1000", "iwm" -> "RUSSELL2000"
        prefix = filename.split("_")[0].upper()
        
        index_label = prefix
        if prefix == "IWB":
            index_label = "RUSSELL1000"
        elif prefix == "IWM":
            index_label = "RUSSELL2000"
        elif prefix == "QQQ":
            index_label = "NASDAQ100"
            
        print(f"\n📖 Procesando {filename} (Etiqueta DB: {index_label})...")
        df = pd.read_csv(file_path)
        
        # Limpieza estándar
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["ticker"] = df["ticker"].str.upper().str.strip()
        df["index_member"] = index_label
        
        # Eliminar duplicados locales
        df = df.drop_duplicates(subset=["date", "ticker", "index_member"])
        
        records = df[["date", "ticker", "index_member"]].values.tolist()
        print(f"   📥 Guardando {len(records)} registros en SQLite...")
        
        cursor.executemany(
            "INSERT OR REPLACE INTO pit_constituents (date, ticker, index_member) VALUES (?, ?, ?)",
            records
        )
        conn.commit()
        total_ingested += len(records)
        print(f"   ✅ {index_label} cargado.")

    # 3. Mostrar resumen estadístico agrupado
    print("\n=============================================")
    print("📊 RESUMEN DE CONSTITUYENTES PIT INGESTADOS:")
    stats = cursor.execute("""
        SELECT index_member, COUNT(*), COUNT(DISTINCT ticker), COUNT(DISTINCT date) 
        FROM pit_constituents 
        GROUP BY index_member
        ORDER BY index_member
    """).fetchall()
    
    for label, count, unique_tickers, dates in stats:
        print(f"  - {label:12}: {count:6} filas | {unique_tickers:4} tickers | {dates:3} snapshots")
        
    db_total = cursor.execute("SELECT COUNT(*) FROM pit_constituents").fetchone()[0]
    print(f"  - TOTAL EN BASE DE DATOS: {db_total} registros.")
    print("=============================================\n")
    
    conn.close()

if __name__ == "__main__":
    ingest_all()
