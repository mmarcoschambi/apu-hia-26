#!/usr/bin/env bash
"""
start_live_session.sh - Inicia la sesión de trading en vivo en el VPS.
Lanza el monitor de precios (auto-trader) y el listener de Telegram en segundo plano.

Modos de operación:
  1. systemd (preferido): Usa systemctl si el binario está disponible.
  2. PID file + nohup (fallback): Escribe PID en run/ para lifecycle management.

Usage:
  ./start_live_session.sh                   # Iniciar sesión (prefiere systemd)
  ./start_live_session.sh --headless        # Iniciar sin mensajes extra (para systemd unit)
  ./start_live_session.sh --status          # Mostrar estado de procesos via PID files
  ./start_live_session.sh --stop            # Detener procesos via PID files
"""

set -euo pipefail

# Configuración de rutas
PROJECT_DIR="/home/marcos/trade/momentum-v2"
RUN_DIR="$PROJECT_DIR/run"
LOG_DIR="$PROJECT_DIR/logs/live"
TRADER_PIDFILE="$RUN_DIR/momentum-trader.pid"
TELEGRAM_PIDFILE="$RUN_DIR/momentum-telegram.pid"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"

HEADLESS=false
ACTION="start"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        --headless) HEADLESS=true ;;
        --status)   ACTION="status" ;;
        --stop)     ACTION="stop" ;;
        *)          ;;
    esac
    shift
done

mkdir -p "$RUN_DIR" "$LOG_DIR"
cd "$PROJECT_DIR" || exit 1

# ── Helpers ────────────────────────────────────────────────────────────

_read_pid() {
    local pidfile="$1"
    if [[ -f "$pidfile" ]]; then
        cat "$pidfile" 2>/dev/null || echo ""
    fi
}

_is_running() {
    local pid="$1"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

_write_pid() {
    local pidfile="$1"
    local pid="$2"
    echo "$pid" > "$pidfile"
    echo "$pid"
}

_clean_pid() {
    local pidfile="$1"
    local name="$2"
    local pid
    pid=$(_read_pid "$pidfile")
    if _is_running "$pid"; then
        kill "$pid" 2>/dev/null || true
        # Wait briefly for graceful shutdown
        for _ in $(seq 1 5); do
            if ! _is_running "$pid"; then
                break
            fi
            sleep 1
        done
        # Force kill if still running
        if _is_running "$pid"; then
            kill -9 "$pid" 2>/dev/null || true
        fi
        echo "  [OK] $name (PID $pid) detenido."
    fi
    rm -f "$pidfile"
}

_has_systemd() {
    command -v systemctl &>/dev/null && systemctl --version &>/dev/null 2>&1
}

# ── Actions ────────────────────────────────────────────────────────────

if [[ "$ACTION" == "status" ]]; then
    echo "📊 Estado de procesos de trading en vivo:"
    echo ""
    for pair in "TRADER:$TRADER_PIDFILE" "TELEGRAM:$TELEGRAM_PIDFILE"; do
        name="${pair%%:*}"
        pidfile="${pair##*:}"
        pid=$(_read_pid "$pidfile")
        if _is_running "$pid"; then
            echo "  ✅ $name corriendo (PID $pid)"
        else
            echo "  ⬜ $name detenido"
        fi
    done
    exit 0
fi

if [[ "$ACTION" == "stop" ]]; then
    echo "🛑 Deteniendo sesión de trading en vivo..."

    # Prefer systemd if available
    if _has_systemd; then
        echo "   systemd detectado, usando systemctl..."
        sudo systemctl stop momentum-trader.service 2>/dev/null || true
        sudo systemctl stop momentum-telegram.service 2>/dev/null || true
        echo "  [OK] Servicios detenidos via systemctl."
    fi

    _clean_pid "$TELEGRAM_PIDFILE" "Telegram Bot Listener"
    _clean_pid "$TRADER_PIDFILE" "Live Auto-Trader"
    echo "✅ Sesión de trading detenida."
    exit 0
fi

# ── START ──────────────────────────────────────────────────────────────

# --systemd mode (preferido)--
if _has_systemd; then
    if [[ "$HEADLESS" != true ]]; then
        echo "🔍 systemd detectado. Usando systemctl para gestionar servicios..."
    fi

    sudo systemctl daemon-reload 2>/dev/null || true
    sudo systemctl restart momentum-trader.service momentum-telegram.service 2>/dev/null || EXIT_CODE=$?

    if [[ ${EXIT_CODE:-0} -eq 0 ]]; then
        if [[ "$HEADLESS" != true ]]; then
            echo "  [OK] Servicios iniciados via systemctl."
            echo ""
            echo "--------------------------------------------------------"
            echo "LIVE SESSION STARTED (systemd)"
            echo "Monitor: systemctl status momentum-trader momentum-telegram"
            echo "Logs:    journalctl -u momentum-trader -f"
            echo "         journalctl -u momentum-telegram -f"
            echo "--------------------------------------------------------"
        fi
        exit 0
    else
        if [[ "$HEADLESS" != true ]]; then
            echo "  ⚠️  systemctl restart falló (exit $EXIT_CODE). Usando fallback nohup..."
        fi
    fi
fi

# --nohup fallback mode (con PID files)--
if [[ "$HEADLESS" != true ]]; then
    echo "📁 Usando modo fallback nohup + PID file..."
fi

# Limpiar PIDs anteriores
_clean_pid "$TRADER_PIDFILE" "Live Auto-Trader (old)"
_clean_pid "$TELEGRAM_PIDFILE" "Telegram Bot Listener (old)"

# 1. Iniciar Auto-Trader
if [[ "$HEADLESS" != true ]]; then
    echo "Iniciando Live Auto-Trader..."
fi
nohup "$PYTHON_BIN" scripts/live_auto_trader.py --monitor --interval 1 \
    > "$LOG_DIR/auto_trader.log" 2>&1 &
TRADER_PID=$(_write_pid "$TRADER_PIDFILE" $!)
echo "  [OK] Auto-Trader PID: $TRADER_PID"

# 2. Iniciar Telegram Bot Listener
if [[ "$HEADLESS" != true ]]; then
    echo "Iniciando Telegram Bot Listener..."
fi
nohup "$PYTHON_BIN" scripts/telegram_bot_listener.py \
    > "$LOG_DIR/telegram_bot.log" 2>&1 &
TELEGRAM_PID=$(_write_pid "$TELEGRAM_PIDFILE" $!)
echo "  [OK] Telegram Listener PID: $TELEGRAM_PID"

if [[ "$HEADLESS" != true ]]; then
    echo ""
    echo "--------------------------------------------------------"
    echo "LIVE SESSION STARTED"
    echo "PIDs: trader=$TRADER_PID | telegram=$TELEGRAM_PID"
    echo "Logs: tail -f logs/live/auto_trader.log"
    echo "      tail -f logs/live/telegram_bot.log"
    echo "Stop: ./start_live_session.sh --stop"
    echo "--------------------------------------------------------"
fi
