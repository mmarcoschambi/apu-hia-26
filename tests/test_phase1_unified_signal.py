#!/usr/bin/env python3
"""Tests for Phase 1 Unified Signal contract and adapters."""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.unified_signal import UnifiedSignal, normalize_score
from src.integration.signal_adapter_a import adapt_signal_a, adapt_batch_a
from src.integration.signal_adapter_b import adapt_signal_b
from src.integration.signal_exporter import export_to_jsonl, signal_to_dict


def sort_signals(signals: list[UnifiedSignal]) -> list[UnifiedSignal]:
    return sorted(
        signals,
        key=lambda s: (s.signal_time, s.ticker, s.source_system, s.strategy_id),
    )


def test_unified_signal_schema_required_fields():
    signal = UnifiedSignal(
        source_system="A",
        strategy_id="test_strategy",
        ticker="AAPL",
        timeframe="1D",
        signal_time="2026-04-22T00:00:00",
        side="long",
        entry_type="next_open",
        entry_price_ref=150.0,
        raw_score=75.0,
        normalized_score=75.0,
        confidence=0.8,
        reason_codes="filter1|filter2",
    )
    d = signal_to_dict(signal)
    assert d["source_system"] == "A"
    assert d["strategy_id"] == "test_strategy"
    assert d["ticker"] == "AAPL"
    assert d["timeframe"] == "1D"
    assert d["signal_time"] == "2026-04-22T00:00:00"
    assert d["side"] == "long"
    assert d["entry_type"] == "next_open"
    assert d["entry_price_ref"] == 150.0
    assert d["raw_score"] == 75.0
    assert d["normalized_score"] == 75.0
    assert d["confidence"] == 0.8
    assert d["reason_codes"] == "filter1|filter2"
    print("[PASS] test_unified_signal_schema_required_fields")


def test_adapter_a_maps_all_required_fields():
    row = {
        "combo": "combo_pure_momentum",
        "ticker": "aapl",
        "signal_date": "2026-04-22",
        "signal_price": 150.0,
        "entry_score": 85.0,
        "stop_price": 140.0,
        "tp1": 165.0,
        "risk_$": 1000.0,
    }
    signal = adapt_signal_a(row)
    assert signal.source_system == "A"
    assert signal.strategy_id == "combo_pure_momentum"
    assert signal.ticker == "AAPL"
    assert signal.signal_time == "2026-04-22"
    assert signal.entry_price_ref == 150.0
    assert signal.stop_price == 140.0
    assert signal.target_price == 165.0
    assert signal.raw_score == 85.0
    assert signal.normalized_score == 85.0
    assert signal.risk_unit == 1000.0
    print("[PASS] test_adapter_a_maps_all_required_fields")


def test_adapter_b_maps_all_required_fields():
    row = {
        "preset_id": "preset_06",
        "ticker": "msft",
        "signal_date": "2026-04-22",
        "entry_price_ref": 300.0,
        "reason_codes": "rs_1m_percentile_min",
    }
    preset_lookup = {"preset_06": 0.75}
    signal = adapt_signal_b(row, preset_lookup)
    assert signal.source_system == "B"
    assert signal.strategy_id == "preset_06"
    assert signal.ticker == "MSFT"
    assert signal.signal_time == "2026-04-22T00:00:00"
    assert signal.entry_price_ref == 300.0
    assert signal.raw_score == 0.75
    assert signal.normalized_score == 87.5
    print("[PASS] test_adapter_b_maps_all_required_fields")


def test_score_normalization_clamps_out_of_range():
    assert normalize_score(110.0, 0.0, 100.0) == 100.0
    assert normalize_score(-10.0, 0.0, 100.0) == 0.0
    assert normalize_score(50.0, 0.0, 100.0) == 50.0
    assert normalize_score(50.0, 0.0, 0.0) == 50.0
    assert normalize_score(50.0, 20.0, 80.0) == 50.0
    assert normalize_score(20.0, 20.0, 80.0) == 0.0
    assert normalize_score(80.0, 20.0, 80.0) == 100.0
    print("[PASS] test_score_normalization_clamps_out_of_range")


def test_adapter_a_alternate_field_names():
    row = {
        "combo_name": "combo_breakout",
        "ticker": "nvda",
        "signal_time": "2026-04-22T10:00:00",
        "score": 90.0,
        "signal_price": 800.0,
    }
    signal = adapt_signal_a(row)
    assert signal.strategy_id == "combo_breakout"
    assert signal.ticker == "NVDA"
    assert signal.raw_score == 90.0
    print("[PASS] test_adapter_a_alternate_field_names")


def test_adapter_b_with_missing_preset_score():
    row = {
        "preset_id": "preset_unknown",
        "ticker": "tsla",
        "signal_date": "2026-04-22",
        "entry_price_ref": 200.0,
    }
    preset_lookup = {}
    signal = adapt_signal_b(row, preset_lookup)
    assert signal.raw_score == 0.0
    assert signal.normalized_score == 50.0
    print("[PASS] test_adapter_b_with_missing_preset_score")


def test_export_is_deterministic_same_input_same_output():
    rows = [
        {
            "combo": "combo_a",
            "ticker": "a",
            "signal_date": "2026-04-22",
            "signal_price": 100.0,
            "entry_score": 80.0,
        },
        {
            "combo": "combo_b",
            "ticker": "b",
            "signal_date": "2026-04-21",
            "signal_price": 50.0,
            "entry_score": 70.0,
        },
    ]
    signals, _ = adapt_batch_a(rows)
    sorted_signals = sort_signals(signals)

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "signals.jsonl"
        export_to_jsonl(sorted_signals, jsonl_path)

        content1 = jsonl_path.read_text()

        signals2, _ = adapt_batch_a(rows[:])
        sorted_signals2 = sort_signals(signals2)
        export_to_jsonl(sorted_signals2, jsonl_path)

        content2 = jsonl_path.read_text()

    assert content1 == content2
    print("[PASS] test_export_is_deterministic_same_input_same_output")


def test_reason_codes_preserved():
    row = {
        "combo": "test_combo",
        "ticker": "test",
        "signal_date": "2026-04-22",
        "signal_price": 100.0,
        "entry_score": 50.0,
        "reason_codes": "filter_a|filter_b|filter_c",
    }
    signal = adapt_signal_a(row)
    assert signal.reason_codes == "filter_a|filter_b|filter_c"
    d = signal_to_dict(signal)
    assert d["reason_codes"] == "filter_a|filter_b|filter_c"
    print("[PASS] test_reason_codes_preserved")


def test_adapter_batch_handles_missing_fields():
    rows = [
        {
            "combo": "combo_good",
            "ticker": "good",
            "signal_date": "2026-04-22",
            "signal_price": 100.0,
            "entry_score": 80.0,
        },
        {},
    ]
    signals, discarded = adapt_batch_a(rows)
    assert len(signals) == 1
    assert signals[0].ticker == "GOOD"
    assert len(discarded) == 1
    print("[PASS] test_adapter_batch_handles_missing_fields")


def main():
    test_unified_signal_schema_required_fields()
    test_adapter_a_maps_all_required_fields()
    test_adapter_b_maps_all_required_fields()
    test_score_normalization_clamps_out_of_range()
    test_adapter_a_alternate_field_names()
    test_adapter_b_with_missing_preset_score()
    test_export_is_deterministic_same_input_same_output()
    test_reason_codes_preserved()
    test_adapter_batch_handles_missing_fields()
    print("\n=== All Phase 1 tests passed ===")


if __name__ == "__main__":
    main()
