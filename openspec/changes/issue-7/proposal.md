# Proposal: US-07: Despliegue de n8n en Docker Compose con Persistencia y Variables Protegidas

## Intent
n8n 1.45.1 con volumen n8n_data, todas las credenciales via env (no hardcoded), DB_TYPE=mysqldb apuntando al host mysql interno.

## Scope
- Epic: EP-03
- Sprint: 1
- Story Points: 5
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:55-115`

## Acceptance Criteria
- [ ] Volumen pmai_n8n_data persiste workflows entre reinicios
- [ ] Variables N8N_* y MYSQL_* tomadas de .env

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
