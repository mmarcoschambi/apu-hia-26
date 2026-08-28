# Proposal: US-10: Pipeline de GitHub Actions para Validación de Compose, Linting y Tests

## Intent
Workflow ci-validation.yml con 3 jobs: compose-schema (config + verificación internal/expose), lint (yamllint + shellcheck + hadolint), docs-check (JSON backlog + trufflehog).

## Scope
- Epic: EP-04
- Sprint: 2
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `.github/workflows/ci-validation.yml`
- `.yamllint.yml`

## Acceptance Criteria
- [ ] PR a main dispara ci-validation
- [ ] Falla si MySQL publica puertos o si app-network no es internal

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
