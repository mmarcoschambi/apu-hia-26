#!/usr/bin/env python3
"""
EXPAND TICKER UNIVERSE - Pre-download tickers for optimization
==============================================================

Downloads and caches tickers needed for the PIT (Point-in-Time) S&P 500
universe or any custom ticker list.

Usage:
    # Download PIT missing tickers (default)
    python3 expand_universe.py --ticker-file pit_missing_tickers.txt --workers 3

    # Download from custom list
    python3 expand_universe.py --ticker-file bugatti_ready_tickers.txt --tickers 300 --workers 5
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import logging
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data.ticker_cache import TickerCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Constants ---
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 2.0
RETRYABLE_ERRORS = (
    "401",
    "429",
    "500",
    "503",
    "crumb",
    "rate limit",
    "too many requests",
)


def load_ticker_list(filepath: str = "pit_missing_tickers.txt", limit: int = 0):
    """Load ticker list from file. limit=0 means all tickers."""
    tickers_file = Path(filepath)
    if not tickers_file.exists():
        logger.error(f"File not found: {filepath}")
        return []

    with open(tickers_file, "r") as f:
        tickers = [
            line.strip()
            for line in f.readlines()
            if line.strip() and not line.startswith("#")
        ]

    if limit > 0:
        tickers = tickers[:limit]

    logger.info(f"Loaded {len(tickers)} tickers from {filepath}")
    return tickers


def is_retryable_error(error_msg: str) -> bool:
    """Check if the error is transient and worth retrying."""
    error_lower = error_msg.lower()
    return any(keyword in error_lower for keyword in RETRYABLE_ERRORS)


def download_ticker(ticker: str, start_date: str, end_date: str) -> tuple:
    """
    Download a single ticker and save to cache.

    THREAD-SAFE: Creates its own TickerCache (own SQLite connection) per call.
    Uses auto_adjust=True to avoid MultiIndex/duplicate column issues.
    Includes retry with exponential backoff for transient Yahoo errors.
    """
    # Each thread gets its own DB connection (thread-safe)
    cache = TickerCache()

    try:
        # Check if already cached with sufficient data
        check = cache.conn.execute(
            "SELECT COUNT(*) FROM ohlcv_cache WHERE ticker = ? AND date >= ? AND date <= ?",
            (ticker, start_date, end_date),
        ).fetchone()[0]

        if check >= 100:
            logger.debug(f"SKIP {ticker}: already cached ({check} days)")
            cache.close()
            return (ticker, True, "cached")

        # Download with retry/backoff
        df = None
        last_error = ""

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                df = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True,  # KEY FIX: eliminates Adj Close / duplicate columns
                )
                break  # Success, exit retry loop
            except Exception as e:
                last_error = str(e)
                if is_retryable_error(last_error) and attempt < MAX_RETRIES:
                    backoff = BASE_BACKOFF_SECONDS * (
                        2 ** (attempt - 1)
                    ) + random.uniform(0, 1)
                    logger.warning(
                        f"RETRY {ticker} (attempt {attempt}/{MAX_RETRIES}): {last_error} - waiting {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                else:
                    cache.close()
                    return (ticker, False, f"download_error: {last_error}")

        if df is None or df.empty:
            cache.close()
            return (
                ticker,
                False,
                f"empty_response: {last_error}" if last_error else "empty_response",
            )

        if len(df) < 50:
            cache.close()
            return (ticker, False, f"insufficient_data ({len(df)} days)")

        # --- Robust MultiIndex handling (from ticker_cache.py pattern) ---
        if isinstance(df.columns, pd.MultiIndex):
            # Try to extract the specific ticker level
            if "Ticker" in df.columns.names:
                try:
                    df = df.xs(ticker, axis=1, level="Ticker")
                except (KeyError, TypeError):
                    try:
                        df.columns = df.columns.droplevel("Ticker")
                    except Exception:
                        pass

            # If still MultiIndex, take Price level (level 0)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        # Deduplicate columns (keep first)
        df = df.loc[:, ~df.columns.duplicated()]

        # Reset index to get Date as a column
        df = df.reset_index()

        # Normalize column names to lowercase, no spaces
        df.columns = [str(col).lower().replace(" ", "") for col in df.columns]

        # Ensure required columns exist
        required = ["date", "open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            cache.close()
            return (ticker, False, f"missing_columns: {missing}")

        # Calculate dollar_volume
        df["dollar_volume"] = df["close"] * df["volume"]

        # Save to cache
        data_to_insert = []
        for _, row in df.iterrows():
            if pd.isna(row["close"]):
                continue
            data_to_insert.append(
                (
                    ticker,
                    row["date"].strftime("%Y-%m-%d")
                    if hasattr(row["date"], "strftime")
                    else str(row["date"]),
                    float(row["open"]) if pd.notna(row["open"]) else None,
                    float(row["high"]) if pd.notna(row["high"]) else None,
                    float(row["low"]) if pd.notna(row["low"]) else None,
                    float(row["close"]),
                    int(row["volume"]) if pd.notna(row["volume"]) else 0,
                    float(row["dollar_volume"])
                    if pd.notna(row["dollar_volume"])
                    else None,
                )
            )

        cache.conn.executemany(
            """INSERT OR REPLACE INTO ohlcv_cache 
               (ticker, date, open, high, low, close, volume, dollar_volume)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            data_to_insert,
        )
        cache.conn.commit()
        cache.close()

        logger.info(f"OK {ticker}: downloaded {len(data_to_insert)} days")
        return (ticker, True, f"downloaded_{len(data_to_insert)}")

    except Exception as e:
        error_msg = str(e)
        # Graceful handling for delisted/merged tickers
        if any(
            kw in error_msg.lower() for kw in ("delisted", "no timezone", "no data")
        ):
            logger.warning(f"DELISTED {ticker}: {error_msg}")
            try:
                cache.close()
            except Exception:
                pass
            return (ticker, False, f"likely_delisted: {error_msg}")

        logger.error(f"ERROR {ticker}: {error_msg}")
        try:
            cache.close()
        except Exception:
            pass
        return (ticker, False, error_msg)


def main():
    parser = argparse.ArgumentParser(description="Expand Ticker Universe")
    parser.add_argument(
        "--tickers",
        type=int,
        default=0,
        help="Number of tickers to download (0 = all from file)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Parallel downloads (keep low for Yahoo rate limits)",
    )
    parser.add_argument("--start-date", type=str, default="2019-01-01")
    parser.add_argument("--end-date", type=str, default="2025-12-31")
    parser.add_argument("--ticker-file", type=str, default="pit_missing_tickers.txt")

    args = parser.parse_args()

    print("=" * 80)
    print("EXPAND TICKER UNIVERSE")
    print("=" * 80)
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Workers: {args.workers}")
    print(f"Ticker file: {args.ticker_file}")
    print("=" * 80)

    # Load ticker list
    tickers = load_ticker_list(args.ticker_file, args.tickers)
    if not tickers:
        logger.error("No tickers to process!")
        return

    print(f"Target: {len(tickers)} tickers")

    # Check current coverage (use a temporary connection)
    check_cache = TickerCache()
    current_count = check_cache.conn.execute(
        "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache WHERE date BETWEEN ? AND ?",
        (args.start_date, args.end_date),
    ).fetchone()[0]
    logger.info(f"Currently cached: {current_count} tickers")
    check_cache.close()

    # Download with ThreadPool
    logger.info(
        f"Starting download of {len(tickers)} tickers with {args.workers} workers..."
    )
    start_time = time.time()

    success_count = 0
    cached_count = 0
    failed_tickers = []
    processed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_ticker = {
            executor.submit(download_ticker, t, args.start_date, args.end_date): t
            for t in tickers
        }

        for future in as_completed(future_to_ticker):
            ticker_name = future_to_ticker[future]
            processed += 1
            try:
                result_ticker, success, msg = future.result()
                if success:
                    if "cached" in msg:
                        cached_count += 1
                    else:
                        success_count += 1
                else:
                    failed_tickers.append((result_ticker, msg))
            except Exception as e:
                logger.error(f"EXCEPTION {ticker_name}: {e}")
                failed_tickers.append((ticker_name, str(e)))

            # Progress report every 25 tickers
            if processed % 25 == 0:
                elapsed_so_far = time.time() - start_time
                rate = processed / elapsed_so_far if elapsed_so_far > 0 else 0
                remaining = (len(tickers) - processed) / rate if rate > 0 else 0
                logger.info(
                    f"Progress: {processed}/{len(tickers)} | "
                    f"OK: {success_count} | Cached: {cached_count} | "
                    f"Failed: {len(failed_tickers)} | "
                    f"ETA: {remaining:.0f}s"
                )

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Downloaded: {success_count}")
    print(f"Already cached: {cached_count}")
    print(f"Failed: {len(failed_tickers)}")
    print(f"Time: {elapsed:.1f}s ({elapsed / max(len(tickers), 1):.1f}s per ticker)")

    # Update count
    final_cache = TickerCache()
    new_count = final_cache.conn.execute(
        "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache WHERE date BETWEEN ? AND ?",
        (args.start_date, args.end_date),
    ).fetchone()[0]
    print(f"Total tickers in cache: {new_count}")
    final_cache.close()

    # Save failed tickers
    if failed_tickers:
        failed_file = Path("failed_tickers_expansion.txt")
        with open(failed_file, "w") as f:
            f.write(f"# Failed tickers - {datetime.now()}\n")
            f.write(f"# Total failed: {len(failed_tickers)}\n")
            for t, msg in sorted(failed_tickers, key=lambda x: x[0]):
                f.write(f"{t}: {msg}\n")
        print(f"Failed tickers saved to: {failed_file}")

    print("=" * 80)


if __name__ == "__main__":
    main()
