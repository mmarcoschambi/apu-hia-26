# Tasks: US-02: Despliegue de Nginx Reverse Proxy como Gateway Centralizado

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Declarar servicio `nginx-gateway` con image, restart, networks
- [x] 1.2 Crear nginx.conf con upstream n8n_backend y location /healthz
- [x] 1.3 Configurar healthcheck wget -q --spider

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 `docker compose ps nginx-gateway` muestra estado running/healthy
- [x] 2.3 `curl http://localhost/healthz` responde 200 con JSON
- [x] 2.4 WebSocket handshake (Upgrade) hacia n8n_backend funciona

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
