#!/usr/bin/env python3
"""
MIGRACION: Pickle -> Parquet
Convierte todos los archivos .pkl de data/cache/ a formato Parquet.

Uso:
    python3 migrate_pickle_to_parquet.py
    python3 migrate_pickle_to_parquet.py --dry-run
    python3 migrate_pickle_to_parquet.py --keep-pkl
"""

import argparse
import pickle
import time
from pathlib import Path

import pandas as pd


def migrate(cache_dir: Path, dry_run: bool = False, keep_pkl: bool = False) -> None:
    pkl_files = sorted(cache_dir.glob("*.pkl"))

    if not pkl_files:
        print(f"No .pkl files found in {cache_dir.resolve()}")
        existing = list(cache_dir.glob("*.parquet"))
        if existing:
            print(f"Note: {len(existing)} .parquet files already exist - migration may have already run.")
        return

    total     = len(pkl_files)
    converted = 0
    skipped   = 0
    errors    = 0
    saved_mb  = 0.0

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"{prefix}Migrating {total} .pkl files -> Parquet")
    print(f"Source: {cache_dir.resolve()}")
    print("-" * 60)

    t0 = time.time()
    for i, pkl_path in enumerate(pkl_files, 1):
        # El pkl puede haber desaparecido si corremos 2 veces
        if not pkl_path.exists():
            skipped += 1
            continue

        parquet_path = pkl_path.with_suffix(".parquet")
        ticker = pkl_path.stem

        # Skip si parquet existe y es mas reciente
        if parquet_path.exists():
            try:
                if parquet_path.stat().st_mtime >= pkl_path.stat().st_mtime:
                    skipped += 1
                    # Borrar pkl huerfano si no queremos conservarlo
                    if not keep_pkl and not dry_run:
                        pkl_path.unlink()
                    continue
            except OSError:
                pass

        try:
            with open(pkl_path, "rb") as f:
                df = pickle.load(f)

            if not isinstance(df, pd.DataFrame):
                print(f"  SKIP {ticker}: not a DataFrame (type={type(df).__name__})")
                skipped += 1
                continue

            pkl_size_mb = pkl_path.stat().st_size / (1024 ** 2)

            if not dry_run:
                df.to_parquet(parquet_path, engine="pyarrow", compression="snappy")
                parquet_size_mb = parquet_path.stat().st_size / (1024 ** 2)
                saved_mb += pkl_size_mb - parquet_size_mb

                if not keep_pkl:
                    pkl_path.unlink()

                if i % 200 == 0 or i == total:
                    elapsed = time.time() - t0
                    rate = i / elapsed if elapsed > 0 else 0
                    print(f"  [{i:>5}/{total}]  rate={rate:.0f} files/s  saved={saved_mb:.0f}MB so far")
            else:
                print(f"  [DRY] {ticker:<14}  {pkl_size_mb:.2f}MB")

            converted += 1

        except Exception as e:
            print(f"  ERROR {ticker}: {e}")
            errors += 1

    elapsed = time.time() - t0
    print("-" * 60)
    print(f"Done in {elapsed:.1f}s")
    print(f"  Converted : {converted}")
    print(f"  Skipped   : {skipped} (parquet already up-to-date or pkl gone)")
    print(f"  Errors    : {errors}")
    if not dry_run and converted > 0:
        print(f"  Space saved: {saved_mb:.1f} MB")
    if errors > 0:
        print("  Re-run to retry failed files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate pickle cache to Parquet")
    parser.add_argument("--cache-dir", default="data/cache")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--keep-pkl", action="store_true")
    args = parser.parse_args()

    cache_path = Path(args.cache_dir)
    if not cache_path.exists():
        print(f"Error: cache directory not found: {cache_path.resolve()}")
        raise SystemExit(1)

    try:
        import pyarrow  # noqa: F401
    except ImportError:
        print("ERROR: pyarrow not installed. Run: pip install pyarrow")
        raise SystemExit(1)

    migrate(cache_path, dry_run=args.dry_run, keep_pkl=args.keep_pkl)
