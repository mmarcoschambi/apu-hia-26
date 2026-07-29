#!/usr/bin/env bash
# DEPLOY VPS - Professional Environment Separation
# Sube solo los archivos livianos (Finviz, Telegram, Scanner) al VPS.
# Excluye la base de datos local pesada (Laboratory machine).
#
# Usage:
#   ./deploy_vps.sh                          # Deploy normal
#   ./deploy_vps.sh --dry-run                # Simulacion, no ejecuta rsync ni cambios
#   ./deploy_vps.sh --host user@host --dir /path/to/target

set -euo pipefail

# Configuración por defecto
REMOTE_HOST="xxmalcomandaxx@trading-vps.us-central1-f.paper-trading-server"
REMOTE_DIR="/home/xxmalcomandaxx/swing-momentum-v1"
DRY_RUN=false
SKIP_VALIDATION=false

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)
      REMOTE_HOST="$2"
      shift
      shift
      ;;
    --dir)
      REMOTE_DIR="$2"
      shift
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --skip-validation)
      SKIP_VALIDATION=true
      shift
      ;;
    *)
      echo "⚠️  Argumento desconocido: $1"
      shift
      ;;
  esac
done

echo "🚀 Iniciando Deploy a la Torre de Control (VPS)..."
echo "📡 Host: $REMOTE_HOST"
echo "📁 Destino: $REMOTE_DIR"
echo ""

# ── Validación Pre-Deploy ─────────────────────────────────────────────

# 1. Verificar que git no tenga cambios sin commit
echo "🔍 [1/5] Verificando estado de git..."
DIRTY_FILES=$(git status --porcelain 2>/dev/null || true)
if [[ -n "$DIRTY_FILES" ]]; then
  echo "❌ ERROR: Hay cambios sin commitear. Deploy bloqueado."
  echo ""
  echo "Archivos modificados/no trackeados:"
  echo "$DIRTY_FILES"
  echo ""
  echo "👉 Opciones:"
  echo "   a) Commitear los cambios: git add -A && git commit -m \"mensaje\""
  echo "   b) Stashearlos temporalmente: git stash"
  echo "   c) Forzar con --skip-validation (no recomendado)"
  exit 1
fi
echo "   ✅ Git limpio."

# 2. Verificar que no hay commits sin push
echo "🔍 [2/5] Verificando push contra remoto..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
LOCAL_SHA=$(git rev-parse HEAD 2>/dev/null || true)
REMOTE_SHA=$(git rev-parse "origin/$CURRENT_BRANCH" 2>/dev/null || true)

if [[ -z "$REMOTE_SHA" ]]; then
  echo "   ⚠️  No se puede determinar el SHA remoto (¿falta remote tracking?)."
  echo "   ⚠️  Asegurate de haber hecho git push antes del deploy."
elif [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  echo "❌ ERROR: La rama local ($CURRENT_BRANCH) no está sincronizada con origin."
  echo "   Local SHA:  $LOCAL_SHA"
  if [[ -n "$REMOTE_SHA" ]]; then
    echo "   Remote SHA: $REMOTE_SHA"
  fi
  echo ""
  echo "👉 Ejecuta: git push origin $CURRENT_BRANCH"
  exit 1
fi
echo "   ✅ Git push verificado (SHA coincide con remoto)."

# ── Modo Dry-Run ──────────────────────────────────────────────────────
if [[ "$DRY_RUN" == true ]]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "   🏜️  DRY RUN — No se ejecutarán cambios reales"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "Se ejecutaría rsync con:"
  echo "   Host:    $REMOTE_HOST"
  echo "   Destino: $REMOTE_DIR"
  echo "   Exclusiones: .git/, .venv/, __pycache__/, data/*.db*, .env, ..."
  echo ""
  echo "Post-sync se ejecutaría:"
  echo "   - Verificación de imports Python"
  echo "   - Instalación/recarga de systemd units"
  echo "   - Health check post-deploy"
  echo ""
  echo "✅ Dry run completado. No se realizaron cambios."
  exit 0
fi

# ── Rsync ─────────────────────────────────────────────────────────────
echo "🔍 [3/5] Sincronizando archivos al VPS..."
echo "📁 Excluyendo Base de Datos Local y Research para mantener el VPS liviano."

rsync -avz --progress \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.streamli*/' \
    --exclude='data/*.db*' \
    --exclude='data/*.sqlite' \
    --exclude='data/*.pkl' \
    --exclude='data/*.bak*' \
    --exclude='data/*.corrupt*' \
    --exclude='data/*.backup' \
    --exclude='data/cache/' \
    --exclude='data/cache_backups/' \
    --exclude='data/screener_cache/' \
    --exclude='data/backtest_data/' \
    --exclude='data/prices/' \
    --exclude='data/history/' \
    --exclude='data/processed/' \
    --exclude='outputs/' \
    --exclude='quantconnect/' \
    --exclude='sp500/' \
    --exclude='scratch/' \
    --exclude='study/' \
    --exclude='experiments/' \
    --exclude='archive/' \
    --exclude='logs/' \
    --exclude='.env' \
    ./ "$REMOTE_HOST:$REMOTE_DIR"

if [[ $? -ne 0 ]]; then
    echo "❌ ERROR: El deploy falló. Revisa la conexión SSH o el nombre del host."
    exit 1
fi

echo "   ✅ Rsync completado."

# ── Validación Post-Deploy ────────────────────────────────────────────
if [[ "$SKIP_VALIDATION" == false ]]; then
    echo "🔍 [4/5] Verificando imports Python en el VPS..."
    SSH_CMD="ssh $REMOTE_HOST"
    PYTHON_CHECK="cd $REMOTE_DIR && .venv/bin/python -c \"
from src.validation.purged_walk_forward import PurgedWalkForwardValidator;
from src.validation.research_gate import ResearchGate;
from src.optimization.s4_gates import GATE_DEGRADATION;
from scripts.live_auto_trader import main as trader_main;
from scripts.telegram_bot_listener import main as telegram_main;
from scripts.finviz_monitor import main as finviz_main;
print('OK: Todos los imports base verificados.')
\""

    if $SSH_CMD "$PYTHON_CHECK" 2>&1; then
        echo "   ✅ Imports Python verificados en VPS."
    else
        echo "   ⚠️  Advertencia: Algunos imports fallaron en el VPS."
        echo "   ⚠️  Posible dependencia faltante o error de entorno."
    fi

    echo "🔍 [5/5] Instalando/recargando systemd units y verificando salud..."
    SYSTEMD_SETUP="cd $REMOTE_DIR && \
sudo cp scripts/sv/momentum-trader.service /etc/systemd/system/ && \
sudo cp scripts/sv/momentum-telegram.service /etc/systemd/system/ && \
sudo systemctl daemon-reload && \
sudo systemctl enable momentum-trader.service momentum-telegram.service && \
sudo systemctl restart momentum-trader.service momentum-telegram.service && \
echo '✅ systemd units instaladas y servicios reiniciados.'"

    if $SSH_CMD "$SYSTEMD_SETUP" 2>&1; then
        echo "   ✅ systemd units instaladas y recargadas."
    else
        echo "   ⚠️  Advertencia: Error al instalar/recargar systemd units en VPS."
        echo "   ⚠️  Ejecuta manualmente: ssh $REMOTE_HOST 'cd $REMOTE_DIR && sudo systemctl daemon-reload'"
    fi

    # Health check post-deploy
    echo "🔍 Verificando health check post-deploy en VPS..."
    HEALTH_CMD="cd $REMOTE_DIR && bash scripts/sv/health_check.sh --preflight"
    if HEALTH_OUTPUT=$($SSH_CMD "$HEALTH_CMD" 2>&1); then
        echo "   ✅ Health check post-deploy: OK"
        echo "$HEALTH_OUTPUT" | while IFS= read -r line; do echo "      $line"; done
    else
        HEALTH_EXIT=$?
        echo "   ⚠️  Health check post-deploy: exit code $HEALTH_EXIT"
        echo "$HEALTH_OUTPUT" | while IFS= read -r line; do echo "      $line"; done
    fi
else
    echo "🔍 [4/5] Validación post-deploy omitida (--skip-validation)."
    echo "🔍 [5/5] Validación post-deploy omitida (--skip-validation)."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deploy completado con éxito."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  Recuerda que el .env no se sincroniza automáticamente por seguridad."
echo "   Si el health check falla, verifica que el .env existe en el VPS:"
echo "   ssh $REMOTE_HOST 'test -f $REMOTE_DIR/.env && echo \"OK\" || echo \"FALTA .env\"'"
echo ""
echo "💡 Para monitorear servicios en VPS:"
echo "   ssh $REMOTE_HOST 'systemctl status momentum-trader momentum-telegram'"
echo "💡 Para ver health check:"
echo "   ssh $REMOTE_HOST 'cd $REMOTE_DIR && bash scripts/sv/health_check.sh'"
