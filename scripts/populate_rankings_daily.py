#!/usr/bin/env python3
"""
scripts/populate_rankings_daily.py  -  REFACTORED v2
=====================================================
Pobla daily_rs_rankings y daily_triad_rankings para un rango de fechas.

CAMBIOS vs v1:
  - ELIMINADOS los subprocess.run() por fecha (era el mayor cuello de botella:
    lanzaba un proceso Python nuevo por cada fecha = 300-500ms overhead x N fechas)
  - Importa funciones directamente y las llama en el mismo proceso
  - Paralelismo con ProcessPoolExecutor: procesa multiples fechas a la vez
  - Check de fechas existentes con 1 solo query bulk (v1 hacia 1 query por fecha en loop)
  - Conexion SQLite con WAL mode para soportar writers concurrentes

Uso:
    python3 scripts/populate_rankings_daily.py --start 2022-01-01 --end 2022-06-30
    python3 scripts/populate_rankings_daily.py --start 2019-01-01 --end 2024-12-31 --workers 4
    python3 scripts/populate_rankings_daily.py --start 2023-01-01 --end 2023-12-31 --rs-only
"""

import sqlite3
import argparse
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


def normalize_date(date_val):
    if not date_val:
        return None
    date_str = str(date_val)
    return date_str.split(" ")[0] if " " in date_str else date_str


def get_trading_dates(conn, start_date, end_date):
    query = """
        SELECT DISTINCT DATE(date) as trading_date FROM ohlcv_cache
        WHERE date >= ? AND date <= ?
          AND ticker NOT LIKE '%-%'
          AND ticker NOT LIKE '^%'
        ORDER BY trading_date
    """
    rows = conn.execute(query, (start_date, end_date)).fetchall()
    return [normalize_date(r[0]) for r in rows]


def get_existing_dates(conn, table, start_date, end_date):
    """1 query bulk en vez de 1 query por fecha (v1 lo hacia en el loop)."""
    rows = conn.execute(
        f"SELECT DISTINCT DATE(date) FROM {table} WHERE DATE(date) >= DATE(?) AND DATE(date) <= DATE(?)",
        (start_date, end_date),
    ).fetchall()
    return {normalize_date(r[0]) for r in rows}


def ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_rs_rankings (
            date DATE NOT NULL, ticker TEXT NOT NULL,
            rs_60d_pct REAL, rs_20d_pct REAL, rs_5d_pct REAL, rs_composite REAL,
            universe_size INTEGER, computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_triad_rankings (
            date DATE NOT NULL, ticker TEXT NOT NULL,
            as_5d_pct REAL, as_21d_pct REAL, trend_score_raw REAL, rs_composite REAL,
            rts_raw REAL, rts_pct REAL, atr14 REAL, atr14_universe_mean REAL,
            pivot_dist_pct REAL, green_candle INTEGER, universe_size INTEGER,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()


def _run_rs(args_tuple):
    """Worker RS: se ejecuta en proceso hijo. Import local necesario."""
    date, overwrite = args_tuple
    try:
        import sys
        import sqlite3 as _sq

        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.populate_rs_rankings import compute_rs_for_date, ensure_table

        conn = _sq.connect(str(DB_PATH), timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        ensure_table(conn)

        if not overwrite:
            existing = conn.execute(
                "SELECT COUNT(*) FROM daily_rs_rankings WHERE date = ?", (date,)
            ).fetchone()[0]
            if existing > 0:
                conn.close()
                return ("rs", date, "skipped", 0, 0)

        result = compute_rs_for_date(conn, date)
        if result.empty:
            conn.close()
            return ("rs", date, "empty", 0, 0)

        if overwrite:
            conn.execute("DELETE FROM daily_rs_rankings WHERE date = ?", (date,))
        result.to_sql("daily_rs_rankings", conn, if_exists="append", index=False)
        conn.commit()
        conn.close()
        return ("rs", date, "ok", len(result), 0)
    except Exception as e:
        return ("rs", date, f"error: {e}", 0, 0)


def _run_triad(args_tuple):
    """Worker Triad: se ejecuta en proceso hijo. Import local necesario."""
    date, overwrite, max_tickers = args_tuple
    try:
        import sys
        import sqlite3 as _sq

        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.populate_triad_rankings import compute_triad_for_date, ensure_table

        conn = _sq.connect(str(DB_PATH), timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        ensure_table(conn)

        top_q = f"""
            SELECT DISTINCT ticker
            FROM ohlcv_cache
            WHERE date >= '{date}' AND date <= '{date} 23:59:59'
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
            conn.close()
            return ("triad", date, "skip_holiday", 0, 1)

        if not overwrite:
            existing = conn.execute(
                "SELECT COUNT(*) FROM daily_triad_rankings WHERE date = ?", (date,)
            ).fetchone()[0]
            if existing > 0:
                conn.close()
                return ("triad", date, "skipped", 0, 0)

        result = compute_triad_for_date(conn, date, max_tickers=max_tickers)
        if result.empty:
            conn.close()
            return ("triad", date, "empty", 0, 0)

        if overwrite:
            conn.execute("DELETE FROM daily_triad_rankings WHERE date = ?", (date,))
        result.to_sql("daily_triad_rankings", conn, if_exists="append", index=False)
        conn.commit()
        conn.close()
        return ("triad", date, "ok", len(result), 0)
    except Exception as e:
        return ("triad", date, f"error: {e}", 0, 0)


def _process_batch(batch_args, worker_fn, workers, label):
    done = skip = empty = err = skip_holiday = 0
    if workers == 1:
        for a in batch_args:
            _, date, status, n, holiday_flag = worker_fn(a)
            if status == "ok":
                done += 1
                logger.info(f"{label} {date}: OK ({n} tickers)")
            elif status == "skipped":
                skip += 1
            elif status == "skip_holiday":
                skip_holiday += 1
                logger.debug(f"{label} {date}: skip_holiday")
            elif status == "empty":
                empty += 1
                logger.warning(f"{label} {date}: empty")
            else:
                err += 1
                logger.warning(f"{label} {date}: {status}")
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(worker_fn, a): a[0] for a in batch_args}
            for fut in as_completed(futures):
                _, date, status, n, holiday_flag = fut.result()
                if status == "ok":
                    done += 1
                    logger.info(f"{label} {date}: OK ({n} tickers)")
                elif status == "skipped":
                    skip += 1
                elif status == "skip_holiday":
                    skip_holiday += 1
                    logger.debug(f"{label} {date}: skip_holiday")
                elif status == "empty":
                    empty += 1
                    logger.warning(f"{label} {date}: empty")
                else:
                    err += 1
                    logger.warning(f"{label} {date}: {status}")
    return done, skip, empty, err, skip_holiday


def main():
    parser = argparse.ArgumentParser(
        description="Pobla rankings diarios para un rango de fechas (v2, sin subprocesses)"
    )
    parser.add_argument("--start", type=str, required=True)
    parser.add_argument("--end", type=str, required=True)
    parser.add_argument("--rs-only", action="store_true")
    parser.add_argument("--triad-only", action="store_true")
    parser.add_argument(
        "--overwrite", action="store_true", help="Sobreescribir fechas existentes"
    )
    parser.add_argument("--max-tickers", type=int, default=500)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Procesos paralelos (default 2; no usar >4 con SQLite)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_tables(conn)

    dates = get_trading_dates(conn, args.start, args.end)
    logger.info(f"Rango: {args.start} a {args.end} - {len(dates)} fechas de trading")

    if not dates:
        logger.error("No hay fechas en ese rango")
        conn.close()
        return

    logger.info(f"Primera: {dates[0]} | Ultima: {dates[-1]}")

    rs_existing = get_existing_dates(conn, "daily_rs_rankings", args.start, args.end)
    triad_existing = get_existing_dates(
        conn, "daily_triad_rankings", args.start, args.end
    )
    conn.close()

    if args.overwrite:
        pending_rs = list(dates)
        pending_triad = list(dates)
    else:
        pending_rs = [d for d in dates if d not in rs_existing]
        pending_triad = [d for d in dates if d not in triad_existing]

    workers = max(1, args.workers)
    rs_done = rs_skip = rs_empty = rs_err = rs_skip_holiday = 0
    triad_done = triad_skip = triad_empty = triad_err = triad_skip_holiday = 0

    if not args.triad_only:
        logger.info(
            f"RS    - pendientes: {len(pending_rs)}, ya feitas: {len(rs_existing)}"
        )
        rs_args = [(d, args.overwrite) for d in pending_rs]
        rs_done, rs_skip, rs_empty, rs_err, rs_skip_holiday = _process_batch(
            rs_args, _run_rs, workers, "RS "
        )

    if not args.rs_only:
        logger.info(
            f"Triad - pendientes: {len(pending_triad)}, ya hechos: {len(triad_existing)}"
        )
        triad_args = [(d, args.overwrite, args.max_tickers) for d in pending_triad]
        triad_done, triad_skip, triad_empty, triad_err, triad_skip_holiday = (
            _process_batch(triad_args, _run_triad, workers, "TRIAD")
        )

    logger.info(f"\n{'=' * 55}")
    logger.info("RESUMEN")
    logger.info(
        f"  RS    - OK: {rs_done}  | skip: {rs_skip} | empty: {rs_empty} | err: {rs_err} | skip_holiday: {rs_skip_holiday}"
    )
    logger.info(
        f"  TRIAD - OK: {triad_done} | skip: {triad_skip} | empty: {triad_empty} | err: {triad_err} | skip_holiday: {triad_skip_holiday}"
    )
    logger.info(f"{'=' * 55}")
    logger.info("COMPLETADO")


if __name__ == "__main__":
    main()
