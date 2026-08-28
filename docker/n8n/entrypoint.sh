#!/usr/bin/env bash
# ==============================================================================
# US-11: Entrypoint de la imagen custom n8n-pmai
# ==============================================================================
# 1) Espera a que MySQL esté healthy (resolución DNS interna en app-network)
# 2) Auto-importa los workflows desde /opt/n8n-workflows/ usando la CLI n8n
# 3) Delega al entrypoint upstream de la imagen oficial
# ==============================================================================
set -Eeuo pipefail

WORKFLOW_DIR="/opt/n8n-workflows"
MYSQL_WAIT_TIMEOUT="${MYSQL_WAIT_TIMEOUT:-60}"

log() { printf '[%s] [entrypoint-pmai] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

# Espera activa de MySQL (best-effort, el healthcheck de compose ya garantiza orden)
if command -v mysqladmin >/dev/null 2>&1; then
    log "Esperando a MySQL (${DB_MYSQLDB_HOST:-mysql}:${DB_MYSQLDB_PORT:-3306})..."
    for i in $(seq 1 "${MYSQL_WAIT_TIMEOUT}"); do
        if mysqladmin ping \
            --host="${DB_MYSQLDB_HOST:-mysql}" \
            --port="${DB_MYSQLDB_PORT:-3306}" \
            --user="${DB_MYSQLDB_USER:-pmai_app}" \
            --password="${DB_MYSQLDB_PASSWORD:-pmai_app_secure_password}" \
            --silent >/dev/null 2>&1; then
            log "MySQL respondiendo (intento ${i})"
            break
        fi
        sleep 1
    done
fi

# Auto-import de workflows (sólo si hay CLI de n8n disponible)
if [ -d "${WORKFLOW_DIR}" ] && command -v n8n >/dev/null 2>&1; then
    shopt -s nullglob
    for wf in "${WORKFLOW_DIR}"/*.json; do
        log "Importando workflow: $(basename "${wf}")"
        n8n import:workflow --input="${wf}" || log "WARN: fallo importando ${wf}"
    done
    shopt -u nullglob
fi

# Handoff al entrypoint upstream
if [ -x "/entrypoint.sh" ]; then
    log "Delegando a entrypoint upstream"
    exec /entrypoint.sh "$@"
fi

# Fallback si la imagen upstream cambia
exec "$@"
