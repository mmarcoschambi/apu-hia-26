#!/usr/bin/env python3
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.indicators.pattern_detection import detect_base_construction
from src.integration.universe_builder import build_universe_for_fold

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
        (ticker, start, end),
    ).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)

def main():
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Para pruebas, usamos el último día hábil de 2024 si querés, o el actual
    # date_str = "2024-12-27" 
    
    print(f"Buscando construcciones de base institucionales (VCP/Flat Base) para {date_str}...")
    
    universe_start = (pd.to_datetime(date_str) - timedelta(days=730)).strftime("%Y-%m-%d")
    snap = build_universe_for_fold(DB_PATH, date_str, universe_start, max_tickers=200)
    
    bases_found = []
    
    df_start = (pd.to_datetime(date_str) - timedelta(days=100)).strftime("%Y-%m-%d")
    
    for ticker in snap.tickers:
        df = load_ohlcv(ticker, df_start, date_str)
        if len(df) < 30: continue
            
        result = detect_base_construction(df, min_base_days=15, atr_period=14)
        
        if result.get("in_base"):
            result["ticker"] = ticker
            result["close"] = df.iloc[-1]["close"]
            bases_found.append(result)
            
    print(f"\nSe encontraron {len(bases_found)} acciones construyendo bases:")
    print("-" * 80)
    print(f"{'Ticker':<8} | {'Close':<8} | {'Pivot':<8} | {'Rango Base':<10} | {'Vol Dry-up':<10} | {'ATR Compresión'}")
    print("-" * 80)
    
    # Ordenar por proximidad al pivot (breakout inminente)
    bases_found.sort(key=lambda x: (x["pivot"] - x["close"]) / x["close"])
    
    for b in bases_found:
        vol_str = "Sí 💧" if b["volume_dry"] else "No"
        print(f"{b['ticker']:<8} | ${b['close']:<7.2f} | ${b['pivot']:<7.2f} | {b['price_range_pct']:>5.1f}%     | {vol_str:<10} | {b['atr_compression']:.2f}x")

if __name__ == "__main__":
    main()
