#!/usr/bin/env bash
# =============================================================================
# SYNC FROM VPS  →  PC LOCAL (WSL2)
# Propósito : Bajar toda la data de investigación del VPS al laboratorio local.
#             Corre los viernes al cierre del mercado (16:15 NY / 18:15 ARG).
# Uso manual: ./sync_from_vps.sh
# Cron auto : ver deploy/crontab_local.txt
# =============================================================================

set -euo pipefail

# ── Configuración ──────────────────────────────────────────────────────────────
REMOTE_HOST="xxmalcomandaxx@trading-vps.us-central1-f.paper-trading-server"
REMOTE_DIR="/home/xxmalcomandaxx/swing-momentum-v1"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # raíz del proyecto local
LOG_FILE="$LOCAL_DIR/logs/sync_from_vps.log"

# ── Parsear argumentos opcionales ─────────────────────────────────────────────
DRY_RUN=false
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
    --host=*)  REMOTE_HOST="${arg#*=}" ;;
    --dir=*)   REMOTE_DIR="${arg#*=}" ;;
  esac
done

RSYNC_FLAGS="-avz --progress --checksum"
if [ "$DRY_RUN" = true ]; then
  RSYNC_FLAGS="$RSYNC_FLAGS --dry-run"
  echo "⚠️  MODO DRY-RUN: no se escribe nada en disco."
fi

mkdir -p "$LOCAL_DIR/logs"
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  📥 SYNC VPS → LOCAL  |  $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  📡 Fuente : $REMOTE_HOST:$REMOTE_DIR"
echo "  📁 Destino: $LOCAL_DIR"
[ "$DRY_RUN" = true ] && echo "  🔍 DRY-RUN activo"
echo "════════════════════════════════════════════════════════════"

# ── Función helper ─────────────────────────────────────────────────────────────
sync_dir() {
  local label="$1"
  local remote_path="$2"
  local local_path="$3"
  shift 3
  local extra_args=("$@")   # filtros rsync adicionales si se pasan

  echo ""
  echo "▶ Sincronizando: $label"
  mkdir -p "$local_path"
  rsync $RSYNC_FLAGS "${extra_args[@]}" \
      "$REMOTE_HOST:$REMOTE_DIR/$remote_path" \
      "$local_path" \
    && echo "  ✅ OK" \
    || echo "  ⚠️  Advertencia en '$label' (continuando...)"
}

# =============================================================================
# 1. UNIVERSO FINVIZ DIARIO  ← EL MÁS VALIOSO
#    paper_finviz/YYYY-MM-DD/snapshot.json  → captura live completa cada día
#    Con todos los tickers, sus métricas y el veredicto del filtro.
# =============================================================================
sync_dir \
  "paper_finviz/ (snapshots diarios del universo Finviz)" \
  "outputs/paper_finviz/" \
  "$LOCAL_DIR/outputs/paper_finviz/"

# =============================================================================
# 2. TELEGRAM MONITOR  ← BRIEFS PREMARKET + RADAR ROTATION
#    Contiene: market_status.json, premarket_brief.json,
#              prealerts.json, radar_rotation.json, close_summary.json
# =============================================================================
sync_dir \
  "telegram_monitor/ (briefs premarket + radar + alertas)" \
  "outputs/telegram_monitor/" \
  "$LOCAL_DIR/outputs/telegram_monitor/"

# =============================================================================
# 3. LIVE SIGNALS  ← SEÑALES EMITIDAS + REJECTION AUDIT
#    live_signals/YYYY-MM-DD/rejection_audit.csv
#    (muestra qué pasó, qué fue bloqueado y por qué)
# =============================================================================
sync_dir \
  "live_signals/ (señales emitidas + rejection audit)" \
  "outputs/live_signals/" \
  "$LOCAL_DIR/outputs/live_signals/"

# =============================================================================
# 4. PAPER TRADING FINVIZ  ← JOURNAL + POSICIONES
#    paper_finviz/journal.json  → track record acumulado del sistema
# =============================================================================
sync_dir \
  "paper_finviz journal + historial rechazos" \
  "outputs/paper_finviz/journal.json" \
  "$LOCAL_DIR/outputs/paper_finviz/" \
  --ignore-missing-args

sync_dir \
  "paper_finviz rejected_short_history.json" \
  "outputs/paper_finviz/rejected_short_history.json" \
  "$LOCAL_DIR/outputs/paper_finviz/" \
  --ignore-missing-args

# =============================================================================
# 5. LIVE PAPER AUTO (ejecución automática real)
#    live_paper_auto/runs/YYYY-MM-DD/
# =============================================================================
sync_dir \
  "live_paper_auto/ (ejecución automática)" \
  "outputs/live_paper_auto/" \
  "$LOCAL_DIR/outputs/live_paper_auto/"

# =============================================================================
# 6. LOGS DEL VPS  ← PARA AUDITORÍA (solo los de cron, no los de debug)
#    Se bajan solo logs/*.log  (finviz_monitor, post_market)
# =============================================================================
mkdir -p "$LOCAL_DIR/logs/vps"
echo ""
echo "▶ Sincronizando: logs/vps (cron logs)"
rsync $RSYNC_FLAGS \
    --include="cron_*.log" \
    --include="finviz_*.log" \
    --exclude="*" \
    "$REMOTE_HOST:$REMOTE_DIR/logs/" \
    "$LOCAL_DIR/logs/vps/" \
  && echo "  ✅ OK" \
  || echo "  ⚠️  Advertencia en logs (continuando...)"

# =============================================================================
# 7. CONFIG ACTIVA DEL VPS (sin .env, sin secretos)
#    Para detectar drift entre laboratorio y tubo de control.
# =============================================================================
echo ""
echo "▶ Sincronizando: config/ (configuración activa VPS)"
mkdir -p "$LOCAL_DIR/config/vps_snapshot"
rsync $RSYNC_FLAGS \
    --exclude=".env" \
    --exclude="*.secret" \
    "$REMOTE_HOST:$REMOTE_DIR/config/" \
    "$LOCAL_DIR/config/vps_snapshot/" \
  && echo "  ✅ OK" \
  || echo "  ⚠️  Advertencia en config (continuando...)"

# =============================================================================
# RESUMEN FINAL
# =============================================================================
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ SYNC COMPLETADO  |  $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  📋 Log guardado en: $LOG_FILE"
echo ""
echo "  📊 Archivos más relevantes para investigación:"
echo "     outputs/paper_finviz/YYYY-MM-DD/snapshot.json"
echo "     outputs/telegram_monitor/YYYY-MM-DD/market_status.json"
echo "     outputs/live_signals/YYYY-MM-DD/rejection_audit.csv"
echo "════════════════════════════════════════════════════════════"
