#!/usr/bin/env bash
# =============================================================================
# WEEKLY ARCHIVE VPS
# Propósito: Comprimir la semana de datos en el VPS antes de que el lab haga
#            el sync del viernes. Corre a las 17:00 NY los viernes.
#
# Qué hace:
#   1. Comprime los directorios de outputs más pesados del día/semana en un
#      .tar.gz con fecha, guardado en outputs/backups/
#   2. Elimina el paper_finviz/monitoring/ de semanas anteriores (muy pesado)
#   3. Deja los 7 días más recientes de cada carpeta intactos para el sync
#
# NOTA: Este script corre EN EL VPS. Se sube con deploy_vps.sh.
# =============================================================================

set -euo pipefail

# Auto-detectar raíz del proyecto (funciona en VPS y local)
# El script vive en <proyecto>/deploy/weekly_archive_vps.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT/outputs/backups"
WEEK=$(date +%Y-W%V)   # ej: 2026-W21
LOG="$PROJECT/logs/cron_weekly_archive.log"

mkdir -p "$BACKUP_DIR"
echo ""
echo "════════════════════════════════════════"
echo "  📦 WEEKLY ARCHIVE  |  $(date '+%Y-%m-%d %H:%M') NY"
echo "  Semana: $WEEK"
echo "════════════════════════════════════════"

# ── 1. Comprimir monitoring/ de paper_finviz (muy pesado, muchos archivos) ───
MONITORING_DIR="$PROJECT/outputs/paper_finviz/monitoring"
if [ -d "$MONITORING_DIR" ] && [ "$(ls -A $MONITORING_DIR)" ]; then
    TAR_PATH="$BACKUP_DIR/paper_finviz_monitoring_${WEEK}.tar.gz"
    echo "▶ Comprimiendo paper_finviz/monitoring/ → $(basename $TAR_PATH)"
    tar -czf "$TAR_PATH" -C "$PROJECT/outputs/paper_finviz" monitoring/
    # Limpiar archivos individuales después de comprimir
    rm -f "$MONITORING_DIR"/*.csv "$MONITORING_DIR"/*.json
    echo "  ✅ OK - $(du -sh $TAR_PATH | cut -f1)"
fi

# ── 2. Eliminar backups con más de 4 semanas (mantener 1 mes) ─────────────────
echo "▶ Eliminando backups de más de 30 días..."
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
echo "  ✅ OK"

# ── 3. Limpieza segura de snapshots antiguos de Finviz (>30 días) ────────────
#     Conserva los últimos 30 días de snapshots diarios para que el sync local
#     tenga margen de sobra para descargarlos aunque falle un día.
echo "▶ Eliminando snapshots de Finviz más viejos de 30 días..."
FINVIZ_DIR="$PROJECT/outputs/paper_finviz"
find "$FINVIZ_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
echo "  ✅ OK"

# ── 4. Rotación de logs de cron > 14 días ────────────────────────────────────
echo "▶ Rotando logs de cron > 14 días..."
find "$PROJECT/logs" -name "cron_*.log" -mtime +14 -delete
echo "  ✅ OK"

echo ""
echo "  📊 Estado actual del disco:"
du -sh "$PROJECT/outputs/"*/ 2>/dev/null | sort -h | tail -10
echo ""
echo "  📦 Backups guardados:"
ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "  (ninguno aún)"
echo ""
echo "════════════════════════════════════════"
echo "  ✅ ARCHIVE COMPLETADO  |  $(date '+%H:%M')"
echo "════════════════════════════════════════"
