#!/usr/bin/env bash
# ==============================================================================
# US-14: Healthcheck integral del stack
# ==============================================================================
# Reporta el estado de cada servicio y verifica endpoints clave.
# Salida: tabla formateada con estado (healthy/unhealthy) y exit code agregador.
# ==============================================================================
set -Eeuo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
EXPECTED_SERVICES=("nginx-gateway" "n8n-automation" "mysql" "mysql-backup")

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker no está instalado o no está en PATH" >&2
    exit 2
fi

echo "================================================================"
echo "  PMA-Docker 2026 - Healthcheck de Stack"
echo "  $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo "================================================================"

fail_count=0
for svc in "${EXPECTED_SERVICES[@]}"; do
    state=$(docker compose -f "${COMPOSE_FILE}" ps --format json "${svc}" 2>/dev/null \
        | jq -r 'if type == "array" then .[0].State else .State end' 2>/dev/null || echo "missing")
    health=$(docker compose -f "${COMPOSE_FILE}" ps --format json "${svc}" 2>/dev/null \
        | jq -r 'if type == "array" then .[0].Health else .Health end' 2>/dev/null || echo "n/a")

    status="${state:-unknown}/${health:-n/a}"
    case "${health}" in
        healthy)        marker="✅" ;;
        starting)       marker="⏳" ;;
        unhealthy)      marker="❌"; fail_count=$((fail_count + 1)) ;;
        *)              marker="⚠️ " ;;
    esac
    printf "  %s  %-18s  %-12s  %s\n" "${marker}" "${svc}" "${state}" "${health}"
done

echo "----------------------------------------------------------------"
# Endpoints externos
gateway_url="${HEALTHCHECK_GATEWAY_URL:-http://localhost/healthz}"
if curl --fail --silent --max-time 5 "${gateway_url}" >/dev/null; then
    echo "  ✅  Gateway healthz      ${gateway_url}"
else
    echo "  ❌  Gateway healthz      ${gateway_url} (no responde)"
    fail_count=$((fail_count + 1))
fi

echo "================================================================"
if [ "${fail_count}" -gt 0 ]; then
    echo "  RESULTADO: ${fail_count} servicio(s) con problemas"
    exit 1
fi
echo "  RESULTADO: stack saludable"
exit 0
