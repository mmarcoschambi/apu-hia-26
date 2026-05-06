#!/usr/bin/env bash
"""
start_live_session.sh - Inicia la sesión de trading en vivo en el VPS.
Lanza el monitor de precios (auto-trader) y el listener de Telegram en segundo plano.
"""

# Configuración de rutas
PROJECT_DIR="/home/marcos/trade/momentum-v2"
LOG_DIR="$PROJECT_DIR/logs/live"
mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR" || exit 1

# 1. Matar procesos anteriores para evitar duplicados
echo "Cleaning up old live processes..."
pkill -f "live_auto_trader.py"
pkill -f "telegram_bot_listener.py"

# 2. Iniciar el GESTOR DE PRECIOS Y AUTO-TRADE (Monitor continuo)
# Redirige logs a logs/live/auto_trader.log
echo "Starting Live Auto-Trader (Automated + Managed flows)..."
nohup .venv/bin/python scripts/live_auto_trader.py --monitor --interval 1 > "$LOG_DIR/auto_trader.log" 2>&1 &
echo "  [OK] Auto-Trader PID: $!"

# 3. Iniciar el BOT LISTENER (Para responder a botones de Telegram)
# Redirige logs a logs/live/telegram_bot.log
echo "Starting Telegram Bot Listener (Interactive flow)..."
nohup .venv/bin/python scripts/telegram_bot_listener.py > "$LOG_DIR/telegram_bot.log" 2>&1 &
echo "  [OK] Telegram Listener PID: $!"

echo ""
echo "--------------------------------------------------------"
echo "LIVE SESSION STARTED"
echo "Monitor Logs: tail -f logs/live/auto_trader.log"
echo "Bot Logs:     tail -f logs/live/telegram_bot.log"
echo "--------------------------------------------------------"
