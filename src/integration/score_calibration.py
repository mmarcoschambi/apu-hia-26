import math
from dataclasses import dataclass
from typing import Optional

from src.integration.edge_analytics import EdgeMetrics


@dataclass
class CalibratedScore:
    source_system: str
    strategy_id: str
    normalized_score: float
    calibrated_score: float
    percentile: float
    window_size: int


def compute_percentile(value: float, values: list[float]) -> float:
    if not values:
        return 50.0
    sorted_vals = sorted(values)
    below = sum(1 for v in sorted_vals if v < value)
    return (below / len(sorted_vals)) * 100.0


def calibrate_scores(
    signals: list[dict],
    window: int = 252,
) -> list[CalibratedScore]:
    results = []

    by_source: dict[str, list[float]] = {}
    for sig in signals:
        src = sig.get("source_system", "")
        score = sig.get("normalized_score", 0.0)
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(score)

    by_source_result: dict[str, list[CalibratedScore]] = {src: [] for src in by_source}

    for src, scores in by_source.items():
        sorted_scores = sorted(scores)
        if len(sorted_scores) < window:
            window_size = len(sorted_scores)
            window_scores = sorted_scores
        else:
            window_size = window
            window_scores = sorted_scores[-window:]

        for sig in signals:
            if sig.get("source_system") != src:
                continue
            score = sig.get("normalized_score", 0.0)
            percentile = compute_percentile(score, window_scores)
            calibrated = max(0.0, min(100.0, percentile))

            result = CalibratedScore(
                source_system=src,
                strategy_id=sig.get("strategy_id", ""),
                normalized_score=score,
                calibrated_score=calibrated,
                percentile=percentile,
                window_size=window_size,
            )
            by_source_result[src].append(result)

    for results_list in by_source_result.values():
        results.extend(results_list)

    return results


def detect_degradation(
    rolling_metrics: list[EdgeMetrics],
    degradation_window: int = 90,
) -> tuple[bool, float]:
    if len(rolling_metrics) < degradation_window * 2:
        return False, 0.0

    first_half = rolling_metrics[:degradation_window]
    second_half = rolling_metrics[degradation_window:]

    avg_exp_first = sum(m.expectancy for m in first_half) / len(first_half)
    avg_exp_second = sum(m.expectancy for m in second_half) / len(second_half)

    pct_drop = (
        (avg_exp_first - avg_exp_second) / abs(avg_exp_first)
        if avg_exp_first != 0
        else 0.0
    )

    is_degraded = pct_drop > 0.20
    return is_degraded, pct_drop
