#!/usr/bin/env bash
# ==============================================================================
# Script invocado por el workflow deploy-production.yml (server-side)
# No se ejecuta localmente; recibe DEPLOY_PATH y IMAGE_TAG como argumentos.
# ==============================================================================
set -Eeuo pipefail

DEPLOY_PATH="${1:?Falta DEPLOY_PATH}"
IMAGE_TAG="${2:-main}"

cd "${DEPLOY_PATH}" || { echo "ERROR: no existe ${DEPLOY_PATH}" >&2; exit 1; }

echo "[deploy] Path: ${DEPLOY_PATH}"
echo "[deploy] Ref:  ${IMAGE_TAG}"

echo "[deploy] Fetch & checkout"
git fetch --tags --prune
if git show-ref --verify --quiet "refs/tags/${IMAGE_TAG}"; then
    git checkout --quiet "tags/${IMAGE_TAG}"
else
    git checkout --quiet "${IMAGE_TAG}"
    git pull --rebase --autostash
fi

if [ ! -f .env ]; then
    echo "ERROR: .env ausente en host" >&2
    exit 1
fi

echo "[deploy] Cargando .env (sin export a logs)"
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "[deploy] Pull de imágenes"
docker compose pull --ignore-pull-failures

echo "[deploy] Up stack"
docker compose up -d --remove-orphans

echo "[deploy] Healthcheck local"
for i in 1 2 3 4 5; do
    if curl --fail --silent --max-time 5 "http://127.0.0.1/healthz" >/dev/null; then
        echo "OK: stack respondiendo"
        exit 0
    fi
    sleep 5
done

echo "WARN: healthcheck no respondió localmente (puede ser normal si el gateway está tras otro proxy)"
exit 0
