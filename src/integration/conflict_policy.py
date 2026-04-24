from dataclasses import dataclass
from typing import Literal

from src.integration.unified_signal import UnifiedSignal


OPPOSITE_RESOLUTION_THRESHOLD = 20


@dataclass
class ConflictDecision:
    decision: Literal["accepted", "dropped", "blocked"]
    reason: Literal[
        "won_by_score",
        "tie_stability_A",
        "dropped_by_score",
        "opposite_resolved",
        "opposite_balanced",
        "cooldown",
    ]


def resolve_same_side(signals: list[UnifiedSignal]) -> list[ConflictDecision]:
    if len(signals) <= 1:
        return [ConflictDecision(decision="accepted", reason="won_by_score")]

    a_signals = [s for s in signals if s.source_system == "A"]
    b_signals = [s for s in signals if s.source_system == "B"]

    a_max = max((s.normalized_score for s in a_signals), default=float("-inf"))
    b_max = max((s.normalized_score for s in b_signals), default=float("-inf"))

    if a_signals and b_signals:
        if a_max > b_max:
            winner_source = "A"
        elif b_max > a_max:
            winner_source = "B"
        else:
            winner_source = "A"
    elif a_signals:
        winner_source = "A"
    else:
        winner_source = "B"

    is_tie = bool(a_signals and b_signals and a_max == b_max)

    decisions = []
    for signal in signals:
        if signal.source_system == winner_source:
            decisions.append(
                ConflictDecision(decision="accepted", reason="won_by_score")
            )
        else:
            if is_tie:
                decisions.append(
                    ConflictDecision(decision="dropped", reason="tie_stability_A")
                )
            else:
                decisions.append(
                    ConflictDecision(decision="dropped", reason="dropped_by_score")
                )

    return decisions


def resolve_opposite_side(
    signals: list[UnifiedSignal],
) -> list[ConflictDecision]:
    if len(signals) <= 1:
        return [ConflictDecision(decision="accepted", reason="won_by_score")]

    a_signals = [s for s in signals if s.source_system == "A"]
    b_signals = [s for s in signals if s.source_system == "B"]

    if not a_signals or not b_signals:
        return resolve_same_side(signals)

    avg_a = sum(s.normalized_score for s in a_signals) / len(a_signals)
    avg_b = sum(s.normalized_score for s in b_signals) / len(b_signals)

    delta = abs(avg_a - avg_b)

    if delta >= OPPOSITE_RESOLUTION_THRESHOLD:
        winner_signals = a_signals if avg_a > avg_b else b_signals
        decisions = []
        for s in signals:
            if s in winner_signals:
                decisions.append(
                    ConflictDecision(decision="accepted", reason="opposite_resolved")
                )
            else:
                decisions.append(
                    ConflictDecision(decision="dropped", reason="opposite_resolved")
                )
        return decisions
    else:
        return [
            ConflictDecision(decision="blocked", reason="opposite_balanced")
            for _ in signals
        ]
