#!/usr/bin/env python3
"""
Validacion rapida para screener structure_pivot (sistema B / ablation).
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.ticker_cache import TickerCache
from src.screeners import ScreenerRegistry


def load_top_tickers(db_path: Path, start: str, end: str, top: int) -> List[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT ticker, AVG(close * volume) AS avg_dv
            FROM ohlcv_cache
            WHERE date BETWEEN ? AND ?
            GROUP BY ticker
            HAVING COUNT(*) >= 60
            ORDER BY avg_dv DESC
            LIMIT ?
            """,
            (start, end, top),
        ).fetchall()
    finally:
        conn.close()
    return [r[0] for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ablation validation for structure_pivot screener")
    parser.add_argument("--start", type=str, default="2024-01-01")
    parser.add_argument("--end", type=str, default="2024-12-31")
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    tickers = [t.upper() for t in args.tickers] if args.tickers else load_top_tickers(
        db_path=db_path,
        start=args.start,
        end=args.end,
        top=args.top,
    )

    if not tickers:
        print("No se encontraron tickers para validar.")
        return

    cache = TickerCache(db_path=db_path)
    batch_start = time.perf_counter()
    ohlcv_map = cache.get_ohlcv_batch(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        offline=True,
    )
    load_seconds = time.perf_counter() - batch_start

    config = ScreenerRegistry.load_config("structure_pivot")
    screener = ScreenerRegistry.get("structure_pivot", config)

    scan_start = time.perf_counter()
    rows = []
    scanned = 0
    passed = 0

    for ticker in tickers:
        df = ohlcv_map.get(ticker)
        if df is None or df.empty:
            continue
        scanned += 1
        result = screener.scan(ticker=ticker, df=df)
        passed += int(result.passed)
        metrics = result.metrics or {}
        rows.append(
            {
                "ticker": ticker,
                "passed": result.passed,
                "score": result.score,
                "reason": result.reason,
                "long_setup": metrics.get("long_setup"),
                "long_break_val": metrics.get("long_break_val"),
                "long_distance_pct": metrics.get("long_distance_pct"),
                "short_setup": metrics.get("short_setup"),
                "short_break_val": metrics.get("short_break_val"),
                "short_distance_pct": metrics.get("short_distance_pct"),
            }
        )

    scan_seconds = time.perf_counter() - scan_start
    results_df = pd.DataFrame(rows).sort_values(by=["passed", "score"], ascending=[False, False])

    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = PROJECT_ROOT / "outputs" / "backtests" / f"structure_pivot_ablation_{ts}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False)

    total_seconds = load_seconds + scan_seconds
    rate = scanned / total_seconds if total_seconds > 0 else 0.0
    print("=" * 80)
    print("STRUCTURE PIVOT ABLATION")
    print("=" * 80)
    print(f"Tickers input:   {len(tickers)}")
    print(f"Tickers scanned: {scanned}")
    print(f"Setups passed:   {passed}")
    print(f"Load time:       {load_seconds:.2f}s")
    print(f"Scan time:       {scan_seconds:.2f}s")
    print(f"Total time:      {total_seconds:.2f}s")
    print(f"Throughput:      {rate:.2f} tickers/s")
    print(f"Output CSV:      {output_path}")


if __name__ == "__main__":
    main()
