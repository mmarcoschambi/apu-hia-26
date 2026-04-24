from dataclasses import dataclass, field
from typing import Dict, Any, Literal

from src.integration.unified_signal import UnifiedSignal


@dataclass
class RoutedSignal:
    signal: UnifiedSignal
    router_decision: Literal["accepted", "dropped", "blocked"]
    router_reason: Literal[
        "won_by_score",
        "tie_stability_A",
        "dropped_by_score",
        "opposite_resolved",
        "opposite_balanced",
        "cooldown",
    ]
    collision_key: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ticker(self) -> str:
        return self.signal.ticker

    @property
    def normalized_score(self) -> float:
        return self.signal.normalized_score

    @property
    def side(self) -> str:
        return self.signal.side

    @property
    def source_system(self) -> str:
        return self.signal.source_system

    @property
    def strategy_id(self) -> str:
        return self.signal.strategy_id
