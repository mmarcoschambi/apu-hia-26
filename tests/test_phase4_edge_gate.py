#!/usr/bin/env python3
"""Tests for Phase 4 Edge Gate."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.edge_analytics import (
    PreflightResult,
    compute_metrics_from_trades,
    compute_preflight,
    compute_rolling_metrics,
)
from src.integration.promotion_gate import (
    GateThresholds,
    evaluate_gate,
    evaluate_all,
)
from src.integration.score_calibration import (
    CalibratedScore,
    calibrate_scores,
    detect_degradation,
)


def make_trade(r_multiple=1.0, source="A", strategy_id="test"):
    return {
        "r_multiple": r_multiple,
        "source_system": source,
        "strategy_id": strategy_id,
    }


def test_preflight_fails_on_low_hydration():
    plan = [
        {
            "source_system": "B",
            "trade_date": "2026-04-22",
            "hydrated_price_source": "input",
        },
    ] * 10
    preflight = compute_preflight(plan)
    assert not preflight.passed
    assert any("hydrated_rate_B" in e for e in preflight.errors)
    print("[PASS] test_preflight_fails_on_low_hydration")


def test_expectancy_formula_matches_reference():
    trades = [
        make_trade(1.0),
        make_trade(2.0),
        make_trade(-1.0),
        make_trade(-1.0),
    ]
    m = compute_metrics_from_trades(trades)
    assert m.trades == 4
    assert m.win_rate == 0.5
    assert m.expectancy == 0.25
    assert abs(m.avg_win - 1.5) < 0.01
    assert abs(m.avg_loss - (-1.0)) < 0.01
    print("[PASS] test_expectancy_formula_matches_reference")


def test_profit_factor_and_payoff_ratio():
    trades = [
        make_trade(2.0),
        make_trade(2.0),
        make_trade(-1.0),
        make_trade(-1.0),
    ]
    m = compute_metrics_from_trades(trades)
    assert m.profit_factor == 2.0
    assert m.payoff_ratio == 2.0
    print("[PASS] test_profit_factor_and_payoff_ratio")


def test_gate_promote_hold_reject_paths():
    thresholds = GateThresholds(
        min_trades=30,
        min_expectancy=0.0,
        min_profit_factor=1.20,
        max_drawdown=0.15,
        min_sharpe=0.80,
    )

    good_trades = [make_trade(1.0)] * 30
    good = compute_metrics_from_trades(good_trades)
    good.expectancy = 0.5
    good.profit_factor = 2.0
    good.max_drawdown = 0.05
    good.sharpe = 1.2

    result = evaluate_gate(good, thresholds)
    assert result.decision == "PROMOTE"
    assert len(result.reasons) == 0

    few_trades = [make_trade(1.0)] * 10
    few = compute_metrics_from_trades(few_trades)
    result2 = evaluate_gate(few, thresholds)
    assert result2.decision == "HOLD"

    bad_trades = [make_trade(-1.0)] * 30
    bad = compute_metrics_from_trades(bad_trades)
    bad.expectancy = -0.3
    bad.profit_factor = 0.5
    result3 = evaluate_gate(bad, thresholds)
    assert result3.decision == "REJECT"
    print("[PASS] test_gate_promote_hold_reject_paths")


def test_score_calibration_monotonicity():
    signals = [
        {"source_system": "A", "strategy_id": "s1", "normalized_score": 30.0},
        {"source_system": "A", "strategy_id": "s2", "normalized_score": 60.0},
        {"source_system": "A", "strategy_id": "s3", "normalized_score": 90.0},
        {"source_system": "A", "strategy_id": "s4", "normalized_score": 15.0},
        {"source_system": "A", "strategy_id": "s5", "normalized_score": 75.0},
    ]
    results = calibrate_scores(signals, 5)
    scores = {r.strategy_id: r.calibrated_score for r in results}

    assert scores["s3"] > scores["s2"]
    assert scores["s5"] > scores["s1"]
    assert scores["s2"] > scores["s4"]
    print("[PASS] test_score_calibration_monotonicity")


def test_deterministic_outputs():
    trades = [make_trade(1.0)] * 5 + [make_trade(-1.0)] * 5
    m1 = compute_metrics_from_trades(trades[:])
    m2 = compute_metrics_from_trades(trades[:])
    assert m1.expectancy == m2.expectancy
    assert m1.profit_factor == m2.profit_factor
    assert m1.trades == m2.trades
    print("[PASS] test_deterministic_outputs")


def test_rolling_degradation_flag():
    profitable = [make_trade(1.0)] * 200
    losing = [make_trade(-0.5)] * 200
    all_trades = profitable + losing
    rolling = compute_rolling_metrics(all_trades, 90)

    is_degraded, pct = detect_degradation(rolling, 90)
    assert is_degraded
    assert pct > 0.20
    print("[PASS] test_rolling_degradation_flag")


def test_gate_all_strategies():
    thresholds = GateThresholds()
    metrics_list = []
    for src in ["A", "B"]:
        m = compute_metrics_from_trades([make_trade(1.0, source=src)] * 30)
        m.source_system = src
        m.strategy_id = f"{src}_strategy"
        m.expectancy = 0.5
        m.profit_factor = 2.0
        m.max_drawdown = 0.05
        m.sharpe = 1.0
        metrics_list.append(m)

    results = evaluate_all(metrics_list, thresholds)
    assert len(results) == 2
    assert all(r.decision == "PROMOTE" for r in results)
    print("[PASS] test_gate_all_strategies")


def main():
    test_preflight_fails_on_low_hydration()
    test_expectancy_formula_matches_reference()
    test_profit_factor_and_payoff_ratio()
    test_gate_promote_hold_reject_paths()
    test_score_calibration_monotonicity()
    test_deterministic_outputs()
    test_rolling_degradation_flag()
    test_gate_all_strategies()
    print("\n=== All Phase 4 tests passed ===")


if __name__ == "__main__":
    main()
