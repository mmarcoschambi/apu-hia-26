#!/usr/bin/env python3
"""Debug hydration coverage — reports missing prices by ticker and date."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


def normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def extract_date(row: dict) -> str:
    for field in ("signal_time", "trade_date", "signal_date"):
        val = row.get(field)
        if val:
            return str(val).split("T")[0].split(" ")[0]
    return ""


def has_close(conn: sqlite3.Connection, ticker: str, date: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM ohlcv_cache WHERE ticker = ? AND date = ? AND close IS NOT NULL LIMIT 1",
        (normalize_ticker(ticker), date),
    )
    return cur.fetchone() is not None


def has_next_open(conn: sqlite3.Connection, ticker: str, date: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM ohlcv_cache
        WHERE ticker = ? AND date > ? AND open IS NOT NULL
        ORDER BY date ASC LIMIT 1
        """,
        (normalize_ticker(ticker), date),
    )
    return cur.fetchone() is not None


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug hydration coverage")
    parser.add_argument("--signals", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--source", default="B", choices=["A", "B"])
    args = parser.parse_args()

    rows = load_jsonl(Path(args.signals))
    rows = [r for r in rows if r.get("source_system") == args.source]

    conn = sqlite3.connect(args.db)

    total = 0
    ok_close = 0
    ok_next_open = 0
    missing_rows = []
    by_ticker = Counter()
    by_date = Counter()
    by_ticker_missing = Counter()

    for r in rows:
        entry_ref = float(r.get("entry_price_ref", 0) or 0)
        if entry_ref > 0:
            continue

        ticker = normalize_ticker(str(r.get("ticker", "")))
        date = extract_date(r)
        if not ticker or not date:
            continue

        total += 1
        by_ticker[ticker] += 1

        if has_close(conn, ticker, date):
            ok_close += 1
        elif has_next_open(conn, ticker, date):
            ok_next_open += 1
        else:
            by_ticker_missing[ticker] += 1
            by_date[date] += 1
            missing_rows.append(
                {
                    "ticker": ticker,
                    "date": date,
                    "strategy_id": r.get("strategy_id", ""),
                }
            )

    conn.close()

    hydrated = ok_close + ok_next_open
    rate = hydrated / total if total else 1.0

    print("=== Hydration Debug ===")
    print(f"source={args.source}")
    print(f"needs_hydration={total}")
    print(f"covered_close={ok_close}")
    print(f"covered_next_open={ok_next_open}")
    print(f"missing={len(missing_rows)}")
    print(f"coverage_rate={rate:.2%}")

    print("\nTop missing tickers:")
    for t, n in by_ticker_missing.most_common(15):
        print(f"  {t}: {n}")

    print("\nTop missing dates:")
    for d, n in by_date.most_common(15):
        print(f"  {d}: {n}")

    print("\nSample missing_price (max 20):")
    for row in missing_rows[:20]:
        print(f"  {row}")


if __name__ == "__main__":
    main()
