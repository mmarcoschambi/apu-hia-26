# Proposal: US-04: Despliegue de MySQL 8.0 con Volumen Persistente y Aislamiento expose: 3306

## Intent
MySQL 8.0.36 con volume pmai_mysql_data, expose: ['3306'] (sin ports), conectado sólo a app-network y backup-network.

## Scope
- Epic: EP-02
- Sprint: 1
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:131-167`

## Acceptance Criteria
- [ ] MySQL no escucha en 0.0.0.0:3306 del host
- [ ] Alias DNS 'mysql' y 'mysql-db' resuelven dentro de app-network

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
