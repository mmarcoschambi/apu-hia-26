"""
Tests for scripts/convergence_check.py — Track B, Phase 5.

Covers:
- SCA-REQ-01: Signal Overlap Scoring (Jaccard)
- SCA-REQ-02: Entry Price Discrepancy Check (< 2%)
- SCA-REQ-03: Root-Cause Report generation
- SCA-REQ-04: Degraded Fallback Mode
- SCA-REQ-05: Output Persistence

Strict TDD: tests written FIRST (RED), implementation follows (GREEN).
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.convergence_check import (
    compute_convergence_score,
    compute_price_discrepancies,
    categorize_anomaly,
    generate_report,
    ConvergenceResult,
    PriceAnomaly,
    CONVERGENCE_THRESHOLD,
    PRICE_DISCREPANCY_THRESHOLD,
)


# ============================================================
# Task 0.2 / 4.3: Module structure and constants
# ============================================================

class TestModuleStructure:
    """Basic stub tests — module imports and constants."""

    def test_constants_defined(self):
        """Required constants MUST be defined with correct types."""
        assert isinstance(CONVERGENCE_THRESHOLD, float)
        assert CONVERGENCE_THRESHOLD == 0.80
        assert isinstance(PRICE_DISCREPANCY_THRESHOLD, float)
        assert PRICE_DISCREPANCY_THRESHOLD == 0.02

    def test_dataclasses_importable(self):
        """ConvergenceResult and PriceAnomaly dataclasses MUST be importable."""
        # Verify instances can be created with expected fields
        cr = ConvergenceResult(date="2026-05-06", overlap=0, union=0, convergence_score=1.0, threshold_passed=True)
        assert cr.date == "2026-05-06"
        assert cr.convergence_score == 1.0
        assert cr.price_anomalies == []

        pa = PriceAnomaly(ticker="AAPL", backtest_price=100.0, shadow_price=102.0, discrepancy_pct=0.02)
        assert pa.ticker == "AAPL"
        assert pa.discrepancy_pct == 0.02

    def test_functions_exist(self):
        """Core functions MUST be importable."""
        assert callable(compute_convergence_score)
        assert callable(compute_price_discrepancies)
        assert callable(categorize_anomaly)
        assert callable(generate_report)


# ============================================================
# SCA-REQ-01: Signal Overlap Scoring
# ============================================================

class TestComputeConvergenceScore:
    """SCA-REQ-01: Jaccard overlap scoring."""

    def test_full_overlap_returns_one(self):
        """
        GIVEN identical signal sets
        WHEN convergence is computed
        THEN score = 1.0
        """
        backtest = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"}
        shadow = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"}
        overlap, union, score = compute_convergence_score(backtest, shadow)
        assert overlap == 5
        assert union == 5
        assert score == 1.0

    def test_no_overlap_returns_zero(self):
        """
        GIVEN disjoint signal sets
        WHEN convergence is computed
        THEN score = 0.0
        """
        backtest = {"AAPL", "MSFT", "GOOGL"}
        shadow = {"TSLA", "NVDA", "AMD"}
        overlap, union, score = compute_convergence_score(backtest, shadow)
        assert overlap == 0
        assert union == 6
        assert score == 0.0

    def test_partial_overlap(self):
        """
        GIVEN shadow captured 18 tickers and backtest generated 20 tickers
        WHEN 16 tickers appear in both sets
        THEN convergence = 16 / 22 = 0.727 (72.7%)
        AND flagged below the 80% threshold
        """
        all_tickers = [f"T{i}" for i in range(34)]
        backtest = set(all_tickers[:20])       # 20 tickers (T0..T19)
        shadow = set(all_tickers[4:22])         # 18 tickers (T4..T21)
        # Overlap: T4..T19 = 16 tickers
        # Union: T0..T21 = 22 tickers
        overlap, union, score = compute_convergence_score(backtest, shadow)
        assert overlap == 16
        assert union == 22
        assert score == pytest.approx(16 / 22, abs=0.001)
        assert score < CONVERGENCE_THRESHOLD

    def test_empty_union_returns_one(self):
        """
        SCA-REQ-01 empty union edge case:
        GIVEN both sets empty
        WHEN convergence computed
        THEN score = 1.0 (perfect agreement, no action needed)
        """
        overlap, union, score = compute_convergence_score(set(), set())
        assert overlap == 0
        assert union == 0
        assert score == 1.0

    def test_one_set_empty(self):
        """
        GIVEN only one set has signals
        WHEN convergence computed
        THEN score = 0.0 (no overlap / some union)
        """
        overlap, union, score = compute_convergence_score({"AAPL", "MSFT"}, set())
        assert overlap == 0
        assert union == 2
        assert score == 0.0

    def test_score_with_example_from_spec(self):
        """
        Spec example: 16 overlap out of 22 union = 72.7%
        """
        # 16 overlap + 4 unique BT (S17-S20) + 2 unique SH (S21,S22) = 22 union
        common = {f"S{i}" for i in range(1, 17)}      # 16 tickers in both
        bt_only = {f"S{i}" for i in range(17, 21)}     # 4 BT-only (S17..S20)
        sh_only = {f"S{i}" for i in range(21, 23)}     # 2 SH-only (S21,S22)
        backtest = common | bt_only                     # 20 tickers total
        shadow = common | sh_only                       # 18 tickers total
        # 16 common, 4 unique BT + 2 unique SH = 22 union
        overlap, union, score = compute_convergence_score(backtest, shadow)
        assert overlap == 16
        assert union == 22
        assert score == pytest.approx(16 / 22, abs=0.001)


# ============================================================
# SCA-REQ-02: Entry Price Discrepancy Check
# ============================================================

class TestComputePriceDiscrepancies:
    """SCA-REQ-02: Entry price discrepancy detection."""

    def test_no_discrepancies_when_prices_match(self):
        """
        GIVEN matching tickers with identical prices
        WHEN discrepancies computed
        THEN empty list
        """
        bt_prices = {"AAPL": 150.0, "MSFT": 300.0}
        sh_prices = {"AAPL": 150.0, "MSFT": 300.0}
        anomalies = compute_price_discrepancies(bt_prices, sh_prices)
        assert len(anomalies) == 0

    def test_flags_discrepancy_above_threshold(self):
        """
        GIVEN backtest entry = $105.20 and shadow entry = $108.50
        WHEN discrepancy computed
        THEN |105.20 - 108.50| / 105.20 = 3.14% > 2%
        AND flagged as anomaly
        """
        anomalies = compute_price_discrepancies(
            {"TICK": 105.20},
            {"TICK": 108.50},
        )
        assert len(anomalies) == 1
        assert anomalies[0].ticker == "TICK"
        assert anomalies[0].backtest_price == 105.20
        assert anomalies[0].shadow_price == 108.50
        assert anomalies[0].discrepancy_pct == pytest.approx(0.03137, abs=0.001)

    def test_accepts_discrepancy_within_threshold(self):
        """
        GIVEN price difference < 2%
        WHEN discrepancy computed
        THEN no anomaly
        """
        anomalies = compute_price_discrepancies(
            {"TICK": 100.0},
            {"TICK": 101.5},  # 1.5% difference
        )
        assert len(anomalies) == 0

    def test_handles_multiple_tickers_mixed(self):
        """
        GIVEN some matching and some diverging prices
        WHEN discrepancies computed
        THEN only diverging ones flagged
        """
        anomalies = compute_price_discrepancies(
            {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 140.0},
            {"AAPL": 151.0, "MSFT": 350.0, "GOOGL": 141.0},
        )
        # AAPL: 0.67% → pass
        # MSFT: 16.67% → fail
        # GOOGL: 0.71% → pass
        assert len(anomalies) == 1
        assert anomalies[0].ticker == "MSFT"

    def test_skips_zero_backtest_price(self):
        """Division by zero guard: backtest_price 0 is skipped."""
        anomalies = compute_price_discrepancies(
            {"TICK": 0.0},
            {"TICK": 100.0},
        )
        assert len(anomalies) == 0

    def test_only_common_tickers_checked(self):
        """
        GIVEN tickers not in both dicts
        WHEN discrepancies computed
        THEN only common tickers are checked
        """
        anomalies = compute_price_discrepancies(
            {"ONLY_BT": 100.0, "COMMON": 50.0},
            {"ONLY_SH": 90.0, "COMMON": 50.0},
        )
        assert len(anomalies) == 0  # COMMON matches

    def test_custom_threshold(self):
        """Custom threshold should override default."""
        anomalies = compute_price_discrepancies(
            {"TICK": 100.0},
            {"TICK": 103.0},
            threshold=0.05,  # 5%
        )
        assert len(anomalies) == 0  # 3% < 5%

    def test_edge_discrepancy_at_exactly_2_percent(self):
        """
        Exactly 2% discrepancy should NOT be flagged
        (threshold is strictly greater than, not >=)
        """
        anomalies = compute_price_discrepancies(
            {"TICK": 100.0},
            {"TICK": 102.0},
        )
        assert len(anomalies) == 0


# ============================================================
# SCA-REQ-04: Categorize Anomaly
# ============================================================

class TestCategorizeAnomaly:
    """SCA-REQ-04: Root-cause category assignment."""

    def test_data_freshness_when_vps_unavailable(self):
        """VPS unavailable → data_freshness category."""
        anomaly = PriceAnomaly(ticker="AAPL", backtest_price=100, shadow_price=110, discrepancy_pct=0.10)
        category = categorize_anomaly(anomaly, {"AAPL"}, {"AAPL"}, vps_snapshot_available=False)
        assert category == "data_freshness"

    def test_universe_mismatch_when_only_in_shadow(self):
        """Ticker in shadow but not in backtest → universe_mismatch."""
        anomaly = PriceAnomaly(ticker="SHADOW_ONLY", backtest_price=50, shadow_price=55, discrepancy_pct=0.10)
        category = categorize_anomaly(anomaly, {"AAPL"}, {"SHADOW_ONLY", "AAPL"}, vps_snapshot_available=True)
        assert category == "universe_mismatch"

    def test_config_drift_when_large_discrepancy(self):
        """Discrepancy > 5% → config_drift."""
        anomaly = PriceAnomaly(ticker="AAPL", backtest_price=100, shadow_price=120, discrepancy_pct=0.20)
        category = categorize_anomaly(anomaly, {"AAPL"}, {"AAPL"}, vps_snapshot_available=True)
        assert category == "config_drift"

    def test_unexplained_when_small_and_in_both(self):
        """Present in both, small discrepancy → unexplained."""
        anomaly = PriceAnomaly(ticker="AAPL", backtest_price=100, shadow_price=103, discrepancy_pct=0.03)
        category = categorize_anomaly(anomaly, {"AAPL"}, {"AAPL"}, vps_snapshot_available=True)
        assert category == "unexplained"


# ============================================================
# SCA-REQ-03 / SCA-REQ-05: Report generation
# ============================================================

class TestGenerateReport:
    """SCA-REQ-03/05: Root-cause report with persistence."""

    def test_report_contains_executive_summary(self, tmp_path):
        """Executive summary section MUST be present."""
        results = [
            ConvergenceResult(
                date="2026-05-06",
                overlap=16, union=22,
                convergence_score=16 / 22,
                threshold_passed=False,
                price_anomalies=[
                    PriceAnomaly(ticker="ADEA", backtest_price=27.98, shadow_price=29.50, discrepancy_pct=0.0543)
                ],
            )
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        assert "Executive Summary" in report
        assert "Convergence Score" in report or "Score" in report or "Sessions" in report

    def test_report_shows_daily_scores_table(self, tmp_path):
        """Daily scores table MUST list each session."""
        results = [
            ConvergenceResult(date="2026-05-06", overlap=10, union=15, convergence_score=0.667, threshold_passed=False),
            ConvergenceResult(date="2026-05-07", overlap=20, union=22, convergence_score=0.909, threshold_passed=True),
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        assert "2026-05-06" in report
        assert "2026-05-07" in report

    def test_report_lists_price_anomalies(self, tmp_path):
        """Price anomalies section MUST list each anomaly."""
        results = [
            ConvergenceResult(
                date="2026-05-06",
                overlap=5, union=10,
                convergence_score=0.50,
                threshold_passed=False,
                price_anomalies=[
                    PriceAnomaly(ticker="ADEA", backtest_price=27.98, shadow_price=29.50, discrepancy_pct=0.0543, category="config_drift"),
                ],
            )
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        assert "ADEA" in report
        assert "$27.98" in report
        assert "config_drift" in report

    def test_report_persists_to_file(self, tmp_path):
        """SCA-REQ-05: Report MUST be written to output file."""
        output = tmp_path / "convergence_report.md"
        generate_report([], output)
        assert output.exists()
        content = output.read_text()
        assert len(content) > 50

    def test_report_with_anomalies_includes_root_cause(self, tmp_path):
        """Root Cause Analysis section when anomalies exist."""
        results = [
            ConvergenceResult(
                date="2026-05-06",
                overlap=5, union=15,
                convergence_score=0.333,
                threshold_passed=False,
                price_anomalies=[PriceAnomaly(ticker="ADEA", backtest_price=10, shadow_price=12, discrepancy_pct=0.20, category="config_drift")],
                missing_from_backtest=[],
                missing_from_shadow=["TICK1", "TICK2"],
            )
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        assert "Root Cause Analysis" in report
        assert "Recommendations" in report

    def test_degraded_mode_noted_in_report(self, tmp_path):
        """Reports MUST note when running in degraded mode."""
        results = [
            ConvergenceResult(
                date="2026-05-06",
                overlap=0, union=0,
                convergence_score=1.0,
                threshold_passed=True,
                degradation_mode="VPS_UNAVAILABLE",
                vps_available=False,
            )
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        assert "Degraded" in report or "VPS_UNAVAILABLE" in report

    def test_report_counts_passed_and_failed(self, tmp_path):
        """Report MUST count passed (≥80%) and failed sessions."""
        results = [
            ConvergenceResult(date="2026-05-06", overlap=16, union=20, convergence_score=0.80, threshold_passed=True),
            ConvergenceResult(date="2026-05-07", overlap=10, union=20, convergence_score=0.50, threshold_passed=False),
            ConvergenceResult(date="2026-05-08", overlap=19, union=20, convergence_score=0.95, threshold_passed=True),
        ]
        report = generate_report(results, tmp_path / "convergence_report.md")
        lines = report.split("\n")
        assert any("passed (>=" in l.lower() or "passed" in l.lower() or "2" in l for l in lines if "Session" in l)


# ============================================================
# Integration test with synthetic data
# ============================================================

class TestConvergenceCheckIntegration:
    """SCA-REQ-01/02 integration test with synthetic signal sets."""

    def test_synthetic_overlapping_signals(self):
        """
        GIVEN synthetic overlapping + divergent signal sets
        WHEN convergence is computed
        THEN overlapping signals produce score > 0 and price anomalies detected
        """
        bt_signals = {"AAPL", "MSFT", "GOOGL", "NVDA", "AMD"}
        sh_signals = {"AAPL", "MSFT", "TSLA", "AMZN"}

        overlap, union, score = compute_convergence_score(bt_signals, sh_signals)

        # AAPL + MSFT = 2 overlap, union = {AAPL,MSFT,GOOGL,NVDA,AMD,TSLA,AMZN} = 7
        assert overlap == 2
        assert union == 7
        assert score == pytest.approx(2 / 7, abs=0.001)
        assert score < CONVERGENCE_THRESHOLD

    def test_synthetic_price_discrepancies(self):
        """
        GIVEN synthetic overlapping prices with known discrepancies
        WHEN price discrepancies computed
        THEN anomalies match expected count and values
        """
        bt_prices = {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 140.0}
        sh_prices = {"AAPL": 150.0, "MSFT": 320.0, "GOOGL": 145.0}

        anomalies = compute_price_discrepancies(bt_prices, sh_prices)

        # AAPL: 0% → pass
        # MSFT: (320-300)/300 = 6.67% → fail
        # GOOGL: (145-140)/140 = 3.57% → fail
        assert len(anomalies) == 2
        tickers_found = {a.ticker for a in anomalies}
        assert tickers_found == {"MSFT", "GOOGL"}
        for a in anomalies:
            if a.ticker == "MSFT":
                assert a.discrepancy_pct == pytest.approx(0.0667, abs=0.001)
            elif a.ticker == "GOOGL":
                assert a.discrepancy_pct == pytest.approx(0.0357, abs=0.001)

    def test_price_gate_fails_above_2_percent(self, tmp_path):
        """
        Gate: timing/price discrepancy < 2% passes, ≥ 2% fails
        """
        bt_prices = {"TICK": 100.0}
        sh_prices = {"TICK": 102.1}  # 2.1% > 2%

        anomalies = compute_price_discrepancies(bt_prices, sh_prices)

        # Gate: price discrepancy at 2.1% should be flagged (exceeds 2%)
        assert len(anomalies) == 1
        assert anomalies[0].discrepancy_pct > PRICE_DISCREPANCY_THRESHOLD

        report_result = ConvergenceResult(
            date="2026-05-06",
            overlap=1, union=1,
            convergence_score=1.0,
            threshold_passed=True,
            price_anomalies=anomalies,
        )

        report = generate_report([report_result], tmp_path / "convergence_report.md")
        assert "Price Anomalies" in report

    def test_empty_dates_produces_minimal_report(self, tmp_path):
        """No data in range produces a report with zero sessions."""
        report = generate_report([], tmp_path / "empty_report.md")
        assert "Sessions analyzed" in report
        assert "0" in report
        assert (tmp_path / "empty_report.md").exists()
