#!/usr/bin/env python3
"""
populate_triad_rankings.py  -  REFACTORED v2

Cambios vs v1:
  - 1 bulk SQL query por fecha (v1 hacia N queries en loop principal
    + N queries adicionales en el segundo loop para AS -- total 2N queries)
  - Pivot + vectorizacion: SMAs calculadas con pandas rolling sobre el pivot
  - Eliminado el segundo loop completo de AS (estaba duplicando todo el trabajo)
  - ~30-80x mas rapido por fecha
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
CREATE TABLE IF NOT EXISTS daily_triad_rankings (
    date DATE NOT NULL,
    ticker TEXT NOT NULL,
    as_5d_pct REAL,
    as_21d_pct REAL,
    trend_score_raw REAL,
    rs_composite REAL,
    rts_raw REAL,
    rts_pct REAL,
    atr14 REAL,
    atr14_universe_mean REAL,
    pivot_dist_pct REAL,
    green_candle INTEGER,
    universe_size INTEGER,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_triad_date ON daily_triad_rankings(date);
CREATE INDEX IF NOT EXISTS idx_triad_rts  ON daily_triad_rankings(date, rts_pct DESC);
"""


def ensure_table(conn):
    for stmt in CREATE_TABLE_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except Exception as e:
                logger.debug(f"Table creation: {e}")
    conn.commit()


def _trend_score_vectorized(close_pivot, sma50, sma150, sma200):
    """
    Calcula trend_score para todos los tickers de una sola vez.
    Misma logica que v1 pero vectorizada sobre columnas del pivot.
    """
    scores = pd.Series(0.0, index=close_pivot.columns)

    if len(sma50) >= 20:
        slope50 = (sma50.iloc[-1] / sma50.iloc[-20].replace(0, np.nan) - 1) * 100
        scores = scores + np.where(slope50 > 0.5, 2, np.where(slope50 > 0, 1, 0))

    if len(sma150) >= 20:
        slope150 = (sma150.iloc[-1] / sma150.iloc[-20].replace(0, np.nan) - 1) * 100
        scores = scores + np.where(slope150 > 0.5, 2, np.where(slope150 > 0, 1, 0))

    if len(sma200) >= 20:
        slope200 = (sma200.iloc[-1] / sma200.iloc[-20].replace(0, np.nan) - 1) * 100
        scores = scores + np.where(slope200 > 0.5, 2, np.where(slope200 > 0, 1, 0))

    price = close_pivot.iloc[-1]
    scores = scores + (price > sma50.iloc[-1]).astype(float).values
    scores = scores + (sma50.iloc[-1] > sma150.iloc[-1]).astype(float).values
    scores = scores + (sma150.iloc[-1] > sma200.iloc[-1]).astype(float).values

    lookback = min(252, len(close_pivot))
    high_52w = close_pivot.iloc[-lookback:].max()
    scores = scores + (price >= high_52w * 0.90).astype(float).values

    return scores.clip(1.0, 11.0)


def compute_triad_for_date(conn, target_date, max_tickers=500):
    """
    v2: 1 bulk query OHLCV + pivot. Cero loops sobre tickers.
    v1 hacia: N queries (loop principal) + N queries mas (loop AS) = 2N total.
    """
    top_q = f"""
        SELECT DISTINCT ticker
        FROM ohlcv_cache
        WHERE date >= '{target_date}' AND date <= '{target_date} 23:59:59'
          AND ticker NOT LIKE '%-%'
          AND ticker NOT LIKE '^%'
          AND rolling_dollar_vol_20 IS NOT NULL
          AND close > 0
          AND volume > 0
        ORDER BY rolling_dollar_vol_20 DESC
        LIMIT {max_tickers}
    """
    top_tickers = [r[0] for r in conn.execute(top_q).fetchall()]
    if len(top_tickers) < 100:
        logger.debug(
            f"{target_date}: feriado/mercado cerrado ({len(top_tickers)} tickers), skip"
        )
        return pd.DataFrame()
    if not top_tickers:
        logger.warning(f"No tickers found for {target_date}")
        return pd.DataFrame()

    from_date = (
        datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=320)
    ).strftime("%Y-%m-%d")

    placeholders = ",".join("?" * len(top_tickers))

    bulk_q = f"""
        SELECT ticker, DATE(date) as date, open, high, low, close, volume
        FROM ohlcv_cache
        WHERE ticker IN ({placeholders})
          AND date >= ? AND date <= ?
        ORDER BY ticker, date
    """
    df = pd.read_sql_query(
        bulk_q, conn, params=top_tickers + [from_date, target_date + " 23:59:59"]
    )
    logger.info(
        f"DEBUG: bulk query returned {len(df)} rows, {df['ticker'].nunique()} tickers"
    )

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["ticker", "date"]).sort_values(["ticker", "date"])

    close_p = df.pivot_table(index="date", columns="ticker", values="close")
    open_p = df.pivot_table(index="date", columns="ticker", values="open")
    high_p = df.pivot_table(index="date", columns="ticker", values="high")
    low_p = df.pivot_table(index="date", columns="ticker", values="low")

    for p in [close_p, open_p, high_p, low_p]:
        p.sort_index(inplace=True)

    target_dt = pd.to_datetime(target_date)
    logger.info(
        f"DEBUG: target_dt={target_dt}, pivot index type={type(close_p.index)}, first few: {list(close_p.index[:3])}"
    )
    if target_dt not in close_p.index:
        logger.warning(
            f"{target_date}: target_dt no está en pivot. "
            f"pivot max={close_p.index.max()}, shape={close_p.shape}"
        )
        return pd.DataFrame()

    close_p = close_p.loc[:target_dt]
    logger.info(
        f"DEBUG: close_p sliced rows: {len(close_p)}, last index: {close_p.index[-1] if len(close_p) > 0 else 'empty'}"
    )
    open_p = open_p.loc[:target_dt]
    high_p = high_p.loc[:target_dt]
    low_p = low_p.loc[:target_dt]

    counts = close_p.notna().sum()
    on_target = close_p.loc[target_dt].notna()
    valid = (counts >= 200) & on_target
    cols = valid[valid].index.tolist()
    logger.info(
        f"DEBUG: counts >= 200: {(counts >= 200).sum()}, on_target: {on_target.sum()}, valid cols: {len(cols)}"
    )

    if not cols:
        return pd.DataFrame()

    close_p = close_p[cols]
    open_p = open_p[cols]
    high_p = high_p[cols]
    low_p = low_p[cols]

    sma50 = close_p.rolling(50, min_periods=50).mean()
    sma150 = close_p.rolling(150, min_periods=150).mean()
    sma200 = close_p.rolling(200, min_periods=200).mean()

    sma_valid = (
        sma50.iloc[-1].notna() & sma150.iloc[-1].notna() & sma200.iloc[-1].notna()
    )
    valid_cols = sma_valid[sma_valid].index.tolist()
    logger.info(f"DEBUG: after SMA filter: {len(valid_cols)} tickers have all SMAs")

    if not valid_cols:
        logger.info(
            f"DEBUG: checking sma50 last for first ticker: {sma50.iloc[-1].head()}"
        )
        return pd.DataFrame()

    if not cols:
        logger.warning(f"No tickers after SMA filter for {target_date}")
        return pd.DataFrame()

    close_p = close_p[cols]
    open_p = open_p[cols]
    high_p = high_p[cols]
    low_p = low_p[cols]
    sma50 = sma50[cols]
    sma150 = sma150[cols]
    sma200 = sma200[cols]

    price = close_p.iloc[-1]

    trend_scores = _trend_score_vectorized(close_p, sma50, sma150, sma200)

    rs_data = pd.Series(50.0, index=cols)
    try:
        rs_df = pd.read_sql_query(
            "SELECT ticker, rs_composite FROM daily_rs_rankings WHERE date = ?",
            conn,
            params=(target_date,),
        )
        if not rs_df.empty:
            rs_series = rs_df.set_index("ticker")["rs_composite"]
            rs_data.update(rs_series)
    except Exception as e:
        logger.debug(f"RS rankings not available: {e}")

    rts_raw = trend_scores * (rs_data / 100.0 * 10)

    prev_close = close_p.shift(1)
    tr1 = high_p - low_p
    tr2 = (high_p - prev_close).abs()
    tr3 = (low_p - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3]).groupby(level=0).max()
    atr14 = tr.rolling(14, min_periods=14).mean().iloc[-1]

    high_20d = high_p.iloc[-21:].max()
    pivot_dist = ((price - high_20d) / high_20d.replace(0, np.nan) * 100).fillna(0.0)

    prev_close_last = close_p.iloc[-2] if len(close_p) >= 2 else price
    green = ((price >= open_p.iloc[-1]) & (price >= prev_close_last)).astype(int)

    ret_5d = (
        (price / close_p.iloc[-6].replace(0, np.nan) - 1) * 100
        if len(close_p) >= 6
        else pd.Series(0.0, index=cols)
    )
    ret_21d = (
        (price / close_p.iloc[-22].replace(0, np.nan) - 1) * 100
        if len(close_p) >= 22
        else pd.Series(0.0, index=cols)
    )
    ret_5d = ret_5d.fillna(0.0)
    ret_21d = ret_21d.fillna(0.0)

    result = pd.DataFrame(
        {
            "ticker": cols,
            "trend_score_raw": trend_scores.values,
            "rs_composite": rs_data.values,
            "rts_raw": rts_raw.values,
            "atr14": atr14.values,
            "pivot_dist_pct": pivot_dist.values,
            "green_candle": green.values,
            "ret_5d_raw": ret_5d.values,
            "ret_21d_raw": ret_21d.values,
        }
    )

    n = len(result)
    if n >= 2:
        result["as_5d_pct"] = result["ret_5d_raw"].rank(pct=True) * 100
        result["as_21d_pct"] = result["ret_21d_raw"].rank(pct=True) * 100
        result["rts_pct"] = result["rts_raw"].rank(pct=True) * 99
    else:
        result["as_5d_pct"] = 50.0
        result["as_21d_pct"] = 50.0
        result["rts_pct"] = 50.0

    result["atr14_universe_mean"] = result["atr14"].mean()
    result["date"] = target_date
    result["universe_size"] = n

    logger.info(f"{target_date}: {n} tickers Triad calculados")

    cols_out = [
        "date",
        "ticker",
        "as_5d_pct",
        "as_21d_pct",
        "trend_score_raw",
        "rs_composite",
        "rts_raw",
        "rts_pct",
        "atr14",
        "atr14_universe_mean",
        "pivot_dist_pct",
        "green_candle",
        "universe_size",
    ]
    return result[cols_out]


def populate_date(conn, target_date, overwrite=False, max_tickers=500):
    if not overwrite:
        existing = conn.execute(
            "SELECT COUNT(*) FROM daily_triad_rankings WHERE date = ?", (target_date,)
        ).fetchone()[0]
        if existing > 0:
            logger.info(f"{target_date}: ya tiene {existing} filas, skip")
            return

    result = compute_triad_for_date(conn, target_date, max_tickers=max_tickers)
    if result.empty:
        logger.warning(f"{target_date}: sin datos suficientes")
        return

    if overwrite:
        conn.execute("DELETE FROM daily_triad_rankings WHERE date = ?", (target_date,))

    result.to_sql("daily_triad_rankings", conn, if_exists="append", index=False)
    conn.commit()
    logger.info(f"{target_date}: insertados {len(result)} tickers")


def get_trading_dates(conn, days_back):
    query = """
        SELECT DISTINCT date FROM ohlcv_cache
        ORDER BY date DESC LIMIT ?
    """
    rows = conn.execute(query, (days_back,)).fetchall()
    return [r[0] for r in reversed(rows)]


def main():
    parser = argparse.ArgumentParser(description="Pobla daily_triad_rankings")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--days-back", type=int, default=90)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-tickers", type=int, default=500)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    dates = [args.date] if args.date else get_trading_dates(conn, args.days_back)
    logger.info(f"Procesando {len(dates)} fecha(s): {dates[:5]}...")
    for d in dates:
        populate_date(conn, d, overwrite=args.overwrite, max_tickers=args.max_tickers)

    conn.close()
    logger.info("Listo.")


if __name__ == "__main__":
    main()
