#!/usr/bin/env python3
"""
scripts/backfill_delisted_prices.py
Descarga precios históricos ajustados para tickers deslistados y truncados 
desde la API de Tiingo y los inserta en ohlcv_cache en ticker_cache.db.
"""

import os
import sys
import sqlite3
import argparse
import time
import requests
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
DEFAULT_START = "2018-01-01"  # Un año antes de 2019 para poder calcular el ADV20 inicial correctamente
DEFAULT_END = "2024-12-31"

def load_env_token() -> str:
    # Intentar cargar desde el archivo .env
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("TIINGO_API_KEY="):
                    return line.strip().split("=")[1].strip()
    return os.environ.get("TIINGO_API_KEY", "")

def get_missing_and_truncated_tickers(index_member: str):
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Todos los tickers que pertenecían al índice especificado PIT
    pit_tickers = [
        r[0] for r in cursor.execute(
            "SELECT DISTINCT ticker FROM pit_constituents WHERE index_member = ?", 
            (index_member,)
        ).fetchall()
    ]
    
    missing = []
    truncated = []
    
    for t in sorted(pit_tickers):
        cnt = cursor.execute("SELECT COUNT(*) FROM ohlcv_cache WHERE ticker=?", (t,)).fetchone()[0]
        if cnt == 0:
            missing.append(t)
        elif cnt < 252:
            truncated.append((t, cnt))
            
    conn.close()
    return missing, truncated

def fetch_and_ingest_ticker(ticker: str, token: str, start: str, end: str) -> bool | str | None:
    print(f"📥 Descargando {ticker} desde Tiingo...")
    
    # Normalizar ticker para la URL de Tiingo (ej: BF.B -> BF-B)
    tiingo_ticker = ticker.lower().replace(".", "-")
    url = f"https://api.tiingo.com/tiingo/daily/{tiingo_ticker}/prices"
    params = {
        "startDate": start,
        "endDate": end,
        "token": token,
        "resampleFreq": "daily"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 429:
            print("⚠️ [HTTP 429] Límite de peticiones de Tiingo alcanzado. Deteniendo proceso para no bloquear la cuenta.")
            print("Sugerencia: Si usas la versión gratuita, espera 1 hora o ingresa un Token Premium.")
            return "abort"
        elif response.status_code == 404:
            print(f"❌ [HTTP 404] Ticker {ticker} no encontrado en Tiingo. (A veces los tickers muy antiguos tienen identificadores especiales).")
            return False
        elif response.status_code != 200:
            print(f"❌ Error HTTP {response.status_code} para {ticker}: {response.text}")
            return False
            
        data = response.json()
        if not data:
            print(f"⚠️ No se encontraron precios para {ticker} en el rango {start} -> {end}")
            return False
            
        df_raw = pd.DataFrame(data)
        
        # Crear un nuevo DataFrame limpio para evitar colisiones de nombres con las columnas crudas de Tiingo
        df = pd.DataFrame()
        df["date"] = pd.to_datetime(df_raw["date"]).dt.strftime("%Y-%m-%d")
        df["open"] = df_raw["adjOpen"]
        df["high"] = df_raw["adjHigh"]
        df["low"] = df_raw["adjLow"]
        df["close"] = df_raw["adjClose"]
        df["volume"] = df_raw["adjVolume"]
        
        # Calcular dollar_volume y rolling_dollar_vol_20
        df["dollar_volume"] = df["close"] * df["volume"]
        df["rolling_dollar_vol_20"] = (
            df["dollar_volume"].rolling(window=20, min_periods=1).mean()
        )
        
        # Columnas requeridas por el esquema de ohlcv_cache
        cols = ["ticker", "date", "open", "high", "low", "close", "volume", "dollar_volume", "rolling_dollar_vol_20"]
        df["ticker"] = ticker
        
        df_to_save = df[cols].copy()
        
        # Guardar en SQLite
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Inserción eficiente
        records = df_to_save.values.tolist()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO ohlcv_cache 
            (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records
        )
        conn.commit()
        conn.close()
        
        print(f"✅ {ticker} importado con éxito: {len(df_to_save)} barras guardadas en ohlcv_cache.")
        return True
        
    except Exception as e:
        print(f"💥 Excepción procesando {ticker}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Backfill de precios históricos para deslistados.")
    parser.add_argument("--token", type=str, help="Token API de Tiingo")
    parser.add_argument("--all", action="store_true", help="Procesar tanto faltantes como truncados")
    parser.add_argument(
        "--index",
        default="SP500",
        choices=["SP500", "RUSSELL1000", "RUSSELL2000", "NASDAQ100"],
        help="Index to backfill missing tickers for"
    )
    args = parser.parse_args()
    
    # 1. Obtener tickers candidatos
    missing, truncated = get_missing_and_truncated_tickers(args.index)
    
    print("\n=============================================")
    print(f"📊 ANÁLISIS DE TICKERS FALTANTES/TRUNCADOS ({args.index}):")
    print(f"  - Tickers completamente faltantes (0 barras): {len(missing)}")
    print(f"  - Tickers con historial truncado (< 252 barras): {len(truncated)}")
    print("=============================================\n")

    # 2. Resolver token
    token = args.token or load_env_token()
    if not token:
        print("❌ Error: No se detectó ninguna API Key de Tiingo.")
        print("Obtén una gratis en https://api.tiingo.com/ e ingresa con:")
        print("  - Argumento: python3 scripts/backfill_delisted_prices.py --token TU_API_KEY")
        print("  - O agrega la línea TIINGO_API_KEY=tu_token en tu archivo .env")
        sys.exit(1)
    
    # Determinar objetivos
    targets = []
    targets.extend(missing)
    if args.all:
        targets.extend([t for t, _ in truncated])
        
    if not targets:
        print("🎉 ¡Excelente! No quedan tickers completamente faltantes en tu base de datos.")
        print("Si quieres recalcular los truncados, corre con el parámetro `--all`")
        return
        
    print(f"🚀 Iniciando descarga de precios para {len(targets)} tickers...")
    print(f"Rango de descarga: {DEFAULT_START} -> {DEFAULT_END}\n")
    
    success_count = 0
    failed_tickers = []
    
    for i, ticker in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] ", end="")
        status = fetch_and_ingest_ticker(ticker, token, DEFAULT_START, DEFAULT_END)
        
        if status == "abort":
            print("\n🛑 Proceso interrumpido debido a límite de peticiones (429).")
            break
        elif status is True:
            success_count += 1
        else:
            failed_tickers.append(ticker)
            
        # Pequeña pausa para no saturar y respetar WAF
        time.sleep(0.6)
        
    print(f"\n🏁 PROCESO FINALIZADO.")
    print(f"  - Tickers importados con éxito: {success_count}/{len(targets)}")
    if failed_tickers:
        print(f"  - Tickers fallidos o no encontrados: {len(failed_tickers)} {failed_tickers}")
    print("Corre de nuevo el backtest para ver el impacto de las pérdidas delisted en tus métricas.")

if __name__ == "__main__":
    main()
