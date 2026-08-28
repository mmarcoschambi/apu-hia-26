# Proposal: US-02: Despliegue de Nginx Reverse Proxy como Gateway Centralizado

## Intent
Contenedor nginx:1.27-alpine con healthcheck, soporte WebSockets para n8n, endpoint /healthz, variables GATEWAY_HTTP_PORT/HTTPS_PORT.

## Scope
- Epic: EP-01
- Sprint: 1
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `docker-compose.yml:31-50`
- `nginx/nginx.conf`

## Acceptance Criteria
- [ ] `docker compose ps nginx-gateway` muestra estado running/healthy
- [ ] `curl http://localhost/healthz` responde 200 con JSON
- [ ] WebSocket handshake (Upgrade) hacia n8n_backend funciona

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
