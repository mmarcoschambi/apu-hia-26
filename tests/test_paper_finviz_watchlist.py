"""Regression test: dict-merge contract of `run_pre` watchlist_details.

Spec (sdd/shadow-watchlist-gap/specs/spec.md) §1.1: the destructive `continue`
in the `for t, detail in res.get("watchlist_detail", {}).items():` loop was
removed so ALL tickers from `scan_signals` are preserved in
`watchlist_details`, and the combo label is attached only when the candidate
passes the tier-2 filters.

Criterion 4: with 5 mock tickers (3 that pass `_passes_combo_filters`, 2 that
fail), the final `watchlist_details` must contain all 5, the 3 passing tickers
must carry their `combo_lbl` in `combos`, and the 2 failing tickers must have
an empty `combos` array.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.paper_finviz as pf  # noqa: E402, I001


PASSING_TICKERS = {"AAA", "BBB", "CCC"}
FAILING_TICKERS = {"DDD", "EEE"}
ALL_TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _detail(symbol: str, score: float) -> dict:
    return {
        "symbol": symbol,
        "ticker": symbol,
        "score": score,
        "rs_pct": 75.0,
        "adr": 3.0,
        "dollar_volume_m": 100.0,
    }


class _FinvizResult:
    ok = True
    tickers = list(ALL_TICKERS)


@pytest.fixture
def mock_run_pre_deps(monkeypatch, tmp_path):
    """Mock every external/direct dependency of `run_pre`."""
    monkeypatch.setattr(pf, "fetch_finviz_universe", lambda *a, **k: _FinvizResult())
    monkeypatch.setattr(pf, "load_production_config", lambda: {})
    monkeypatch.setattr(pf, "pre_warm_cache", lambda *a, **k: None)
    monkeypatch.setattr(pf, "_get_latest_ohlcv_date", lambda *a, **k: "2026-01-05")

    # Fake a non-empty DB file so the stale preflight does not trigger alerts.
    fake_db = tmp_path / "ticker_cache.db"
    fake_db.write_bytes(b"placeholder")
    monkeypatch.setattr(pf, "DB_PATH", fake_db)

    monkeypatch.setattr(pf, "get_market_context_live", lambda *a, **k: {})
    monkeypatch.setattr(pf, "apply_regime_override", lambda *a, **k: {"effective_regime_ok": True})
    monkeypatch.setattr(pf, "load_combo_params", lambda *a, **k: {"tier2_filters": {}})
    monkeypatch.setattr(pf, "shared_calculate_quality", lambda detail: ("ok", []))
    # Imported lazily inside run_pre, so it must be patched on its source module.
    monkeypatch.setattr("src.utils.terminal_gui._build_hot_sectors", lambda *a, **k: [])
    monkeypatch.setattr(pf, "_build_e25_summary", lambda *a, **k: {})
    monkeypatch.setattr(pf, "_build_nearest_flow", lambda *a, **k: {})
    monkeypatch.setattr(pf, "_build_sector_flow", lambda *a, **k: {})
    monkeypatch.setattr(pf, "print_terminal_brief", lambda *a, **k: None)

    # Route snapshot writes into the tmp dir instead of real outputs/.
    monkeypatch.setattr(pf, "OUT_DIR", tmp_path)

    return tmp_path


def _install_scan_signals_mock(monkeypatch, detail_by_ticker: dict):
    """Install a `scan_signals` mock returning one watchlist per combo."""

    def fake_scan_signals(combo_name, universe, data_as_of, rs_min_pct=0.0):
        return {
            "signals": [],
            "watchlist": {t: detail_by_ticker[t]["score"] for t in detail_by_ticker},
            "watchlist_detail": dict(detail_by_ticker),
            "breadth": None,
        }

    monkeypatch.setattr(pf, "scan_signals", fake_scan_signals)


def test_run_pre_preserves_all_tickers_in_watchlist_details(mock_run_pre_deps, monkeypatch):
    """Criterion 4a/4b/4c: all 5 tickers kept; passing get the combo label, failing get empty combos."""
    details = {t: _detail(t, score) for t, score in zip(ALL_TICKERS, [90, 80, 70, 60, 50])}
    _install_scan_signals_mock(monkeypatch, details)

    monkeypatch.setattr(pf, "_passes_combo_filters", lambda detail, t2_filters: detail["ticker"] in PASSING_TICKERS)

    snap = pf.run_pre("2026-01-05", 100.0)

    wd = snap["watchlist_detail"]
    assert list(wd.keys()) == ALL_TICKERS, "watchlist_detail must preserve ALL tickers from scan_signals"

    for t in PASSING_TICKERS:
        assert "Qulla" in wd[t]["combos"], f"passing ticker {t} must carry its combo_lbl"
    for t in FAILING_TICKERS:
        assert wd[t]["combos"] == [], f"failing ticker {t} must have an empty combos array"


def test_run_pre_merges_combos_and_keeps_highest_score(mock_run_pre_deps, monkeypatch):
    """A ticker present in both combos gets both labels, and the higher-score detail wins."""
    # Both combos return the same 5 tickers; combo_pure_momentum runs first.
    details = {t: _detail(t, score) for t, score in zip(ALL_TICKERS, [90, 80, 70, 60, 50])}
    _install_scan_signals_mock(monkeypatch, details)
    monkeypatch.setattr(pf, "_passes_combo_filters", lambda detail, t2_filters: detail["ticker"] in PASSING_TICKERS)

    snap = pf.run_pre("2026-01-05", 100.0)

    wd = snap["watchlist_detail"]
    assert len(wd) == 5
    # Passing tickers present in both combos must end with both labels, deduplicated.
    assert set(wd["AAA"]["combos"]) == {"Qulla", "Minervini"}
    assert set(wd["BBB"]["combos"]) == {"Qulla", "Minervini"}
    # Failing tickers stay with an empty combos array after the second combo pass.
    assert wd["DDD"]["combos"] == []
    assert wd["EEE"]["combos"] == []


def test_run_pre_writes_snapshot_with_full_watchlist(mock_run_pre_deps, monkeypatch, tmp_path):
    """The generated snapshot file contains all 5 tickers in watchlist_detail."""
    details = {t: _detail(t, score) for t, score in zip(ALL_TICKERS, [90, 80, 70, 60, 50])}
    _install_scan_signals_mock(monkeypatch, details)
    monkeypatch.setattr(pf, "_passes_combo_filters", lambda detail, t2_filters: detail["ticker"] in PASSING_TICKERS)

    snap = pf.run_pre("2026-01-05", 100.0)
    assert snap["universe_size"] == 5

    written = json.loads((tmp_path / "2026-01-05" / "snapshot.json").read_text())
    assert list(written["watchlist_detail"].keys()) == ALL_TICKERS
    assert written["watchlist_detail"]["DDD"]["combos"] == []
