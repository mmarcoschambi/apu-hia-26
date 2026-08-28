# Tasks: US-11: Pipeline de Construcción de Imágenes Docker y Publicación en GHCR

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Crear Dockerfile custom con COPY de workflows
- [x] 1.2 Crear entrypoint.sh con wait-MySQL + auto-import
- [x] 1.3 Configurar workflow con metadata-action + build-push-action

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 Push a main publica tag 'latest' en ghcr.io
- [x] 2.3 Tag vX.Y.Z publica versión semántica

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
