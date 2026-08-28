#!/usr/bin/env bash
# ==============================================================================
# Lint local: valida docker-compose.yml con y sin .env.example
# ==============================================================================
set -Eeuo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

echo "[lint] Validando ${COMPOSE_FILE} sin .env"
docker compose -f "${COMPOSE_FILE}" config --quiet

echo "[lint] Validando con .env.example"
TMP_ENV="$(mktemp)"
cp .env.example "${TMP_ENV}"
docker compose --env-file "${TMP_ENV}" -f "${COMPOSE_FILE}" config --quiet
rm -f "${TMP_ENV}"

echo "[lint] Verificando aislamiento de MySQL"
if docker compose -f "${COMPOSE_FILE}" config | yq -e '.services.mysql.ports // [] | length > 0' >/dev/null 2>&1; then
    echo "FAIL: MySQL publica puertos al host" >&2
    exit 1
fi
echo "OK: MySQL sólo usa 'expose' (sin ports en host)"

echo "[lint] Verificando internal: true en app-network"
if ! docker compose -f "${COMPOSE_FILE}" config | yq -e '.networks."app-network".internal == true' >/dev/null 2>&1; then
    echo "FAIL: app-network no tiene internal: true" >&2
    exit 1
fi
echo "OK: app-network con internal: true"

echo "[lint] Todos los chequeos pasaron"
