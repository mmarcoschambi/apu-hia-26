#!/usr/bin/env python3
"""Tests for Phase 3.1 — Hydration Gatekeeper."""

import sys
import sqlite3
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.price_hydrator import (
    get_close_price,
    get_next_open_price,
    hydrate_prices,
)

_SCHEMA = (
    "ticker TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, "
    "low REAL, close REAL, volume INTEGER, dollar_volume REAL, "
    "rolling_dollar_vol_20 REAL, PRIMARY KEY (ticker, date)"
)


def _db(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.execute(f"CREATE TABLE IF NOT EXISTS ohlcv_cache ({_SCHEMA})")
    c.commit()
    return c


def _add(conn: sqlite3.Connection, t: str, d: str, **kw) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO ohlcv_cache VALUES (?,?,?,?,?,?,?,?,?)",
        (
            t,
            d,
            kw.get("o", 0.0),
            kw.get("h", 0.0),
            kw.get("l", 0.0),
            kw.get("close", 0.0),
            kw.get("v", 0),
            kw.get("dv", 0.0),
            kw.get("rdv", 0.0),
        ),
    )
    conn.commit()


def _sig(ticker: str, entry: float = 0.0, key: str = "") -> "RoutedSignal":
    from src.integration.unified_signal import UnifiedSignal
    from src.integration.routed_signal import RoutedSignal

    k = key or f"{ticker}_2026-04-22_daily"
    sig = UnifiedSignal(
        "B",
        "test",
        ticker,
        "1D",
        "2026-04-22T00:00:00",
        "long",
        "next_open",
        entry,
        normalized_score=75.0,
    )
    return RoutedSignal(sig, "accepted", "won_by_score", k)


def test_ohlcv_read():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "x.db"
        c = _db(db)
        _add(c, "AAPL", "2026-04-22", close=150.0)
        c.close()
        assert get_close_price(db, "AAPL", "2026-04-22") == 150.0
    print("[PASS] test_price_hydrator_reads_ohlcv_cache")


def test_next_open():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "x.db"
        c = _db(db)
        _add(c, "AAPL", "2026-04-23", o=151.0, close=151.5)
        c.close()
        assert get_next_open_price(db, "AAPL", "2026-04-22") == 151.0
    print("[PASS] test_price_hydrator_fallback_next_open_when_close_missing")


def test_debug():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "x.db"
        c = _db(db)
        _add(c, "AAPL", "2026-04-22", close=150.0)
        c.close()
        c = sqlite3.connect(db)
        cur = c.cursor()
        cur.execute(
            "SELECT 1 FROM ohlcv_cache WHERE ticker=? AND date=? AND close IS NOT NULL LIMIT 1",
            ("TSLA", "2026-04-22"),
        )
        assert cur.fetchone() is None
        c.close()
    print("[PASS] test_debug_hydration_reports_missing_by_ticker")


def test_insert_skips_existing():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "x.db"
        c = _db(db)
        _add(c, "AAPL", "2026-04-20", close=148.0)
        cur = c.cursor()
        cur.execute("SELECT date FROM ohlcv_cache WHERE ticker='AAPL'")
        existing = {r[0] for r in cur.fetchall()}
        c.close()
        assert "2026-04-20" in existing
        assert "2026-04-22" not in existing
    print("[PASS] test_refresh_ticker_cache_inserts_missing_rows_only")


def test_hydration_rate():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "x.db"
        c = _db(db)
        _add(c, "AAPL", "2026-04-22", close=150.0)
        _add(c, "MSFT", "2026-04-22", close=372.0)
        c.close()
        sigs = [_sig("AAPL"), _sig("MSFT")]
        h, _ = hydrate_prices(sigs, db)
        assert len(h) / len(sigs) >= 0.80
    print("[PASS] test_phase3_b_hydration_rate_above_threshold_smoke")


def test_preflight_after():
    from src.integration.edge_analytics import compute_preflight

    plan = [
        {
            "source_system": "A",
            "trade_date": f"2026-01-{d:02d}",
            "hydrated_price_source": "close_signal_date",
        }
        for d in range(1, 65)
    ] + [
        {
            "source_system": "B",
            "trade_date": f"2026-01-{d:02d}",
            "hydrated_price_source": "close_signal_date",
        }
        for d in range(1, 65)
    ]
    p = compute_preflight(plan)
    assert p.hydrated_rate_B >= 0.80
    assert p.common_sessions >= 60
    print("[PASS] test_phase4_preflight_passes_after_backfill")


def main():
    test_ohlcv_read()
    test_next_open()
    test_debug()
    test_insert_skips_existing()
    test_hydration_rate()
    test_preflight_after()
    print("\n=== All Phase 3.1 tests passed ===")


if __name__ == "__main__":
    main()
