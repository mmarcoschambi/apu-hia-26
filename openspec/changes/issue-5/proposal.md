# Proposal: US-05: Configuración de Schemas, Usuario de Aplicación y Healthchecks

## Intent
Schema pmai_db + tablas productos y eventos_webhook (seed data), usuario pmai_app con permisos mínimos, healthcheck mysqladmin ping.

## Scope
- Epic: EP-02
- Sprint: 1
- Story Points: 2
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:155-165`
- `mysql/init/01-init.sql`

## Acceptance Criteria
- [ ] Tabla productos con 3 registros seed
- [ ] Healthcheck mysqladmin ping pasa en <30s

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
