from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.paper.demo_portfolio import load_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MONITOR_ROOT = PROJECT_ROOT / "outputs" / "telegram_monitor"
DEMO_ROOT = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"


def _dated_dirs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted([p for p in base.iterdir() if p.is_dir()], key=lambda p: p.name)


def latest_date(base: Path) -> str | None:
    dirs = _dated_dirs(base)
    return dirs[-1].name if dirs else None


def resolve_monitor_date(date: str | None = None) -> str | None:
    return date or latest_date(MONITOR_ROOT)


def resolve_demo_date(date: str | None = None) -> str | None:
    if date:
        return date
    state = load_state()
    if state.date:
        return state.date
    return latest_date(DEMO_ROOT)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def load_monitor_snapshot(date: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    resolved = resolve_monitor_date(date)
    if not resolved:
        return None, None
    payload = _load_json(MONITOR_ROOT / resolved / "market_status.json")
    return resolved, payload


def load_prealerts(date: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    resolved = resolve_monitor_date(date)
    if not resolved:
        return None, []
    payload = _load_json(MONITOR_ROOT / resolved / "prealerts.json") or {}
    return resolved, list(payload.get("signals", []))


def load_demo_context(date: str | None = None) -> tuple[str | None, dict[str, Any]]:
    resolved = resolve_demo_date(date)
    if not resolved:
        return None, {}
    day_dir = DEMO_ROOT / resolved
    return resolved, {
        "portfolio_state": _load_json(day_dir / "portfolio_state.json") or {},
        "run_report": _load_json(day_dir / "run_report.json") or {},
        "positions": _load_csv(day_dir / "positions.csv"),
        "intents": _load_csv(day_dir / "execution_intents.csv"),
        "orders": _load_csv(day_dir / "orders.csv"),
        "fills": _load_csv(day_dir / "fills.csv"),
    }


def build_market_message(date: str | None = None) -> str:
    resolved, snapshot = load_monitor_snapshot(date)
    state = load_state()
    if not resolved or not snapshot:
        return "⚠️ <b>MARKET</b>\nNo monitor data available yet."

    warnings = snapshot.get("finviz_warnings") or []
    signals = snapshot.get("signals") or []
    top = signals[:5]
    
    status_icon = "🟢" if snapshot.get('regime_ok') else "🔴"
    
    lines = [
        f"🌐 <b>MARKET OVERVIEW | {resolved}</b>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"{status_icon} <b>Regime Status:</b> {'<b>OK</b>' if snapshot.get('regime_ok') else '<b>BLOCKED</b>'}",
        f"📊 Universe Size: <code>{snapshot.get('universe_size', 0)}</code>",
        f"🛰 Monitor Signals: <code>{len(signals)}</code>",
        f"🛑 Demo Kill Switch: <code>{'ON' if state.kill_switch else 'OFF'}</code>",
    ]
    if warnings:
        lines.append("\n⚠️ <b>Warnings:</b>")
        for warning in warnings[:3]:
            lines.append(f"• {warning}")
    if top:
        lines.append("\n🔥 <b>Top Candidates:</b>")
        lines.append("<pre>")
        lines.append(f"{'Ticker':<7} {'Combo':<12} {'Entry':<8} {'Stop'}")
        lines.append(f"{'-'*7} {'-'*12} {'-'*8} {'-'*6}")
        for signal in top:
            ticker = signal.get('ticker', '?')
            combo = signal.get('combo', signal.get('combo_name', 'n/a'))[:12]
            entry = float(signal.get('entry_price', 0) or 0)
            stop = float(signal.get('stop_loss', signal.get('stop_price', 0)) or 0)
            lines.append(f"{ticker:<7} {combo:<12} {entry:<8.2f} {stop:.2f}")
        lines.append("</pre>")
    return "\n".join(lines)


def build_watchlist_message(date: str | None = None, limit: int = 10) -> str:
    resolved, signals = load_prealerts(date)
    if not resolved:
        return "⚠️ <b>WATCHLIST</b>\nNo prealerts available yet."
        
    lines = [
        f"📋 <b>WATCHLIST | {resolved}</b>", 
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"🔍 Candidates: <code>{len(signals)}</code>"
    ]
    
    if not signals:
        lines.append("\nNo watchlist candidates yet.")
        return "\n".join(lines)
        
    lines.append("\n<pre>")
    lines.append(f"{'Ticker':<7} {'Combo':<12} {'Entry':<8} {'Stop'}")
    lines.append(f"{'-'*7} {'-'*12} {'-'*8} {'-'*6}")
    for signal in signals[:limit]:
        ticker = signal.get('ticker', '?')
        combo = signal.get('combo', signal.get('combo_name', 'n/a'))[:12]
        entry = float(signal.get('entry_price', 0) or 0)
        stop = float(signal.get('stop_loss', signal.get('stop_price', 0)) or 0)
        lines.append(f"{ticker:<7} {combo:<12} {entry:<8.2f} {stop:.2f}")
    lines.append("</pre>")
    return "\n".join(lines)


def build_monitor_signals_message(date: str | None = None, limit: int = 5) -> str:
    resolved, signals = load_prealerts(date)
    if not resolved:
        return "⚠️ <b>SIGNALS</b>\nNo monitor signals available yet."
        
    lines = [
        f"🛰 <b>MONITOR SIGNALS | {resolved}</b>", 
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"📡 Candidates: <code>{len(signals)}</code>"
    ]
    
    if not signals:
        lines.append("\nNo monitor candidates available.")
        return "\n".join(lines)
        
    lines.append("\n<pre>")
    lines.append(f"{'Ticker':<7} {'Combo':<12} {'Entry':<8} {'Stop'}")
    lines.append(f"{'-'*7} {'-'*12} {'-'*8} {'-'*6}")
    for signal in signals[:limit]:
        ticker = signal.get('ticker', '?')
        combo = signal.get('combo', signal.get('combo_name', 'n/a'))[:12]
        entry = float(signal.get('entry_price', 0) or 0)
        stop = float(signal.get('stop_loss', signal.get('stop_price', 0)) or 0)
        lines.append(f"{ticker:<7} {combo:<12} {entry:<8.2f} {stop:.2f}")
    lines.append("</pre>")
    return "\n".join(lines)


def build_signals_message(date: str | None = None, limit: int = 5) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>SIGNALS</b>\nNo demo candidates available yet."
    intents = ctx.get("intents", pd.DataFrame())
    if intents.empty:
        return f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>\nNo demo candidates available."
    pending = intents[intents["status"].astype(str).isin(["pending", "snoozed"])].copy()
    if pending.empty:
        return f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>\nNo pending demo candidates."

    lines = [
        f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>", 
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"⏱ Pending: <code>{len(pending)}</code>"
    ]
    
    lines.append("\n<pre>")
    lines.append(f"{'Ticker':<7} {'Status':<8} {'Entry':<8} {'Stop'}")
    lines.append(f"{'-'*7} {'-'*8} {'-'*8} {'-'*6}")
    for _, row in pending.head(limit).iterrows():
        ticker = row['ticker']
        status = row.get('status', 'pending')[:8]
        entry = float(row.get('entry_price_ref', 0) or 0)
        stop = float(row.get('stop_price', 0) or 0)
        lines.append(f"{ticker:<7} {status:<8} {entry:<8.2f} {stop:.2f}")
    lines.append("</pre>")
    return "\n".join(lines)


def build_portfolio_message(date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>PORTFOLIO</b>\nNo demo portfolio state available yet."
    state = ctx.get("portfolio_state") or {}
    metrics = state.get("metrics") or {}
    positions = ctx.get("positions", pd.DataFrame())
    open_positions = positions[positions["status"].astype(str) == "open"] if not positions.empty else pd.DataFrame()

    pnl = float(metrics.get('realized_pnl', 0) or 0)
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    
    lines = [
        f"💼 <b>PORTFOLIO STATUS | {resolved}</b>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"🔹 Status: <code>{state.get('status', 'idle')}</code>",
        f"🛑 Kill switch: <code>{'ON' if state.get('kill_switch') else 'OFF'}</code>",
        f"⏸ Entries paused: <code>{'ON' if state.get('entries_paused') else 'OFF'}</code>\n",
        f"📂 Open: <code>{metrics.get('open_positions', 0)}</code> | "
        f"🔒 Closed: <code>{metrics.get('closed_positions', 0)}</code>",
        f"⏱ Pending: <code>{metrics.get('pending_intents', 0)}</code> | "
        f"💤 Snoozed: <code>{metrics.get('snoozed_intents', 0)}</code>",
        f"{pnl_icon} Realized PnL: <b>${pnl:.2f}</b>",
    ]
    if not open_positions.empty:
        lines.append("\n📈 <b>Open Positions:</b>")
        lines.append("<pre>")
        lines.append(f"{'Ticker':<7} {'Qty':<4} {'Entry':<8} {'Stop'}")
        lines.append(f"{'-'*7} {'-'*4} {'-'*8} {'-'*6}")
        for _, row in open_positions.head(5).iterrows():
            ticker = row['ticker']
            qty = int(float(row.get('qty', 0) or 0))
            entry = float(row.get('entry_price', 0) or 0)
            stop = float(row.get('stop_price', 0) or 0)
            lines.append(f"{ticker:<7} {qty:<4} {entry:<8.2f} {stop:.2f}")
        lines.append("</pre>")
    return "\n".join(lines)


def build_position_message(ticker: str, date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return f"⚠️ <b>POSITION</b>\nNo portfolio data for <code>{ticker}</code>."
    positions = ctx.get("positions", pd.DataFrame())
    if positions.empty:
        return f"⚠️ <b>POSITION | {resolved}</b>\nNo positions for <code>{ticker}</code>."
    mask = positions["ticker"].astype(str).str.upper() == ticker.upper()
    if not mask.any():
        return f"⚠️ <b>POSITION | {resolved}</b>\nNo positions for <code>{ticker}</code>."
    row = positions[mask].iloc[0]
    
    status_icon = "🟢" if row.get('status', '') == 'open' else "🔒"
    
    lines = [
        f"📊 <b>POSITION DETAILS | {resolved}</b>",
        f"Ticker: <b>{row['ticker']}</b>",
        f"Status: {status_icon} <code>{row.get('status', 'unknown')}</code>",
        f"Qty: <code>{int(float(row.get('qty', 0) or 0))}</code>\n",
        f"Entry: <code>{float(row.get('entry_price', 0) or 0):.2f}</code>",
        f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>",
        f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code>",
        f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>\n",
        f"Entry trigger: <code>{row.get('entry_trigger', 'n/a')}</code>",
        f"Exit trigger: <code>{row.get('exit_trigger', 'n/a')}</code>",
        f"Confirmed by: <code>{row.get('confirmed_by', 'n/a')}</code>",
    ]
    return "\n".join(lines)


def build_paper_run_message(date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>PAPER RUN</b>\nNo demo run available yet."
    report = ctx.get("run_report") or {}
    metrics = report.get("metrics") or {}
    
    pnl = float(metrics.get('realized_pnl', 0) or 0)
    pnl_icon = "🟢" if pnl >= 0 else "🔴"
    
    lines = [
        f"📝 <b>PAPER RUN REPORT | {resolved}</b>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"🔹 Status: <code>{report.get('status', 'idle')}</code>",
        f"✅ Approved intents: <code>{report.get('approved_intents', 0)}</code>",
        f"❌ Rejected intents: <code>{report.get('rejected_intents', 0)}</code>",
        f"💤 Snoozed intents: <code>{report.get('snoozed_intents', 0)}</code>\n",
        f"📂 Open positions: <code>{report.get('open_positions', 0)}</code>",
        f"🔒 Closed positions: <code>{report.get('closed_positions', 0)}</code>",
        f"🛒 Orders: <code>{metrics.get('orders', 0)}</code> | 🔄 Fills: <code>{metrics.get('fills', 0)}</code>",
        f"{pnl_icon} Realized PnL: <b>${pnl:.2f}</b>",
    ]
    return "\n".join(lines)


def build_signal_cards(date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return []
    intents = ctx.get("intents", pd.DataFrame())
    if intents.empty:
        return []
    pending = intents[intents["status"].astype(str).isin(["pending", "snoozed"])].copy()
    cards: list[dict[str, Any]] = []
    for _, row in pending.head(limit).iterrows():
        signal_id = str(row["signal_id"])
        text = (
            f"🎯 <b>{row['ticker']}</b> | {row['strategy_id']}\n"
            f"Entry: <code>{float(row.get('entry_price_ref', 0) or 0):.2f}</code>\n"
            f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>\n"
            f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code> | "
            f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>\n"
            f"Status: <code>{row.get('status', 'pending')}</code>"
        )
        cards.append(
            {
                "text": text,
                "buttons": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve_trade:{signal_id}"},
                        {"text": "❌ Reject", "callback_data": f"reject_trade:{signal_id}"},
                    ],
                    [
                        {"text": "💤 Snooze", "callback_data": f"snooze_trade:{signal_id}"},
                        {"text": "🔄 Refresh", "callback_data": "refresh:signals"},
                    ],
                ],
            }
        )
    return cards


def build_position_cards(date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return []
    positions = ctx.get("positions", pd.DataFrame())
    if positions.empty:
        return []
    open_positions = positions[positions["status"].astype(str) == "open"].copy()
    cards: list[dict[str, Any]] = []
    for _, row in open_positions.head(limit).iterrows():
        position_id = str(row["position_id"])
        text = (
            f"📈 <b>{row['ticker']}</b>\n"
            f"Qty: <code>{int(float(row.get('qty', 0) or 0))}</code>\n"
            f"Entry: <code>{float(row.get('entry_price', 0) or 0):.2f}</code>\n"
            f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>\n"
            f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code> | "
            f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>"
        )
        cards.append(
            {
                "text": text,
                "buttons": [
                    [
                        {"text": "🔒 Close", "callback_data": f"close_position:{position_id}"},
                        {"text": "🔄 Refresh", "callback_data": "refresh:portfolio"},
                    ]
                ],
            }
        )
    return cards
