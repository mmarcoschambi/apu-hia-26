# Proposal: US-03: Configuración de Redes Aisladas y Políticas de Reinicio Automático

## Intent
Tres redes bridge: gateway-net (pública), app-network (internal: true para n8n+MySQL), backup-network (internal: true para mysql-backup). Restart unless-stopped en todos los servicios.

## Scope
- Epic: EP-01
- Sprint: 2
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:14-39`

## Acceptance Criteria
- [ ] `docker network inspect pmai_app_net` reporta Internal: true
- [ ] Restart policy = unless-stopped en todos los servicios

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
