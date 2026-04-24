from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.router_exporter import export_routed_to_jsonl
from src.integration.routed_signal import RoutedSignal
from src.integration.unified_signal import UnifiedSignal


def test_export_routed_to_jsonl_preserves_signal_metadata(tmp_path):
    signal = UnifiedSignal(
        source_system="B",
        strategy_id="preset_06",
        ticker="NVDA",
        timeframe="1D",
        signal_time="2024-03-13T00:00:00",
        side="long",
        entry_type="next_open",
        entry_price_ref=89.620849,
        stop_price=85.13980655,
        target_price=103.06397635,
        raw_score=0.0,
        normalized_score=50.0,
        confidence=0.5,
        risk_unit=None,
        reason_codes="rs_1m_percentile_min|trend_base",
        metadata={
            "historical_plan": True,
            "price_origin": "trades_csv",
            "price_validation_mode": "historical_fill",
        },
    )
    routed = RoutedSignal(
        signal=signal,
        router_decision="accepted",
        router_reason="won_by_score",
        collision_key="NVDA_2024-03-13_daily",
        metadata={"router_exported": True},
    )

    output_path = tmp_path / "routed.jsonl"
    export_routed_to_jsonl([routed], output_path)

    exported = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert exported["metadata"]["historical_plan"] is True
    assert exported["metadata"]["price_origin"] == "trades_csv"
    assert exported["metadata"]["price_validation_mode"] == "historical_fill"
    assert exported["metadata"]["router_exported"] is True