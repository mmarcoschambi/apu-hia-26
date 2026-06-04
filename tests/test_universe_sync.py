#!/usr/bin/env python3
"""
Test suite for Master Universe integration.

Smoke + unit tests para:
  - sync_universe: no pisa CSV si Finviz falla
  - universe_loader: prioridad tickers > file > stable > db
  - daily_signal_scanner: --universe-source stable
  - run_combo_scanner: múltiples agentes sin reconsultar Finviz

Uso:
    python3 tests/test_universe_sync.py
"""

import csv
import json
import tempfile
import contextlib
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

STABLE_CSV = PROJECT_ROOT / "data" / "stable_universe.csv"
STABLE_META = PROJECT_ROOT / "data" / "stable_universe.meta.json"


@contextlib.contextmanager
def temp_tiny_stable_universe():
    backup = PROJECT_ROOT / "data" / "stable_universe.csv.tiny_temp.bak"
    backup_meta = PROJECT_ROOT / "data" / "stable_universe.meta.json.tiny_temp.bak"
    
    if STABLE_CSV.exists():
        shutil.copy(STABLE_CSV, backup)
    if STABLE_META.exists():
        shutil.copy(STABLE_META, backup_meta)
        
    try:
        STABLE_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(STABLE_CSV, "w") as f:
            f.write("ticker,sector,theme\nAAPL,Technology,tech_theme\nMSFT,Technology,tech_theme\n")
        with open(STABLE_META, "w") as f:
            json.dump({
                "tickers_count": 2,
                "tickers_hash": "d3b07384d113edec49eaa6238ad5ff00b7190280a7ae24317130a08e1e7e4072",
                "provider": "finviz_scrape",
                "fetched_at": "2026-05-21T15:00:00",
                "filters": "cap_fake_filter"
            }, f)
        yield
    finally:
        if backup.exists():
            shutil.move(backup, STABLE_CSV)
        else:
            if STABLE_CSV.exists():
                STABLE_CSV.unlink()
        if backup_meta.exists():
            shutil.move(backup_meta, STABLE_META)
        else:
            if STABLE_META.exists():
                STABLE_META.unlink()



def test_universe_loader_explicit():
    from src.scanner.universe_loader import load_scan_universe

    t = load_scan_universe(tickers=["AAPL", "MSFT", "NVDA"])
    assert len(t) == 3, f"Expected 3, got {len(t)}"
    assert t == ["AAPL", "MSFT", "NVDA"], f"Unexpected order: {t}"
    print("  PASS: explicit tickers")


def test_universe_loader_file():
    from src.scanner.universe_loader import load_scan_universe

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["ticker"])
        for t in ["XYZ", "ABC", "DEF"]:
            writer.writerow([t])
    try:
        t = load_scan_universe(source="file", path=Path(f.name))
        assert len(t) == 3, f"Expected 3, got {len(t)}"
        assert t == ["ABC", "DEF", "XYZ"], f"Unexpected: {t}"
        print("  PASS: file source")
    finally:
        Path(f.name).unlink()


def test_universe_loader_stable():
    from src.scanner.universe_loader import load_scan_universe

    if STABLE_CSV.exists():
        t = load_scan_universe(source="stable")
        assert len(t) > 0, "stable_universe.csv should not be empty"
        assert t == sorted(t), "Should be sorted"
        print(f"  PASS: stable source ({len(t)} tickers)")
    else:
        print("  SKIP: stable_universe.csv not found")


def test_universe_loader_db():
    from src.scanner.universe_loader import load_scan_universe

    t = load_scan_universe(source="db", top_n=10)
    assert len(t) <= 10, f"Expected <=10, got {len(t)}"
    # DB returns in dollar volume order (not alphabetically sorted)
    print(f"  PASS: db source ({len(t)} tickers)")


def test_sync_no_overwrite_on_error():
    import shutil
    import importlib
    from scripts.sync_universe import run_sync

    backup_csv = PROJECT_ROOT / "data" / "stable_universe.csv.bak"
    backup_meta = PROJECT_ROOT / "data" / "stable_universe.meta.json.bak"

    if STABLE_CSV.exists():
        shutil.copy(STABLE_CSV, backup_csv)
    if STABLE_META.exists():
        shutil.copy(STABLE_META, backup_meta)

    try:
        if STABLE_CSV.exists():
            before_df = pd.read_csv(STABLE_CSV, usecols=["ticker"])
            before_hash = before_df["ticker"].sum()

        from src.data.finviz_universe_provider import UniverseFetchResult

        def _fail(*args, **kwargs):
            return UniverseFetchResult(
                tickers=[],
                provider="finviz_scrape",
                fetched_at="2026-04-24T00:00:00",
                pages_ok=0,
                raw_rows=0,
                parse_warnings=["test_mock_failure"],
                ok=False,
                error="test_network_error",
            )

        mod = importlib.import_module("scripts.sync_universe")
        orig_fetch = mod.fetch_finviz_universe
        mod.fetch_finviz_universe = _fail
        try:
            result = run_sync(override_filters="cap_fake_filter")
            assert not result["ok"], f"Should fail on mock error: {result}"
            assert "error" in result, "Should have error field"
        finally:
            mod.fetch_finviz_universe = orig_fetch

        if STABLE_CSV.exists():
            after_df = pd.read_csv(STABLE_CSV, usecols=["ticker"])
            after_hash = after_df["ticker"].sum()
            assert before_hash == after_hash, (
                f"CSV must NOT be modified when Finviz fails. "
                f"Before sum={before_hash}, After sum={after_hash}"
            )
            print(
                f"  PASS: CSV untouched on Finviz error ({len(before_df)} tickers preserved)"
            )

    finally:
        if backup_csv.exists():
            shutil.move(backup_csv, STABLE_CSV)
        if backup_meta.exists():
            shutil.move(backup_meta, STABLE_META)


def test_sync_meta_json():
    if STABLE_META.exists():
        with open(STABLE_META) as f:
            meta = json.load(f)

        assert "tickers_count" in meta, "Missing tickers_count"
        assert "tickers_hash" in meta, "Missing tickers_hash"
        assert "provider" in meta, "Missing provider"
        assert "fetched_at" in meta, "Missing fetched_at"
        assert "filters" in meta, "Missing filters"

        assert meta["tickers_count"] > 0, "tickers_count should be > 0"
        assert len(meta["tickers_hash"]) == 64, (
            "tickers_hash should be SHA256 (64 hex chars)"
        )

        print(
            f"  PASS: meta.json valid ({meta['tickers_count']} tickers, hash={meta['tickers_hash'][:16]}...)"
        )
    else:
        print(
            "  SKIP: stable_universe.meta.json not found (run sync_universe.py first)"
        )


def test_scanner_stable_flag():
    import subprocess

    with temp_tiny_stable_universe():
        result = subprocess.run(
            [
                "python3",
                "src/scanner/daily_signal_scanner.py",
                "--universe-source",
                "stable",
                "--top",
                "10",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    assert result.returncode == 0, f"Scanner failed: {result.stderr}"
    assert "Scanning" in result.stdout and "tickers" in result.stdout, (
        f"Unexpected output: {result.stdout[:200]}"
    )
    print("  PASS: daily_signal_scanner --universe-source stable")


def test_combo_scanner_multi():
    import subprocess

    with temp_tiny_stable_universe():
        result = subprocess.run(
            [
                "python3",
                "scripts/run_combo_scanner.py",
                "--universe-source",
                "stable",
                "--agents",
                "combo_pure_momentum",
                "combo_ideal_setup",
                "--dry-run",
                "--skip-tier2",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert result.returncode == 0, f"Combo scanner failed: {result.stderr}"
    assert "combo_pure_momentum" in result.stdout, (
        f"Missing pure_momentum: {result.stdout}"
    )
    assert "combo_ideal_setup" in result.stdout, f"Missing ideal_setup: {result.stdout}"
    assert "Universe:" in result.stdout and "tickers" in result.stdout, (
        f"Missing universe count: {result.stdout}"
    )
    print("  PASS: run_combo_scanner multi-agent (real pipelines)")


def test_combo_scanner_output_files():
    import subprocess
    from scripts.run_combo_scanner import run_combo_scan

    with temp_tiny_stable_universe():
        result = run_combo_scan(
            universe_source="stable",
            agent_names=["combo_pure_momentum"],
            dry_run=False,
            skip_tier2=True,
        )

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = PROJECT_ROOT / "outputs" / "live_signals" / today

    assert result["ok"], f"run_combo_scan failed: {result}"
    assert out_dir.exists(), f"Output dir not created: {out_dir}"
    assert (out_dir / "combo_pure_momentum.csv").exists(), "Agent CSV not created"
    assert (out_dir / "combined.csv").exists(), "Combined CSV not created"
    assert (out_dir / "run_summary.json").exists(), "Summary JSON not created"

    with open(out_dir / "run_summary.json") as f:
        summary = json.load(f)
    assert "scan_date" in summary, "Missing scan_date in summary"
    assert "agents" in summary, "Missing agents in summary"
    assert summary["universe_count"] > 0, (
        f"Wrong universe count: {summary['universe_count']}"
    )

    print(f"  PASS: output files created in {out_dir}")


def test_screener_gate_blocks_signal():
    import importlib
    from src.signals.signal_engine import SignalDecision

    mod = importlib.import_module("scripts.run_combo_scanner")
    orig_evaluate = mod.evaluate_ticker

    mod.evaluate_ticker = lambda *a, **kw: SignalDecision(
        ticker="TESTFAIL",
        mode="A",
        passed=False,
        reject_reason="screener_fail:Fake failure",
    )

    signals = mod.scan_combo(
        {
            "name": "test",
            "screener": {"name": "fake"},
            "tier2_filters": {},
            "pattern": {},
        },
        ["TESTFAIL"],
        {"TESTFAIL": pd.DataFrame({"close": [100.0] * 70})},
        None,
        {"TESTFAIL": pd.Series([100.0] * 70)},
    )

    mod.evaluate_ticker = orig_evaluate

    assert len(signals) == 0, (
        f"Ticker must NOT appear when screener returns passed=False, got {len(signals)} signals"
    )
    print("  PASS: screener gate blocks signal (screener PASS required)")


def test_tier2_gate_blocks_signal():
    import importlib
    from src.signals.signal_engine import SignalDecision

    mod = importlib.import_module("scripts.run_combo_scanner")
    orig_evaluate = mod.evaluate_ticker

    mod.evaluate_ticker = lambda *a, **kw: SignalDecision(
        ticker="TESTPASS",
        mode="A",
        passed=False,
        reject_reason="tier2_fail:rvol:0.10 < 0.80",
    )

    signals = mod.scan_combo(
        {
            "name": "test",
            "screener": {"name": "fake"},
            "tier2_filters": {"min_rvol": 0.8},
            "pattern": {},
        },
        ["TESTPASS"],
        {"TESTPASS": pd.DataFrame({"close": [100.0] * 70})},
        None,
        {"TESTPASS": pd.Series([100.0] * 70)},
    )

    mod.evaluate_ticker = orig_evaluate

    assert len(signals) == 0, (
        f"Ticker must NOT appear when tier2 returns passed=False, got {len(signals)} signals"
    )
    print("  PASS: tier2 gate blocks signal (tier2 PASS required)")


def test_tier2_rs_percentile_required_when_enabled():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    metrics = Tier2Metrics(
        rvol=1.0,
        adr_pct=2.0,
        dist_sma20=4.0,
        consol_days=6,
        volume=500000,
        close=100.0,
        dollar_vol_M=50.0,
        rs_ret=0.1,
        rs_percentile=65.0,
    )
    passed, reason = apply_tier2_filters(
        metrics,
        {
            "use_rs_percentile": True,
            "min_rs_percentile": 80.0,
        },
    )
    assert not passed, "RS percentile must block when enabled and below threshold"
    assert reason == "tier2_fail:rs_percentile:65.0<80.0"
    print("  PASS: RS percentile enforced when enabled")


def test_tier2_rs_percentile_ignored_when_disabled():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    metrics = Tier2Metrics(
        rvol=1.0,
        adr_pct=2.0,
        dist_sma20=4.0,
        consol_days=6,
        volume=500000,
        close=100.0,
        dollar_vol_M=50.0,
        rs_ret=0.1,
        rs_percentile=10.0,
    )
    passed, reason = apply_tier2_filters(
        metrics,
        {
            "use_rs_percentile": False,
            "min_rs_percentile": 80.0,
        },
    )
    assert passed, f"RS percentile should not block when disabled, got: {reason}"
    print("  PASS: RS percentile ignored when disabled")


def test_universe_stats_db_count_eligible_tickers():
    import importlib
    import sqlite3

    mod = importlib.import_module("src.scanner.universe_loader")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE ohlcv_cache (ticker TEXT, date TEXT, close REAL, volume REAL)"
        )
        for i in range(35):
            conn.execute(
                "INSERT INTO ohlcv_cache VALUES (?, date('now', ?), ?, ?)",
                ("AAA", f"-{i} days", 10.0, 1000000.0),
            )
        for i in range(31):
            conn.execute(
                "INSERT INTO ohlcv_cache VALUES (?, date('now', ?), ?, ?)",
                ("BBB", f"-{i} days", 20.0, 2000000.0),
            )
        for i in range(10):
            conn.execute(
                "INSERT INTO ohlcv_cache VALUES (?, date('now', ?), ?, ?)",
                ("CCC", f"-{i} days", 30.0, 3000000.0),
            )
        conn.commit()
        conn.close()

        orig_db = mod.DB_PATH
        orig_stable = mod.STABLE_CSV
        mod.DB_PATH = db_path
        mod.STABLE_CSV = Path(tmpdir) / "missing_stable.csv"
        try:
            stats = mod.universe_stats()
        finally:
            mod.DB_PATH = orig_db
            mod.STABLE_CSV = orig_stable

        assert stats["source"] == "db"
        assert stats["count"] == 2, f"Expected 2 eligible tickers, got {stats}"
    print("  PASS: universe_stats counts eligible DB tickers")


def test_tier2_all_thresholds_respected():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    m = Tier2Metrics(
        rvol=0.5,
        adr_pct=1.0,
        dist_sma20=20.0,
        consol_days=2,
        volume=50000,
        close=50.0,
        dollar_vol_M=5.0,
        rs_ret=None,
    )
    t2 = {
        "min_rvol": 0.8,
        "min_adr": 2.0,
        "max_dist_sma20": 10.0,
        "min_consolidation_days": 5,
        "min_volume": 100000,
        "min_dollar_volume": 10_000_000,
    }

    passed, reason = apply_tier2_filters(m, t2)
    assert not passed, f"Should fail tier2: {reason}"
    assert "rvol" in reason, f"Expected rvol reason, got: {reason}"
    print(f"  PASS: tier2 correctly rejects (first fail: {reason})")


def test_tier2_dist_sma20_threshold():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    m = Tier2Metrics(
        rvol=2.0,
        adr_pct=3.0,
        dist_sma20=50.0,
        consol_days=10,
        volume=1_000_000,
        close=100.0,
        dollar_vol_M=100.0,
    )
    passed, reason = apply_tier2_filters(m, {"max_dist_sma20": 10.0})
    assert not passed, f"Should fail on dist_sma20: {reason}"
    assert "dist" in reason
    print(f"  PASS: dist_sma20 threshold respected ({reason})")


def test_tier2_dollar_vol_threshold():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    m = Tier2Metrics(
        rvol=2.0,
        adr_pct=3.0,
        dist_sma20=3.0,
        consol_days=10,
        volume=500_000,
        close=10.0,
        dollar_vol_M=1.0,
    )
    passed, reason = apply_tier2_filters(m, {"min_dollar_volume": 10_000_000})
    assert not passed, f"Should fail on dollar_vol: {reason}"
    assert "tier2_fail:dollar_vol:" in reason
    print(f"  PASS: dollar_vol threshold respected ({reason})")


def test_tier2_require_positive_rs():
    from src.signals.signal_engine import apply_tier2_filters, Tier2Metrics

    m_neg = Tier2Metrics(
        rvol=2.0,
        adr_pct=3.0,
        dist_sma20=3.0,
        consol_days=10,
        volume=500_000,
        close=100.0,
        dollar_vol_M=100.0,
        rs_ret=-0.05,
    )
    passed, _ = apply_tier2_filters(m_neg, {"require_positive_rs": True})
    assert not passed, "Negative RS should be rejected"

    m_pos = Tier2Metrics(
        rvol=2.0,
        adr_pct=3.0,
        dist_sma20=3.0,
        consol_days=10,
        volume=500_000,
        close=100.0,
        dollar_vol_M=100.0,
        rs_ret=0.10,
    )
    passed, _ = apply_tier2_filters(m_pos, {"require_positive_rs": True})
    assert passed, "Positive RS should be accepted"
    print("  PASS: require_positive_rs gate works")


def test_universe_stats_db_count():
    import shutil
    from src.scanner.universe_loader import universe_stats, STABLE_CSV

    backup = PROJECT_ROOT / "data" / "stable_universe.csv.stats_test.bak"
    if STABLE_CSV.exists():
        shutil.copy(STABLE_CSV, backup)

    try:
        if STABLE_CSV.exists():
            shutil.move(STABLE_CSV, STABLE_CSV.with_suffix(".csv.test_ignore"))

        stats = universe_stats()
        assert stats["source"] == "db", f"Expected db source, got {stats['source']}"
        assert stats["count"] > 0, f"DB count should be > 0, got {stats['count']}"
        print(f"  PASS: universe_stats DB count={stats['count']}")

    finally:
        if STABLE_CSV.with_suffix(".csv.test_ignore").exists():
            shutil.move(STABLE_CSV.with_suffix(".csv.test_ignore"), STABLE_CSV)
        if backup.exists():
            shutil.move(backup, STABLE_CSV)


def test_combo_scanner_screener_plus_tier2():
    from scripts.run_combo_scanner import run_combo_scan
    from src.signals.signal_engine import SignalDecision
    import importlib

    mod = importlib.import_module("scripts.run_combo_scanner")
    orig_evaluate = mod.evaluate_ticker

    mod.evaluate_ticker = lambda *a, **kw: SignalDecision(
        ticker="TICK",
        mode="A",
        passed=False,
        reject_reason="fake_rvol_fail",
    )

    with temp_tiny_stable_universe():
        result = run_combo_scan(
            universe_source="stable",
            agent_names=["combo_pure_momentum"],
            dry_run=True,
            skip_tier2=False,
        )

    mod.evaluate_ticker = orig_evaluate

    assert result["total_signals"] == 0, (
        f"Must emit 0 signals when tier2 blocks (screener passed but tier2 failed). "
        f"Got {result['total_signals']}"
    )
    print("  PASS: screener passed + tier2 failed = 0 signals")


def main():
    print("\n" + "=" * 60)
    print("  MASTER UNIVERSE INTEGRATION TESTS")
    print("=" * 60 + "\n")

    tests = [
        ("universe_loader/explicit", test_universe_loader_explicit),
        ("universe_loader/file", test_universe_loader_file),
        ("universe_loader/stable", test_universe_loader_stable),
        ("universe_loader/db", test_universe_loader_db),
        ("sync_no_overwrite", test_sync_no_overwrite_on_error),
        ("sync_meta_json", test_sync_meta_json),
        ("scanner/stable_flag", test_scanner_stable_flag),
        ("combo_scanner/multi", test_combo_scanner_multi),
        ("combo_scanner/outputs", test_combo_scanner_output_files),
        ("combo_scanner/screener_gate", test_screener_gate_blocks_signal),
        ("combo_scanner/tier2_gate", test_tier2_gate_blocks_signal),
        ("combo_scanner/tier2_all_thresholds", test_tier2_all_thresholds_respected),
        ("combo_scanner/tier2_dist", test_tier2_dist_sma20_threshold),
        ("combo_scanner/tier2_dv", test_tier2_dollar_vol_threshold),
        ("combo_scanner/tier2_rs", test_tier2_require_positive_rs),
        ("combo_scanner/rs_percentile_enabled", test_tier2_rs_percentile_required_when_enabled),
        ("combo_scanner/rs_percentile_disabled", test_tier2_rs_percentile_ignored_when_disabled),
        ("universe_stats/db_count", test_universe_stats_db_count),
        ("universe_stats/db_count_temp", test_universe_stats_db_count_eligible_tickers),
        ("combo_scanner/screener_plus_tier2", test_combo_scanner_screener_plus_tier2),
    ]

    passed = 0
    failed = 0
    skipped = 0

    with temp_tiny_stable_universe():
        for name, fn in tests:
            print(f"  {name}...")
            try:
                fn()
                passed += 1
            except Exception as e:
                if "SKIP" in str(e) or "skipped" in str(e).lower():
                    skipped += 1
                    print(f"  SKIP: {e}")
                else:
                    failed += 1
                    print(f"  FAIL: {e}")

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 60}\n")

    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
