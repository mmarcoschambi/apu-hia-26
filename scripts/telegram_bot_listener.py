#!/usr/bin/env python3
"""
telegram_bot_listener.py - Listener persistente para un bot / dos chats.

Chat monitor: solo lectura.
Chat demo: callbacks y eventos demo separados.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.execution_ledger import TelegramActionEvent, append_jsonl
from src.paper.demo_portfolio import (
    approve_intent,
    close_position,
    load_state,
    reject_intent,
    set_kill_switch,
    snooze_intent,
)
from src.paper.telegram_views import (
    build_market_message,
    build_monitor_signals_message,
    build_paper_run_message,
    build_portfolio_message,
    build_position_cards,
    build_position_message,
    build_signal_cards,
    build_signals_message,
    build_watchlist_message,
    build_watchlist_detail,
)
from src.paper.telegram_views import load_monitor_snapshot
from src.utils.telegram_client import (
    answer_callback,
    edit_message,
    get_updates,
    send_message_with_buttons,
)

EVENTS_DIR = PROJECT_ROOT / "outputs" / "telegram_events"
STATE_DIR = PROJECT_ROOT / "outputs" / "telegram_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

REFRESH_BUTTONS = {
    "market": [
        [
            {"text": "🔄 Refresh", "callback_data": "refresh:market"},
            {"text": "⚡ Regen All", "callback_data": "regenerate:market"},
        ]
    ],
    "signals": [
        [
            {"text": "🔄 Refresh", "callback_data": "refresh:signals"},
            {"text": "🧪 Shadow Audit", "callback_data": "shadow_audit:signals"},
        ]
    ],
    "watchlist": [
        [
            {"text": "🔄 Refresh", "callback_data": "refresh:watchlist"},
            {"text": "🧪 Shadow Audit", "callback_data": "shadow_audit:watchlist"},
        ]
    ],
    "portfolio": [[{"text": "🔄 Refresh", "callback_data": "refresh:portfolio"}]],
    "paper_run": [
        [
            {"text": "🔄 Refresh", "callback_data": "refresh:paper_run"},
            {"text": "🧪 Shadow Audit", "callback_data": "shadow_audit:paper_run"},
        ]
    ],
}

load_dotenv()


def _load_offset() -> int:
    path = STATE_DIR / "updates_offset.json"
    if not path.exists():
        return 0
    try:
        return int(json.loads(path.read_text()).get("offset", 0))
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    (STATE_DIR / "updates_offset.json").write_text(json.dumps({"offset": offset}, indent=2))


def _is_monitor_chat(chat_id: str) -> bool:
    return chat_id == os.getenv("TELEGRAM_CHAT_ID_MONITOR")


def _is_demo_chat(chat_id: str) -> bool:
    return chat_id == os.getenv("TELEGRAM_CHAT_ID_DEMO")


def _is_shared_chat(chat_id: str) -> bool:
    monitor_id = os.getenv("TELEGRAM_CHAT_ID_MONITOR")
    demo_id = os.getenv("TELEGRAM_CHAT_ID_DEMO")
    return bool(chat_id and monitor_id and demo_id and monitor_id == demo_id == chat_id)


def _is_live_chat(chat_id: str) -> bool:
    return chat_id == os.getenv("TELEGRAM_CHAT_ID_LIVE")


def _get_system_for_chat(chat_id: str) -> str | None:
    # Resuelve qué sistema filtrar según el chat ID.
    chat_id = str(chat_id)
    chat_live = os.getenv("TELEGRAM_CHAT_ID_LIVE")
    chat_sys_b = os.getenv("TELEGRAM_CHAT_ID_SYSTEM_B")
    chat_monitor = os.getenv("TELEGRAM_CHAT_ID_MONITOR")
    chat_demo = os.getenv("TELEGRAM_CHAT_ID_DEMO")
    chat_sys_a = os.getenv("TELEGRAM_CHAT_ID")

    if chat_live and chat_id == chat_live:
        return "B"
    if chat_sys_b and chat_id == chat_sys_b:
        return "B"
    if chat_monitor and chat_id == chat_monitor:
        return "A"
    if chat_demo and chat_id == chat_demo:
        return "A"
    if chat_sys_a and chat_id == chat_sys_a:
        return "A"
    return None


def _log_action(
    chat_id: str, user_id: str, action: str, payload: dict, status: str = "received"
) -> None:
    event = TelegramActionEvent(
        event_id=f"evt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        chat_id=str(chat_id),
        user_id=str(user_id),
        action=action,
        payload=payload,
        status=status,
        metadata={"listener": "telegram_bot_listener"},
    )
    append_jsonl(EVENTS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl", event)


def _command_args(text: str) -> tuple[str, str]:
    parts = text.split(maxsplit=1)
    command = parts[0].lstrip("/").lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    return command, arg


def _is_ticker(val: str) -> bool:
    if not val:
        return False
    val = val.strip().upper()
    if "-" in val:
        return False
    if val.isdigit():
        return False
    return 1 <= len(val) <= 6


def _send_view(chat_id: str, view: str, arg: str = "", interactive: bool = False) -> None:
    if view == "market":
        msg_text, msg_buttons = build_market_message(arg or None)
        send_message_with_buttons(
            msg_text,
            buttons=msg_buttons if msg_buttons else REFRESH_BUTTONS["market"],
            chat_id=chat_id,
        )
        return
    if view == "watchlist":
        if arg and _is_ticker(arg):
            msg_text = build_watchlist_detail(arg)
            buttons = [
                [
                    {"text": "🔄 Refresh", "callback_data": f"watchlist_detail:{arg.upper()}"},
                    {"text": "📋 Watchlist", "callback_data": "watchlist_page:1"},
                ]
            ]
            send_message_with_buttons(msg_text, buttons=buttons, chat_id=chat_id)
            return

        # Resolve page and date
        page = 1
        date_str = None
        if arg:
            if "-" in arg:
                date_str = arg
            elif arg.isdigit():
                page = int(arg)

        system = _get_system_for_chat(chat_id)
        msg_text, msg_buttons = build_watchlist_message(date=date_str, page=page, system=system)
        send_message_with_buttons(
            msg_text,
            buttons=msg_buttons if msg_buttons else REFRESH_BUTTONS["watchlist"],
            chat_id=chat_id,
        )
        return
    if view == "signals":
        send_message_with_buttons(
            build_signals_message(arg or None),
            buttons=REFRESH_BUTTONS["signals"],
            chat_id=chat_id,
        )
        if interactive:
            for card in build_signal_cards(arg or None):
                send_message_with_buttons(card["text"], card["buttons"], chat_id=chat_id)
        return
    if view == "portfolio":
        send_message_with_buttons(
            build_portfolio_message(arg or None),
            buttons=REFRESH_BUTTONS["portfolio"],
            chat_id=chat_id,
        )
        if interactive:
            for card in build_position_cards(arg or None):
                send_message_with_buttons(card["text"], card["buttons"], chat_id=chat_id)
        return
    if view == "paper_run":
        send_message_with_buttons(
            build_paper_run_message(arg or None),
            buttons=REFRESH_BUTTONS["paper_run"],
            chat_id=chat_id,
        )
        return


def _handle_message(update: dict) -> None:
    message = update.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    text = (message.get("text") or "").strip()
    user_id = str((message.get("from") or {}).get("id", ""))
    if not text.startswith("/"):
        return

    command, arg = _command_args(text)
    _log_action(chat_id, user_id, command, {"text": text, "arg": arg}, status="received")

    if command not in {
        "signals",
        "market",
        "watchlist",
        "portfolio",
        "position",
        "paper_run",
        "kill_switch",
    }:
        return

    shared_chat = _is_shared_chat(chat_id)
    monitor_chat = _is_monitor_chat(chat_id)
    demo_chat = _is_demo_chat(chat_id)
    live_chat = _is_live_chat(chat_id)

    if not (monitor_chat or demo_chat or shared_chat or live_chat):
        return

    if (monitor_chat or live_chat) and not shared_chat:
        if command == "signals":
            send_message_with_buttons(
                build_monitor_signals_message(arg or None),
                buttons=REFRESH_BUTTONS["signals"],
                chat_id=chat_id,
            )
            return
        if command == "position":
            if not arg:
                send_message_with_buttons(
                    "📊 <b>POSITION</b>\nUsage: <code>/position TICKER</code>",
                    buttons=REFRESH_BUTTONS["portfolio"],
                    chat_id=chat_id,
                )
                return
            send_message_with_buttons(
                build_position_message(arg),
                buttons=REFRESH_BUTTONS["portfolio"],
                chat_id=chat_id,
            )
            return
        if command == "kill_switch":
            send_message_with_buttons(
                "🛑 <b>KILL SWITCH</b>\nRead-only in monitor chat.",
                buttons=REFRESH_BUTTONS["portfolio"],
                chat_id=chat_id,
            )
            return
        _send_view(chat_id, command, arg, interactive=False)
        return

    if demo_chat or shared_chat:
        if command == "kill_switch":
            if not arg:
                state = load_state()
                send_message_with_buttons(
                    f"🛑 <b>Demo Kill Switch</b>\nCurrent state: <code>{'ON' if state.kill_switch else 'OFF'}</code>",
                    buttons=REFRESH_BUTTONS["portfolio"],
                    chat_id=chat_id,
                )
                return
            enabled = arg.lower() in {"on", "1", "true", "enable", "enabled"}
            set_kill_switch(enabled, chat_id, user_id)
            _log_action(chat_id, user_id, "kill_switch", {"state": arg}, status="applied")
            send_message_with_buttons(
                f"🛑 <b>Demo Kill Switch</b> -> <code>{'ON' if enabled else 'OFF'}</code>",
                buttons=REFRESH_BUTTONS["portfolio"],
                chat_id=chat_id,
            )
            return
        if command == "position" and not arg:
            send_message_with_buttons(
                "📊 <b>POSITION</b>\nUsage: <code>/position TICKER</code>",
                buttons=REFRESH_BUTTONS["portfolio"],
                chat_id=chat_id,
            )
            return
        if command == "position":
            send_message_with_buttons(
                build_position_message(arg),
                buttons=REFRESH_BUTTONS["portfolio"],
                chat_id=chat_id,
            )
            return
        if command == "watchlist":
            _send_view(chat_id, command, arg, interactive=False)
            return
        if command == "market":
            msg_text, msg_buttons = build_market_message(arg or None)
            send_message_with_buttons(
                msg_text,
                buttons=msg_buttons if msg_buttons else REFRESH_BUTTONS["market"],
                chat_id=chat_id,
            )
            return
        if command == "signals" and shared_chat:
            _send_view(chat_id, command, arg, interactive=True)
            return
        _send_view(chat_id, command, arg, interactive=command in {"signals", "portfolio"})
        return


def _handle_callback(update: dict) -> None:
    cb = update.get("callback_query") or {}
    callback_id = cb.get("id")
    data = cb.get("data") or ""
    message = cb.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))
    user_id = str((cb.get("from") or {}).get("id", ""))

    if not callback_id:
        return

    shared_chat = _is_shared_chat(chat_id)
    monitor_chat = _is_monitor_chat(chat_id)
    demo_chat = _is_demo_chat(chat_id)
    live_chat = _is_live_chat(chat_id)

    if not (monitor_chat or demo_chat or live_chat):
        answer_callback(callback_id, "Chat not allowed")
        return

    action, _, payload = data.partition(":")
    state = load_state()

    if action == "regenerate":
        import subprocess

        target = payload or "market"
        answer_callback(callback_id, f"Regenerating {target} data... (approx 30s)")

        if target == "market":
            subprocess.Popen([sys.executable, "scripts/finviz_monitor.py"])

        _log_action(chat_id, user_id, "regenerate", {"target": target}, status="applied")
        return

    if action == "refresh":
        target = payload or "market"
        if target == "position":
            answer_callback(callback_id, "use /position <ticker>")
            return
        if target == "watchlist":
            page = 1
            msg_text = message.get("text", "")
            import re

            m = re.search(r"Page (\d+)/", msg_text)
            if m:
                try:
                    page = int(m.group(1))
                except:
                    pass
            system = _get_system_for_chat(chat_id)
            resolved_text, resolved_buttons = build_watchlist_message(page=page, system=system)
            edit_message(
                chat_id=chat_id,
                message_id=message.get("message_id"),
                text=resolved_text,
                buttons=resolved_buttons,
            )
            _log_action(
                chat_id, user_id, "refresh", {"target": target, "page": page}, status="applied"
            )
            answer_callback(callback_id, "Watchlist refreshed")
            return
        if (monitor_chat or live_chat) and not shared_chat and target == "signals":
            send_message_with_buttons(
                build_monitor_signals_message(),
                buttons=REFRESH_BUTTONS["signals"],
                chat_id=chat_id,
            )
            _log_action(chat_id, user_id, "refresh", {"target": target}, status="applied")
            answer_callback(callback_id, f"{target} refreshed")
            return
        interactive = (demo_chat or shared_chat) and target in {"signals", "portfolio"}
        _send_view(chat_id, target, "", interactive=interactive)
        _log_action(chat_id, user_id, "refresh", {"target": target}, status="applied")
        answer_callback(callback_id, f"{target} refreshed")
        return

    if action == "noop":
        answer_callback(callback_id)
        return

    if action == "shadow_audit":
        target = payload or "market"
        if target not in {"market", "signals", "watchlist", "paper_run"}:
            answer_callback(callback_id, "Unsupported audit target")
            return
        resolved, snapshot = load_monitor_snapshot()
        if not resolved or not snapshot:
            answer_callback(callback_id, "No shadow audit available")
            return
        if target == "market":
            brief, buttons = build_market_message(resolved)
        elif target == "watchlist":
            brief, buttons = build_watchlist_message(resolved)
        elif target == "signals":
            brief, buttons = build_signals_message(resolved), REFRESH_BUTTONS["signals"]
        else:
            brief, buttons = build_paper_run_message(resolved), REFRESH_BUTTONS["paper_run"]
        edit_message(
            chat_id=chat_id,
            message_id=message.get("message_id"),
            text=brief,
            buttons=buttons,
        )
        answer_callback(callback_id, "Shadow audit loaded")
        _log_action(
            chat_id, user_id, "shadow_audit", {"target": target, "date": resolved}, status="applied"
        )
        return

    if action == "watchlist_page":
        try:
            page = int(payload)
        except ValueError:
            page = 1
        system = _get_system_for_chat(chat_id)
        resolved_text, resolved_buttons = build_watchlist_message(page=page, system=system)
        edit_message(
            chat_id=chat_id,
            message_id=message.get("message_id"),
            text=resolved_text,
            buttons=resolved_buttons,
        )
        answer_callback(callback_id, f"Page {page} loaded")
        return

    if action == "watchlist_detail":
        ticker = payload.upper()
        msg_text = build_watchlist_detail(ticker)
        buttons = [
            [
                {"text": "🔄 Refresh", "callback_data": f"watchlist_detail:{ticker}"},
                {"text": "📋 Watchlist", "callback_data": "watchlist_page:1"},
            ]
        ]
        edit_message(
            chat_id=chat_id,
            message_id=message.get("message_id"),
            text=msg_text,
            buttons=buttons,
        )
        answer_callback(callback_id, f"{ticker} refreshed")
        return

    if not (demo_chat or shared_chat):
        answer_callback(callback_id, "Not allowed in this chat")
        return

    if action == "approve_trade" and (state.kill_switch or state.entries_paused):
        answer_callback(callback_id, "Kill switch ON")
        return

    if action == "approve_trade":
        result = approve_intent(state.date, payload, chat_id, user_id, callback_id)
        answer_callback(
            callback_id, "approved" if result.get("ok") else str(result.get("reason", "error"))
        )
        _send_view(chat_id, "portfolio", "", interactive=True)
        return
    if action == "reject_trade":
        result = reject_intent(state.date, payload, chat_id, user_id, callback_id)
        answer_callback(
            callback_id, "rejected" if result.get("ok") else str(result.get("reason", "error"))
        )
        _send_view(chat_id, "signals", "", interactive=True)
        return
    if action == "snooze_trade":
        result = snooze_intent(state.date, payload, chat_id, user_id, callback_id)
        answer_callback(
            callback_id, "snoozed" if result.get("ok") else str(result.get("reason", "error"))
        )
        _send_view(chat_id, "signals", "", interactive=True)
        return
    if action == "close_position":
        result = close_position(state.date, payload, chat_id, user_id, callback_id, confirm=False)
        if result.get("confirm_required"):
            send_message_with_buttons(
                "<b>Confirm close?</b>",
                buttons=[
                    [
                        {"text": "Confirm close", "callback_data": f"confirm_close:{payload}"},
                        {"text": "Refresh", "callback_data": "refresh:portfolio"},
                    ]
                ],
                chat_id=chat_id,
            )
        answer_callback(
            callback_id,
            "confirm close"
            if result.get("confirm_required")
            else str(result.get("reason", "error")),
        )
        return
    if action == "confirm_close":
        result = close_position(state.date, payload, chat_id, user_id, callback_id, confirm=True)
        answer_callback(
            callback_id, "closed" if result.get("ok") else str(result.get("reason", "error"))
        )
        _send_view(chat_id, "portfolio", "", interactive=True)
        return

    _log_action(chat_id, user_id, action, {"data": data}, status="received")
    answer_callback(callback_id, f"{action} received")


def main() -> None:
    offset = _load_offset()
    while True:
        updates = get_updates(offset=offset, timeout=20)
        for update in updates:
            offset = update.get("update_id", offset) + 1
            _save_offset(offset)
            if "message" in update:
                _handle_message(update)
            elif "callback_query" in update:
                _handle_callback(update)
        time.sleep(1)


if __name__ == "__main__":
    main()
