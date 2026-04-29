#!/usr/bin/env python3
"""Fase 2 CLI: Signal Router - Deduplication and Conflict Resolution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.router_exporter import (
    export_conflicts_report,
    export_routed_to_csv,
    export_routed_to_jsonl,
    export_summary,
)
from src.integration.signal_router import SignalRouter


def load_unified_signals(input_path: Path) -> list:
    signals = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                signals.append(json.loads(line))
    return signals


def dict_to_signal(d: dict):

    from src.integration.unified_signal import UnifiedSignal

    return UnifiedSignal(
        source_system=d["source_system"],
        strategy_id=d["strategy_id"],
        ticker=d["ticker"],
        timeframe=d["timeframe"],
        signal_time=d["signal_time"],
        side=d["side"],
        entry_type=d["entry_type"],
        entry_price_ref=d["entry_price_ref"],
        stop_price=d.get("stop_price"),
        target_price=d.get("target_price"),
        raw_score=d.get("raw_score", 0.0),
        normalized_score=d.get("normalized_score", 0.0),
        confidence=d.get("confidence", 0.5),
        risk_unit=d.get("risk_unit"),
        reason_codes=d.get("reason_codes", ""),
        metadata=d.get("metadata", {}),
    )


def main():
    parser = argparse.ArgumentParser(description="Signal Router Phase 2")
    parser.add_argument("--input", required=True, help="Path to unified signals JSONL")
    parser.add_argument("--out", required=True, help="Output base path")
    parser.add_argument(
        "--no-cooldown",
        action="store_true",
        help="Disable cooldown enforcement",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_base = Path(args.out)
    cooldown_enabled = not args.no_cooldown

    raw_signals = load_unified_signals(input_path)
    signals = [dict_to_signal(d) for d in raw_signals]

    router = SignalRouter(cooldown_enabled=cooldown_enabled)
    accepted, dropped, blocked = router.route_signals(signals)

    accepted_jsonl = output_base.with_suffix(".jsonl")
    accepted_csv = output_base.with_name(
        output_base.stem.replace("accepted", "accepted") + ".csv"
    )
    if output_base.stem == "router_output":
        accepted_jsonl = output_base.parent / "router_accepted.jsonl"
        accepted_csv = output_base.parent / "router_accepted.csv"

    dropped_csv = output_base.parent / "router_dropped.csv"
    blocked_csv = output_base.parent / "router_blocked.csv"
    conflicts_csv = output_base.parent / "router_conflicts.csv"
    summary_json = output_base.parent / "router_summary.json"

    export_routed_to_jsonl(accepted, accepted_jsonl)
    export_routed_to_csv(accepted, accepted_csv)
    export_routed_to_csv(dropped, dropped_csv)
    export_routed_to_csv(blocked, blocked_csv)
    export_conflicts_report(dropped, blocked, conflicts_csv)

    summary = router.get_summary(accepted, dropped, blocked)
    export_summary(summary, summary_json)

    print("=== Phase 2 Router Report ===")
    print(f"Input signals: {summary['total_input']}")
    print(f"Accepted: {summary['accepted']}")
    print(f"Dropped: {summary['dropped']}")
    print(f"Blocked: {summary['blocked']}")
    print(f"  - Dropped by score: {summary['dropped_by_score']}")
    print(f"  - Dropped opposite resolved: {summary['dropped_opposite_resolved']}")
    print(f"  - Blocked opposite balanced: {summary['blocked_opposite_balanced']}")
    print(f"  - Blocked cooldown: {summary['blocked_cooldown']}")
    print("\nOutputs:")
    print(f"  Accepted JSONL: {accepted_jsonl}")
    print(f"  Accepted CSV: {accepted_csv}")
    print(f"  Dropped CSV: {dropped_csv}")
    print(f"  Blocked CSV: {blocked_csv}")
    print(f"  Conflicts CSV: {conflicts_csv}")
    print(f"  Summary JSON: {summary_json}")


if __name__ == "__main__":
    main()
