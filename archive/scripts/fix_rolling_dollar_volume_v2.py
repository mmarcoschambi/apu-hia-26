#!/usr/bin/env python3
"""
fix_rolling_dollar_volume_v2.py
---------------------------------
Recalcula rolling_dollar_vol_20 para todos los tickers con NULL.
Version 2: bulk SQL, sin loops fila-por-fila. 50-100x mas rapido.

Estrategia:
  1. Leer ticker completo en memoria (1 query SELECT)
  2. Calcular rolling en pandas
  3. Hacer 1 sola UPDATE por ticker via executemany (batch)
  4. Commit cada N tickers (no cada fila)

Estimacion: ~5-10 minutos para 5500 tickers vs 30+ horas del script anterior.

Usage:
    python fix_rolling_dollar_volume_v2.py
    python fix_rolling_dollar_volume_v2.py --ticker AAPL
    python fix_rolling_dollar_volume_v2.py --batch-size 50
    python fix_rolling_dollar_volume_v2.py --resume   (salta tickers ya completos)
    python fix_rolling_dollar_volume_v2.py --resume --dry-run   (solo diagnostico)
"""

import sqlite3
import pandas as pd
from pathlib import Path
import logging
import argparse
import time
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "data" / "ticker_cache.db"


def fix_ticker_bulk(conn, ticker):
    """
    Lee un ticker, calcula rolling_dollar_vol_20, actualiza en batch.
    Retorna (rows_updated, skipped).
    """
    rows = conn.execute(
        "SELECT date, close, volume FROM ohlcv_cache WHERE ticker = ? ORDER BY date",
        (ticker,),
    ).fetchall()

    if not rows:
        return 0, True

    df = pd.DataFrame(rows, columns=["date", "close", "volume"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["dollar_volume"] = df["close"] * df["volume"]
    df["rolling_dollar_vol_20"] = (
        df["dollar_volume"].rolling(window=20, min_periods=1).mean()
    )

    # Batch update: 1 executemany por ticker en vez de N UPDATE individuales
    records = [
        (round(float(rdv), 2) if pd.notna(rdv) else None, ticker, date)
        for date, rdv in zip(df["date"], df["rolling_dollar_vol_20"])
    ]

    conn.executemany(
        "UPDATE ohlcv_cache SET rolling_dollar_vol_20 = ? WHERE ticker = ? AND date = ?",
        records,
    )

    return len(records), False


def main():
    parser = argparse.ArgumentParser(description="Fix rolling_dollar_vol_20 - v2 fast")
    parser.add_argument(
        "--ticker", type=str, default=None, help="Procesar solo este ticker"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Commit cada N tickers (default: 100)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Solo procesa tickers que aun tienen NULL (skip completos)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limitar a N tickers (para pruebas)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo diagnostico: muestra cuantos tickers/filas se procesarian",
    )
    parser.add_argument(
        "--heartbeat",
        type=int,
        default=10,
        help="Log de progreso cada N segundos (default: 10)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("fix_rolling_dollar_volume_v2 — BULK MODE")
    logger.info("=" * 60)

    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=50000")
    conn.execute("PRAGMA temp_store=MEMORY")

    # Estado inicial
    stats = conn.execute("""
        SELECT COUNT(*) total,
               SUM(CASE WHEN rolling_dollar_vol_20 IS NULL THEN 1 ELSE 0 END) nulls
        FROM ohlcv_cache
    """).fetchone()
    logger.info(
        f"Estado inicial — Total filas: {stats[0]:,}  NULL: {stats[1]:,} ({stats[1] / stats[0] * 100:.1f}%)"
    )

    # Cargar lista de tickers a procesar
    if args.ticker:
        tickers = [args.ticker]
    elif args.resume:
        # Solo tickers que tienen AL MENOS UNA fila con NULL
        tickers = [
            row[0]
            for row in conn.execute("""
            SELECT DISTINCT ticker FROM ohlcv_cache
            WHERE rolling_dollar_vol_20 IS NULL
            ORDER BY ticker
        """).fetchall()
        ]
        logger.info(f"Modo resume: {len(tickers)} tickers con NULL pendientes")
        if args.dry_run:
            total_null_rows = conn.execute("""
                SELECT COUNT(*) FROM ohlcv_cache
                WHERE rolling_dollar_vol_20 IS NULL
            """).fetchone()[0]
            logger.info(f"  → Filas a actualizar: {total_null_rows:,}")
            logger.info(f"  → tickers únicos a procesar: {len(tickers)}")
            logger.info(f"  → AVG filas/ticker: {total_null_rows / len(tickers):.1f}")
            return
    else:
        tickers = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker"
            ).fetchall()
        ]

    if args.limit:
        tickers = tickers[: args.limit]
        logger.info(f"Limitado a {len(tickers)} tickers (--limit)")

    logger.info(f"Tickers a procesar: {len(tickers)}")
    if len(tickers) > 0:
        logger.info(f"  Primer ticker: {tickers[0]}")
        logger.info(f"  Último ticker: {tickers[-1]}")
    else:
        logger.warning("  No hay tickers pendientes de procesamiento")
        return

    t0 = time.time()
    total_rows = 0
    total_tickers = 0
    errors = []
    last_heartbeat = time.time()

    for i, ticker in enumerate(tqdm(tickers, desc="Procesando", unit="ticker")):
        try:
            rows, skipped = fix_ticker_bulk(conn, ticker)
            if not skipped:
                total_rows += rows
                total_tickers += 1

            # Commit cada batch_size tickers (no cada fila)
            if (i + 1) % args.batch_size == 0:
                conn.commit()
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                remaining = (len(tickers) - i - 1) / rate if rate > 0 else 0
                logger.info(
                    f"  [{i + 1}/{len(tickers)}] "
                    f"{rate:.1f} tickers/s | "
                    f"ETA: {remaining / 60:.1f} min | "
                    f"Filas: {total_rows:,}"
                )

            # Heartbeat cada N segundos
            if time.time() - last_heartbeat > args.heartbeat:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                logger.info(
                    f"  🔥 Heartbeat [{i + 1}/{len(tickers)}] "
                    f"{rate:.1f} tickers/s | "
                    f"Filas procesadas: {total_rows:,}"
                )
                last_heartbeat = time.time()

        except Exception as e:
            errors.append((ticker, str(e)))
            if len(errors) <= 5:
                logger.warning(f"  ERROR {ticker}: {e}")

    # Commit final
    conn.commit()

    elapsed = time.time() - t0
    logger.info("=" * 60)
    logger.info(f"COMPLETADO en {elapsed / 60:.1f} minutos")
    logger.info(f"  Tickers actualizados: {total_tickers:,}")
    logger.info(f"  Filas actualizadas:   {total_rows:,}")
    if errors:
        logger.warning(f"  Errores: {len(errors)} tickers — {errors[:5]}")

    # Estado final
    stats2 = conn.execute("""
        SELECT COUNT(*) total,
               SUM(CASE WHEN rolling_dollar_vol_20 IS NULL THEN 1 ELSE 0 END) nulls,
               SUM(CASE WHEN rolling_dollar_vol_20 IS NOT NULL THEN 1 ELSE 0 END) ok
        FROM ohlcv_cache
    """).fetchone()
    logger.info(
        f"Estado final — NULL: {stats2[1]:,} ({stats2[1] / stats2[0] * 100:.1f}%)  OK: {stats2[2]:,}"
    )

    # Impacto en universo backtest
    universe_count = conn.execute("""
        SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache
        WHERE date BETWEEN '2019-01-01' AND '2025-12-31'
        AND rolling_dollar_vol_20 IS NOT NULL
        AND ticker NOT LIKE '%-%'
    """).fetchone()[0]
    logger.info(
        f"Universo backtest 2019-2025 con rolling_vol: {universe_count} tickers"
    )

    conn.close()


if __name__ == "__main__":
    main()
