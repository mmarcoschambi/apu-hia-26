import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.integration.routed_signal import RoutedSignal


def _normalize_ticker(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def _extract_signal_date(routed: RoutedSignal) -> str:
    parts = routed.collision_key.split("_")
    if len(parts) >= 3:
        return parts[1]
    signal_time = routed.signal.signal_time
    return signal_time.split("T")[0]


def get_close_price(db_path: Path, ticker: str, date: str) -> Optional[float]:
    ticker = _normalize_ticker(ticker)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT close FROM ohlcv_cache WHERE ticker = ? AND date = ?",
            (ticker, date),
        )
        row = cur.fetchone()
        conn.close()
        if not row or row["close"] is None:
            return None
        value = float(row["close"])
        return value if value > 0 else None
    except Exception:
        return None


def get_next_open_price(db_path: Path, ticker: str, date: str) -> Optional[float]:
    ticker = _normalize_ticker(ticker)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, open
            FROM ohlcv_cache
            WHERE ticker = ? AND date > ?
            ORDER BY date ASC
            LIMIT 1
            """,
            (ticker, date),
        )
        row = cur.fetchone()
        conn.close()
        if not row or row["open"] is None:
            return None
        value = float(row["open"])
        return value if value > 0 else None
    except Exception:
        return None


def hydrate_prices(
    routed_signals: list[RoutedSignal],
    db_path: Path,
) -> tuple[list[RoutedSignal], list[dict]]:
    hydrated: list[RoutedSignal] = []
    rejected: list[dict] = []

    close_cache: dict[tuple[str, str], Optional[float]] = {}
    next_open_cache: dict[tuple[str, str], Optional[float]] = {}

    for routed in routed_signals:
        signal = routed.signal

        if signal.entry_price_ref > 0:
            signal.metadata["hydrated_price_source"] = "input"
            hydrated.append(routed)
            continue

        signal_date = _extract_signal_date(routed)
        key = (_normalize_ticker(signal.ticker), signal_date)

        if key not in close_cache:
            close_cache[key] = get_close_price(db_path, signal.ticker, signal_date)
        close_price = close_cache[key]

        if close_price and close_price > 0:
            signal.entry_price_ref = close_price
            signal.metadata["hydrated_price_source"] = "close_signal_date"
            hydrated.append(routed)
            continue

        if key not in next_open_cache:
            next_open_cache[key] = get_next_open_price(
                db_path, signal.ticker, signal_date
            )
        next_open = next_open_cache[key]

        if next_open and next_open > 0:
            signal.entry_price_ref = next_open
            signal.metadata["hydrated_price_source"] = "open_next_session"
            hydrated.append(routed)
            continue

        rejected.append(
            {
                "signal": routed,
                "reason": "missing_price",
                "ticker": signal.ticker,
                "date": signal_date,
                "attempts": ["close_signal_date", "open_next_session"],
            }
        )

    return hydrated, rejected


def get_missing_keys(
    routed_signals: list[RoutedSignal],
) -> list[tuple[str, str]]:
    missing = []
    for routed in routed_signals:
        if routed.signal.entry_price_ref > 0:
            continue
        signal_date = _extract_signal_date(routed)
        missing.append((_normalize_ticker(routed.signal.ticker), signal_date))
    return missing
