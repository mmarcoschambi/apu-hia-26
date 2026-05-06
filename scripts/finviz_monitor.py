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
from src.utils.terminal_gui import build_telegram_brief, print_terminal_brief

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
    date = snapshot.get("date", "n/a")

    lines = [
        f"🚀 <b>SIGNAL ALERTS | {date}</b>",
        f"📊 <b>Stats:</b>",
        f"• Regime: <b>{'OK' if regime_ok else 'BLOCKED'}</b>",
        f"• Universe: <code>{snapshot.get('universe_size', 0)}</code>",
        f"• Signals: <code>{len(signals)}</code>",
        f"• Pages OK: <code>{snapshot.get('finviz_pages_ok', 0)}</code>",
    ]

    if signals:
        lines.append("\n🔥 <b>TOP CANDIDATES:</b>")
        # Mostrar los top 5 señales con detalles
        for s in signals[:5]:
            ticker = s.get("ticker", "?")
            price = s.get("entry_price", 0)
            score = s.get("score", 0)
            rvol = s.get("rvol", 1.0)
            dv = s.get("dollar_volume_m", 0)

            lines.append(
                f"⭐ <b>{ticker}</b> (Score: {score:.1f})\n"
                f"   Price: ${price:.2f} | RVOL: {rvol:.1f}x | DV: {int(dv)}M"
            )

        lines.append("\n📋 <b>SIGNAL TABLE:</b>")
        lines.append("<code>Ticker   Score  Price   RVOL</code>")
        lines.append("<code>------- ------ -------- ----</code>")
        for s in signals[:10]:
            ticker = s.get("ticker", "?")[:7].ljust(7)
            score = f"{s.get('score', 0):.1f}".center(6)
            price = f"{s.get('entry_price', 0):.2f}".rjust(8)
            rvol = f"{s.get('rvol', 1.0):.1f}".rjust(4)
            lines.append(f"<code>{ticker} {score} {price} {rvol}</code>")
    else:
        lines.append("\nNo confirmed signals today.")

    watchlist_scored = snapshot.get("watchlist_scored", {})
    if watchlist_scored:
        sig_tickers = {s.get("ticker") for s in signals}
        watchlist = [(t, score) for t, score in watchlist_scored.items() if t not in sig_tickers]
        watchlist.sort(key=lambda x: x[1], reverse=True)

        if watchlist:
            lines.append("\n🔭 <b>WATCHLIST (Top RS):</b>")
            formatted = [f"{t}:{int(score)}" for t, score in watchlist[:10]]
            lines.append(f"<code>{', '.join(formatted)}</code>")
            if len(watchlist) > 10:
                lines.append(f"<i>...and {len(watchlist) - 10} more</i>")

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

    brief = build_telegram_brief(snapshot)
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

    # OUTPUT TERMINAL GUI
    print_terminal_brief(snapshot)


if __name__ == "__main__":
    main()
