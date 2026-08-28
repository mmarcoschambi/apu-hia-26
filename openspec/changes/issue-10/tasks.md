# Tasks: US-10: Pipeline de GitHub Actions para Validación de Compose, Linting y Tests

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Crear .github/workflows/ci-validation.yml
- [x] 1.2 Configurar .yamllint.yml
- [x] 1.3 Documentar uso de yq para introspección

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 PR a main dispara ci-validation
- [x] 2.3 Falla si MySQL publica puertos o si app-network no es internal

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
