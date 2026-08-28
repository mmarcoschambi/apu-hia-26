# Tasks: US-07: Despliegue de n8n en Docker Compose con Persistencia y Variables Protegidas

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Declarar servicio n8n-automation con expose: 5678
- [x] 1.2 Configurar DB_TYPE=mysqldb y variables DB_MYSQLDB_*
- [x] 1.3 Conectar a gateway-net y app-network

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 Volumen pmai_n8n_data persiste workflows entre reinicios
- [x] 2.3 Variables N8N_* y MYSQL_* tomadas de .env

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
