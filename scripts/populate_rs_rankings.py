"""
populate_rs_rankings.py  -  REFACTORED v2
Pobla la tabla daily_rs_rankings.

Cambios vs v1:
  - 1 bulk SQL query por fecha en vez de N queries individuales (N = nro tickers)
  - Pivot + vectorizacion numpy: cero loops Python sobre tickers
  - ~20-50x mas rapido por fecha
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import logging
import sys

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


def ensure_table(conn):
    for stmt in CREATE_TABLE_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


def compute_rs_for_date(conn, target_date):
    """
    Carga TODOS los tickers en un solo bulk query y vectoriza los calculos.
    v1 hacia N queries individuales en loop; v2 hace 1 query + pivot en pandas.
    """
    from_date = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=120)
    ).strftime("%Y-%m-%d")

    bulk_q = """
        SELECT ticker, DATE(date) as date, close
        FROM ohlcv_cache
        WHERE date >= ? AND date <= ?
          AND ticker NOT LIKE '%-KS'
          AND ticker NOT LIKE '%-VN'
          AND ticker NOT LIKE '%-T'
          AND ticker NOT LIKE '^%'
        ORDER BY ticker, date
    """
    df = pd.read_sql_query(bulk_q, conn, params=(from_date, target_date + " 23:59:59"))

    if df.empty:
        logger.warning(f"No data found for {from_date} to {target_date}")
        return pd.DataFrame()

    pivot = df.pivot_table(index="date", columns="ticker", values="close")
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index()

    target_dt = pd.to_datetime(target_date)
    if target_dt not in pivot.index:
        logger.warning(
            f"{target_date}: target_dt no está en pivot. "
            f"pivot max={pivot.index.max()}, shape={pivot.shape}"
        )
        return pd.DataFrame()

    pivot = pivot.loc[:target_dt]

    valid_on_target = pivot.loc[target_date].notna()
    counts = pivot.notna().sum()
    valid_mask = valid_on_target & (counts >= 65)
    pivot = pivot.loc[:, valid_mask]

    if pivot.shape[1] == 0:
        return pd.DataFrame()

    last = pivot.iloc[-1]
    p5 = pivot.iloc[-6] if len(pivot) >= 6 else None
    p20 = pivot.iloc[-21] if len(pivot) >= 21 else None
    p60 = pivot.iloc[-61] if len(pivot) >= 61 else None

    def safe_ret(last_s, base_s):
        if base_s is None:
            return pd.Series(0.0, index=last_s.index)
        valid = (base_s > 0) & base_s.notna() & last_s.notna()
        ret = pd.Series(0.0, index=last_s.index)
        ret[valid] = (last_s[valid] / base_s[valid] - 1) * 100
        return ret

    ret_5d = safe_ret(last, p5)
    ret_20d = safe_ret(last, p20)
    ret_60d = safe_ret(last, p60)

    has_60d = ret_60d != 0.0
    ret_5d = ret_5d[has_60d]
    ret_20d = ret_20d[has_60d]
    ret_60d = ret_60d[has_60d]

    if len(ret_60d) < 2:
        return pd.DataFrame()

    def to_pct(s):
        ranks = s.rank(method="average")
        return (ranks - 1) / (len(s) - 1) * 100

    result = pd.DataFrame(
        {
            "ticker": ret_60d.index,
            "rs_60d_pct": to_pct(ret_60d).values,
            "rs_20d_pct": to_pct(ret_20d).values,
            "rs_5d_pct": to_pct(ret_5d).values,
        }
    )

    result["rs_composite"] = (
        0.50 * result["rs_60d_pct"]
        + 0.35 * result["rs_20d_pct"]
        + 0.15 * result["rs_5d_pct"]
    )
    result["date"] = target_date
    result["universe_size"] = len(result)

    logger.info(f"{target_date}: {len(result)} tickers RS calculados")
    return result[
        [
            "date",
            "ticker",
            "rs_60d_pct",
            "rs_20d_pct",
            "rs_5d_pct",
            "rs_composite",
            "universe_size",
        ]
    ]


def populate_date(conn, target_date, overwrite=False):
    if target_date:
        target_date = str(target_date)[:10]
    if not overwrite:
        existing = conn.execute(
            "SELECT COUNT(*) FROM daily_rs_rankings WHERE date = ?", (target_date,)
        ).fetchone()[0]
        if existing > 0:
            logger.info(f"{target_date}: ya tiene {existing} filas, skip")
            return

    result = compute_rs_for_date(conn, target_date)
    if result.empty:
        logger.warning(f"{target_date}: sin datos suficientes")
        return

    if overwrite:
        conn.execute("DELETE FROM daily_rs_rankings WHERE date = ?", (target_date,))

    result.to_sql("daily_rs_rankings", conn, if_exists="append", index=False)
    conn.commit()
    logger.info(f"{target_date}: insertados {len(result)} tickers")


def get_trading_dates(conn, days_back):
    query = """
        SELECT DISTINCT date FROM ohlcv_cache
        WHERE ticker NOT LIKE '%-KS' AND ticker NOT LIKE '%-VN' AND ticker NOT LIKE '%-T'
        AND ticker NOT LIKE '^%'
        ORDER BY date DESC LIMIT ?
    """
    rows = conn.execute(query, (days_back,)).fetchall()
    return [r[0] for r in reversed(rows)]


def main():
    parser = argparse.ArgumentParser(description="Pobla daily_rs_rankings")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--days-back", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    dates = [args.date] if args.date else get_trading_dates(conn, args.days_back)
    logger.info(f"Procesando {len(dates)} fecha(s)")
    for d in dates:
        populate_date(conn, d, overwrite=args.overwrite)

    conn.close()
    logger.info("Listo.")


if __name__ == "__main__":
    main()
