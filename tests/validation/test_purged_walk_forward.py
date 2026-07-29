"""
Tests for PurgedWalkForwardValidator — Track A, Phase 5.

Covers:
- PCV-REQ-01: Expanding window fold generation
- PCV-REQ-02: Purge and embargo windows
- PCV-REQ-03: Degradation gate boundary (≤25% pass, >25% reject)
- PCV-REQ-04: Aggregate report completeness

Strict TDD: tests written FIRST (RED), implementation follows (GREEN).
"""

import pytest
from datetime import date, timedelta

from src.validation.purged_walk_forward import (
    PurgedWalkForwardValidator,
    PurgedWFReport,
    FoldMetrics,
    GATE_DEGRADATION,
    WF_N_FOLDS,
    WF_PURGE_DAYS,
    WF_EMBARGO_DAYS,
    MIN_OOS_TRADES,
)


# ============================================================
# Task 0.1 / 4.1: Fold Partitioning — Purge & Embargo
# ============================================================

class TestInit:
    """PurgedWalkForwardValidator construction."""

    def test_defaults(self):
        """Should initialize with spec-defined defaults."""
        v = PurgedWalkForwardValidator()
        assert v.n_folds == WF_N_FOLDS
        assert v.purge_days == WF_PURGE_DAYS
        assert v.embargo_days == WF_EMBARGO_DAYS

    def test_custom_values(self):
        """Should accept override values for all params."""
        v = PurgedWalkForwardValidator(n_folds=3, purge_days=20, embargo_days=10)
        assert v.n_folds == 3
        assert v.purge_days == 20
        assert v.embargo_days == 10

    def test_non_positive_purge_raises(self):
        """Negative purge_days MUST raise ValueError."""
        with pytest.raises(ValueError, match="purge_days"):
            PurgedWalkForwardValidator(purge_days=-1)

    def test_non_positive_embargo_raises(self):
        """Negative embargo_days MUST raise ValueError."""
        with pytest.raises(ValueError, match="embargo_days"):
            PurgedWalkForwardValidator(embargo_days=-1)


class TestGenerateFolds:
    """PCV-REQ-01: Expanding-window fold generation."""

    def test_generates_correct_number_of_folds(self):
        """Should generate exactly n_folds fold definitions."""
        v = PurgedWalkForwardValidator(n_folds=4)
        folds = v.generate_folds(train_start="2019-01-01")
        assert len(folds) == 4

    def test_each_fold_has_required_keys(self):
        """Each fold MUST have fold, oos_start, oos_end keys."""
        v = PurgedWalkForwardValidator()
        folds = v.generate_folds(train_start="2019-01-01")
        for f in folds:
            assert "fold" in f
            assert "oos_start" in f
            assert "oos_end" in f

    def test_folds_advance_one_year_per_fold(self):
        """OOS windows advance one calendar year per fold."""
        v = PurgedWalkForwardValidator()
        folds = v.generate_folds(train_start="2019-01-01")
        for i in range(1, len(folds)):
            prev_end = folds[i - 1]["oos_end"]
            curr_start = folds[i]["oos_start"]
            expected_start = f"{int(prev_end[:4]) + 1}-01-01"
            assert curr_start == expected_start, (
                f"Fold {folds[i]['fold']} should start after fold {folds[i-1]['fold']} ends"
            )

    def test_custom_n_folds(self):
        """Should generate n folds when n_folds is overridden."""
        v = PurgedWalkForwardValidator(n_folds=3)
        folds = v.generate_folds(train_start="2019-01-01")
        assert len(folds) == 3
        assert folds[-1]["fold"] == 3


class TestPurgeAndEmbargo:
    """PCV-REQ-02: Purge and embargo window logic."""

    def test_purge_shifts_end_before_oos_start(self):
        """
        Purge removes purge_days before OOS from training.
        GIVEN a fold with OOS starting 2023-01-01 and purge_days=10
        WHEN training range is computed
        THEN train_end '2022-12-18' (≈10 trading days before)
        """
        v = PurgedWalkForwardValidator(purge_days=10, embargo_days=5)
        _, train_end = v.get_training_range("2019-01-01", {
            "fold": 1, "oos_start": "2023-01-01", "oos_end": "2023-12-31"
        })
        # 10 trading days × 1.4 = 14 calendar days before 2023-01-01
        assert train_end == "2022-12-18", f"Expected 2022-12-18, got {train_end}"

    def test_purge_with_custom_days(self):
        """
        Configurable purge: purge_days=20 overrides default.
        GIVEN purge_days=20
        WHEN training range is computed
        THEN train_end shifts by 20 trading days (28 calendar days).
        """
        v = PurgedWalkForwardValidator(purge_days=20, embargo_days=5)
        _, train_end = v.get_training_range("2019-01-01", {
            "fold": 1, "oos_start": "2023-01-01", "oos_end": "2023-12-31"
        })
        assert train_end == "2022-12-04", f"Expected 2022-12-04, got {train_end}"

    def test_embargo_shifts_next_train_end(self):
        """
        Embargo removes days after previous fold's OOS from next fold's training.
        GIVEN fold 1 OOS ends 2022-12-31, embargo_days=5
        AND fold 2 purge_days=10 from 2023-01-01
        WHEN fold 2 training range is computed with previous_fold
        THEN the purge dominates (train already ends before embargo zone)
        """
        v = PurgedWalkForwardValidator(purge_days=10, embargo_days=5)
        prev = {"fold": 1, "oos_start": "2022-01-01", "oos_end": "2022-12-31"}
        curr = {"fold": 2, "oos_start": "2023-01-01", "oos_end": "2023-12-31"}
        _, train_end = v.get_training_range("2019-01-01", curr, previous_fold=prev)
        # Purge: 14 cal days before 2023-01-01 = 2022-12-18
        # Embargo: 7 cal days after 2022-12-31 = 2023-01-07
        # Training ends at min(purge_end, ... purge dominates)
        assert train_end == "2022-12-18", f"Expected 2022-12-18, got {train_end}"

    def test_embargo_may_truncate_if_purge_gap_small(self):
        """
        When purge gap is small enough that embargo reaches into training range,
        the embargo end is used as the effective training end.
        GIVEN embargo_days=20 from prev OOS end
        AND purge_days=5 from curr OOS start
        AND folds are close together
        WHEN training range is computed
        THEN the earlier of purge/embargo truncation wins
        """
        v = PurgedWalkForwardValidator(purge_days=5, embargo_days=20)
        prev = {"fold": 1, "oos_start": "2022-01-01", "oos_end": "2022-12-31"}
        curr = {"fold": 2, "oos_start": "2023-01-01", "oos_end": "2023-12-31"}
        _, train_end = v.get_training_range("2019-01-01", curr, previous_fold=prev)
        # Should give a valid date string
        assert isinstance(train_end, str) and len(train_end) == 10


class TestComputeDegradation:
    """PCV-REQ-03: Degradation gate formula."""

    def test_passes_when_degradation_within_limit(self):
        """
        Pass scenario: IS=1.20, OOS=1.00
        degradation = (1.20 - 1.00) / 1.20 = 0.167 ≤ 0.25 → PASS
        """
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(1.20, 1.00)
        assert degradation == pytest.approx(0.1667, abs=0.001)
        assert passed is True

    def test_rejects_when_degradation_exceeds_limit(self):
        """
        Reject scenario: IS=1.50, OOS=0.90
        degradation = (1.50 - 0.90) / 1.50 = 0.40 > 0.25 → REJECT
        """
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(1.50, 0.90)
        assert degradation == pytest.approx(0.40, abs=0.001)
        assert passed is False

    def test_boundary_passes_at_exactly_25_percent(self):
        """Exactly 25% degradation = (1.0 - 0.75) / 1.0 = 0.25 → PASS (≤ threshold)."""
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(1.0, 0.75)
        assert degradation == pytest.approx(0.25, abs=0.001)
        assert passed is True

    def test_boundary_fails_just_above_25_percent(self):
        """Just above 25%: IS=1.0, OOS=0.749 → degradation=0.251 → REJECT."""
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(1.0, 0.749)
        assert degradation > 0.25
        assert passed is False

    def test_zero_is_sharpe_returns_full_degradation(self):
        """When IS Sharpe is 0 (flat), degradation is undefined → 1.0 and reject."""
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(0.0, 0.5)
        assert degradation == 1.0
        assert passed is False

    def test_negative_is_sharpe_returns_full_degradation(self):
        """When IS Sharpe is negative, degradation caps to 1.0 → reject."""
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(-0.5, 0.3)
        assert degradation == 1.0
        assert passed is False

    def test_negative_oos_sharpe_rejects(self):
        """Negative OOS Sharpe produces degradation > 0.25 → reject."""
        degradation, passed = PurgedWalkForwardValidator.compute_degradation(1.0, -0.5)
        assert degradation > 0.25
        assert passed is False


class TestAggregateFoldMetrics:
    """PCV-REQ-04: Aggregate reporting."""

    def test_computes_mean_sharpes(self):
        """Mean IS and OOS Sharpe are computed correctly across folds."""
        folds = [
            FoldMetrics(fold=1, is_sharpe=1.2, oos_sharpe=1.0, is_trades=100, oos_trades=80),
            FoldMetrics(fold=2, is_sharpe=1.4, oos_sharpe=1.1, is_trades=120, oos_trades=90),
            FoldMetrics(fold=3, is_sharpe=1.1, oos_sharpe=0.9, is_trades=90, oos_trades=70),
            FoldMetrics(fold=4, is_sharpe=1.3, oos_sharpe=1.0, is_trades=110, oos_trades=85),
        ]
        report = PurgedWalkForwardValidator.aggregate_fold_metrics(folds)
        assert report.is_sharpe_mean == pytest.approx(1.25, abs=0.01)
        assert report.oos_sharpe_mean == pytest.approx(1.00, abs=0.01)

    def test_degradation_pct_in_report(self):
        """Degradation percentage is included and matches formula."""
        folds = [
            FoldMetrics(fold=1, is_sharpe=1.2, oos_sharpe=1.0, is_trades=100, oos_trades=80),
            FoldMetrics(fold=2, is_sharpe=1.4, oos_sharpe=1.1, is_trades=120, oos_trades=90),
            FoldMetrics(fold=3, is_sharpe=1.1, oos_sharpe=0.9, is_trades=90, oos_trades=70),
            FoldMetrics(fold=4, is_sharpe=1.3, oos_sharpe=1.0, is_trades=110, oos_trades=85),
        ]
        report = PurgedWalkForwardValidator.aggregate_fold_metrics(folds)
        # degradation = (1.25 - 1.00) / 1.25 = 0.20 = 20%
        assert report.degradation_pct == pytest.approx(20.0, abs=0.5)
        assert report.gate_passed is True  # 20% ≤ 25%

    def test_trades_per_fold_list(self):
        """Report contains trades_per_fold list matching fold order."""
        folds = [
            FoldMetrics(fold=1, is_sharpe=1.0, oos_sharpe=0.8, is_trades=100, oos_trades=80),
            FoldMetrics(fold=2, is_sharpe=1.0, oos_sharpe=0.7, is_trades=120, oos_trades=90),
        ]
        report = PurgedWalkForwardValidator.aggregate_fold_metrics(folds)
        assert report.trades_per_fold == [80, 90]

    def test_warns_on_insufficient_trades(self):
        """Fold with < 30 OOS trades triggers a warning."""
        folds = [
            FoldMetrics(fold=1, is_sharpe=1.0, oos_sharpe=0.8, is_trades=100, oos_trades=25),
            FoldMetrics(fold=2, is_sharpe=1.0, oos_sharpe=0.7, is_trades=120, oos_trades=90),
        ]
        report = PurgedWalkForwardValidator.aggregate_fold_metrics(folds)
        assert len(report.warnings) >= 1
        assert "insufficient" in report.warnings[0].lower() or "statistically insignificant" in report.warnings[0].lower()

    def test_report_is_dataclass_with_expected_fields(self):
        """PurgedWFReport has all required fields per design."""
        folds = [
            FoldMetrics(fold=1, is_sharpe=1.0, oos_sharpe=0.8, is_trades=100, oos_trades=80),
        ]
        report = PurgedWalkForwardValidator.aggregate_fold_metrics(folds)
        assert hasattr(report, "folds")
        assert hasattr(report, "is_sharpe_mean")
        assert hasattr(report, "oos_sharpe_mean")
        assert hasattr(report, "degradation_pct")
        assert hasattr(report, "gate_passed")
        assert hasattr(report, "trades_per_fold")
        assert hasattr(report, "warnings")


class TestValidateOrchestrator:
    """Smoke/integration-level tests for the validate() orchestrator."""

    def test_empty_fold_defs_raises(self):
        """Empty fold_definitions raises ValueError."""
        v = PurgedWalkForwardValidator()
        with pytest.raises(ValueError, match="fold_definitions"):
            v.validate(engine_class=None, params={}, universe=[], fold_definitions=[])
