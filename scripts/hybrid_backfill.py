#!/usr/bin/env python3
"""
scripts/hybrid_backfill.py
Pipeline híbrido inteligente para poblar precios históricos de tickers faltantes.
1. Intenta descargar gratis en bulk vía yfinance (para tickers activos).
2. Si yfinance falla o es deslistado, recurre a la API de Tiingo (para deslistados reales).
"""

import os
import sys
import sqlite3
import argparse
import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
DEFAULT_START = "2018-01-01"  # Un año antes de 2019 para el cálculo de ADV20
DEFAULT_END = "2024-12-31"

def load_env_token() -> str:
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
    
    # Obtener tickers PIT únicos del índice especificado
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

def fetch_yfinance(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    """Intenta descargar datos ajustados desde yfinance."""
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
    end_str = end_dt.strftime("%Y-%m-%d")
    
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end_str,
            progress=False,
            auto_adjust=True,
        )
        if df.empty or len(df) < 20:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        
        # Calcular columnas de volumen
        df["dollar_volume"] = df["close"] * df["volume"]
        df["rolling_dollar_vol_20"] = (
            df["dollar_volume"].rolling(window=20, min_periods=1).mean()
        )
        
        cols = ["date", "open", "high", "low", "close", "volume", "dollar_volume", "rolling_dollar_vol_20"]
        return df[cols].copy()
    except Exception:
        return None

def fetch_tiingo(ticker: str, token: str, start: str, end: str) -> pd.DataFrame | None:
    """Descarga precios históricos ajustados desde la API de Tiingo (para deslistados)."""
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
            return "rate_limit"
        elif response.status_code != 200:
            return None
            
        data = response.json()
        if not data:
            return None
            
        df_raw = pd.DataFrame(data)
        
        df = pd.DataFrame()
        df["date"] = pd.to_datetime(df_raw["date"]).dt.strftime("%Y-%m-%d")
        df["open"] = df_raw["adjOpen"]
        df["high"] = df_raw["adjHigh"]
        df["low"] = df_raw["adjLow"]
        df["close"] = df_raw["adjClose"]
        df["volume"] = df_raw["adjVolume"]
        
        df["dollar_volume"] = df["close"] * df["volume"]
        df["rolling_dollar_vol_20"] = (
            df["dollar_volume"].rolling(window=20, min_periods=1).mean()
        )
        
        cols = ["date", "open", "high", "low", "close", "volume", "dollar_volume", "rolling_dollar_vol_20"]
        return df[cols].copy()
    except Exception:
        return None

def save_to_sqlite(ticker: str, df: pd.DataFrame):
    df["ticker"] = ticker
    cols = ["ticker", "date", "open", "high", "low", "close", "volume", "dollar_volume", "rolling_dollar_vol_20"]
    df_to_save = df[cols].copy()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
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

def main():
    parser = argparse.ArgumentParser(description="Pipeline híbrido inteligente de backfill (yfinance -> Tiingo).")
    parser.add_argument("--token", type=str, help="Token API de Tiingo")
    parser.add_argument("--all", action="store_true", help="Procesar tanto faltantes como truncados")
    parser.add_argument(
        "--index",
        default="SP500",
        choices=["SP500", "RUSSELL1000", "RUSSELL2000", "NASDAQ100", "DIA", "MDY", "SLY", "VUG", "VTV", "XLK"],
        help="Índice objetivo para poblar precios"
    )
    args = parser.parse_args()
    
    # 1. Analizar base de datos
    missing, truncated = get_missing_and_truncated_tickers(args.index)
    
    print("\n=============================================")
    print(f"📊 PIPELINE HÍBRIDO DE DATOS ({args.index}):")
    print(f"  - Tickers completamente faltantes (0 barras): {len(missing)}")
    print(f"  - Tickers con historial truncado (< 252 barras): {len(truncated)}")
    print("=============================================\n")
    
    targets = []
    targets.extend(missing)
    if args.all:
        targets.extend([t for t, _ in truncated])
        
    if not targets:
        print("🎉 ¡Excelente! No quedan tickers pendientes en SQLite para este índice.")
        return
        
    token = args.token or load_env_token()
    
    print(f"🚀 Iniciando procesamiento híbrido para {len(targets)} tickers...")
    print(f"Rango de fechas: {DEFAULT_START} -> {DEFAULT_END}\n")
    
    yf_success = 0
    tiingo_success = 0
    failed = []
    
    for i, ticker in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] Procesando {ticker}... ", end="", flush=True)
        
        # --- PASO 1: Intentar con yfinance (GRATIS) ---
        df_yf = fetch_yfinance(ticker, DEFAULT_START, DEFAULT_END)
        if df_yf is not None:
            save_to_sqlite(ticker, df_yf)
            print(f"✅ [yfinance] {len(df_yf)} barras importadas.")
            yf_success += 1
            time.sleep(0.3)
            continue
            
        # --- PASO 2: Recurrir a Tiingo (FALLBACK) ---
        if not token:
            print("❌ [yfinance] Falló. (Tiingo omitido: Falta token)")
            failed.append(ticker)
            continue
            
        df_tiingo = fetch_tiingo(ticker, token, DEFAULT_START, DEFAULT_END)
        
        if isinstance(df_tiingo, str) and df_tiingo == "rate_limit":
            print("\n⚠️ [Tiingo] HTTP 429 Límite alcanzado. Abortando fallback nocturno por esta hora.")
            failed.extend(targets[i-1:])
            break
        elif df_tiingo is not None:
            save_to_sqlite(ticker, df_tiingo)
            print(f"✅ [Tiingo] {len(df_tiingo)} barras importadas (Deslistado real).")
            tiingo_success += 1
            time.sleep(0.6)
        else:
            print("❌ [Ambos] Falló. Ticker no recuperable.")
            failed.append(ticker)
            
    print("\n=============================================")
    print("🏁 PROCESO HÍBRIDO COMPLETADO:")
    print(f"  - Total procesados: {yf_success + tiingo_success}/{len(targets)}")
    print(f"    - Vía yfinance (Gratis) : {yf_success}")
    print(f"    - Vía Tiingo (Fallback) : {tiingo_success}")
    if failed:
        print(f"  - Tickers fallidos      : {len(failed)} {failed[:15]}...")
    print("=============================================\n")

if __name__ == "__main__":
    main()
