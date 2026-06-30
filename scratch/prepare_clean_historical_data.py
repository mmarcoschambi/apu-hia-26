#!/usr/bin/env python3
"""
prepare_clean_historical_data.py — Limpia la caché local (data/ticker_cache.db) de la
corrupción residual del Issue #39 y descarga de yfinance los datos OHLCV limpios para
los últimos 3 meses.

Sienta las bases para validar el sistema principal con 3 meses de histórico limpio.
"""

import os
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta
import socket
import pandas as pd
import yfinance as yf

# Configurar timeout global para evitar que yfinance se cuelgue indefinidamente
socket.setdefaulttimeout(15)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "ticker_cache.db"
OUT_DIR = ROOT / "outputs" / "paper_finviz"


def get_vps_snapshot_tickers(days_back: int = 90) -> tuple[set[str], str, str]:
    """Escanea las carpetas de outputs/paper_finviz de los últimos N días y extrae los tickers."""
    tickers = set()
    today = datetime.now()
    start_date = today - timedelta(days=days_back)
    
    dates_found = []
    
    for path in OUT_DIR.iterdir():
        if not path.is_dir():
            continue
        try:
            folder_date = datetime.strptime(path.name, "%Y-%m-%d")
            if folder_date >= start_date:
                dates_found.append(path.name)
        except ValueError:
            continue
            
    if not dates_found:
        print(f"  [ERROR] No se encontraron carpetas de fechas en los últimos {days_back} días en {OUT_DIR}")
        sys.exit(1)
        
    dates_found.sort()
    min_date = dates_found[0]
    max_date = dates_found[-1]
    
    print(f"  [Snapshots] Escaneando {len(dates_found)} fechas desde {min_date} hasta {max_date}...")
    
    for date_str in dates_found:
        snap_path = OUT_DIR / date_str / "snapshot.json"
        if snap_path.exists():
            try:
                with open(snap_path) as f:
                    data = json.load(f)
                    wl = data.get("watchlist_detail", {})
                    for t in wl.keys():
                        tickers.add(t.upper().replace(".", "-"))
            except Exception as e:
                print(f"    [WARN] No se pudo leer {snap_path}: {e}")
                
    return tickers, min_date, max_date


PROGRESS_FILE = ROOT / "scratch" / "warmup_progress.json"


def load_progress() -> set[str]:
    """Carga la lista de tickers que ya fueron descargados y guardados de forma limpia."""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
                return set(data.get("completed", []))
        except Exception:
            pass
    return set()


def save_progress(completed_tickers: set[str]) -> None:
    """Guarda el progreso actual en el archivo JSON."""
    try:
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"completed": sorted(list(completed_tickers))}, f, indent=2)
    except Exception as e:
        print(f"    [WARN] No se pudo guardar progreso en {PROGRESS_FILE}: {e}")


def clean_corrupted_tickers_in_db(tickers: list[str], start_date_str: str) -> None:
    """Borra la data histórica corrupta de los tickers especificados."""
    if not tickers:
        return
        
    print(f"  [DB] Conectando a {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Asegurar esquema básico
    cur.execute("PRAGMA journal_mode=WAL")
    
    # Borramos de ohlcv_cache para que no quede data sucia duplicada
    # Hacemos el borrado desde la fecha de inicio menos 300 días para limpiar historial
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    clean_from_dt = (start_dt - timedelta(days=300)).strftime("%Y-%m-%d")
    
    print(f"  [DB] Eliminando registros de ohlcv_cache y daily_rs_rankings para {len(tickers)} tickers desde {clean_from_dt}...")
    
    # SQLite limit de variables es habitualmente 999, borramos en batches de 500
    batch_size = 500
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        placeholders = ",".join(["?"] * len(batch))
        
        cur.execute(
            f"DELETE FROM ohlcv_cache WHERE ticker IN ({placeholders}) AND date >= ?",
            tuple(batch + [clean_from_dt])
        )
        cur.execute(
            f"DELETE FROM daily_rs_rankings WHERE ticker IN ({placeholders}) AND date >= ?",
            tuple(batch + [clean_from_dt])
        )
        
    conn.commit()
    conn.close()
    print("  [DB] Limpieza de tickers pendientes completada con éxito.")


def fetch_and_store_ohlcv(
    pending_tickers: list[str],
    completed_tickers: set[str],
    start_date_str: str,
    end_date_str: str,
    total_original: int
) -> None:
    """Descarga de yfinance los datos limpios y los almacena en ohlcv_cache, actualizando progreso."""
    if not pending_tickers:
        print("  [yfinance] Todos los tickers ya fueron completados previamente.")
        return

    # Ampliamos la fecha de inicio hacia atrás para tener suficiente historial para las MAs (200 períodos)
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    extended_start = (start_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    
    # Fin del período de descarga (mañana del end_date para asegurar cobertura)
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
    extended_end = (end_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    
    print(f"  [yfinance] Rango de descarga extendido: {extended_start} a {extended_end}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    
    # Asegurar esquema por si acaso
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            dollar_volume REAL,
            rolling_dollar_vol_20 REAL,
            PRIMARY KEY (ticker, date)
        )
        """
    )
    conn.commit()
    
    success_count = 0
    start_idx = len(completed_tickers) + 1
    
    print(f"  [yfinance] Descargando {len(pending_tickers)} tickers pendientes (iniciando en {start_idx}/{total_original})...")
    
    for idx, ticker in enumerate(pending_tickers, start_idx):
        try:
            # Descargar datos
            df = yf.download(
                ticker,
                start=extended_start,
                end=extended_end,
                progress=False,
                auto_adjust=True
            )
            
            if df.empty:
                print(f"    [{idx}/{total_original}] ⚠️  {ticker}: Sin datos en yfinance")
                # Lo registramos como completado para no intentar de nuevo en un restart
                completed_tickers.add(ticker)
                save_progress(completed_tickers)
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            df["dollar_volume"] = df["Close"] * df["Volume"]
            df["rolling_dollar_vol_20"] = (
                df["dollar_volume"].rolling(window=20, min_periods=1).mean()
            )
            
            # Formatear filas para insertar
            rows = []
            for _, r in df.iterrows():
                rows.append((
                    ticker,
                    r["date"],
                    float(r["Open"]),
                    float(r["High"]),
                    float(r["Low"]),
                    float(r["Close"]),
                    int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
                    float(r["dollar_volume"]) if pd.notna(r["dollar_volume"]) else 0.0,
                    float(r["rolling_dollar_vol_20"]) if pd.notna(r["rolling_dollar_vol_20"]) else 0.0
                ))
                
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv_cache
                (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            conn.commit()
            success_count += 1
            print(f"    [{idx}/{total_original}] ✅ {ticker}: {len(rows)} filas ingresadas")
            
            # Actualizar progreso
            completed_tickers.add(ticker)
            save_progress(completed_tickers)
            
        except Exception as e:
            print(f"    [{idx}/{total_original}] ❌ {ticker}: Falló descarga — {e}")
            
    conn.close()
    print(f"\n  [yfinance] Completado. Descargados con éxito en esta sesión: {success_count}/{len(pending_tickers)} tickers")


def main():
    print("=" * 80)
    print("  PREPARACIÓN DE HISTÓRICO LIMPIO DE 3 MESES (LABORATORIO LOCAL)")
    print("=" * 80)
    
    # 1. Obtener tickers de los snapshots de los últimos 90 días
    tickers, min_date, max_date = get_vps_snapshot_tickers(days_back=90)
    tickers_list = sorted(list(tickers))
    total_original = len(tickers_list)
    print(f"  Encontrados {total_original} tickers únicos en snapshots de los últimos 90 días.")
    
    if not tickers_list:
        print("  [ERROR] No hay tickers para procesar.")
        sys.exit(1)
        
    # 2. Cargar progreso previo
    completed_tickers = load_progress()
    if completed_tickers:
        print(f"  [Resume] Encontrados {len(completed_tickers)} tickers ya procesados anteriormente.")
        pending_tickers = [t for t in tickers_list if t not in completed_tickers]
    else:
        pending_tickers = tickers_list
        
    print(f"  [Resume] Quedan {len(pending_tickers)} tickers por procesar.")
    
    # 3. Limpiar base de datos local (solo los pendientes, para no perder lo ya descargado)
    if pending_tickers:
        clean_corrupted_tickers_in_db(pending_tickers, min_date)
    
    # 4. Descargar e insertar datos frescos y limpios de yfinance
    fetch_and_store_ohlcv(pending_tickers, completed_tickers, min_date, max_date, total_original)
    
    # 5. Si terminamos todo, eliminamos el archivo de progreso
    if len(completed_tickers) >= total_original:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            print("  [Resume] Descarga completada al 100%. Limpiando archivo de progreso.")
            
    print("\n" + "=" * 80)
    print("  SIGUIENTES PASOS SUGERIDOS")
    print("=" * 80)
    print("  Para recalcular los rankings diarios y dejar la base lista para validación:")
    print(f"  python3 scripts/populate_rankings_daily.py --start {min_date} --end {max_date} --overwrite --workers 2")
    print("=" * 80)


if __name__ == "__main__":
    main()
