#!/usr/bin/env python3
"""
scratch/refresh_ohlcv_subset.py
Descarga y actualiza velas diarias (OHLCV) desde yfinance para los tickers dados.
v2: Batching de 200 tickers, days_back=180 para tapar gaps y cálculo real de rolling_dollar_vol_20.
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

BATCH_SIZE = 200

def refresh_tickers(ticker_file: str, days_back: int = 180):
    tickers_path = Path(ticker_file)
    if not tickers_path.exists():
        print(f"Error: No existe el archivo {ticker_file}")
        return

    with open(tickers_path, "r", encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"[*] Tickers a actualizar: {len(tickers)} (Ventana: {days_back} dias)")
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days_back)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    total_inserted = 0

    total_batches = (len(tickers) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch = tickers[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        print(f"[*] Batch {batch_idx + 1}/{total_batches} ({len(batch)} tickers)...")

        try:
            data = yf.download(
                batch,
                start=start_str,
                end=end_str,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False
            )
        except Exception as e:
            print(f"[!] Error descargando batch {batch_idx + 1}: {e}")
            continue

        rows = []
        for ticker in batch:
            try:
                if len(batch) == 1:
                    df = data.copy()
                else:
                    if ticker not in data.columns.get_level_values(0):
                        continue
                    df = data[ticker].copy()

                if df.empty or "Close" not in df.columns:
                    continue

                df = df.dropna(subset=["Close"]).sort_index()
                if df.empty:
                    continue

                df["dollar_volume"] = df["Close"] * df["Volume"]
                df["rolling_dollar_vol_20"] = df["dollar_volume"].rolling(window=20, min_periods=1).mean()

                df = df.reset_index()

                for _, r in df.iterrows():
                    d_str = pd.to_datetime(r["Date"]).strftime("%Y-%m-%d")
                    close_val = float(r["Close"])
                    vol_val = int(r["Volume"]) if pd.notna(r["Volume"]) else 0
                    open_val = float(r["Open"]) if "Open" in r and pd.notna(r["Open"]) else close_val
                    high_val = float(r["High"]) if "High" in r and pd.notna(r["High"]) else close_val
                    low_val = float(r["Low"]) if "Low" in r and pd.notna(r["Low"]) else close_val
                    dollar_vol = float(r["dollar_volume"]) if pd.notna(r["dollar_volume"]) else close_val * vol_val
                    rolling_vol = float(r["rolling_dollar_vol_20"]) if pd.notna(r["rolling_dollar_vol_20"]) else dollar_vol

                    rows.append((
                        ticker, d_str, open_val, high_val, low_val, close_val, vol_val, dollar_vol, rolling_vol
                    ))
            except Exception:
                continue

        if rows:
            conn.executemany(
                """
                INSERT OR REPLACE INTO ohlcv_cache
                (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            conn.commit()
            total_inserted += len(rows)

    print(f"[OK] Proceso finalizado. Total registros insertados/actualizados: {total_inserted}")
    conn.close()

if __name__ == "__main__":
    t_file = sys.argv[1] if len(sys.argv) > 1 else "data/universe_1200.txt"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    refresh_tickers(t_file, days_back=days)
