import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

def debug_breadth():
    conn = sqlite3.connect(str(DB_PATH))
    
    # 1. Obtener fechas de trading de EE.UU. usando SPY como proxy
    spy_df = pd.read_sql_query(
        "SELECT date FROM ohlcv_cache WHERE ticker = 'SPY' AND date BETWEEN '2025-01-01' AND '2025-09-30' ORDER BY date",
        conn
    )
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    trading_dates = spy_df["date"].tolist()
    
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JNJ", "JPM"]
    entries = pd.DataFrame(False, index=trading_dates, columns=test_tickers)
    
    tickers = entries.columns.tolist()
    lookback_days = 20
    
    fetch_start = (entries.index[0] - pd.Timedelta(days=lookback_days * 2)).strftime("%Y-%m-%d")
    fetch_end = entries.index[-1].strftime("%Y-%m-%d")
    
    df = pd.read_sql_query(
        "SELECT ticker, date, close, high, low FROM ohlcv_cache WHERE date BETWEEN ? AND ? ORDER BY ticker, date",
        conn,
        params=[fetch_start, fetch_end],
    )
    
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df["ticker"] = df["ticker"].str.upper().str.strip()
    df = df.sort_values(["ticker", "date"]).drop_duplicates(
        subset=["ticker", "date"], keep="last"
    )
    
    close_pivot = df.pivot(index="date", columns="ticker", values="close")
    
    print("--- DIAGNÓSTICO ---")
    print(f"Index type: {close_pivot.index.dtype}")
    print(f"Columns type (close values): {df['close'].dtype}")
    
    # Ver si hay domingos u otros días de fin de semana en el índice de close_pivot
    days_of_week = close_pivot.index.dayofweek
    print(f"Days of week in close_pivot index: {set(days_of_week)}")
    weekend_days = close_pivot.index[days_of_week >= 5]
    print(f"Weekend days count: {len(weekend_days)}")
    if len(weekend_days) > 0:
        print(f"Sample weekend days: {list(weekend_days[:5])}")
    
    # Evaluar SMA20 global
    sma20 = close_pivot.rolling(20, min_periods=20).mean()
    non_nan_sma20 = sma20.notna().sum().sum()
    total_cells = sma20.size
    print(f"Global SMA20: Total cells: {total_cells}, Non-NaN cells: {non_nan_sma20} ({non_nan_sma20/total_cells*100:.4f}%)")
    
    # ¿Qué pasa si filtramos y limpiamos el DataFrame?
    # 1. Quedarnos sólo con tickers de EE.UU. (ej. que no tengan guiones ni puntos que indiquen otros mercados, o que estén en el superset de tickers de EE.UU.)
    # Los tickers de EE.UU. suelen no terminar en -KS, -SZ, -SS, .HK, .TO, etc.
    # Excluimos tickers que tengan guiones o que terminen con sufijos internacionales conocidos
    international_suffix = ('-KS', '-SZ', '-SS', '.HK', '.TO', '-HK', '-JP', '.L', '.PA', '.DE')
    us_tickers = [t for t in close_pivot.columns if not t.endswith(international_suffix) and '-' not in t]
    print(f"US Tickers estimated: {len(us_tickers)} / {len(close_pivot.columns)}")
    
    close_pivot_us = close_pivot[us_tickers]
    
    # 2. Reindexar al calendario oficial de trading de EE.UU. (trading_dates)
    # Primero reindexamos para eliminar días que no son de trading de EE.UU.
    close_pivot_us_clean = close_pivot_us.reindex(trading_dates)
    
    # Calcular SMA20 para el set limpio de EE.UU.
    sma20_us = close_pivot_us_clean.rolling(20, min_periods=20).mean()
    non_nan_sma20_us = sma20_us.notna().sum().sum()
    total_cells_us = sma20_us.size
    print(f"Cleaned US SMA20: Total cells: {total_cells_us}, Non-NaN cells: {non_nan_sma20_us} ({non_nan_sma20_us/total_cells_us*100:.2f}%)")
    
    # Calcular ratio para el set limpio
    above_us = (close_pivot_us_clean > sma20_us).sum(axis=1)
    universe_size_us = close_pivot_us_clean.notna().sum(axis=1).replace(0, np.nan)
    ratio_series_us = (above_us / universe_size_us).fillna(0.0)
    
    print("\nSample Cleaned US ratio_series (first 30 dates):")
    print(ratio_series_us.head(30))
    
    conn.close()

if __name__ == "__main__":
    debug_breadth()
