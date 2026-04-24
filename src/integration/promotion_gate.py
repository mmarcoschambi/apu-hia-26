import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.integration.edge_analytics import EdgeMetrics


PromotionDecision = Literal["PROMOTE", "HOLD", "REJECT"]


@dataclass
class GateThresholds:
    min_trades: int = 30
    min_expectancy: float = 0.0
    min_profit_factor: float = 1.20
    max_drawdown: float = 0.15
    min_sharpe: float = 0.80


@dataclass
class PromotionResult:
    strategy_id: str
    source_system: str
    decision: PromotionDecision
    reasons: list = field(default_factory=list)


def load_thresholds(config_path: Path) -> GateThresholds:
    with open(config_path, "r") as f:
        data = json.load(f)
    return GateThresholds(
        min_trades=data.get("min_trades", 30),
        min_expectancy=data.get("min_expectancy", 0.0),
        min_profit_factor=data.get("min_profit_factor", 1.20),
        max_drawdown=data.get("max_drawdown", 0.15),
        min_sharpe=data.get("min_sharpe", 0.80),
    )


def evaluate_gate(metrics: EdgeMetrics, thresholds: GateThresholds) -> PromotionResult:
    reasons = []

    if metrics.trades < thresholds.min_trades:
        reasons.append(
            f"insufficient_trades: {metrics.trades} < {thresholds.min_trades}"
        )

    if metrics.expectancy <= thresholds.min_expectancy:
        reasons.append(
            f"expectancy: {metrics.expectancy:.4f} <= {thresholds.min_expectancy}"
        )

    if metrics.profit_factor < thresholds.min_profit_factor:
        reasons.append(
            f"profit_factor: {metrics.profit_factor:.4f} < {thresholds.min_profit_factor}"
        )

    if metrics.max_drawdown > thresholds.max_drawdown:
        reasons.append(
            f"max_drawdown: {metrics.max_drawdown:.4f} > {thresholds.max_drawdown}"
        )

    if metrics.sharpe < thresholds.min_sharpe:
        reasons.append(f"sharpe: {metrics.sharpe:.4f} < {thresholds.min_sharpe}")

    if not reasons:
        decision: PromotionDecision = "PROMOTE"
    elif metrics.trades < thresholds.min_trades:
        decision = "HOLD"
    else:
        decision = "REJECT"

    return PromotionResult(
        strategy_id=metrics.strategy_id,
        source_system=metrics.source_system,
        decision=decision,
        reasons=reasons,
    )


def evaluate_all(
    all_metrics: list[EdgeMetrics], thresholds: GateThresholds
) -> list[PromotionResult]:
    return [evaluate_gate(m, thresholds) for m in all_metrics]
