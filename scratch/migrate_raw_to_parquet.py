"""
scratch/migrate_raw_to_parquet.py
Migración atómica del layout de datos: SQLite + Parquet individual
-> data/raw/stocks/daily/ particionado por año (Hive-style).

Source:      data/ticker_cache.db -> ohlcv_cache (7.7M rows, 6096 tickers)
Target:      data/raw/stocks/daily/year=YYYY/part.parquet
Compression: zstd
Row groups:  250,000 rows
"""

from __future__ import annotations

import gc
import json
import logging
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("migrate_raw")

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ticker_cache.db"
TARGET_DIR = ROOT / "data" / "raw" / "stocks" / "daily"

CANONICAL_COLUMNS = [
    "date", "ticker", "open", "high", "low", "close",
    "adj_close", "volume", "source",
]
CANONICAL_DTYPES = {
    "date": pa.date32(),
    "ticker": pa.string(),
    "open": pa.float64(),
    "high": pa.float64(),
    "low": pa.float64(),
    "close": pa.float64(),
    "adj_close": pa.float64(),
    "volume": pa.int64(),
    "source": pa.string(),
}
ROW_GROUP_SIZE = 250_000


def _build_schema() -> pa.Schema:
    fields = []
    for col in CANONICAL_COLUMNS:
        dtype = CANONICAL_DTYPES[col]
        fields.append(pa.field(col, dtype))
    return pa.schema(fields)


def _extract_from_db(
    chunk_size: int = 500_000,
) -> pd.DataFrame:
    """Read OHLCV from SQLite in chunks, return deduplicated DataFrame."""
    conn = sqlite3.connect(str(DB_PATH))
    total = pd.read_sql("SELECT COUNT(*) FROM ohlcv_cache", conn).iloc[0, 0]
    logger.info("DB ohlcv_cache rows: %s", f"{total:,}")

    chunks: list[pd.DataFrame] = []
    offset = 0
    t0 = time.perf_counter()

    while offset < total:
        chunk = pd.read_sql(
            """
            SELECT ticker, date, open, high, low, close, volume
            FROM ohlcv_cache
            ORDER BY ticker, date
            LIMIT ? OFFSET ?
            """,
            conn,
            params=(chunk_size, offset),
            parse_dates=["date"],
        )
        if chunk.empty:
            break
        chunks.append(chunk)
        offset += len(chunk)
        logger.info(
            "  Extracted %s / %s rows (%.1f%%)",
            f"{offset:,}", f"{total:,}", offset / total * 100,
        )

    conn.close()
    df = pd.concat(chunks, ignore_index=True)
    logger.info("Concatenated: %s rows", f"{len(df):,}")

    # Cast dates to datetime64
    df["date"] = pd.to_datetime(df["date"], utc=False)

    # Drop rows with NaT dates
    nat_mask = df["date"].isna()
    if nat_mask.any():
        logger.warning("Dropping %s rows with NaT dates", nat_mask.sum())
        df = df[~nat_mask]

    # Deduplicate by (ticker, date) — keep last
    before = len(df)
    df = df.drop_duplicates(subset=["ticker", "date"], keep="last")
    after = len(df)
    dupes = before - after
    if dupes:
        logger.warning("Removed %s duplicates", f"{dupes:,}")

    # Cast columns
    df["open"] = df["open"].astype("float64")
    df["high"] = df["high"].astype("float64")
    df["low"] = df["low"].astype("float64")
    df["close"] = df["close"].astype("float64")
    df["adj_close"] = df["close"].astype("float64")  # no adj_close source
    df["volume"] = df["volume"].fillna(0).astype("int64")
    df["source"] = "yfinance"

    # Reorder to canonical
    df = df[CANONICAL_COLUMNS]
    elapsed = time.perf_counter() - t0
    logger.info("DB extraction done in %.1fs — %s rows", elapsed, f"{len(df):,}")
    return df


def _validate_data(df: pd.DataFrame) -> dict:
    """Validate data quality, return report."""
    report = {
        "total_rows": len(df),
        "min_date": str(df["date"].min()),
        "max_date": str(df["date"].max()),
        "unique_tickers": int(df["ticker"].nunique()),
        "null_prices": int(
            df["open"].isna().sum()
            + df["high"].isna().sum()
            + df["low"].isna().sum()
            + df["close"].isna().sum()
        ),
        "zero_prices": int(
            ((df["open"] == 0) | (df["high"] == 0) | (df["low"] == 0) | (df["close"] == 0)).sum()
        ),
        "negative_prices": int(
            ((df["open"] < 0) | (df["high"] < 0) | (df["low"] < 0) | (df["close"] < 0)).sum()
        ),
        "null_volumes": int(df["volume"].isna().sum()),
        "zero_volumes": int((df["volume"] == 0).sum()),
        "columns": list(df.columns),
        "dtypes": {c: str(d) for c, d in df.dtypes.items()},
    }
    # Per-ticker stats
    ticker_stats = (
        df.groupby("ticker")["date"]
        .agg(["min", "max", "count"])
        .reset_index()
        .rename(columns={"min": "first_date", "max": "last_date", "count": "rows"})
    )
    report["ticker_stats"] = {
        "min_rows": int(ticker_stats["rows"].min()),
        "max_rows": int(ticker_stats["rows"].max()),
        "mean_rows": round(float(ticker_stats["rows"].mean()), 1),
    }
    return report


def _write_partitioned(
    df: pd.DataFrame,
    target: Path,
    schema: pa.Schema,
):
    """Write DataFrame as Hive-partitioned Parquet by year using PyArrow."""
    # Build pyarrow table WITHOUT schema validation (keep all columns including year)
    df["year"] = df["date"].dt.year.astype("int32")
    tbl = pa.Table.from_pandas(df, preserve_index=False)

    # Cast canonical columns to target types; year stays as int32 for partitioning
    canonical_fields = {f.name: f.type for f in schema}
    cast_fields = []
    for name in tbl.column_names:
        if name in canonical_fields:
            cast_fields.append(
                pa.field(name, canonical_fields[name])
            )
        elif name == "year":
            cast_fields.append(pa.field("year", pa.int32()))
        else:
            raise ValueError(f"Unexpected column: {name}")
    tbl = tbl.cast(pa.schema(cast_fields))

    # Group by year and write per-partition
    year_col = df["year"].values
    unique_years = sorted(set(year_col))

    staging = target.parent / f".tmp_staging_{uuid.uuid4().hex[:12]}"
    logger.info("Staging directory: %s", staging)

    for year in unique_years:
        mask = year_col == year
        indices = np.where(mask)[0]
        part_tbl = tbl.take(indices.tolist())
        # Drop year column from data (partition key is the directory)
        part_tbl = part_tbl.drop(["year"])

        part_dir = staging / f"year={year}"
        part_dir.mkdir(parents=True, exist_ok=True)
        part_path = part_dir / "part.parquet"

        pq.write_table(
            part_tbl,
            str(part_path),
            compression="zstd",
            row_group_size=ROW_GROUP_SIZE,
            version="2.6",
            data_page_size=1024 * 1024,  # 1 MiB
        )
        logger.info(
            "  year=%s -> %s rows -> %.1f MiB",
            year, len(indices),
            part_path.stat().st_size / 1024 / 1024,
        )

    # Atomic replace via rename
    old_backup = None
    if target.exists():
        old_backup = target.parent / f".tmp_old_{uuid.uuid4().hex[:8]}"
        target.rename(old_backup)
        logger.info("  Backed up old target to %s", old_backup)

    staging.rename(target)
    logger.info("  Atomic replace done")

    # Clean up old backup
    if old_backup and old_backup.exists():
        import shutil
        shutil.rmtree(old_backup, ignore_errors=True)
        logger.info("  Removed old backup")


def main():
    t_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("MIGRATION: SQLite -> Hive-partitioned Parquet")
    logger.info("=" * 60)
    logger.info("Source:      %s", DB_PATH)
    logger.info("Target:      %s", TARGET_DIR)
    logger.info("Compression: zstd | Row groups: %s", f"{ROW_GROUP_SIZE:,}")

    # 1. Extract
    t0 = time.perf_counter()
    df = _extract_from_db()
    logger.info("Extract: %.1fs | %s rows", time.perf_counter() - t0, f"{len(df):,}")

    # 2. Validate input quality
    quality_before = _validate_data(df)
    logger.info(
        "Quality: %s tickers | %s -> %s | null_prices=%s | zero_prices=%s",
        quality_before["unique_tickers"],
        quality_before["min_date"],
        quality_before["max_date"],
        quality_before["null_prices"],
        quality_before["zero_prices"],
    )

    # 3. Write partitioned
    schema = _build_schema()
    t0 = time.perf_counter()
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    _write_partitioned(df, TARGET_DIR, schema)

    # 4. Read back and verify
    t0 = time.perf_counter()
    df_verify = ds.dataset(str(TARGET_DIR), format="parquet").to_table().to_pandas()
    logger.info("Verification read: %.1fs | %s rows", time.perf_counter() - t0, f"{len(df_verify):,}")

    quality_after = _validate_data(df_verify)

    # 5. Quality report
    # Normalize date strings for comparison (strip time components)
    b_min = quality_before["min_date"][:10]
    b_max = quality_before["max_date"][:10]
    a_min = quality_after["min_date"][:10]
    a_max = quality_after["max_date"][:10]

    report = {
        "migration_timestamp": datetime.now().isoformat(),
        "source": str(DB_PATH),
        "target": str(TARGET_DIR),
        "schema": CANONICAL_COLUMNS,
        "compression": "zstd",
        "row_group_size": ROW_GROUP_SIZE,
        "before": quality_before,
        "after": quality_after,
        "consistency": {
            "rows_match": quality_before["total_rows"] == quality_after["total_rows"],
            "min_date_match": b_min == a_min,
            "max_date_match": b_max == a_max,
            "tickers_match": quality_before["unique_tickers"] == quality_after["unique_tickers"],
            "no_new_corruption": (
                quality_after["null_prices"] <= quality_before["null_prices"]
                and quality_after["zero_prices"] <= quality_before["zero_prices"]
            ),
        },
        "timing_seconds": {
            "total": round(time.perf_counter() - t_start, 2),
        },
    }

    report_path = ROOT / "data" / "data_quality_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Quality report: %s", report_path)

    # 6. Print summary
    logger.info("=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("  Total rows:       %s", f"{quality_after['total_rows']:,}")
    logger.info("  Unique tickers:   %s", quality_after["unique_tickers"])
    logger.info("  Date range:       %s -> %s", quality_after["min_date"], quality_after["max_date"])
    logger.info("  Null prices:      %s", quality_after["null_prices"])
    logger.info("  Zero prices:      %s", quality_after["zero_prices"])
    logger.info("  Rows match:       %s", report["consistency"]["rows_match"])
    logger.info("  Total time:       %.1fs", report["timing_seconds"]["total"])

    all_ok = all(report["consistency"].values())
    if all_ok:
        logger.info("  STATUS: MIGRATION VERIFIED - 0 records lost")
    else:
        failed = [k for k, v in report["consistency"].items() if not v]
        logger.error("  STATUS: CONSISTENCY FAILURE - %s", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
