# Tasks: US-09: Implementación de Flujo de Webhooks y Alertas Automáticas

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Definir workflow JSON con nodos Webhook, IF, MySQL, SMTP
- [x] 1.2 Montar workflows/ en n8n container
- [x] 1.3 Configurar N8N_SMTP_* en .env

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 POST /webhook/pmai-alerts responde 200 con JSON
- [x] 2.3 Eventos con severity=critical disparan email

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
