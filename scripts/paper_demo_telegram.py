#!/usr/bin/env python3
"""
paper_demo_telegram.py - Ledger demo separado para Telegram + Finviz.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.paper.demo_portfolio import persist_candidates
from src.paper.telegram_views import build_signal_cards, build_signals_message
from src.utils.telegram_client import send_message_with_buttons

OUT_DIR = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"


def _load_finviz_signals(date: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "outputs" / "paper_finviz" / date / "snapshot.json"
    if not path.exists():
        return pd.DataFrame()
    snap = json.loads(path.read_text())
    return pd.DataFrame(snap.get("signals", []))


def run_demo(date: str, send_telegram: bool = False) -> dict:
    signals_df = _load_finviz_signals(date)
    
    # ── [FIX] Deduplicar por ticker ─────────────────────────────────────────
    # Si un ticker aparece en múltiples combos, nos quedamos con el que tenga
    # mayor position_size (o el primero si ambos son 0/setups).
    if not signals_df.empty:
        signals_df = (signals_df.sort_values("position_size", ascending=False)
                      .drop_duplicates("ticker"))
    
    intents = persist_candidates(date, signals_df, source_universe="finviz")
    day_dir = OUT_DIR / date
    day_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "date": date,
        "status": "demo_candidates_ready" if intents else "idle",
        "signals": len(signals_df),
        "intents": len(intents),
        "positions": 0,
        "generated_at": datetime.now().isoformat(),
    }
    demo_chat_id = os.getenv("TELEGRAM_CHAT_ID_DEMO")
    if send_telegram and demo_chat_id and intents:
        send_message_with_buttons(
            build_signals_message(date),
            buttons=[[{"text": "Refresh", "callback_data": "refresh:signals"}]],
            chat_id=demo_chat_id,
        )
        for card in build_signal_cards(date):
            send_message_with_buttons(card["text"], card["buttons"], chat_id=demo_chat_id)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Finviz Telegram demo portfolio")
    parser.add_argument("--date", default=None)
    parser.add_argument("--telegram", action="store_true", help="Send candidates to demo chat")
    args = parser.parse_args()
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    state = run_demo(date, send_telegram=args.telegram)
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
