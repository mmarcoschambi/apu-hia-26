"""
fix_ohlcv_derived_fields.py
Calcula y escribe sma20, avg_volume_20, trend_aligned, rvol_ratio
en ohlcv_cache para todos los tickers / fechas donde esten NULL.
Modo: --full (todo el historico) o --incremental (ultimos 30 dias)
"""
import sqlite3, pandas as pd, numpy as np, sys, argparse, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path("/home/marcos/trade/momentum-v2/data/ticker_cache.db")

def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula campos derivados sobre df con columnas open/high/low/close/volume."""
    df = df.sort_values("date").copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"].replace(0, np.nan)

    df["sma20"]        = c.rolling(20, min_periods=10).mean()
    df["sma50"]        = c.rolling(50, min_periods=25).mean()
    df["sma_50"]       = df["sma50"]
    df["sma200"]       = c.rolling(200, min_periods=100).mean()
    df["sma_200"]      = df["sma200"]
    df["sma100"]       = c.rolling(100, min_periods=50).mean()
    df["ema_8"]        = c.ewm(span=8,  adjust=False).mean()
    df["ema_21"]       = c.ewm(span=21, adjust=False).mean()
    df["avg_volume_20"]= v.rolling(20, min_periods=5).mean()
    df["adr_pct_20"]   = ((h - l) / c * 100).rolling(20, min_periods=10).mean()
    df["adr_pct_14"]   = ((h - l) / c * 100).rolling(14, min_periods=7).mean()
    df["adr_14"]       = df["adr_pct_14"]

    # trend_aligned: 1 si close > sma50 > sma200, else 0
    s50  = df["sma50"].fillna(0)
    s200 = df["sma200"].fillna(0)
    df["trend_aligned"]      = ((c > s50) & (s50 > s200)).astype(int)
    df["price_above_sma50"]  = (c > s50).astype(int)
    df["price_above_sma200"] = (c > s200).astype(int)
    df["sma50_above_sma200"] = (s50 > s200).astype(int)

    return df

def run(mode: str = "incremental"):
    conn = sqlite3.connect(str(DB_PATH))

    if mode == "full":
        logger.info("Modo FULL — recalculando todos los tickers")
        tickers = [r[0] for r in conn.execute(
            "SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker"
        )]
    else:
        logger.info("Modo INCREMENTAL — tickers con sma20 NULL en ultimos 60 dias")
        tickers = [r[0] for r in conn.execute("""
            SELECT DISTINCT ticker FROM ohlcv_cache
            WHERE date >= DATE('now', '-60 days')
              AND sma20 IS NULL
            ORDER BY ticker
        """)]

    logger.info(f"Tickers a procesar: {len(tickers)}")
    updated_rows = 0

    for i, ticker in enumerate(tickers):
        try:
            df = pd.read_sql_query(
                "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
                "WHERE ticker=? ORDER BY date",
                conn, params=(ticker,)
            )
            if len(df) < 20:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = compute_derived(df)

            # Escribir solo las filas que cambiaron
            for _, row in df.iterrows():
                conn.execute("""
                    UPDATE ohlcv_cache SET
                        sma20=?, sma50=?, sma_50=?, sma200=?, sma_200=?,
                        sma100=?, ema_8=?, ema_21=?,
                        avg_volume_20=?, adr_pct_20=?, adr_pct_14=?, adr_14=?,
                        trend_aligned=?, price_above_sma50=?,
                        price_above_sma200=?, sma50_above_sma200=?
                    WHERE ticker=? AND date=?
                """, (
                    row.get("sma20"), row.get("sma50"), row.get("sma50"),
                    row.get("sma200"), row.get("sma200"), row.get("sma100"),
                    row.get("ema_8"), row.get("ema_21"),
                    row.get("avg_volume_20"), row.get("adr_pct_20"),
                    row.get("adr_pct_14"), row.get("adr_pct_14"),
                    int(row.get("trend_aligned", 0)),
                    int(row.get("price_above_sma50", 0)),
                    int(row.get("price_above_sma200", 0)),
                    int(row.get("sma50_above_sma200", 0)),
                    ticker, row["date"].strftime("%Y-%m-%d")
                ))
                updated_rows += 1

            if (i + 1) % 50 == 0:
                conn.commit()
                logger.info(f"  [{i+1}/{len(tickers)}] {ticker} — {updated_rows:,} filas actualizadas")

        except Exception as e:
            logger.error(f"  Error en {ticker}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Completado. Total filas actualizadas: {updated_rows:,}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    run("full" if args.full else "incremental")
