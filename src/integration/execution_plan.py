from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, Any


@dataclass
class ExecutionPlanRow:
    source_system: Literal["A", "B"]
    strategy_id: str
    ticker: str
    trade_date: str
    side: Literal["long", "short"]
    entry_type: Literal["next_open", "limit", "stop"]
    entry_price_ref: float
    hydrated_price_source: Literal["input", "close_signal_date"]
    stop_price: Optional[float]
    target_price: Optional[float]
    risk_budget_usd: float
    risk_per_trade_usd: float
    per_share_risk: float
    shares: int
    notional_usd: float
    router_reason: str
    collision_key: str
    metadata: Dict[str, Any] = field(default_factory=dict)
