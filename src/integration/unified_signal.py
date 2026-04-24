from dataclasses import dataclass, field
from typing import Dict, Any, Literal, Optional


@dataclass
class UnifiedSignal:
    source_system: Literal["A", "B"]
    strategy_id: str
    ticker: str
    timeframe: str
    signal_time: str
    side: Literal["long", "short"]
    entry_type: Literal["next_open", "limit", "stop"]
    entry_price_ref: float
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    raw_score: float = 0.0
    normalized_score: float = 0.0
    confidence: float = 0.5
    risk_unit: Optional[float] = None
    reason_codes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_score(raw: float, lo: float = 0.0, hi: float = 100.0) -> float:
    if hi <= lo:
        return 50.0
    x = (raw - lo) / (hi - lo)
    return max(0.0, min(100.0, x * 100.0))
