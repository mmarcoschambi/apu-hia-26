#!/usr/bin/env python3
"""
send_watchlist.py - Genera y envía la watchlist de pre-market a Telegram al abrir el mercado.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.paper.telegram_views import build_watchlist_message
from src.utils.telegram_client import send_message_with_buttons

def main():
    import os
    print("⏳ Generando y enviando watchlist del día...")
    
    # 1. System A watchlist
    print("Sending System A (Qulla) watchlist...")
    text_a, buttons_a = build_watchlist_message(system="A")
    chat_a = os.getenv("TELEGRAM_CHAT_ID_MONITOR")
    success_a = send_message_with_buttons(text_a, buttons_a, chat_id=chat_a)
    if success_a:
        print("✅ Watchlist Sistema A enviada con éxito a Telegram.")
    else:
        print("❌ Error: No se pudo enviar la watchlist del Sistema A.")

    # 2. System B watchlist
    print("Sending System B (Minervini) watchlist...")
    text_b, buttons_b = build_watchlist_message(system="B")
    chat_b = os.getenv("TELEGRAM_CHAT_ID_SYSTEM_B") or chat_a
    success_b = send_message_with_buttons(text_b, buttons_b, chat_id=chat_b)
    if success_b:
        print("✅ Watchlist Sistema B enviada con éxito a Telegram.")
    else:
        print("❌ Error: No se pudo enviar la watchlist del Sistema B.")

    if not success_a and not success_b:
        sys.exit(1)

if __name__ == "__main__":
    main()
