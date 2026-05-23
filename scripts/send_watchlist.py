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
    print("⏳ Generando y enviando watchlist del día...")
    # build_watchlist_message resolves the latest available date if not specified
    text, buttons = build_watchlist_message()
    
    success = send_message_with_buttons(text, buttons)
    if success:
        print("✅ Watchlist enviada con éxito a Telegram.")
    else:
        print("❌ Error: No se pudo enviar la watchlist a Telegram.")
        sys.exit(1)

if __name__ == "__main__":
    main()
