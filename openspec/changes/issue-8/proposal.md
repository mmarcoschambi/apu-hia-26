# Proposal: US-08: Integración Nativa de n8n con MySQL mediante Resolución DNS Interna

## Intent
DB_MYSQLDB_HOST=mysql resuelve internamente gracias a los aliases del servicio MySQL. Cero exposición de 3306 al host.

## Scope
- Epic: EP-03
- Sprint: 1
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:69-72`
- `docker-compose.yml:131-141`

## Acceptance Criteria
- [ ] `docker compose exec n8n-automation nslookup mysql` resuelve al contenedor

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
