# Tasks: US-03: Configuración de Redes Aisladas y Políticas de Reinicio Automático

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Definir gateway-net, app-network (internal), backup-network (internal)
- [x] 1.2 Adjuntar cada servicio a su red correspondiente
- [x] 1.3 Configurar restart: unless-stopped en todos los servicios

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 `docker network inspect pmai_app_net` reporta Internal: true
- [x] 2.3 Restart policy = unless-stopped en todos los servicios

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
