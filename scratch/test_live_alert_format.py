import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.telegram_client import telegram_send

load_dotenv()

chat_id = os.getenv("TELEGRAM_CHAT_ID_LIVE")
if not chat_id:
    print("ERROR: TELEGRAM_CHAT_ID_LIVE no definido.")
    sys.exit(1)

# 1. Mock de Alerta que PASA (Sistema A)
msg_pass = (
    "<b>[SISTEMA A]</b> 🧭 <b>LIVE SIGNAL: NVDA</b> (Technology)\n"
    "🆕 <b>NUEVO TICKER</b>\n\n"
    "⚡ <b>TRIGGER DETAILS:</b>\n"
    "• Live Trigger: <b>PASS</b>\n"
    "• Price: <b>$127.40</b> (Break: $125.00)\n"
    "• Live RVOL: <b>1.85x</b>\n\n"
    "🟢 <b>ENTRY GATE STATUS: PASS</b>\n"
    "• Gate Reason: <code>trend_score=0.85; rs_percentile=89.2%</code>\n"
    "• Source: <i>canonical_signal_engine:combo_pure_momentum</i>\n\n"
    "📊 <b>GATE METRICS:</b>\n"
    "• RS Percentile: <b>89.2%</b>\n"
    "• ADR %: <b>4.85%</b>\n"
    "• Dollar Volume: <b>$12450.2M</b>\n"
    "• Dist SMA20: <b>3.15%</b>\n"
    "• Sector ETF Dist: <b>1.20%</b>\n\n"
    "📈 <a href=\"https://www.tradingview.com/symbols/NVDA/\">Ver en TradingView</a>\n\n"
    "📢 <b>ACTION:</b>\n"
    "<b>🟢 Trigger validado. Elegible para entrada swing manual.</b>"
)

# 2. Mock de Alerta que BLOQUEA con Sizing (Sistema B / Minervini con E25)
msg_blocked = (
    "<b>[SISTEMA B]</b> 🧭 <b>LIVE SIGNAL: COCO</b> (Consumer Defensive)\n"
    "📋 <b>EN WATCHLIST</b>\n\n"
    "⚡ <b>TRIGGER DETAILS:</b>\n"
    "• Live Trigger: <b>PASS</b>\n"
    "• Price: <b>$82.54</b> (Break: $80.51)\n"
    "• Live RVOL: <b>1.54x</b>\n\n"
    "🔴 <b>ENTRY GATE STATUS: BLOCKED</b>\n"
    "• Gate Reason: <code>screener_fail:minervini_trend=FAIL</code>\n"
    "• Source: <i>snapshot_partial:combo_stage2_breakout</i>\n\n"
    "📊 <b>GATE METRICS:</b>\n"
    "• RS Percentile: <b>78.4%</b>\n"
    "• ADR %: <b>3.45%</b>\n"
    "• Dollar Volume: <b>$45.8M</b>\n"
    "• Dist SMA20: <b>14.20%</b> (E25 Sizing factor: 0.55x)\n"
    "• Sector ETF Dist: <b>-1.50%</b>\n\n"
    "📈 <a href=\"https://www.tradingview.com/symbols/COCO/\">Ver en TradingView</a>\n\n"
    "📢 <b>ACTION:</b>\n"
    "<b>🔴 Evitar entrada: bloqueado por tendencia de Minervini.</b>"
)

print("Enviando mock PASS...")
telegram_send(msg_pass, chat_id=chat_id)

print("Enviando mock BLOCKED...")
telegram_send(msg_blocked, chat_id=chat_id)

print("Done.")
