# Tasks: US-15: Gestión Centralizada de Secretos y Variables de Entorno Seguras

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Definir .env.example con placeholders seguros
- [x] 1.2 Excluir .env, secrets/, certs/ en .gitignore
- [x] 1.3 Agregar job trufflehog al pipeline CI

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 .env no aparece en `git status` ni en commits
- [x] 2.3 Trufflehog falla el build si detecta secretos verificados

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
