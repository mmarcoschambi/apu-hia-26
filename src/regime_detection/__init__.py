"""
Baseline regime detection package.

Provides a simple heuristic baseline, forward label generation,
walk-forward backtesting, and summary metrics.
"""

from src.regime_detection.baseline_rules import (
    BaselineThresholds,
    classify_regime_baseline,
)
from src.regime_detection.labels_generator import (
    LABEL_GREEN,
    LABEL_RED,
    LABEL_YELLOW,
    generate_forward_labels,
)
from src.regime_detection.backtest_engine import (
    BacktestConfig,
    WalkForwardBacktestResult,
    WalkForwardRegimeBacktester,
)
from src.regime_detection.metrics_reporter import (
    compare_baseline_to_buy_and_hold,
    generate_metrics_report,
)

__all__ = [
    "BaselineThresholds",
    "classify_regime_baseline",
    "LABEL_GREEN",
    "LABEL_RED",
    "LABEL_YELLOW",
    "generate_forward_labels",
    "BacktestConfig",
    "WalkForwardBacktestResult",
    "WalkForwardRegimeBacktester",
    "compare_baseline_to_buy_and_hold",
    "generate_metrics_report",
]
