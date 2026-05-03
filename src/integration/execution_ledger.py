from __future__ import annotations

import csv
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Optional


def _now() -> str:
    return datetime.now().isoformat()


def _stable_hash(payload: str) -> str:
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if is_dataclass(value):
            cleaned[key] = asdict(value)
        elif isinstance(value, Path):
            cleaned[key] = str(value)
        else:
            cleaned[key] = value
    return cleaned


def dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    if is_dataclass(obj):
        return _clean_payload(asdict(obj))
    if isinstance(obj, dict):
        return _clean_payload(obj)
    raise TypeError(f"Unsupported object type: {type(obj)!r}")


def write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dataclass_to_dict(row), ensure_ascii=False) + "\n")


def append_jsonl(path: Path, row: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(dataclass_to_dict(row), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: Iterable[Any]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    dict_rows = [dataclass_to_dict(r) for r in rows]
    fieldnames = list(dict_rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dict_rows)


@dataclass
class SignalSnapshot:
    date: str
    source_universe: str
    universe_size: int
    regime: Dict[str, Any] = field(default_factory=dict)
    signals_count: int = 0
    generated_at: str = field(default_factory=_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionIntent:
    intent_id: str
    signal_id: str
    source_universe: str
    ticker: str
    strategy_id: str
    signal_date: str
    side: Literal["long", "short"]
    entry_type: Literal["next_open", "limit", "stop"]
    entry_price_ref: float
    stop_price: Optional[float]
    target_price: Optional[float]
    risk_budget_usd: float
    risk_per_trade_usd: float
    per_share_risk: float
    shares: int
    notional_usd: float
    decision_source: str
    tp1_price: Optional[float] = None
    tp2_price: Optional[float] = None
    status: str = "pending"
    status_reason: Optional[str] = None
    snoozed_until: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    created_at: str = field(default_factory=_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TelegramActionEvent:
    event_id: str
    chat_id: str
    user_id: str
    action: str
    payload: Dict[str, Any]
    status: str = "received"
    created_at: str = field(default_factory=_now)
    applied_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderRecord:
    order_id: str
    intent_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    order_type: str
    qty: int
    price: float
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    signal_id: Optional[str] = None
    source_universe: Optional[str] = None
    decision_source: Optional[str] = None
    status: str = "created"
    created_at: str = field(default_factory=_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FillRecord:
    fill_id: str
    order_id: str
    intent_id: str
    ticker: str
    side: Literal["BUY", "SELL"]
    price: float
    qty: int
    fee: float = 0.0
    timestamp: str = field(default_factory=_now)
    reason: Optional[str] = None
    signal_id: Optional[str] = None
    source_universe: Optional[str] = None
    decision_source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionRecord:
    position_id: str
    signal_id: str
    intent_id: str
    ticker: str
    source_universe: str
    strategy_id: str
    side: Literal["long", "short"]
    qty: int
    entry_price: float
    stop_price: Optional[float]
    tp1_price: Optional[float]
    tp2_price: Optional[float]
    entry_trigger: str
    exit_trigger: Optional[str] = None
    decision_source: str = "system"
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    exited: bool = False
    exit_price: Optional[float] = None
    exit_fee: Optional[float] = None
    realized_pnl: Optional[float] = None
    entry_date: Optional[str] = None
    exit_date: Optional[str] = None
    status: str = "open"
    created_at: str = field(default_factory=_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


def make_signal_id(
    source_universe: str, ticker: str, strategy_id: str, signal_date: str
) -> str:
    return f"sig_{_stable_hash('|'.join([source_universe, ticker, strategy_id, signal_date]))}"


def make_intent_id(
    signal_id: str, entry_price_ref: float, stop_price: Optional[float], shares: int
) -> str:
    payload = f"{signal_id}|{entry_price_ref:.6f}|{stop_price if stop_price is not None else 'na'}|{shares}"
    return f"intent_{_stable_hash(payload)}"


def make_order_id(intent_id: str, side: str = "BUY") -> str:
    return f"ord_{_stable_hash(f'{intent_id}|{side}')}"


def make_fill_id(order_id: str, suffix: str = "fill") -> str:
    return f"{suffix}_{_stable_hash(order_id)}"


def make_position_id(intent_id: str) -> str:
    return f"pos_{_stable_hash(intent_id)}"


class ExecutionBackend(ABC):
    @abstractmethod
    def preview_order(self, intent: ExecutionIntent) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, intent: ExecutionIntent) -> OrderRecord:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def sync_positions(self) -> list[PositionRecord]:
        raise NotImplementedError

    @abstractmethod
    def sync_fills(self) -> list[FillRecord]:
        raise NotImplementedError


class PaperBackend(ExecutionBackend):
    def __init__(self) -> None:
        self.orders: list[OrderRecord] = []
        self.fills: list[FillRecord] = []
        self.positions: list[PositionRecord] = []

    def preview_order(self, intent: ExecutionIntent) -> Dict[str, Any]:
        return {
            "intent_id": intent.intent_id,
            "ticker": intent.ticker,
            "shares": intent.shares,
        }

    def submit_order(self, intent: ExecutionIntent) -> OrderRecord:
        order = OrderRecord(
            order_id=make_order_id(intent.intent_id),
            intent_id=intent.intent_id,
            ticker=intent.ticker,
            side="BUY",
            order_type=intent.entry_type,
            qty=intent.shares,
            price=float(intent.entry_price_ref),
            stop_price=intent.stop_price,
            target_price=intent.target_price,
            status="filled",
        )
        self.orders.append(order)
        return order

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {"order_id": order_id, "status": "cancelled"}

    def sync_positions(self) -> list[PositionRecord]:
        return self.positions

    def sync_fills(self) -> list[FillRecord]:
        return self.fills


class BrokerBackend(ExecutionBackend):
    def preview_order(self, intent: ExecutionIntent) -> Dict[str, Any]:
        return {"status": "stub", "intent_id": intent.intent_id}

    def submit_order(self, intent: ExecutionIntent) -> OrderRecord:
        raise NotImplementedError("Broker backend not connected yet")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        return {"order_id": order_id, "status": "stub"}

    def sync_positions(self) -> list[PositionRecord]:
        return []

    def sync_fills(self) -> list[FillRecord]:
        return []


def intent_from_signal(
    signal: Dict[str, Any],
    *,
    source_universe: str,
    decision_source: str,
    risk_budget_usd: float,
    risk_per_trade_usd: float,
    side: str = "long",
    entry_type: str = "next_open",
    signal_date: Optional[str] = None,
) -> ExecutionIntent:
    ticker = str(signal.get("ticker", "UNKNOWN")).upper()
    strategy_id = str(
        signal.get("combo_name")
        or signal.get("agent_name")
        or signal.get("mode")
        or "unknown"
    )
    signal_date = signal_date or str(
        signal.get("signal_date") or signal.get("date") or ""
    )
    entry_price_ref = float(signal.get("entry_price", signal.get("close", 0.0)) or 0.0)
    stop_price = signal.get("stop_loss")
    if stop_price is None:
        stop_price = signal.get("stop_price")
    stop_price = float(stop_price) if stop_price not in (None, "", "nan") else None
    raw_tp1_price = signal.get("tp1_price", signal.get("tp1"))
    tp1_price = (
        float(raw_tp1_price) if raw_tp1_price not in (None, "", "nan") else None
    )
    raw_tp2_price = signal.get("tp2_price", signal.get("tp2"))
    tp2_price = (
        float(raw_tp2_price) if raw_tp2_price not in (None, "", "nan") else None
    )
    target_price = signal.get("target_price")
    target_price = (
        float(target_price) if target_price not in (None, "", "nan") else None
    )
    if target_price is None:
        target_price = tp2_price or tp1_price
    if tp1_price is None:
        tp1_price = target_price
    if tp2_price is None:
        tp2_price = target_price
    per_share_risk = (
        abs(entry_price_ref - stop_price) if stop_price is not None else 0.0
    )
    shares = int(
        signal.get("position_size") or signal.get("shares") or signal.get("size") or 0
    )
    notional_usd = float(entry_price_ref * shares)
    signal_id = make_signal_id(source_universe, ticker, strategy_id, signal_date)
    intent_id = make_intent_id(signal_id, entry_price_ref, stop_price, shares)
    metadata = dict(signal)
    metadata["source_universe"] = source_universe
    metadata["decision_source"] = decision_source
    return ExecutionIntent(
        intent_id=intent_id,
        signal_id=signal_id,
        source_universe=source_universe,
        ticker=ticker,
        strategy_id=strategy_id,
        signal_date=signal_date,
        side=side,
        entry_type=entry_type,  # type: ignore[arg-type]
        entry_price_ref=entry_price_ref,
        stop_price=stop_price,
        target_price=target_price,
        risk_budget_usd=risk_budget_usd,
        risk_per_trade_usd=risk_per_trade_usd,
        per_share_risk=per_share_risk,
        shares=shares,
        notional_usd=notional_usd,
        decision_source=decision_source,
        tp1_price=tp1_price,
        tp2_price=tp2_price,
        metadata=metadata,
    )
