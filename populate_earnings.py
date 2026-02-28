#!/usr/bin/env python3
"""
Populate Earnings Cache
========================
Descarga earnings dates para todos los tickers en ohlcv_cache
y los guarda en earnings_cache (SQLite).

Usa yfinance ticker.earnings_dates para obtener:
  - report_date, eps_estimate, eps_actual, surprise_pct

Maneja rate limiting de Yahoo Finance con retry + backoff exponencial.

Usage:
    python3 populate_earnings.py --skip-existing
    python3 populate_earnings.py --tickers AAPL,MSFT,NVDA
    python3 populate_earnings.py --limit 100
    python3 populate_earnings.py --us-only --skip-existing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yfinance as yf
from yfinance.exceptions import YFRateLimitError
import pandas as pd
from src.data.ticker_cache import TickerCache
import time
import argparse
import warnings


def fetch_earnings(ticker: str, cache: TickerCache, max_retries: int = 3) -> int:
    """Descarga earnings dates para un ticker y guarda en SQLite.

    Returns:
        > 0: number of earnings records saved
          0: no earnings data available (normal for ETFs, intl tickers)
         -1: non-retryable error
         -2: rate limited (caller should back off)
    """
    for attempt in range(max_retries):
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                t = yf.Ticker(ticker)
                earnings = t.earnings_dates

            if earnings is None or earnings.empty:
                return 0

            df_to_save = pd.DataFrame()
            df_to_save["report_date"] = earnings.index
            df_to_save["eps_estimate"] = (
                earnings["EPS Estimate"].values
                if "EPS Estimate" in earnings.columns
                else None
            )
            df_to_save["eps_actual"] = (
                earnings["Reported EPS"].values
                if "Reported EPS" in earnings.columns
                else None
            )
            df_to_save["surprise_pct"] = (
                earnings["Surprise(%)"].values
                if "Surprise(%)" in earnings.columns
                else None
            )

            count = cache.save_earnings(ticker, df_to_save)
            return count

        except YFRateLimitError:
            if attempt < max_retries - 1:
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s
                print(
                    f"RATE LIMITED - esperando {wait}s (intento {attempt + 1}/{max_retries})... ",
                    end="",
                    flush=True,
                )
                time.sleep(wait)
                print("reintentando... ", end="", flush=True)
            else:
                return -2

        except Exception as e:
            err = str(e)[:80]
            if "No data" in err or "404" in err or "not found" in err.lower():
                return 0
            if "Rate" in err or "429" in err or "Too Many" in err:
                if attempt < max_retries - 1:
                    wait = 60 * (attempt + 1)
                    print(f"RATE LIMITED - esperando {wait}s... ", end="", flush=True)
                    time.sleep(wait)
                    print("reintentando... ", end="", flush=True)
                else:
                    return -2
            else:
                return -1

    return -1


def main():
    parser = argparse.ArgumentParser(description="Populate earnings cache")
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated ticker list (default: all from ohlcv_cache)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max tickers to process (0=all)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip tickers that already have earnings in cache",
    )
    parser.add_argument(
        "--us-only",
        action="store_true",
        help="Solo tickers US (sin sufijos como -KS, -HK, -T, etc.)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Pausa larga cada N tickers (default: 15)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay en segundos entre requests (default: 0.5)",
    )
    parser.add_argument(
        "--batch-pause",
        type=float,
        default=5.0,
        help="Pausa en segundos entre batches (default: 5)",
    )
    args = parser.parse_args()

    cache = TickerCache()

    # --- Determine ticker list ---
    if args.tickers:
        tickers = sorted(set(t.strip().upper() for t in args.tickers.split(",")))
    else:
        rows = cache.conn.execute(
            "SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker"
        ).fetchall()
        tickers = [r[0] for r in rows]

    # --- Filter US-only ---
    if args.us_only:
        # US tickers: no suffix (no dash) except BRK-B
        us_exceptions = {"BRK-B"}
        before = len(tickers)
        tickers = [t for t in tickers if "-" not in t or t in us_exceptions]
        print(f"  Filtrado US-only: {before} -> {len(tickers)} tickers")

    if args.limit > 0:
        tickers = tickers[: args.limit]

    print(f"POPULATE EARNINGS CACHE")
    print(f"{'=' * 60}")
    print(f"  Total tickers: {len(tickers)}")

    # --- Skip existing ---
    if args.skip_existing:
        existing = set(
            r[0]
            for r in cache.conn.execute(
                "SELECT DISTINCT ticker FROM earnings_cache"
            ).fetchall()
        )
        before = len(tickers)
        tickers = [t for t in tickers if t not in existing]
        print(f"  Ya en cache:    {before - len(tickers)}")
        print(f"  Por descargar:  {len(tickers)}")

    if not tickers:
        print(f"\nTodos los tickers ya tienen earnings data.")
        return

    print(f"  Batch size:     {args.batch_size}")
    print(f"  Delay:          {args.delay}s (entre requests)")
    print(f"  Batch pause:    {args.batch_pause}s (entre batches)")
    print(f"{'=' * 60}\n")

    start_time = time.time()
    success = 0
    no_data = 0
    failed = []
    rate_limited = []
    consecutive_errors = 0

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] {ticker:6s} ... ", end="", flush=True)

        count = fetch_earnings(ticker, cache)

        if count > 0:
            print(f"OK ({count} dates)")
            success += 1
            consecutive_errors = 0
        elif count == 0:
            print(f"sin data")
            no_data += 1
            consecutive_errors = 0
        elif count == -2:
            print(f"RATE LIMITED (agotados reintentos)")
            rate_limited.append(ticker)
            consecutive_errors += 1
            # Si llevamos 5+ rate limits seguidos, pausa larga
            if consecutive_errors >= 5:
                pause = 120
                print(
                    f"\n  ** {consecutive_errors} rate limits seguidos - pausa de {pause}s **\n"
                )
                time.sleep(pause)
                consecutive_errors = 0
        else:
            print(f"ERROR")
            failed.append(ticker)
            consecutive_errors += 1

        # Rate limiting preventivo
        if i % args.batch_size == 0:
            print(
                f"\n  -- batch {i}/{len(tickers)} done, pausa {args.batch_pause}s --\n"
            )
            time.sleep(args.batch_pause)
        else:
            time.sleep(args.delay)

    elapsed = time.time() - start_time

    # --- Summary ---
    total_earnings = cache.conn.execute(
        "SELECT COUNT(*) FROM earnings_cache"
    ).fetchone()[0]
    distinct_tickers = cache.conn.execute(
        "SELECT COUNT(DISTINCT ticker) FROM earnings_cache"
    ).fetchone()[0]

    print(f"\n{'=' * 60}")
    print(f"COMPLETADO")
    print(f"{'=' * 60}")
    print(f"  Exitosos:       {success}/{len(tickers)}")
    print(f"  Sin data:       {no_data} (ETFs, OTC, etc.)")
    print(f"  Rate limited:   {len(rate_limited)}")
    print(f"  Errores:        {len(failed)}")
    print(f"  Tiempo:         {elapsed / 60:.1f} minutos")
    print(
        f"  DB total:       {total_earnings} earnings records, {distinct_tickers} tickers"
    )

    if rate_limited:
        print(f"\nRate limited (reintentar luego): {', '.join(rate_limited[:30])}")
        if len(rate_limited) > 30:
            print(f"  ... y {len(rate_limited) - 30} mas")

    if failed:
        print(f"\nFallidos: {', '.join(failed[:30])}")
        if len(failed) > 30:
            print(f"  ... y {len(failed) - 30} mas")

    # Tip
    remaining = len(rate_limited) + len(failed)
    if remaining > 0:
        print(f"\nTip: espera 15-30 min y ejecuta de nuevo con --skip-existing")


if __name__ == "__main__":
    main()
