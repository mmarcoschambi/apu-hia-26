#!/usr/bin/env bash
# ==============================================================================
# US-06: mysqldump - Copia lógica automatizada de base de datos MySQL
# ==============================================================================
# Genera un dump comprimido .sql.gz con timestamp y aplica una política de
# retención eliminando los archivos más antiguos que BACKUP_RETENTION_DAYS.
# Diseñado para correr como sidecar periódico (cada BACKUP_INTERVAL_HOURS).
# ==============================================================================
set -Eeuo pipefail

# --- Configuración desde entorno (con defaults seguros) ---
: "${MYSQL_HOST:=mysql}"
: "${MYSQL_PORT:=3306}"
: "${MYSQL_DATABASE:=pmai_db}"
: "${MYSQL_USER:?ERROR: MYSQL_USER no está definido}"
: "${MYSQL_PASSWORD:?ERROR: MYSQL_PASSWORD no está definido}"

: "${BACKUP_DIR:=/backups}"
: "${BACKUP_RETENTION_DAYS:=7}"
: "${BACKUP_INTERVAL_HOURS:=24}"
: "${BACKUP_COMPRESS:=gzip}"
: "${BACKUP_RUN_ONCE:=false}"

mkdir -p "${BACKUP_DIR}"

log() {
    printf '[%s] [backup] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run_backup() {
    local timestamp
    timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
    local filename="${BACKUP_DIR}/${MYSQL_DATABASE}_${timestamp}.sql.gz"
    local tmpfile
    tmpfile="$(mktemp --suffix=.sql)"

    log "Iniciando dump lógico de '${MYSQL_DATABASE}' desde ${MYSQL_HOST}:${MYSQL_PORT}"

    # mysqldump con opciones para dump consistente y reproducible
    if mysqldump \
        --host="${MYSQL_HOST}" \
        --port="${MYSQL_PORT}" \
        --user="${MYSQL_USER}" \
        --password="${MYSQL_PASSWORD}" \
        --single-transaction \
        --quick \
        --routines \
        --triggers \
        --events \
        --hex-blob \
        --default-character-set=utf8mb4 \
        --set-gtid-purged=OFF \
        --no-tablespaces \
        "${MYSQL_DATABASE}" > "${tmpfile}"; then

        ${BACKUP_COMPRESS} -9 < "${tmpfile}" > "${filename}"
        rm -f "${tmpfile}"

        local size
        size="$(du -h "${filename}" | cut -f1)"
        log "Backup completado: $(basename "${filename}") (${size})"

        apply_retention
    else
        local rc=$?
        rm -f "${tmpfile}"
        log "ERROR: mysqldump falló con código ${rc}"
        return "${rc}"
    fi
}

apply_retention() {
    local deleted
    deleted=$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${MYSQL_DATABASE}_*.sql.gz" \
        -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete | wc -l)
    if [ "${deleted}" -gt 0 ]; then
        log "Retención aplicada: ${deleted} archivo(s) > ${BACKUP_RETENTION_DAYS} días eliminado(s)"
    fi
}

# --- Bucle principal ---
log "Servicio de backup inicializado (intervalo=${BACKUP_INTERVAL_HOURS}h, retención=${BACKUP_RETENTION_DAYS}d)"

if [ "${BACKUP_RUN_ONCE}" = "true" ]; then
    run_backup
    exit $?
fi

while true; do
    if run_backup; then
        log "Próximo backup en ${BACKUP_INTERVAL_HOURS}h"
    else
        log "Reintentando en 1h tras fallo"
        sleep 3600
        continue
    fi
    # shellcheck disable=SC2034
    SECONDS=$((BACKUP_INTERVAL_HOURS * 3600))
    sleep "${SECONDS}" &
    wait $!
done
