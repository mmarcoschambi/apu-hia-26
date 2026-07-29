"""
Tests for scripts/run_dynamic_switch_backtest.py — Track C, Phase 5.

Covers:
- DRS-REQ-01: Health score to mode mapping (reused from config.feature_flags)
- DRS-REQ-04: Backtest mode comparison (3-way, pass/fail gate)
- DRS-REQ-05: Historical mode persistence structure

Strict TDD: tests written FIRST (RED), implementation follows (GREEN).
"""

import sys
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_dynamic_switch_backtest import (
    compute_mode_assignments,
    compare_mode_metrics,
    format_comparison_output,
    ModeAssignment,
    ComparisonVerdict,
    REGRESSION_THRESHOLD,
)


# ============================================================
# Task 4.4: Module structure and constants
# ============================================================

class TestModuleStructure:
    """Basic stub tests — module imports and constants."""

    def test_constants_defined(self):
        """Required constants MUST be defined with correct values."""
        assert isinstance(REGRESSION_THRESHOLD, float)
        # Threshold is -10%: dynamic return must not be >10% worse than best static
        assert REGRESSION_THRESHOLD == 0.10

    def test_dataclasses_importable(self):
        """ModeAssignment and ComparisonVerdict dataclasses MUST be importable."""
        ma = ModeAssignment(date="2023-01-03", mode="ATTACK", risk_multiplier=1.0, use_theme_group_filter=False)
        assert ma.date == "2023-01-03"
        assert ma.mode == "ATTACK"
        assert ma.risk_multiplier == 1.0
        assert ma.use_theme_group_filter is False

        cv = ComparisonVerdict(
            best_static_mode="ATTACK",
            best_static_return=12.0,
            dynamic_return=11.0,
            dynamic_regression_pct=-0.0833,
            passed=True,
        )
        assert cv.best_static_mode == "ATTACK"
        assert cv.best_static_return == 12.0
        assert cv.dynamic_return == 11.0
        assert cv.passed is True

    def test_functions_exist(self):
        """Core functions MUST be importable."""
        assert callable(compute_mode_assignments)
        assert callable(compare_mode_metrics)
        assert callable(format_comparison_output)


# ============================================================
# DRS-REQ-01: Mode assignment computation
# ============================================================

class TestComputeModeAssignments:
    """DRS-REQ-01: Health score to mode mapping via get_active_mode()."""

    def test_attack_only_profile(self):
        """
        GIVEN all health_scores >= 6
        WHEN compute_mode_assignments is called
        THEN attack_profile has all ATTACK, defense_profile has all DEFENSE_FULL,
        AND dynamic_profile has all ATTACK
        """
        records = [
            {"date": "2023-01-03", "health_score": 7},
            {"date": "2023-01-04", "health_score": 6},
            {"date": "2023-01-05", "health_score": 7},
        ]
        result = compute_mode_assignments(records)

        assert "attack_profile" in result
        assert "defense_profile" in result
        assert "dynamic_profile" in result

        # All dates present
        assert len(result["attack_profile"]) == 3
        assert len(result["defense_profile"]) == 3
        assert len(result["dynamic_profile"]) == 3

        # Mode A: always ATTACK
        for ma in result["attack_profile"]:
            assert ma.mode == "ATTACK"
            assert ma.risk_multiplier == 1.0
            assert ma.use_theme_group_filter is False

        # Mode B: always DEFENSE_FULL
        for ma in result["defense_profile"]:
            assert ma.mode == "DEFENSE_FULL"
            assert ma.risk_multiplier == 0.35
            assert ma.use_theme_group_filter is True

        # Mode C: dynamic matches attack (all >= 6)
        for ma in result["dynamic_profile"]:
            assert ma.mode == "ATTACK"
            assert ma.risk_multiplier == 1.0

    def test_defense_full_only_profile(self):
        """
        GIVEN all health_scores < 4
        WHEN compute_mode_assignments is called
        THEN dynamic profile has all DEFENSE_FULL
        """
        records = [
            {"date": "2023-01-03", "health_score": 2},
            {"date": "2023-01-04", "health_score": 1},
            {"date": "2023-01-05", "health_score": 3},
        ]
        result = compute_mode_assignments(records)

        for ma in result["dynamic_profile"]:
            assert ma.mode == "DEFENSE_FULL"
            assert ma.risk_multiplier == 0.35
            assert ma.use_theme_group_filter is True

    def test_defense_partial_mid_range(self):
        """
        GIVEN health_scores between 4-5
        WHEN compute_mode_assignments is called
        THEN dynamic profile has DEFENSE_PARTIAL
        """
        records = [
            {"date": "2023-01-03", "health_score": 4},
            {"date": "2023-01-04", "health_score": 5},
        ]
        result = compute_mode_assignments(records)

        for ma in result["dynamic_profile"]:
            assert ma.mode == "DEFENSE_PARTIAL"
            assert ma.risk_multiplier == 0.75
            assert ma.use_theme_group_filter is True

    def test_mixed_health_scores(self):
        """
        GIVEN a mix of health scores (7, 3, 5)
        WHEN compute_mode_assignments is called
        THEN dynamic profile has correct mode per date (ATTACK, DEFENSE_FULL, DEFENSE_PARTIAL)
        """
        records = [
            {"date": "2023-01-03", "health_score": 7},  # ATTACK
            {"date": "2023-01-04", "health_score": 3},  # DEFENSE_FULL
            {"date": "2023-01-05", "health_score": 5},  # DEFENSE_PARTIAL
        ]
        result = compute_mode_assignments(records)

        dynamic = result["dynamic_profile"]
        assert dynamic[0].mode == "ATTACK"
        assert dynamic[1].mode == "DEFENSE_FULL"
        assert dynamic[2].mode == "DEFENSE_PARTIAL"

        # Attack profile always ATTACK
        for ma in result["attack_profile"]:
            assert ma.mode == "ATTACK"

        # Defense profile always DEFENSE_FULL
        for ma in result["defense_profile"]:
            assert ma.mode == "DEFENSE_FULL"

    def test_empty_records(self):
        """GIVEN empty records WHEN called THEN all profiles empty."""
        result = compute_mode_assignments([])
        assert result["attack_profile"] == []
        assert result["defense_profile"] == []
        assert result["dynamic_profile"] == []

    def test_edge_boundary_at_6(self):
        """
        DRS-REQ-01 edge: Score exactly 6 is ATTACK (inclusive).
        """
        records = [{"date": "2023-01-03", "health_score": 6}]
        result = compute_mode_assignments(records)
        assert result["dynamic_profile"][0].mode == "ATTACK"

    def test_edge_boundary_at_4(self):
        """
        DRS-REQ-01 edge: Score exactly 4 is DEFENSE_PARTIAL (inclusive).
        """
        records = [{"date": "2023-01-03", "health_score": 4}]
        result = compute_mode_assignments(records)
        assert result["dynamic_profile"][0].mode == "DEFENSE_PARTIAL"

    def test_edge_boundary_at_3(self):
        """
        DRS-REQ-01 edge: Score 3 is DEFENSE_FULL (< 4).
        """
        records = [{"date": "2023-01-03", "health_score": 3}]
        result = compute_mode_assignments(records)
        assert result["dynamic_profile"][0].mode == "DEFENSE_FULL"

    def test_dates_preserved_in_order(self):
        """
        GIVEN records in chronological order
        WHEN compute_mode_assignments
        THEN dates preserved in output profiles
        """
        records = [
            {"date": "2023-06-01", "health_score": 6},
            {"date": "2023-06-15", "health_score": 2},
            {"date": "2023-07-01", "health_score": 4},
        ]
        result = compute_mode_assignments(records)
        dates_dynamic = [ma.date for ma in result["dynamic_profile"]]
        assert dates_dynamic == ["2023-06-01", "2023-06-15", "2023-07-01"]


# ============================================================
# DRS-REQ-04: Mode comparison and no-regression gate
# ============================================================

class TestCompareModeMetrics:
    """DRS-REQ-04: Three-way comparison with no-regression gate."""

    def test_dynamic_passes_when_better_than_both_static(self):
        """
        GIVEN dynamic return (25%) exceeds both ATTACK (12%) and DEFENSE (8%)
        WHEN compare_mode_metrics
        THEN verdict passes (no regression)
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 12.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 8.0, "Sharpe": 0.6, "MDD": -10.0},
            metrics_dynamic={"CAGR": 25.0, "Sharpe": 1.2, "MDD": -12.0},
        )
        assert verdict.best_static_mode == "ATTACK"
        assert verdict.best_static_return == 12.0
        assert verdict.dynamic_return == 25.0
        # Regression is positive (dynamic is better) → passes
        assert verdict.dynamic_regression_pct > 0
        assert verdict.passed is True

    def test_dynamic_passes_within_threshold(self):
        """
        DRS-REQ-04 Scenario: dynamic mode passes
        GIVEN ATTACK=12%, DEFENSE=8%, dynamic=11%
        WHEN compare_mode_metrics
        THEN dynamic (11%) is within 10% of best (12%) → regression = (11-12)/12 = -8.3%
        AND verdict passes
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 12.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 8.0, "Sharpe": 0.6, "MDD": -10.0},
            metrics_dynamic={"CAGR": 11.0, "Sharpe": 0.9, "MDD": -12.0},
        )
        assert verdict.best_static_mode == "ATTACK"
        assert verdict.best_static_return == 12.0
        assert verdict.dynamic_return == 11.0
        assert verdict.dynamic_regression_pct == pytest.approx(-0.08333, abs=0.001)
        assert verdict.passed is True

    def test_dynamic_fails_beyond_threshold(self):
        """
        DRS-REQ-04 Scenario: dynamic mode fails
        GIVEN ATTACK=15%, DEFENSE=5%, dynamic=4%
        WHEN compare_mode_metrics
        THEN (4-15)/15 = -73.3% regression → REJECT
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 15.0, "Sharpe": 1.0, "MDD": -20.0},
            metrics_defense={"CAGR": 5.0, "Sharpe": 0.4, "MDD": -8.0},
            metrics_dynamic={"CAGR": 4.0, "Sharpe": 0.3, "MDD": -6.0},
        )
        assert verdict.best_static_mode == "ATTACK"
        assert verdict.best_static_return == 15.0
        assert verdict.dynamic_return == 4.0
        assert verdict.dynamic_regression_pct == pytest.approx(-0.73333, abs=0.001)
        assert verdict.passed is False

    def test_defense_is_best_static(self):
        """
        GIVEN DEFENSE return > ATTACK return
        WHEN compare_mode_metrics
        THEN best_static_mode = DEFENSE_FULL
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 5.0, "Sharpe": 0.3, "MDD": -20.0},
            metrics_defense={"CAGR": 12.0, "Sharpe": 0.9, "MDD": -8.0},
            metrics_dynamic={"CAGR": 11.0, "Sharpe": 0.8, "MDD": -10.0},
        )
        assert verdict.best_static_mode == "DEFENSE_FULL"
        assert verdict.best_static_return == 12.0
        assert verdict.dynamic_regression_pct == pytest.approx(-0.08333, abs=0.001)
        assert verdict.passed is True

    def test_dynamic_ties_best_static(self):
        """
        GIVEN dynamic return equals best static return
        WHEN compare_mode_metrics
        THEN regression = 0, passes
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 10.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 7.0, "Sharpe": 0.5, "MDD": -10.0},
            metrics_dynamic={"CAGR": 10.0, "Sharpe": 0.9, "MDD": -12.0},
        )
        assert verdict.best_static_mode == "ATTACK"
        assert verdict.dynamic_regression_pct == 0.0
        assert verdict.passed is True

    def test_exactly_at_threshold_returns_true(self):
        """
        Regression exactly -10.0% should pass (threshold is inclusive).
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 10.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 5.0, "Sharpe": 0.4, "MDD": -8.0},
            metrics_dynamic={"CAGR": 9.0, "Sharpe": 0.7, "MDD": -12.0},
        )
        # (9-10)/10 = -0.10 exactly
        assert verdict.dynamic_regression_pct == pytest.approx(-0.10, abs=0.001)
        assert verdict.passed is True

    def test_barely_below_threshold_fails(self):
        """
        Regression -10.1% should fail (just past threshold).
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 10.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 5.0, "Sharpe": 0.4, "MDD": -8.0},
            metrics_dynamic={"CAGR": 8.99, "Sharpe": 0.7, "MDD": -12.0},
        )
        # (8.99-10)/10 = -0.101
        assert verdict.dynamic_regression_pct == pytest.approx(-0.101, abs=0.001)
        assert verdict.passed is False

    def test_best_static_zero_return(self):
        """GIVEN best static return is 0 WHEN comparing regression THEN handle gracefully."""
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 0.0, "Sharpe": 0.0, "MDD": -5.0},
            metrics_defense={"CAGR": -2.0, "Sharpe": -0.1, "MDD": -5.0},
            metrics_dynamic={"CAGR": 1.0, "Sharpe": 0.1, "MDD": -3.0},
        )
        # Best static = 0.0 (ATTACK). Regression formula: (1-0)/0 → division by zero
        # Should handle gracefully
        assert verdict.passed is True  # dynamic outperforms both


# ============================================================
# Output formatting
# ============================================================

class TestFormatComparisonOutput:
    """Output format consistency."""

    def test_output_contains_all_modes(self):
        """JSON output MUST contain entries for all three modes."""
        verdict = ComparisonVerdict(
            best_static_mode="ATTACK",
            best_static_return=12.0,
            dynamic_return=11.0,
            dynamic_regression_pct=-0.0833,
            passed=True,
        )
        result = format_comparison_output(
            metrics_attack={"CAGR": 12.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 8.0, "Sharpe": 0.6, "MDD": -10.0},
            metrics_dynamic={"CAGR": 11.0, "Sharpe": 0.9, "MDD": -12.0},
            verdict=verdict,
        )

        assert "mode_a_attack" in result
        assert "mode_b_defense" in result
        assert "mode_c_dynamic" in result
        assert "verdict" in result

        # Each mode entry has key metrics
        for key in ["mode_a_attack", "mode_b_defense", "mode_c_dynamic"]:
            entry = result[key]
            assert "CAGR" in entry
            assert "Sharpe" in entry
            assert "MDD" in entry

        # Verdict has required fields
        v = result["verdict"]
        assert "best_static_mode" in v
        assert "best_static_return" in v
        assert "dynamic_return" in v
        assert "dynamic_regression_pct" in v
        assert "passed" in v

    def test_output_json_serializable(self):
        """Output dict MUST be JSON-serializable."""
        verdict = ComparisonVerdict(
            best_static_mode="ATTACK",
            best_static_return=12.0,
            dynamic_return=11.0,
            dynamic_regression_pct=-0.0833,
            passed=True,
        )
        result = format_comparison_output(
            metrics_attack={"CAGR": 12.0, "Sharpe": 0.8, "MDD": -15.0},
            metrics_defense={"CAGR": 8.0, "Sharpe": 0.6, "MDD": -10.0},
            metrics_dynamic={"CAGR": 11.0, "Sharpe": 0.9, "MDD": -12.0},
            verdict=verdict,
        )
        serialized = json.dumps(result, indent=2)
        assert isinstance(serialized, str)
        # Can be deserialized back
        deserialized = json.loads(serialized)
        assert deserialized["verdict"]["passed"] is True

    def test_failed_verdict_in_output(self):
        """Failed verdict is clearly visible in output."""
        verdict = ComparisonVerdict(
            best_static_mode="ATTACK",
            best_static_return=15.0,
            dynamic_return=4.0,
            dynamic_regression_pct=-0.7333,
            passed=False,
        )
        result = format_comparison_output(
            metrics_attack={"CAGR": 15.0, "Sharpe": 1.0, "MDD": -20.0},
            metrics_defense={"CAGR": 5.0, "Sharpe": 0.4, "MDD": -8.0},
            metrics_dynamic={"CAGR": 4.0, "Sharpe": 0.3, "MDD": -6.0},
            verdict=verdict,
        )
        assert result["verdict"]["passed"] is False
        assert "FAIL" in json.dumps(result) or result["verdict"]["passed"] is False


# ============================================================
# Integration test: synthetic health scores
# ============================================================

class TestDynamicSwitchIntegration:
    """Integration test with synthetic health scores per DRS-REQ-04."""

    def test_synthetic_mixed_scores_profiles(self):
        """
        GIVEN synthetic health scores covering all regime categories
        WHEN compute_mode_assignments
        THEN profiles have correct mode distribution
        """
        records = [
            {"date": "2023-01-03", "health_score": 7},  # ATTACK
            {"date": "2023-01-04", "health_score": 4},  # DEFENSE_PARTIAL
            {"date": "2023-01-05", "health_score": 2},  # DEFENSE_FULL
            {"date": "2023-01-06", "health_score": 6},  # ATTACK
            {"date": "2023-01-07", "health_score": 5},  # DEFENSE_PARTIAL
            {"date": "2023-01-08", "health_score": 1},  # DEFENSE_FULL
            {"date": "2023-01-09", "health_score": 0},  # DEFENSE_FULL
            {"date": "2023-01-10", "health_score": 6},  # ATTACK
        ]
        result = compute_mode_assignments(records)

        # Count mode occurrences in dynamic profile
        from collections import Counter
        mode_counts = Counter(ma.mode for ma in result["dynamic_profile"])
        assert mode_counts["ATTACK"] == 3       # dates 0, 3, 7
        assert mode_counts["DEFENSE_PARTIAL"] == 2  # dates 1, 4
        assert mode_counts["DEFENSE_FULL"] == 3     # dates 2, 5, 6

        # Attack profile: all ATTACK
        all_attack = all(ma.mode == "ATTACK" for ma in result["attack_profile"])
        assert all_attack is True

        # Defense profile: all DEFENSE_FULL
        all_defense = all(ma.mode == "DEFENSE_FULL" for ma in result["defense_profile"])
        assert all_defense is True

    def test_profile_risk_multiplier_propagation(self):
        """
        GIVEN health scores for each regime
        WHEN compute_mode_assignments
        THEN risk_multiplier matches the expected mode values
        """
        records = [
            {"date": "2023-01-03", "health_score": 7},  # ATTACK → 1.0
            {"date": "2023-01-04", "health_score": 4},  # DEFENSE_PARTIAL → 0.75
            {"date": "2023-01-05", "health_score": 2},  # DEFENSE_FULL → 0.35
        ]
        result = compute_mode_assignments(records)

        dynamic = result["dynamic_profile"]
        assert dynamic[0].risk_multiplier == 1.0
        assert dynamic[1].risk_multiplier == 0.75
        assert dynamic[2].risk_multiplier == 0.35

    def test_synthetic_comparison_pass(self):
        """
        GIVEN synthetic metrics where dynamic outperforms both static
        WHEN compare_mode_metrics
        THEN verdict passes
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 10.0, "Sharpe": 0.7, "MDD": -18.0},
            metrics_defense={"CAGR": 7.0, "Sharpe": 0.5, "MDD": -9.0},
            metrics_dynamic={"CAGR": 14.0, "Sharpe": 1.0, "MDD": -12.0},
        )
        assert verdict.passed is True
        assert verdict.best_static_mode == "ATTACK"

    def test_synthetic_comparison_fail(self):
        """
        GIVEN synthetic metrics where dynamic severely underperforms
        WHEN compare_mode_metrics
        THEN verdict fails
        """
        verdict = compare_mode_metrics(
            metrics_attack={"CAGR": 20.0, "Sharpe": 1.2, "MDD": -25.0},
            metrics_defense={"CAGR": 6.0, "Sharpe": 0.4, "MDD": -8.0},
            metrics_dynamic={"CAGR": 5.0, "Sharpe": 0.3, "MDD": -7.0},
        )
        assert verdict.passed is False
        assert verdict.best_static_mode == "ATTACK"
