#!/usr/bin/env python3
"""Incremental backfill of ohlcv_cache from signals B (tickers + date range)."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


def normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def load_required_tickers(path: Path, source: str) -> list[str]:
    tickers = set()
    dates_by_ticker: dict[str, list[str]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source_system") != source:
                continue
            t = normalize_ticker(str(row.get("ticker", "")))
            if not t:
                continue
            tickers.add(t)

            for field in ("signal_time", "trade_date", "signal_date"):
                val = row.get(field)
                if val:
                    d = str(val).split("T")[0].split(" ")[0]
                    if t not in dates_by_ticker:
                        dates_by_ticker[t] = []
                    dates_by_ticker[t].append(d)
                    break

    return sorted(tickers)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            dollar_volume REAL,
            rolling_dollar_vol_20 REAL,
            PRIMARY KEY (ticker, date)
        )
        """
    )
    conn.commit()


def get_existing_dates(
    conn: sqlite3.Connection, ticker: str, start: str, end: str
) -> set[str]:
    cur = conn.cursor()
    cur.execute(
        "SELECT date FROM ohlcv_cache WHERE ticker = ? AND date BETWEEN ? AND ?",
        (ticker, start, end),
    )
    return {r[0] for r in cur.fetchall()}


def fetch_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
    df = yf.download(
        ticker,
        start=start,
        end=end_dt.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()
    df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df["dollar_volume"] = df["Close"] * df["Volume"]
    df["rolling_dollar_vol_20"] = (
        df["dollar_volume"].rolling(window=20, min_periods=1).mean()
    )
    return df


def insert_missing_rows(
    conn: sqlite3.Connection, ticker: str, df: pd.DataFrame, existing: set[str]
) -> int:
    rows = []
    for _, r in df.iterrows():
        d = r["date"]
        if d in existing:
            continue
        rows.append(
            (
                ticker,
                d,
                float(r["Open"]),
                float(r["High"]),
                float(r["Low"]),
                float(r["Close"]),
                int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
                float(r["dollar_volume"]) if pd.notna(r["dollar_volume"]) else 0.0,
                float(r["rolling_dollar_vol_20"])
                if pd.notna(r["rolling_dollar_vol_20"])
                else 0.0,
            )
        )
    if not rows:
        return 0
    conn.executemany(
        """
        INSERT OR IGNORE INTO ohlcv_cache
        (ticker, date, open, high, low, close, volume, dollar_volume, rolling_dollar_vol_20)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Incremental backfill ohlcv_cache from signals"
    )
    parser.add_argument("--tickers-from", required=True)
    parser.add_argument("--source", default="B", choices=["A", "B"])
    parser.add_argument("--db", required=True)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()

    tickers = load_required_tickers(Path(args.tickers_from), args.source)
    if not tickers:
        print("No tickers found.")
        return

    conn = sqlite3.connect(args.db)
    ensure_schema(conn)

    inserted_total = 0
    for i, ticker in enumerate(tickers, start=1):
        existing = get_existing_dates(conn, ticker, args.start, args.end)
        df = fetch_ohlcv(ticker, args.start, args.end)

        if df.empty:
            print(f"[{i}/{len(tickers)}] {ticker}: no_data")
            continue

        inserted = insert_missing_rows(conn, ticker, df, existing)
        inserted_total += inserted
        print(f"[{i}/{len(tickers)}] {ticker}: inserted={inserted}")

    conn.close()
    print(f"Done. tickers={len(tickers)} inserted={inserted_total}")


if __name__ == "__main__":
    main()
