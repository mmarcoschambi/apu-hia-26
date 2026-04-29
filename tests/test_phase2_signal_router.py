#!/usr/bin/env python3
"""Tests for Phase 2 Signal Router."""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.conflict_policy import (
    resolve_opposite_side,
    resolve_same_side,
)
from src.integration.signal_router import (
    SignalRouter,
    make_collision_key,
)
from src.integration.unified_signal import UnifiedSignal


def create_signal(
    ticker="AAPL",
    side="long",
    score=75.0,
    source="A",
    strategy_id="test_strategy",
    timeframe="1D",
    signal_time="2026-04-22T00:00:00",
):
    return UnifiedSignal(
        source_system=source,
        strategy_id=strategy_id,
        ticker=ticker,
        timeframe=timeframe,
        signal_time=signal_time,
        side=side,
        entry_type="next_open",
        entry_price_ref=150.0,
        raw_score=score,
        normalized_score=score,
        confidence=0.5,
    )


def test_same_side_higher_score_wins():
    signals = [
        create_signal(ticker="AAPL", score=80.0, source="A"),
        create_signal(ticker="AAPL", score=60.0, source="B"),
    ]
    decisions = resolve_same_side(signals)
    assert decisions[0].decision == "accepted"
    assert decisions[0].reason == "won_by_score"
    assert decisions[1].decision == "dropped"
    assert decisions[1].reason == "dropped_by_score"
    print("[PASS] test_same_side_higher_score_wins")


def test_same_side_tie_prioritizes_A():
    signals = [
        create_signal(ticker="AAPL", score=75.0, source="B"),
        create_signal(ticker="AAPL", score=75.0, source="A"),
    ]
    decisions = resolve_same_side(signals)
    a_decision = next(d for d, s in zip(decisions, signals) if s.source_system == "A")
    b_decision = next(d for d, s in zip(decisions, signals) if s.source_system == "B")
    assert a_decision.decision == "accepted"
    assert b_decision.decision == "dropped"
    assert b_decision.reason == "tie_stability_A"
    print("[PASS] test_same_side_tie_prioritizes_A")


def test_opposite_side_delta_above_threshold_resolves():
    signals = [
        create_signal(ticker="AAPL", score=80.0, source="A", side="long"),
        create_signal(ticker="AAPL", score=40.0, source="B", side="short"),
    ]
    decisions = resolve_opposite_side(signals)
    long_decision = next(d for d, s in zip(decisions, signals) if s.side == "long")
    short_decision = next(d for d, s in zip(decisions, signals) if s.side == "short")
    assert long_decision.decision == "accepted"
    assert long_decision.reason == "opposite_resolved"
    assert short_decision.decision == "dropped"
    print("[PASS] test_opposite_side_delta_above_threshold_resolves")


def test_opposite_side_delta_below_threshold_blocks_both():
    signals = [
        create_signal(ticker="AAPL", score=65.0, source="A", side="long"),
        create_signal(ticker="AAPL", score=55.0, source="B", side="short"),
    ]
    decisions = resolve_opposite_side(signals)
    assert all(d.decision == "blocked" for d in decisions)
    assert all(d.reason == "opposite_balanced" for d in decisions)
    print("[PASS] test_opposite_side_delta_below_threshold_blocks_both")


def test_cooldown_blocks_followup_signals_same_session():
    router = SignalRouter(cooldown_enabled=True)
    signals = [
        create_signal(ticker="AAPL", score=65.0, source="A", side="long"),
        create_signal(ticker="AAPL", score=55.0, source="B", side="short"),
    ]
    accepted, dropped, blocked = router.route_signals(signals)
    assert len(blocked) == 2
    assert any(r.router_reason == "opposite_balanced" for r in blocked)
    ticker = signals[0].ticker
    assert router.is_in_cooldown(ticker)
    second_signals = [
        create_signal(ticker="AAPL", score=90.0, source="A", side="long"),
    ]
    accepted2, dropped2, blocked2 = router.route_signals(second_signals)
    assert all(r.router_reason == "cooldown" for r in blocked2)
    print("[PASS] test_cooldown_blocks_followup_signals_same_session")


def test_collision_key_respects_timeframe_bucket():
    s1 = create_signal(ticker="AAPL", timeframe="1D")
    s2 = create_signal(ticker="AAPL", timeframe="15m")
    s3 = create_signal(ticker="AAPL", timeframe="1h")
    key1 = make_collision_key(s1)
    key2 = make_collision_key(s2)
    key3 = make_collision_key(s3)
    assert key1 == "AAPL_2026-04-22_daily"
    assert key2 == "AAPL_2026-04-22_intraday"
    assert key3 == "AAPL_2026-04-22_intraday"
    print("[PASS] test_collision_key_respects_timeframe_bucket")


def test_router_output_deterministic_order():
    router = SignalRouter()
    signals = [
        create_signal(ticker="A", score=75.0, source="A"),
        create_signal(ticker="B", score=65.0, source="B"),
        create_signal(ticker="A", score=80.0, source="B"),
    ]
    accepted, _, _ = router.route_signals(signals)
    with tempfile.TemporaryDirectory() as tmpdir:
        from src.integration.router_exporter import export_routed_to_jsonl

        path = Path(tmpdir) / "test.jsonl"
        export_routed_to_jsonl(accepted, path)
        content1 = path.read_text()
        accepted2, _, _ = router.route_signals(signals[:])
        export_routed_to_jsonl(accepted2, path)
        content2 = path.read_text()
    assert content1 == content2
    print("[PASS] test_router_output_deterministic_order")


def test_router_summary_counts_consistent_with_outputs():
    router = SignalRouter()
    signals = [
        create_signal(ticker="A", score=80.0, source="A"),
        create_signal(ticker="A", score=60.0, source="B"),
        create_signal(ticker="B", score=50.0, source="A"),
    ]
    accepted, dropped, blocked = router.route_signals(signals)
    summary = router.get_summary(accepted, dropped, blocked)
    assert summary["total_input"] == 3
    assert summary["accepted"] == 2
    assert summary["dropped"] == 1
    print("[PASS] test_router_summary_counts_consistent_with_outputs")


def main():
    test_same_side_higher_score_wins()
    test_same_side_tie_prioritizes_A()
    test_opposite_side_delta_above_threshold_resolves()
    test_opposite_side_delta_below_threshold_blocks_both()
    test_cooldown_blocks_followup_signals_same_session()
    test_collision_key_respects_timeframe_bucket()
    test_router_output_deterministic_order()
    test_router_summary_counts_consistent_with_outputs()
    print("\n=== All Phase 2 tests passed ===")


if __name__ == "__main__":
    main()
