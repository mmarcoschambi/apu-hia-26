"""Tests for ticker_cache resilience patterns.

Tasks covered:
  1. Tenacity retry with exponential jitter on download
  2. DLQ writer for failed ticker batches
  3. Live trading scanner DLQ drain and retry
  4. PRAGMA journal_mode=WAL preservation
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock, call, mock_open

import pandas as pd
import pytest

from src.data.ticker_cache import TickerCache


# ──────────────────────────────────────────────────────────────────────
# Task 4: Confirm journal_mode=WAL is preserved on connection
# ──────────────────────────────────────────────────────────────────────
class TestWALMode:
    """Task 4: PRAGMA journal_mode=WAL preservation."""

    def test_wal_mode_on_connection(self, tmp_path):
        """Verify WAL journal mode is active after TickerCache.__init__."""
        db_path = tmp_path / "test_wal.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            cursor = cache.conn.execute("PRAGMA journal_mode")
            row = cursor.fetchone()
            assert row is not None, "PRAGMA journal_mode returned no result"
            actual_mode = row[0].lower()
            assert actual_mode == "wal", f"Expected journal_mode=wal, got {actual_mode}"
        finally:
            cache.close()

    def test_wal_persists_after_write(self, tmp_path):
        """WAL mode survives a write-then-read cycle."""
        db_path = tmp_path / "test_wal_write.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            cache.conn.execute("CREATE TABLE IF NOT EXISTS _test_wal (id INTEGER)")
            cache.conn.execute("INSERT INTO _test_wal VALUES (1)")
            cache.conn.commit()

            cursor = cache.conn.execute("PRAGMA journal_mode")
            row = cursor.fetchone()
            assert row[0].lower() == "wal", "WAL lost after write"
        finally:
            cache.close()


# ──────────────────────────────────────────────────────────────────────
# Task 1: Tenacity retry with exponential jitter
# ──────────────────────────────────────────────────────────────────────
class TestTenacityRetry:
    """Task 1: Tenacity retry decorator on batch download."""

    def test_retry_decorator_present(self, tmp_path):
        """Ensure _download_chunk has a tenacity retry wrapper."""
        db_path = tmp_path / "test_retry.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            raw = getattr(cache._download_chunk, "__wrapped__", None)
            retry_stat = getattr(cache._download_chunk, "retry", None)
            # tenacity attaches .retry attribute and __wrapped__
            has_retry = raw is not None or retry_stat is not None
            assert has_retry, (
                "_download_chunk should be wrapped with @retry "
                "(expected .__wrapped__ or .retry attribute)"
            )
        finally:
            cache.close()

    @patch("src.data.ticker_cache.yf.download")
    def test_download_chunk_retries_on_failure(self, mock_download, tmp_path):
        """_download_chunk retries when yf.download raises."""
        db_path = tmp_path / "test_chunk_retry.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            mock_download.side_effect = [
                Exception("Rate limited"),
                Exception("Timeout"),
                MagicMock(),
            ]

            # _download_chunk is idempotent — it's the retried helper
            result = cache._download_chunk(["AAPL"], "2024-01-01", "2024-01-10")

            assert mock_download.call_count == 3, (
                f"Expected 3 calls (fail + fail + success), got {mock_download.call_count}"
            )
        finally:
            cache.close()


# ──────────────────────────────────────────────────────────────────────
# Task 2: DLQ writer for failed ticker batches
# ──────────────────────────────────────────────────────────────────────
class TestDLQWriter:
    """Task 2: Dead Letter Queue writer to data/dlq_failures.json."""

    def test_dlq_writes_failed_tickers(self, tmp_path):
        """_write_dlq appends failures to dlq_failures.json."""
        db_path = tmp_path / "test_dlq.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            cache._write_dlq(["AAPL", "GOOGL"])

            dlq_path = Path(db_path).parent / "dlq_failures.json"
            assert dlq_path.exists(), "DLQ file should exist after write"
            with open(dlq_path) as f:
                data = json.load(f)
            assert isinstance(data, list), "DLQ should be a JSON array"
            assert "AAPL" in data, "AAPL should be in DLQ"
            assert "GOOGL" in data, "GOOGL should be in DLQ"
        finally:
            cache.close()

    def test_dlq_append_no_duplicates(self, tmp_path):
        """DLQ should not duplicate tickers already present."""
        db_path = tmp_path / "test_dlq_dedup.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            cache._write_dlq(["AAPL"])
            cache._write_dlq(["AAPL", "GOOGL"])

            dlq_path = Path(db_path).parent / "dlq_failures.json"
            with open(dlq_path) as f:
                data = json.load(f)
            assert data.count("AAPL") == 1, "AAPL should not be duplicated"
            assert "GOOGL" in data, "GOOGL should be added"
            assert len(data) == 2, f"Expected 2 entries, got {len(data)}"
        finally:
            cache.close()

    def test_dlq_empty_tickers_does_nothing(self, tmp_path):
        """Writing empty list does not create DLQ file."""
        db_path = tmp_path / "test_dlq_empty.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            cache._write_dlq([])

            dlq_path = Path(db_path).parent / "dlq_failures.json"
            if dlq_path.exists():
                with open(dlq_path) as f:
                    data = json.load(f)
                assert data == [], "DLQ should be empty array"
        finally:
            cache.close()

    @patch("src.data.ticker_cache.yf.download")
    def test_update_ohlcv_batch_writes_dlq_on_failure(self, mock_download, tmp_path):
        """Failed ticker processing writes to DLQ automatically."""
        db_path = tmp_path / "test_batch_dlq.db"
        cache = TickerCache(db_path=str(db_path))
        try:
            # Return a DataFrame that will cause processing failure
            bad_df = pd.DataFrame()
            mock_download.return_value = bad_df

            cache.update_ohlcv_batch(["FAIL_TICKER"], "2024-01-01", "2024-01-10")

            dlq_path = Path(db_path).parent / "dlq_failures.json"
            assert dlq_path.exists(), "DLQ file should exist"
            with open(dlq_path) as f:
                data = json.load(f)
            assert "FAIL_TICKER" in data, "FAIL_TICKER should be recorded in DLQ"
        finally:
            cache.close()


# ──────────────────────────────────────────────────────────────────────
# Task 3: Live trading scanner DLQ drain
# ──────────────────────────────────────────────────────────────────────
class TestScannerDLQDrain:
    """Task 3: LiveTradingScanner reads and retries DLQ."""

    def test_drain_dlq_returns_failed_tickers(self, tmp_path):
        """drain_dlq reads tickers from dlq_failures.json and clears it."""
        from scripts.live_trading_scanner import drain_dlq

        dlq_file = tmp_path / "data" / "dlq_failures.json"
        dlq_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dlq_file, "w") as f:
            json.dump(["AAPL", "NVDA", "TSLA"], f)

        result = drain_dlq(str(dlq_file))

        assert result == ["AAPL", "NVDA", "TSLA"], (
            f"Expected ['AAPL', 'NVDA', 'TSLA'], got {result}"
        )
        assert not dlq_file.exists() or dlq_file.stat().st_size == 0, (
            "DLQ file should be removed after drain"
        )

    def test_drain_dlq_nonexistent_file(self, tmp_path):
        """drain_dlq returns empty list when DLQ file does not exist."""
        from scripts.live_trading_scanner import drain_dlq

        result = drain_dlq(str(tmp_path / "data" / "dlq_failures.json"))
        assert result == [], f"Expected empty list, got {result}"

    def test_drain_dlq_empty_file(self, tmp_path):
        """drain_dlq returns empty list when DLQ file is empty."""
        from scripts.live_trading_scanner import drain_dlq

        dlq_file = tmp_path / "data" / "dlq_failures.json"
        dlq_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dlq_file, "w") as f:
            json.dump([], f)

        result = drain_dlq(str(dlq_file))
        assert result == [], f"Expected empty list, got {result}"
        assert not dlq_file.exists(), "DLQ file should be removed after draining empty list"
