import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from src.integration.routed_signal import RoutedSignal


def routed_signal_to_dict(routed: RoutedSignal) -> Dict[str, Any]:
    metadata = dict(routed.signal.metadata or {})
    if routed.metadata:
        metadata.update(routed.metadata)

    signal_dict = {
        "source_system": routed.signal.source_system,
        "strategy_id": routed.signal.strategy_id,
        "ticker": routed.signal.ticker,
        "timeframe": routed.signal.timeframe,
        "signal_time": routed.signal.signal_time,
        "side": routed.signal.side,
        "entry_type": routed.signal.entry_type,
        "entry_price_ref": routed.signal.entry_price_ref,
        "stop_price": routed.signal.stop_price,
        "target_price": routed.signal.target_price,
        "raw_score": routed.signal.raw_score,
        "normalized_score": routed.signal.normalized_score,
        "confidence": routed.signal.confidence,
        "risk_unit": routed.signal.risk_unit,
        "reason_codes": routed.signal.reason_codes,
        "metadata": metadata,
    }
    signal_dict["router_decision"] = routed.router_decision
    signal_dict["router_reason"] = routed.router_reason
    signal_dict["collision_key"] = routed.collision_key
    return signal_dict


def sort_routed_signals(signals: List[RoutedSignal]) -> List[RoutedSignal]:
    return sorted(
        signals,
        key=lambda r: (
            r.collision_key,
            r.source_system,
            r.strategy_id,
        ),
    )


def export_routed_to_jsonl(signals: List[RoutedSignal], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_signals = sort_routed_signals(signals)
    with open(path, "w", encoding="utf-8") as f:
        for routed in sorted_signals:
            f.write(
                json.dumps(routed_signal_to_dict(routed), ensure_ascii=False) + "\n"
            )


def export_routed_to_csv(signals: List[RoutedSignal], path: Path) -> None:
    if not signals:
        return
    sorted_signals = sort_routed_signals(signals)
    path.parent.mkdir(parents=True, exist_ok=True)
    first = routed_signal_to_dict(sorted_signals[0])
    fieldnames = list(first.keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for routed in sorted_signals:
            writer.writerow(routed_signal_to_dict(routed))


def export_summary(summary: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def export_conflicts_report(
    dropped: List[RoutedSignal],
    blocked: List[RoutedSignal],
    path: Path,
) -> None:
    all_conflicts = dropped + blocked
    if not all_conflicts:
        return
    sorted_conflicts = sort_routed_signals(all_conflicts)
    export_routed_to_csv(sorted_conflicts, path)
