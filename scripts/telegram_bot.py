#!/usr/bin/env python3
"""
telegram_bot.py - Bot read-only inicial para observabilidad.

Comandos:
    /signals [YYYY-MM-DD]
    /portfolio [YYYY-MM-DD]
    /parity YYYY-MM-DD
    /position TICKER
    /kill_switch on|off

Este scaffold solo responde lectura. No ejecuta trades.
"""

from __future__ import annotations

import os
import shlex
import json
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_DIR = PROJECT_ROOT / "outputs" / "telegram_events"
EVENTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv()


@dataclass
class BotCommand:
    name: str
    args: list[str]


def parse_command(text: str) -> BotCommand:
    parts = shlex.split(text.strip()) if text else []
    if not parts:
        return BotCommand(name="", args=[])
    name = parts[0].lstrip("/")
    return BotCommand(name=name, args=parts[1:])


def handle_command(text: str) -> str:
    cmd = parse_command(text)
    if cmd.name == "signals":
        date = cmd.args[0] if cmd.args else None
        return json.dumps(
            {"command": "signals", "date": date or "today", "status": "read_only"}
        )
    if cmd.name == "portfolio":
        date = cmd.args[0] if cmd.args else None
        return json.dumps(
            {"command": "portfolio", "date": date or "latest", "status": "read_only"}
        )
    if cmd.name == "parity":
        return json.dumps(
            {
                "command": "parity",
                "date": cmd.args[0] if cmd.args else None,
                "status": "read_only",
            }
        )
    if cmd.name == "position":
        return json.dumps(
            {
                "command": "position",
                "ticker": cmd.args[0] if cmd.args else None,
                "status": "read_only",
            }
        )
    if cmd.name == "kill_switch":
        return json.dumps(
            {
                "command": "kill_switch",
                "state": cmd.args[0] if cmd.args else None,
                "status": "stub",
            }
        )
    return json.dumps({"command": "unknown", "raw": text, "status": "unknown"})


def log_event(command: str, payload: dict) -> Path:
    event = {
        "event_id": f"evt_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "command": command,
        "payload": payload,
        "status": "received",
        "created_at": datetime.now().isoformat(),
    }
    day = datetime.now().strftime("%Y-%m-%d")
    path = EVENTS_DIR / f"{day}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return path


def main() -> None:
    print(f"telegram_bot scaffold ready @ {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
