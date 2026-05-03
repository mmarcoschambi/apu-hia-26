#!/usr/bin/env python3
"""
finviz_monitor.py - Finviz radar y briefs para VPS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.paper_finviz import run_pre
from src.utils.telegram_client import send_message_with_buttons

OUT_DIR = PROJECT_ROOT / "outputs" / "telegram_monitor"


def _save(date: str, name: str, payload: dict) -> Path:
    day_dir = OUT_DIR / date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def build_brief(snapshot: dict) -> str:
    signals = snapshot.get("signals", [])
    regime_ok = snapshot.get("regime_ok", False)
    warnings = snapshot.get("finviz_warnings") or []
    top = signals[:5]
    lines = [
        f"<b>FINVIZ BRIEF | {snapshot['date']}</b>",
        f"Regime: <b>{'OK' if regime_ok else 'BLOCKED'}</b>",
        f"Universe: <code>{snapshot.get('universe_size', 0)}</code>",
        f"Signals: <code>{len(signals)}</code>",
        f"Pages OK: <code>{snapshot.get('finviz_pages_ok', 0)}</code>",
    ]
    if warnings:
        lines.append("Warnings:")
        for warning in warnings[:3]:
            lines.append(f"- {warning}")
    if top:
        lines.append("Top candidates:")
        for signal in top:
            lines.append(
                f"- <b>{signal.get('ticker', '?')}</b> "
                f"{signal.get('combo', signal.get('combo_name', 'n/a'))} "
                f"entry={float(signal.get('entry_price', 0) or 0):.2f} "
                f"stop={float(signal.get('stop_loss', signal.get('stop_price', 0)) or 0):.2f}"
            )
    else:
        lines.append("No candidates today.")
    return "\n".join(lines)


def build_prealerts(snapshot: dict) -> dict:
    signals = snapshot.get("signals", [])
    top = sorted(signals, key=lambda s: str(s.get("ticker", "")))[:10]
    return {
        "date": snapshot["date"],
        "signals": top,
        "signals_count": len(signals),
        "generated_at": datetime.now().isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Finviz monitor")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    date = args.date or datetime.now().strftime("%Y-%m-%d")

    snapshot = run_pre(date, drift_override=100.0)
    if not snapshot:
        payload = {"date": date, "status": "failed", "generated_at": datetime.now().isoformat()}
        _save(date, "market_status.json", payload)
        return

    brief = build_brief(snapshot)
    prealerts = build_prealerts(snapshot)

    _save(date, "market_status.json", snapshot)
    _save(date, "premarket_brief.json", {"date": date, "brief": brief})
    _save(date, "prealerts.json", prealerts)
    _save(
        date,
        "close_summary.json",
        {
            "date": date,
            "status": "pending_close_summary",
            "signals_count": len(snapshot.get("signals", [])),
            "generated_at": datetime.now().isoformat(),
        },
    )

    monitor_chat_id = os.getenv("TELEGRAM_CHAT_ID_MONITOR")
    if monitor_chat_id:
        send_message_with_buttons(
            brief,
            buttons=[[{"text": "Refresh", "callback_data": "refresh:market"}]],
            chat_id=monitor_chat_id,
        )


if __name__ == "__main__":
    main()
