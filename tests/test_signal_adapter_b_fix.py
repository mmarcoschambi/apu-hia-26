"""Tests unitarios para signal_adapter_b.py (Fix Temporal + Fix Riesgo).

Cubre los dos fixes del B-Adapter:
  - FIX 1: signal_time usa execution_date, no la fecha del backtest.
  - FIX 2: stop_price y target_price nunca son None ni <= 0.
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.integration.signal_adapter_b import (
    DEFAULT_STOP_PCT,
    DEFAULT_TARGET_PCT,
    SignalValidationError,
    adapt_batch_b,
    adapt_signal_b,
    _inject_risk,
    _resolve_execution_date,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_ROW = {
    "preset_id": "preset_06",
    "ticker": "NVDA",
    "signal_date": "2024-03-13",
    "entry_price_ref": 100.0,
    "stop_price": None,
    "target_price": None,
    "confidence": 0.6,
    "reason_codes": "momentum",
}

SCORE_LOOKUP = {"preset_06": 0.75, "preset_07": 0.60}


# ---------------------------------------------------------------------------
# FIX 1 - Alineacion Temporal
# ---------------------------------------------------------------------------
class TestResolveExecutionDate:
    def test_none_returns_today(self):
        result = _resolve_execution_date(None)
        assert result == date.today().isoformat()

    def test_string_passthrough(self):
        assert _resolve_execution_date("2026-04-24") == "2026-04-24"

    def test_string_truncates_to_date(self):
        assert _resolve_execution_date("2026-04-24T09:30:00") == "2026-04-24"

    def test_date_object(self):
        assert _resolve_execution_date(date(2026, 4, 24)) == "2026-04-24"

    def test_datetime_object(self):
        assert _resolve_execution_date(datetime(2026, 4, 24, 9, 30)) == "2026-04-24"


class TestSignalTimeFix:
    def test_signal_time_uses_execution_date_not_backtest_date(self):
        """La fecha del backtest (2024) NO debe aparecer en signal_time."""
        sig = adapt_signal_b(
            VALID_ROW,
            SCORE_LOOKUP,
            execution_date="2026-04-24",
        )
        assert sig.signal_time.startswith("2026-04-24"), (
            f"signal_time deberia ser 2026-04-24, obtenido: {sig.signal_time}"
        )
        assert "2024" not in sig.signal_time

    def test_original_date_preserved_in_metadata(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP, execution_date="2026-04-24")
        assert sig.metadata["original_signal_date"] == "2024-03-13"
        assert sig.metadata["date_aligned"] is True

    def test_no_execution_date_uses_today(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP)
        assert sig.signal_time.startswith(date.today().isoformat())

    def test_same_date_date_aligned_false(self):
        row = {**VALID_ROW, "signal_date": date.today().isoformat()}
        sig = adapt_signal_b(row, SCORE_LOOKUP)
        assert sig.metadata["date_aligned"] is False


# ---------------------------------------------------------------------------
# FIX 2 - Inyeccion de Riesgo
# ---------------------------------------------------------------------------
class TestInjectRisk:
    def test_pct_fallback_no_atr_no_preset(self):
        stop, target = _inject_risk(100.0, None, None, None, 0.05, 0.15)
        assert stop == pytest.approx(95.0)
        assert target == pytest.approx(115.0)

    def test_atr_takes_priority_over_pct(self):
        stop, target = _inject_risk(100.0, None, None, atr=2.0, stop_pct=0.05, target_pct=0.15)
        assert stop == pytest.approx(97.0)   # 100 - 1.5*2
        assert target == pytest.approx(106.0)  # 100 + 3*2

    def test_preset_value_takes_priority(self):
        stop, target = _inject_risk(100.0, 90.0, 120.0, atr=2.0, stop_pct=0.05, target_pct=0.15)
        assert stop == pytest.approx(90.0)
        assert target == pytest.approx(120.0)

    def test_zero_entry_returns_passthrough(self):
        stop, target = _inject_risk(0.0, None, None, None, 0.05, 0.15)
        assert stop == 0.0
        assert target == 0.0


class TestStopTargetNeverNone:
    def test_stop_price_not_none_without_preset(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP, execution_date="2026-04-24")
        assert sig.stop_price is not None
        assert sig.stop_price > 0

    def test_target_price_not_none_without_preset(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP, execution_date="2026-04-24")
        assert sig.target_price is not None
        assert sig.target_price > 0

    def test_stop_source_pct_fallback_in_metadata(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP)
        assert sig.metadata["stop_source"] == "pct_fallback"

    def test_stop_source_atr_when_atr_present(self):
        row = {**VALID_ROW, "atr": 3.0}
        sig = adapt_signal_b(row, SCORE_LOOKUP)
        assert sig.metadata["stop_source"] == "atr"
        assert sig.metadata["atr_used"] == pytest.approx(3.0)

    def test_stop_source_preset_when_stop_defined(self):
        row = {**VALID_ROW, "stop_price": 92.0, "target_price": 115.0}
        sig = adapt_signal_b(row, SCORE_LOOKUP)
        assert sig.metadata["stop_source"] == "preset"
        assert sig.stop_price == pytest.approx(92.0)
        assert sig.target_price == pytest.approx(115.0)

    def test_custom_pct_respected(self):
        sig = adapt_signal_b(VALID_ROW, SCORE_LOOKUP, stop_pct=0.08, target_pct=0.20)
        assert sig.stop_price == pytest.approx(100.0 * 0.92)
        assert sig.target_price == pytest.approx(100.0 * 1.20)


# ---------------------------------------------------------------------------
# Validacion y batch
# ---------------------------------------------------------------------------
class TestValidation:
    def test_missing_preset_id_raises(self):
        row = {k: v for k, v in VALID_ROW.items() if k != "preset_id"}
        with pytest.raises(SignalValidationError, match="preset_id"):
            adapt_signal_b(row, SCORE_LOOKUP)

    def test_invalid_ticker_raises(self):
        row = {**VALID_ROW, "ticker": "nan"}
        with pytest.raises(SignalValidationError, match="ticker"):
            adapt_signal_b(row, SCORE_LOOKUP)


class TestBatchAdapter:
    def test_batch_returns_correct_counts(self):
        rows = [
            VALID_ROW,
            {**VALID_ROW, "preset_id": "preset_07"},
            {"preset_id": "", "ticker": "AAPL", "signal_date": "2024-01-01"},  # invalido
        ]
        signals, discarded = adapt_batch_b(rows, SCORE_LOOKUP, execution_date="2026-04-24")
        assert len(signals) == 2
        assert len(discarded) == 1

    def test_batch_all_signals_use_execution_date(self):
        rows = [VALID_ROW, {**VALID_ROW, "preset_id": "preset_07"}]
        signals, _ = adapt_batch_b(rows, SCORE_LOOKUP, execution_date="2026-04-24")
        for s in signals:
            assert s.signal_time.startswith("2026-04-24")

    def test_batch_all_signals_have_stop(self):
        rows = [VALID_ROW, {**VALID_ROW, "preset_id": "preset_07"}]
        signals, _ = adapt_batch_b(rows, SCORE_LOOKUP, execution_date="2026-04-24")
        for s in signals:
            assert s.stop_price is not None and s.stop_price > 0
