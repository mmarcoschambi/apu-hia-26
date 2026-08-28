# Proposal: US-12: Despliegue Continuo Automatizado (CD) hacia el Servidor de Producción

## Intent
Workflow deploy-production.yml que al publicarse un release o manualmente: SSH al host, git pull, docker compose pull+up, healthcheck post-deploy con retry, smoke test de ps.

## Scope
- Epic: EP-04
- Sprint: 2
- Story Points: 5
- Status: **Implemented**

## Affected Files
- `.github/workflows/deploy-production.yml`

## Acceptance Criteria
- [ ] Release publicado dispara deploy a producción
- [ ] Healthcheck post-deploy con 10 reintentos (100s)

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
