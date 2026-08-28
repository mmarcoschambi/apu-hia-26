# Tasks: US-12: Despliegue Continuo Automatizado (CD) hacia el Servidor de Producción

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Configurar secrets DEPLOY_HOST, DEPLOY_SSH_KEY, DEPLOY_PATH, DEPLOY_HEALTH_URL
- [x] 1.2 Definir environment 'production' con URL
- [x] 1.3 Heredar permisos read de packages

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 Release publicado dispara deploy a producción
- [x] 2.3 Healthcheck post-deploy con 10 reintentos (100s)

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
