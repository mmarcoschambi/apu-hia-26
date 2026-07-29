#!/usr/bin/env bash
# health_check.sh - Report process status, DB connection, last trade timestamp.
# Exit 0 = healthy, 1 = degraded, 2 = critical failure.
#
# Usage:
#   ./scripts/sv/health_check.sh          # normal check
#   ./scripts/sv/health_check.sh --preflight  # pre-deploy check (no DB/age checks)
#   ./scripts/sv/health_check.sh --json   # JSON output

set -euo pipefail

PROJECT_DIR="/home/marcos/trade/momentum-v2"
RUN_DIR="${PROJECT_DIR}/run"
LOG_DIR="${PROJECT_DIR}/logs/live"
TRADER_PIDFILE="${RUN_DIR}/momentum-trader.pid"
TELEGRAM_PIDFILE="${RUN_DIR}/momentum-telegram.pid"
HEALTH_LOG="/var/log/momentum/health.log"

TRADER_RUNNING=0
TELEGRAM_RUNNING=0
DB_OK=0
TRADE_FRESH=0
EXIT_CODE=0
MODE="normal"

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --preflight) MODE="preflight" ;;
        --json)      MODE="json" ;;
        *)           ;;
    esac
    shift
done

# --- Helper: check if process is alive via PID file ---
_check_pid() {
    local pidfile="$1"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile" 2>/dev/null || echo "")
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# --- Helper: check if a process is running by name (fallback) ---
_check_process_name() {
    local pattern="$1"
    pgrep -f "$pattern" >/dev/null 2>&1
}

# --- Check services ---
if _check_pid "$TRADER_PIDFILE"; then
    TRADER_RUNNING=1
else
    # Fallback: check by process name
    if _check_process_name "live_auto_trader.py" || _check_process_name "finviz_monitor.py"; then
        TRADER_RUNNING=1
    fi
fi

if _check_pid "$TELEGRAM_PIDFILE"; then
    TELEGRAM_RUNNING=1
else
    if _check_process_name "telegram_bot_listener.py"; then
        TELEGRAM_RUNNING=1
    fi
fi

# --- Database connection check (skip in preflight) ---
if [[ "$MODE" != "preflight" ]]; then
    if command -v sqlite3 &>/dev/null; then
        local_db="${PROJECT_DIR}/data/ticker_cache.db"
        if [[ -f "$local_db" ]]; then
            if sqlite3 "$local_db" "SELECT 1;" &>/dev/null; then
                DB_OK=1
            fi
        fi
    fi
fi

# --- Last trade timestamp check (skip in preflight) ---
TRADE_FRESH=1  # Default to OK
if [[ "$MODE" != "preflight" ]]; then
    # Look for the most recent trade log entry
    latest_log=$(find "${PROJECT_DIR}/outputs" -name "trade_log.txt" -newer "${PROJECT_DIR}/.git/HEAD" 2>/dev/null | head -1)
    if [[ -n "$latest_log" ]]; then
        last_line=$(tail -1 "$latest_log" 2>/dev/null || echo "")
        if [[ -n "$last_line" ]]; then
            # Extract timestamp from log line: [YYYY-MM-DD HH:MM:SS]
            ts=$(echo "$last_line" | grep -oP '\[\K[\d-]+ [\d:]+(?=\])' || echo "")
            if [[ -n "$ts" ]]; then
                trade_epoch=$(date -d "$ts" +%s 2>/dev/null || echo 0)
                now_epoch=$(date +%s)
                if [[ $(( now_epoch - trade_epoch )) -gt 86400 ]]; then
                    TRADE_FRESH=0
                fi
            fi
        fi
    fi
fi

# --- Determine exit code ---
if [[ $TRADER_RUNNING -eq 0 && $TELEGRAM_RUNNING -eq 0 ]]; then
    EXIT_CODE=2  # Critical: both down
elif [[ $TRADER_RUNNING -eq 1 && $TELEGRAM_RUNNING -eq 1 ]]; then
    if [[ "$MODE" != "preflight" ]]; then
        if [[ $DB_OK -eq 0 || $TRADE_FRESH -eq 0 ]]; then
            EXIT_CODE=1  # Degraded
        else
            EXIT_CODE=0  # Healthy
        fi
    else
        EXIT_CODE=0  # Preflight: all processes running is good enough
    fi
else
    EXIT_CODE=1  # Degraded: one service down
fi

# --- Output ---
HEALTH_LINE=""
HEALTH_LINE+="STATUS="
if [[ $EXIT_CODE -eq 0 ]]; then
    HEALTH_LINE+="healthy"
elif [[ $EXIT_CODE -eq 1 ]]; then
    HEALTH_LINE+="degraded"
else
    HEALTH_LINE+="critical"
fi
HEALTH_LINE+=$'\n'

if [[ $TRADER_RUNNING -eq 1 ]]; then
    HEALTH_LINE+="TRADER=running"
else
    HEALTH_LINE+="TRADER=stopped"
fi
HEALTH_LINE+=$'\n'

if [[ $TELEGRAM_RUNNING -eq 1 ]]; then
    HEALTH_LINE+="TELEGRAM=running"
else
    HEALTH_LINE+="TELEGRAM=stopped"
fi
HEALTH_LINE+=$'\n'

if [[ "$MODE" != "preflight" ]]; then
    if [[ $DB_OK -eq 1 ]]; then
        HEALTH_LINE+="DB=ok"
    else
        HEALTH_LINE+="DB=unavailable"
    fi
    HEALTH_LINE+=$'\n'
    if [[ $TRADE_FRESH -eq 1 ]]; then
        HEALTH_LINE+="LAST_TRADE=recent"
    else
        HEALTH_LINE+="LAST_TRADE=stale"
    fi
    HEALTH_LINE+=$'\n'
fi

if [[ "$MODE" == "json" ]]; then
    # Collect failed services for JSON output
    FAILED_SERVICES="[]"
    if [[ $TRADER_RUNNING -eq 0 && $TELEGRAM_RUNNING -eq 0 ]]; then
        FAILED_SERVICES='["momentum-trader", "momentum-telegram"]'
    elif [[ $TRADER_RUNNING -eq 0 ]]; then
        FAILED_SERVICES='["momentum-trader"]'
    elif [[ $TELEGRAM_RUNNING -eq 0 ]]; then
        FAILED_SERVICES='["momentum-telegram"]'
    fi

    echo "{"
    echo "  \"status\": \"$(echo "$HEALTH_LINE" | grep STATUS | cut -d= -f2)\","
    echo "  \"exit_code\": $EXIT_CODE,"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"services\": {"
    echo "    \"trader\": $([ $TRADER_RUNNING -eq 1 ] && echo "\"running\"" || echo "\"stopped\""),"
    echo "    \"telegram\": $([ $TELEGRAM_RUNNING -eq 1 ] && echo "\"running\"" || echo "\"stopped\"")"
    echo "  },"
    if [[ "$MODE" != "preflight" ]]; then
        echo "  \"database\": $([ $DB_OK -eq 1 ] && echo "\"ok\"" || echo "\"unavailable\""),"
        echo "  \"last_trade\": $([ $TRADE_FRESH -eq 1 ] && echo "\"recent\"" || echo "\"stale\"")"
    else
        echo "  \"mode\": \"preflight\""
    fi
    echo "}"
else
    echo "$HEALTH_LINE"
fi

# --- Write to health log (only if directory exists) ---
HEALTH_LOG_DIR=$(dirname "$HEALTH_LOG" 2>/dev/null || echo "")
if [[ -n "$HEALTH_LOG_DIR" ]]; then
    mkdir -p "$HEALTH_LOG_DIR" 2>/dev/null || true
    echo "$(date -Iseconds) STATUS=$([ $EXIT_CODE -eq 0 ] && echo "healthy" || ([ $EXIT_CODE -eq 1 ] && echo "degraded" || echo "critical"))" >> "$HEALTH_LOG" 2>/dev/null || true
fi

exit $EXIT_CODE
