"""
populate_rs_rankings.py
Pobla la tabla daily_rs_rankings en ticker_cache.db.
Se ejecuta después de populate_market_data.py.

Uso:
    python scripts/populate_rs_rankings.py [--date 2025-01-15] [--days-back 1]
"""
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import logging
import sys

# Asegurar que el path raíz del proyecto esté en sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_rs_rankings (
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    rs_60d_pct REAL,
    rs_20d_pct REAL,
    rs_5d_pct REAL,
    rs_composite REAL,
    universe_size INTEGER,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_rs_date ON daily_rs_rankings(date);
CREATE INDEX IF NOT EXISTS idx_rs_pct  ON daily_rs_rankings(date, rs_60d_pct DESC);
"""


def ensure_table(conn: sqlite3.Connection):
    for stmt in CREATE_TABLE_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


def compute_rs_for_date(conn: sqlite3.Connection, target_date: str) -> pd.DataFrame:
    """
    Para cada ticker activo en target_date calcula performance a 5d, 20d, 60d
    y devuelve percentiles cross-seccionales.
    """
    # Necesitamos precios hasta target_date con suficiente historia (60d + buffer)
    from_date = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=100)).strftime("%Y-%m-%d")

    query = """
        SELECT ticker, date, close
        FROM ohlcv_cache
        WHERE date BETWEEN ? AND ?
        ORDER BY ticker, date
    """
    df = pd.read_sql_query(query, conn, params=(from_date, target_date))

    if df.empty:
        logger.warning(f"No data found for date range {from_date} – {target_date}")
        return pd.DataFrame()

    # Pivot: índice = date, columnas = ticker
    pivot = df.pivot(index="date", columns="ticker", values="close")
    pivot.index = pd.to_datetime(pivot.index)
    pivot.sort_index(inplace=True)

    if target_date not in pivot.index.strftime("%Y-%m-%d").tolist():
        logger.warning(f"target_date {target_date} not in data")
        return pd.DataFrame()

    target_idx = pivot.index[pivot.index.strftime("%Y-%m-%d") == target_date][0]
    target_pos = pivot.index.get_loc(target_idx)

    def perf(lookback: int) -> pd.Series:
        if target_pos < lookback:
            return pd.Series(dtype=float)
        past_idx = target_pos - lookback
        past_prices = pivot.iloc[past_idx]
        curr_prices = pivot.iloc[target_pos]
        return (curr_prices / past_prices - 1) * 100

    p5  = perf(5)
    p20 = perf(20)
    p60 = perf(60)

    # Alinear en un solo DataFrame (sólo tickers con datos en los 3 períodos)
    combined = pd.DataFrame({"ret_5d": p5, "ret_20d": p20, "ret_60d": p60}).dropna()
    if combined.empty:
        return pd.DataFrame()

    n = len(combined)

    def to_percentile(series: pd.Series) -> pd.Series:
        ranks = series.rank(method="average")
        return (ranks - 1) / (n - 1) * 100 if n > 1 else pd.Series(50.0, index=series.index)

    combined["rs_5d_pct"]  = to_percentile(combined["ret_5d"])
    combined["rs_20d_pct"] = to_percentile(combined["ret_20d"])
    combined["rs_60d_pct"] = to_percentile(combined["ret_60d"])
    combined["rs_composite"] = (
        0.50 * combined["rs_60d_pct"]
        + 0.35 * combined["rs_20d_pct"]
        + 0.15 * combined["rs_5d_pct"]
    )
    combined["date"] = target_date
    combined["universe_size"] = n
    combined = combined.reset_index().rename(columns={"ticker": "ticker"})

    return combined[["date", "ticker", "rs_60d_pct", "rs_20d_pct", "rs_5d_pct", "rs_composite", "universe_size"]]


def populate_date(conn: sqlite3.Connection, target_date: str, overwrite: bool = False):
    if not overwrite:
        existing = conn.execute(
            "SELECT COUNT(*) FROM daily_rs_rankings WHERE date = ?", (target_date,)
        ).fetchone()[0]
        if existing > 0:
            logger.info(f"{target_date}: ya tiene {existing} filas, skip (--overwrite para forzar)")
            return

    logger.info(f"Calculando RS para {target_date} ...")
    result = compute_rs_for_date(conn, target_date)
    if result.empty:
        logger.warning(f"{target_date}: sin datos suficientes")
        return

    if overwrite:
        conn.execute("DELETE FROM daily_rs_rankings WHERE date = ?", (target_date,))

    result.to_sql("daily_rs_rankings", conn, if_exists="append", index=False)
    conn.commit()
    logger.info(f"{target_date}: insertados {len(result)} tickers (universo={result['universe_size'].iloc[0]})")


def get_trading_dates(conn: sqlite3.Connection, days_back: int) -> list:
    query = """
        SELECT DISTINCT date FROM ohlcv_cache
        ORDER BY date DESC
        LIMIT ?
    """
    rows = conn.execute(query, (days_back,)).fetchall()
    return [r[0] for r in reversed(rows)]


def main():
    parser = argparse.ArgumentParser(description="Pobla daily_rs_rankings")
    parser.add_argument("--date", type=str, default=None, help="Fecha específica YYYY-MM-DD")
    parser.add_argument("--days-back", type=int, default=1, help="Cantidad de días a repoblar")
    parser.add_argument("--overwrite", action="store_true", help="Sobreescribir filas existentes")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    if args.date:
        dates = [args.date]
    else:
        dates = get_trading_dates(conn, args.days_back)

    logger.info(f"Procesando {len(dates)} fecha(s): {dates}")
    for d in dates:
        populate_date(conn, d, overwrite=args.overwrite)

    conn.close()
    logger.info("Listo.")


if __name__ == "__main__":
    main()
