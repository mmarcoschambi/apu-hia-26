import csv
import json
from pathlib import Path

from src.integration.unified_signal import UnifiedSignal


def signal_to_dict(signal: UnifiedSignal) -> dict:
    return {
        "source_system": signal.source_system,
        "strategy_id": signal.strategy_id,
        "ticker": signal.ticker,
        "timeframe": signal.timeframe,
        "signal_time": signal.signal_time,
        "side": signal.side,
        "entry_type": signal.entry_type,
        "entry_price_ref": signal.entry_price_ref,
        "stop_price": signal.stop_price,
        "target_price": signal.target_price,
        "raw_score": signal.raw_score,
        "normalized_score": signal.normalized_score,
        "confidence": signal.confidence,
        "risk_unit": signal.risk_unit,
        "reason_codes": signal.reason_codes,
        "metadata": signal.metadata,
    }


def export_to_jsonl(signals: list[UnifiedSignal], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for signal in signals:
            f.write(json.dumps(signal_to_dict(signal), ensure_ascii=False) + "\n")


def export_to_csv(signals: list[UnifiedSignal], output_path: Path) -> None:
    if not signals:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(signal_to_dict(signals[0]).keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for signal in signals:
            writer.writerow(signal_to_dict(signal))


def sort_signals(signals: list[UnifiedSignal]) -> list[UnifiedSignal]:
    return sorted(
        signals,
        key=lambda s: (s.signal_time, s.ticker, s.source_system, s.strategy_id),
    )
