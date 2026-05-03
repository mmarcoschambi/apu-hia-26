from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.integration.execution_ledger import (
    ExecutionIntent,
    FillRecord,
    OrderRecord,
    PositionRecord,
    append_jsonl,
    dataclass_to_dict,
    make_fill_id,
    make_order_id,
    make_position_id,
    write_csv,
    write_jsonl,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_ROOT = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"
STATE_FILE = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "system_state.json"

DEFAULT_SNOOZE_MINUTES = 120


@dataclass
class PortfolioState:
    date: str
    kill_switch: bool = False
    entries_paused: bool = False
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "idle"
    open_positions: list[dict[str, Any]] = field(default_factory=list)
    closed_positions: list[dict[str, Any]] = field(default_factory=list)
    pending_intents: list[dict[str, Any]] = field(default_factory=list)
    processed_callbacks: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def day_dir(date: str) -> Path:
    path = DEMO_ROOT / date
    path.mkdir(parents=True, exist_ok=True)
    return path


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now().isoformat()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_optional_float(value: Any) -> float | None:
    if value in (None, "", "nan"):
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return None


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        return pd.read_csv(path).to_dict(orient="records")
    except Exception:
        return []


def _write_records(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        if path.exists():
            path.unlink()
        return
    pd.DataFrame(rows).to_csv(path, index=False)


def load_state() -> PortfolioState:
    if not STATE_FILE.exists():
        return PortfolioState(date=_today())
    try:
        data = json.loads(STATE_FILE.read_text())
        return PortfolioState(**data)
    except Exception:
        return PortfolioState(date=_today())


def save_state(state: PortfolioState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(asdict(state), indent=2, default=str))


def _intents_path(date: str) -> Path:
    return day_dir(date) / "execution_intents.csv"


def _intents_jsonl(date: str) -> Path:
    return day_dir(date) / "execution_intents.jsonl"


def _positions_path(date: str) -> Path:
    return day_dir(date) / "positions.csv"


def _orders_path(date: str) -> Path:
    return day_dir(date) / "orders.csv"


def _fills_path(date: str) -> Path:
    return day_dir(date) / "fills.csv"


def _events_path(date: str) -> Path:
    return day_dir(date) / "telegram_events.jsonl"


def _decision_audit_path(date: str) -> Path:
    return day_dir(date) / "decision_audit.jsonl"


def _portfolio_state_path(date: str) -> Path:
    return day_dir(date) / "portfolio_state.json"


def _run_report_path(date: str) -> Path:
    return day_dir(date) / "run_report.json"


def _append_action_log(date: str, event: dict[str, Any]) -> None:
    append_jsonl(_events_path(date), event)
    append_jsonl(_decision_audit_path(date), event)


def _load_day_intents(date: str) -> list[dict[str, Any]]:
    return _load_records(_intents_path(date))


def _save_day_intents(date: str, rows: list[dict[str, Any]]) -> None:
    _write_records(_intents_path(date), rows)
    if rows:
        write_jsonl(_intents_jsonl(date), rows)
    elif _intents_jsonl(date).exists():
        _intents_jsonl(date).unlink()


def _load_day_positions(date: str) -> list[dict[str, Any]]:
    return _load_records(_positions_path(date))


def _load_day_orders(date: str) -> list[dict[str, Any]]:
    return _load_records(_orders_path(date))


def _load_day_fills(date: str) -> list[dict[str, Any]]:
    return _load_records(_fills_path(date))


def _write_day_positions(date: str, rows: list[dict[str, Any]]) -> None:
    _write_records(_positions_path(date), rows)


def _write_day_orders(date: str, rows: list[dict[str, Any]]) -> None:
    _write_records(_orders_path(date), rows)


def _write_day_fills(date: str, rows: list[dict[str, Any]]) -> None:
    _write_records(_fills_path(date), rows)


def _normalize_intent_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized.setdefault("tp1_price", normalized.get("target_price"))
    normalized.setdefault("tp2_price", normalized.get("target_price"))
    normalized.setdefault("status", "pending")
    normalized.setdefault("status_reason", None)
    normalized.setdefault("snoozed_until", None)
    normalized.setdefault("confirmed_by", None)
    normalized.setdefault("confirmed_at", None)
    normalized.setdefault("metadata", {})
    if isinstance(normalized.get("metadata"), str):
        try:
            normalized["metadata"] = json.loads(normalized["metadata"])
        except Exception:
            normalized["metadata"] = {"raw_metadata": normalized["metadata"]}
    return normalized


def load_intents(date: str) -> pd.DataFrame:
    path = _intents_path(date)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def save_intents(date: str, intents: list[ExecutionIntent]) -> None:
    rows = [dataclass_to_dict(intent) for intent in intents]
    _save_day_intents(date, rows)


def _coerce_datetime(value: Any) -> datetime | None:
    if value in (None, "", "nan"):
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def build_intents_from_signals(
    date: str, signals: pd.DataFrame, source_universe: str = "finviz"
) -> list[ExecutionIntent]:
    from src.integration.execution_ledger import intent_from_signal

    if signals.empty:
        return []

    intents: list[ExecutionIntent] = []
    for _, row in signals.iterrows():
        signal = row.to_dict()
        signal["signal_date"] = date
        signal["combo_name"] = signal.get(
            "combo", signal.get("combo_name", "finviz_demo")
        )
        signal["source_universe"] = source_universe
        signal["decision_source"] = "telegram"
        intent = intent_from_signal(
            signal,
            source_universe=source_universe,
            decision_source="telegram",
            risk_budget_usd=1000.0,
            risk_per_trade_usd=1000.0,
            signal_date=date,
        )
        intents.append(intent)
    return intents


def persist_candidates(
    date: str, signals: pd.DataFrame, source_universe: str = "finviz"
) -> list[ExecutionIntent]:
    intents = build_intents_from_signals(date, signals, source_universe=source_universe)
    new_rows = [dataclass_to_dict(intent) for intent in intents]
    existing_rows = [
        _normalize_intent_row(row) for row in _load_day_intents(date)
    ]
    existing_by_signal = {str(row.get("signal_id")): row for row in existing_rows}
    new_by_signal = {str(row.get("signal_id")): row for row in new_rows}

    merged_rows: list[dict[str, Any]] = []
    for signal_id, new_row in new_by_signal.items():
        existing = existing_by_signal.get(signal_id)
        if existing:
            merged = dict(new_row)
            merged["status"] = existing.get("status", merged.get("status", "pending"))
            merged["status_reason"] = existing.get("status_reason")
            merged["snoozed_until"] = existing.get("snoozed_until")
            merged["confirmed_by"] = existing.get("confirmed_by")
            merged["confirmed_at"] = existing.get("confirmed_at")
            merged["created_at"] = existing.get("created_at", merged.get("created_at"))
            merged_rows.append(_normalize_intent_row(merged))
        else:
            merged_rows.append(_normalize_intent_row(new_row))

    for signal_id, existing in existing_by_signal.items():
        if signal_id in new_by_signal:
            continue
        expired = dict(existing)
        if expired.get("status", "pending") == "pending":
            expired["status"] = "expired"
            expired["status_reason"] = "missing_from_latest_refresh"
        merged_rows.append(_normalize_intent_row(expired))

    _save_day_intents(date, merged_rows)
    state = load_state()
    state.date = date
    state.status = "candidates_ready" if merged_rows else "idle"
    _sync_state(date, state)
    return [ExecutionIntent(**row) for row in merged_rows]


def _mark_callback_processed(state: PortfolioState, callback_id: str) -> bool:
    if callback_id in state.processed_callbacks:
        return False
    state.processed_callbacks.append(callback_id)
    return True


def _find_intent(rows: list[dict[str, Any]], signal_id: str) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for idx, row in enumerate(rows):
        if str(row.get("signal_id")) == signal_id:
            return idx, _normalize_intent_row(row)
    return None, None


def _find_position(rows: list[dict[str, Any]], position_id: str) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for idx, row in enumerate(rows):
        if str(row.get("position_id")) == position_id:
            return idx, dict(row)
    return None, None


def _rebuild_run_report(date: str, state: PortfolioState) -> dict[str, Any]:
    positions = _load_day_positions(date)
    orders = _load_day_orders(date)
    fills = _load_day_fills(date)
    intents = [_normalize_intent_row(row) for row in _load_day_intents(date)]

    open_positions = [
        p for p in positions if not _as_bool(p.get("exited")) and p.get("status") != "closed"
    ]
    closed_positions = [
        p for p in positions if _as_bool(p.get("exited")) or p.get("status") == "closed"
    ]
    pending_intents = [
        i for i in intents if str(i.get("status", "pending")) in {"pending", "snoozed"}
    ]
    approved_intents = [i for i in intents if str(i.get("status")) == "approved"]
    rejected_intents = [i for i in intents if str(i.get("status")) == "rejected"]
    expired_intents = [i for i in intents if str(i.get("status")) == "expired"]
    snoozed_intents = [i for i in intents if str(i.get("status")) == "snoozed"]
    realized_pnl = sum(_as_optional_float(p.get("realized_pnl")) or 0.0 for p in closed_positions)

    state.open_positions = open_positions
    state.closed_positions = closed_positions
    state.pending_intents = pending_intents
    state.generated_at = _now()
    state.metrics = {
        "open_positions": len(open_positions),
        "closed_positions": len(closed_positions),
        "pending_intents": len([i for i in pending_intents if str(i.get("status")) == "pending"]),
        "snoozed_intents": len(snoozed_intents),
        "approved_intents": len(approved_intents),
        "rejected_intents": len(rejected_intents),
        "expired_intents": len(expired_intents),
        "orders": len(orders),
        "fills": len(fills),
        "realized_pnl": round(realized_pnl, 2),
        "kill_switch": state.kill_switch,
        "entries_paused": state.entries_paused,
    }
    if open_positions:
        state.status = "position_open"
    elif pending_intents:
        state.status = "candidates_ready"
    elif state.kill_switch:
        state.status = "killed"
    else:
        state.status = "idle"

    run_report = {
        "date": date,
        "generated_at": state.generated_at,
        "status": state.status,
        "kill_switch": state.kill_switch,
        "entries_paused": state.entries_paused,
        "metrics": state.metrics,
        "open_positions": len(open_positions),
        "closed_positions": len(closed_positions),
        "pending_intents": state.metrics["pending_intents"],
        "snoozed_intents": state.metrics["snoozed_intents"],
        "approved_intents": state.metrics["approved_intents"],
        "rejected_intents": state.metrics["rejected_intents"],
        "expired_intents": state.metrics["expired_intents"],
    }
    _portfolio_state_path(date).write_text(json.dumps(asdict(state), indent=2, default=str))
    _run_report_path(date).write_text(json.dumps(run_report, indent=2, default=str))
    save_state(state)
    return run_report


def _sync_state(date: str, state: PortfolioState | None = None) -> PortfolioState:
    state = state or load_state()
    state.date = date
    _rebuild_run_report(date, state)
    return state


def approve_intent(
    date: str, signal_id: str, chat_id: str, user_id: str, callback_id: str
) -> dict[str, Any]:
    state = load_state()
    if state.kill_switch or state.entries_paused:
        return {"ok": False, "reason": "entries_paused"}
    if not _mark_callback_processed(state, callback_id):
        return {"ok": True, "reason": "duplicate_ignored"}

    intents = [_normalize_intent_row(row) for row in _load_day_intents(date)]
    idx, match = _find_intent(intents, signal_id)
    if match is None or idx is None:
        return {"ok": False, "reason": "intent_not_found"}

    if str(match.get("status")) == "approved":
        _sync_state(date, state)
        return {"ok": True, "reason": "already_approved"}

    existing_positions = _load_day_positions(date)
    existing_position = next(
        (p for p in existing_positions if str(p.get("intent_id")) == str(match.get("intent_id"))),
        None,
    )
    if existing_position and not _as_bool(existing_position.get("exited")):
        match["status"] = "approved"
        match["confirmed_by"] = str(user_id)
        match["confirmed_at"] = _now()
        intents[idx] = match
        _save_day_intents(date, intents)
        _sync_state(date, state)
        return {"ok": True, "reason": "position_already_open", "position": existing_position}

    intent = ExecutionIntent(**match)
    timestamp = _now()
    order = OrderRecord(
        order_id=make_order_id(intent.intent_id),
        intent_id=intent.intent_id,
        ticker=intent.ticker,
        side="BUY",
        order_type=intent.entry_type,
        qty=intent.shares,
        price=float(intent.entry_price_ref),
        stop_price=intent.stop_price,
        target_price=intent.tp2_price or intent.target_price,
        signal_id=intent.signal_id,
        source_universe=intent.source_universe,
        decision_source=intent.decision_source,
        status="filled",
        metadata={"tp1_price": intent.tp1_price, "tp2_price": intent.tp2_price},
    )
    fill = FillRecord(
        fill_id=make_fill_id(order.order_id),
        order_id=order.order_id,
        intent_id=intent.intent_id,
        ticker=intent.ticker,
        side="BUY",
        price=float(intent.entry_price_ref),
        qty=intent.shares,
        fee=0.0,
        reason="telegram_approve",
        signal_id=intent.signal_id,
        source_universe=intent.source_universe,
        decision_source=intent.decision_source,
    )
    position = PositionRecord(
        position_id=make_position_id(intent.intent_id),
        signal_id=intent.signal_id,
        intent_id=intent.intent_id,
        ticker=intent.ticker,
        source_universe=intent.source_universe,
        strategy_id=intent.strategy_id,
        side=intent.side,
        qty=intent.shares,
        entry_price=float(intent.entry_price_ref),
        stop_price=intent.stop_price,
        tp1_price=intent.tp1_price,
        tp2_price=intent.tp2_price,
        entry_trigger="telegram_approve",
        decision_source=intent.decision_source,
        confirmed_by=str(user_id),
        confirmed_at=timestamp,
        exited=False,
        status="open",
        entry_date=date,
        metadata={"chat_id": chat_id},
    )

    orders = _load_day_orders(date)
    orders.append(asdict(order))
    _write_day_orders(date, orders)

    fills = _load_day_fills(date)
    fills.append(asdict(fill))
    _write_day_fills(date, fills)

    existing_positions.append(asdict(position))
    _write_day_positions(date, existing_positions)

    match["status"] = "approved"
    match["status_reason"] = "telegram_approve"
    match["confirmed_by"] = str(user_id)
    match["confirmed_at"] = timestamp
    intents[idx] = match
    _save_day_intents(date, intents)

    event = {
        "event_id": callback_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "action": "approve_trade",
        "payload": {"signal_id": signal_id, "intent_id": intent.intent_id},
        "status": "applied",
        "created_at": timestamp,
        "applied_at": timestamp,
    }
    _append_action_log(date, event)
    _sync_state(date, state)
    return {"ok": True, "position": asdict(position), "order": asdict(order)}


def reject_intent(
    date: str, signal_id: str, chat_id: str, user_id: str, callback_id: str
) -> dict[str, Any]:
    state = load_state()
    if not _mark_callback_processed(state, callback_id):
        return {"ok": True, "reason": "duplicate_ignored"}

    intents = [_normalize_intent_row(row) for row in _load_day_intents(date)]
    idx, match = _find_intent(intents, signal_id)
    if match is None or idx is None:
        return {"ok": False, "reason": "intent_not_found"}

    match["status"] = "rejected"
    match["status_reason"] = "telegram_reject"
    match["confirmed_by"] = str(user_id)
    match["confirmed_at"] = _now()
    intents[idx] = match
    _save_day_intents(date, intents)
    event = {
        "event_id": callback_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "action": "reject_trade",
        "payload": {"signal_id": signal_id, "intent_id": match.get("intent_id")},
        "status": "applied",
        "created_at": _now(),
        "applied_at": _now(),
    }
    _append_action_log(date, event)
    _sync_state(date, state)
    return {"ok": True}


def snooze_intent(
    date: str, signal_id: str, chat_id: str, user_id: str, callback_id: str
) -> dict[str, Any]:
    state = load_state()
    if not _mark_callback_processed(state, callback_id):
        return {"ok": True, "reason": "duplicate_ignored"}

    intents = [_normalize_intent_row(row) for row in _load_day_intents(date)]
    idx, match = _find_intent(intents, signal_id)
    if match is None or idx is None:
        return {"ok": False, "reason": "intent_not_found"}

    snoozed_until = (datetime.now() + timedelta(minutes=DEFAULT_SNOOZE_MINUTES)).isoformat()
    match["status"] = "snoozed"
    match["status_reason"] = "telegram_snooze"
    match["snoozed_until"] = snoozed_until
    match["confirmed_by"] = str(user_id)
    match["confirmed_at"] = _now()
    intents[idx] = match
    _save_day_intents(date, intents)
    event = {
        "event_id": callback_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "action": "snooze_trade",
        "payload": {
            "signal_id": signal_id,
            "intent_id": match.get("intent_id"),
            "snoozed_until": snoozed_until,
        },
        "status": "applied",
        "created_at": _now(),
        "applied_at": _now(),
    }
    _append_action_log(date, event)
    _sync_state(date, state)
    return {"ok": True, "snoozed_until": snoozed_until}


def set_kill_switch(
    enabled: bool, chat_id: str, user_id: str, callback_id: str | None = None
) -> PortfolioState:
    state = load_state()
    state.kill_switch = enabled
    state.status = "killed" if enabled else "active"
    if callback_id:
        state.processed_callbacks.append(callback_id)
        event = {
            "event_id": callback_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "action": "kill_switch",
            "payload": {"enabled": enabled},
            "status": "applied",
            "created_at": _now(),
            "applied_at": _now(),
        }
        _append_action_log(state.date, event)
    _sync_state(state.date, state)
    return state


def close_position(
    date: str,
    position_id: str,
    chat_id: str,
    user_id: str,
    callback_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    state = load_state()
    if not _mark_callback_processed(state, callback_id):
        return {"ok": True, "reason": "duplicate_ignored"}

    positions = _load_day_positions(date)
    idx, pos = _find_position(positions, position_id)
    if pos is None or idx is None:
        return {"ok": False, "reason": "position_not_found"}

    if not confirm:
        preview_event = {
            "event_id": callback_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "action": "close_position_preview",
            "payload": {"position_id": position_id},
            "status": "preview",
            "created_at": _now(),
        }
        _append_action_log(date, preview_event)
        state.status = "awaiting_close_confirm"
        _sync_state(date, state)
        return {"ok": True, "confirm_required": True, "position": pos}

    if _as_bool(pos.get("exited")) or str(pos.get("status")) == "closed":
        _sync_state(date, state)
        return {"ok": True, "reason": "already_closed", "position": pos}

    timestamp = _now()
    pos["exited"] = True
    pos["status"] = "closed"
    pos["exit_trigger"] = "telegram_close"
    pos["exit_date"] = date
    pos["exit_price"] = pos.get("entry_price")
    pos["realized_pnl"] = 0.0
    pos["confirmed_by"] = str(user_id)
    pos["confirmed_at"] = timestamp
    positions[idx] = pos
    _write_day_positions(date, positions)

    orders = _load_day_orders(date)
    close_order = OrderRecord(
        order_id=make_order_id(str(pos.get("intent_id")), side="SELL"),
        intent_id=str(pos.get("intent_id")),
        ticker=str(pos.get("ticker")),
        side="SELL",
        order_type="market",
        qty=int(float(pos.get("qty", 0) or 0)),
        price=float(pos.get("entry_price", 0) or 0),
        stop_price=_as_optional_float(pos.get("stop_price")),
        target_price=_as_optional_float(pos.get("tp2_price")),
        signal_id=str(pos.get("signal_id")),
        source_universe=str(pos.get("source_universe")),
        decision_source="telegram",
        status="filled",
    )
    orders.append(asdict(close_order))
    _write_day_orders(date, orders)

    fills = _load_day_fills(date)
    close_fill = FillRecord(
        fill_id=make_fill_id(close_order.order_id, suffix="close"),
        order_id=close_order.order_id,
        intent_id=str(pos.get("intent_id")),
        ticker=str(pos.get("ticker")),
        side="SELL",
        price=float(pos.get("entry_price", 0) or 0),
        qty=int(float(pos.get("qty", 0) or 0)),
        fee=0.0,
        reason="telegram_close",
        signal_id=str(pos.get("signal_id")),
        source_universe=str(pos.get("source_universe")),
        decision_source="telegram",
    )
    fills.append(asdict(close_fill))
    _write_day_fills(date, fills)

    event = {
        "event_id": callback_id,
        "chat_id": chat_id,
        "user_id": user_id,
        "action": "close_position",
        "payload": {"position_id": position_id, "intent_id": pos.get("intent_id")},
        "status": "applied",
        "created_at": timestamp,
        "applied_at": timestamp,
    }
    _append_action_log(date, event)
    _sync_state(date, state)
    return {"ok": True, "position": pos}
