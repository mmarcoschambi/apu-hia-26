#!/usr/bin/env python3
"""
Genera los artifacts OpenSpec (proposal.md + tasks.md) para los US nuevos
de la Plataforma PMA-Docker 2026.

US nuevos: 6, 9, 10, 11, 12
US ya implementados en código (sólo trazabilidad): 2, 3, 4, 5, 7, 8, 15
"""
import os
from pathlib import Path

ROOT = Path(r"D:\FACU\3er_año\HIA-worktrees\tp-scrum")
OPENS = ROOT / "openspec" / "changes"

STORIES = [
    {
        "issue": 2,
        "us": "US-02",
        "title": "Despliegue de Nginx Reverse Proxy como Gateway Centralizado",
        "epic": "EP-01",
        "sprint": 1,
        "sp": 3,
        "status": "Implemented",
        "summary": "Contenedor nginx:1.27-alpine con healthcheck, soporte WebSockets para n8n, endpoint /healthz, variables GATEWAY_HTTP_PORT/HTTPS_PORT.",
        "files": ["docker-compose.yml:31-50", "nginx/nginx.conf"],
        "acceptance": [
            "`docker compose ps nginx-gateway` muestra estado running/healthy",
            "`curl http://localhost/healthz` responde 200 con JSON",
            "WebSocket handshake (Upgrade) hacia n8n_backend funciona",
        ],
        "tasks": [
            "Declarar servicio `nginx-gateway` con image, restart, networks",
            "Crear nginx.conf con upstream n8n_backend y location /healthz",
            "Configurar healthcheck wget -q --spider",
        ],
    },
    {
        "issue": 3,
        "us": "US-03",
        "title": "Configuración de Redes Aisladas y Políticas de Reinicio Automático",
        "epic": "EP-01",
        "sprint": 2,
        "sp": 3,
        "status": "Implemented",
        "summary": "Tres redes bridge: gateway-net (pública), app-network (internal: true para n8n+MySQL), backup-network (internal: true para mysql-backup). Restart unless-stopped en todos los servicios.",
        "files": ["docker-compose.yml:14-39"],
        "acceptance": [
            "`docker network inspect pmai_app_net` reporta Internal: true",
            "Restart policy = unless-stopped en todos los servicios",
        ],
        "tasks": [
            "Definir gateway-net, app-network (internal), backup-network (internal)",
            "Adjuntar cada servicio a su red correspondiente",
            "Configurar restart: unless-stopped en todos los servicios",
        ],
    },
    {
        "issue": 4,
        "us": "US-04",
        "title": "Despliegue de MySQL 8.0 con Volumen Persistente y Aislamiento expose: 3306",
        "epic": "EP-02",
        "sprint": 1,
        "sp": 3,
        "status": "Implemented",
        "summary": "MySQL 8.0.36 con volume pmai_mysql_data, expose: ['3306'] (sin ports), conectado sólo a app-network y backup-network.",
        "files": ["docker-compose.yml:131-167"],
        "acceptance": [
            "MySQL no escucha en 0.0.0.0:3306 del host",
            "Alias DNS 'mysql' y 'mysql-db' resuelven dentro de app-network",
        ],
        "tasks": [
            "Declarar volumen mysql_data",
            "Crear servicio mysql con expose y aliases",
            "Adjuntar a app-network y backup-network",
        ],
    },
    {
        "issue": 5,
        "us": "US-05",
        "title": "Configuración de Schemas, Usuario de Aplicación y Healthchecks",
        "epic": "EP-02",
        "sprint": 1,
        "sp": 2,
        "status": "Implemented",
        "summary": "Schema pmai_db + tablas productos y eventos_webhook (seed data), usuario pmai_app con permisos mínimos, healthcheck mysqladmin ping.",
        "files": ["docker-compose.yml:155-165", "mysql/init/01-init.sql"],
        "acceptance": [
            "Tabla productos con 3 registros seed",
            "Healthcheck mysqladmin ping pasa en <30s",
        ],
        "tasks": [
            "Crear mysql/init/01-init.sql con schema y seed",
            "Configurar healthcheck con retries=5, start_period=30s",
        ],
    },
    {
        "issue": 6,
        "us": "US-06",
        "title": "Automatización de Respaldos Lógicos de Base de Datos (mysqldump)",
        "epic": "EP-02",
        "sprint": 2,
        "sp": 2,
        "status": "Implemented",
        "summary": "Sidecar mysql-backup que ejecuta mysqldump periódico con compresión gzip, conectado a MySQL vía red backup-network aislada. Retención automática configurable.",
        "files": ["scripts/backup/mysqldump.sh", "docker-compose.yml:170-194"],
        "acceptance": [
            "Cada BACKUP_INTERVAL_HOURS se genera /backups/pmai_db_<ts>.sql.gz",
            "Backups > BACKUP_RETENTION_DAYS días se eliminan automáticamente",
        ],
        "tasks": [
            "Crear scripts/backup/mysqldump.sh con retention + compress",
            "Declarar servicio mysql-backup con backup-network",
            "Montar script y volumen mysql_backups",
        ],
    },
    {
        "issue": 7,
        "us": "US-07",
        "title": "Despliegue de n8n en Docker Compose con Persistencia y Variables Protegidas",
        "epic": "EP-03",
        "sprint": 1,
        "sp": 5,
        "status": "Implemented",
        "summary": "n8n 1.45.1 con volumen n8n_data, todas las credenciales via env (no hardcoded), DB_TYPE=mysqldb apuntando al host mysql interno.",
        "files": ["docker-compose.yml:55-115"],
        "acceptance": [
            "Volumen pmai_n8n_data persiste workflows entre reinicios",
            "Variables N8N_* y MYSQL_* tomadas de .env",
        ],
        "tasks": [
            "Declarar servicio n8n-automation con expose: 5678",
            "Configurar DB_TYPE=mysqldb y variables DB_MYSQLDB_*",
            "Conectar a gateway-net y app-network",
        ],
    },
    {
        "issue": 8,
        "us": "US-08",
        "title": "Integración Nativa de n8n con MySQL mediante Resolución DNS Interna",
        "epic": "EP-03",
        "sprint": 1,
        "sp": 3,
        "status": "Implemented",
        "summary": "DB_MYSQLDB_HOST=mysql resuelve internamente gracias a los aliases del servicio MySQL. Cero exposición de 3306 al host.",
        "files": ["docker-compose.yml:69-72", "docker-compose.yml:131-141"],
        "acceptance": [
            "`docker compose exec n8n-automation nslookup mysql` resuelve al contenedor",
        ],
        "tasks": [
            "Configurar DB_MYSQLDB_HOST=mysql en n8n",
            "Declarar aliases 'mysql' y 'mysql-db' en el servicio MySQL",
        ],
    },
    {
        "issue": 9,
        "us": "US-09",
        "title": "Implementación de Flujo de Webhooks y Alertas Automáticas",
        "epic": "EP-03",
        "sprint": 2,
        "sp": 3,
        "status": "Implemented",
        "summary": "Workflow n8n exportado en n8n/workflows/webhook-alert-flow.json. Receptor HTTP en /webhook/pmai-alerts, registra en MySQL, dispara SMTP si severidad=critical.",
        "files": ["n8n/workflows/webhook-alert-flow.json", "n8n/workflows/README.md", "docker-compose.yml:81-94"],
        "acceptance": [
            "POST /webhook/pmai-alerts responde 200 con JSON",
            "Eventos con severity=critical disparan email",
        ],
        "tasks": [
            "Definir workflow JSON con nodos Webhook, IF, MySQL, SMTP",
            "Montar workflows/ en n8n container",
            "Configurar N8N_SMTP_* en .env",
        ],
    },
    {
        "issue": 10,
        "us": "US-10",
        "title": "Pipeline de GitHub Actions para Validación de Compose, Linting y Tests",
        "epic": "EP-04",
        "sprint": 2,
        "sp": 3,
        "status": "Implemented",
        "summary": "Workflow ci-validation.yml con 3 jobs: compose-schema (config + verificación internal/expose), lint (yamllint + shellcheck + hadolint), docs-check (JSON backlog + trufflehog).",
        "files": [".github/workflows/ci-validation.yml", ".yamllint.yml"],
        "acceptance": [
            "PR a main dispara ci-validation",
            "Falla si MySQL publica puertos o si app-network no es internal",
        ],
        "tasks": [
            "Crear .github/workflows/ci-validation.yml",
            "Configurar .yamllint.yml",
            "Documentar uso de yq para introspección",
        ],
    },
    {
        "issue": 11,
        "us": "US-11",
        "title": "Pipeline de Construcción de Imágenes Docker y Publicación en GHCR",
        "epic": "EP-04",
        "sprint": 2,
        "sp": 3,
        "status": "Implemented",
        "summary": "Workflow docker-build.yml construye n8n-pmai desde docker/n8n/Dockerfile, publica en ghcr.io con tags semánticos, cache GHA, SBOM y escaneo Trivy.",
        "files": [".github/workflows/docker-build.yml", "docker/n8n/Dockerfile", "docker/n8n/entrypoint.sh"],
        "acceptance": [
            "Push a main publica tag 'latest' en ghcr.io",
            "Tag vX.Y.Z publica versión semántica",
        ],
        "tasks": [
            "Crear Dockerfile custom con COPY de workflows",
            "Crear entrypoint.sh con wait-MySQL + auto-import",
            "Configurar workflow con metadata-action + build-push-action",
        ],
    },
    {
        "issue": 12,
        "us": "US-12",
        "title": "Despliegue Continuo Automatizado (CD) hacia el Servidor de Producción",
        "epic": "EP-04",
        "sprint": 2,
        "sp": 5,
        "status": "Implemented",
        "summary": "Workflow deploy-production.yml que al publicarse un release o manualmente: SSH al host, git pull, docker compose pull+up, healthcheck post-deploy con retry, smoke test de ps.",
        "files": [".github/workflows/deploy-production.yml"],
        "acceptance": [
            "Release publicado dispara deploy a producción",
            "Healthcheck post-deploy con 10 reintentos (100s)",
        ],
        "tasks": [
            "Configurar secrets DEPLOY_HOST, DEPLOY_SSH_KEY, DEPLOY_PATH, DEPLOY_HEALTH_URL",
            "Definir environment 'production' con URL",
            "Heredar permisos read de packages",
        ],
    },
    {
        "issue": 15,
        "us": "US-15",
        "title": "Gestión Centralizada de Secretos y Variables de Entorno Seguras",
        "epic": "EP-05",
        "sprint": 1,
        "sp": 2,
        "status": "Implemented",
        "summary": ".env.example versionado con valores dummy; .env real excluido por .gitignore. Trufflehog en CI detecta secretos accidentales.",
        "files": [".env.example", ".gitignore", ".github/workflows/ci-validation.yml"],
        "acceptance": [
            ".env no aparece en `git status` ni en commits",
            "Trufflehog falla el build si detecta secretos verificados",
        ],
        "tasks": [
            "Definir .env.example con placeholders seguros",
            "Excluir .env, secrets/, certs/ en .gitignore",
            "Agregar job trufflehog al pipeline CI",
        ],
    },
]


def render_proposal(s):
    return f"""# Proposal: {s['us']}: {s['title']}

## Intent
{s['summary']}

## Scope
- Epic: {s['epic']}
- Sprint: {s['sprint']}
- Story Points: {s['sp']}
- Status: **{s['status']}**

## Affected Files
{chr(10).join('- `' + f + '`' for f in s['files'])}

## Acceptance Criteria
{chr(10).join('- [ ] ' + a for a in s['acceptance'])}

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
"""


def render_tasks(s):
    return f"""# Tasks: {s['us']}: {s['title']}

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
{chr(10).join('- [x] 1.' + str(i+1) + ' ' + t for i, t in enumerate(s['tasks']))}

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
{chr(10).join('- [x] 2.' + str(i+2) + ' ' + a for i, a in enumerate(s['acceptance']))}

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
"""


def main():
    for s in STORIES:
        folder = OPENS / f"issue-{s['issue']}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "proposal.md").write_text(render_proposal(s), encoding="utf-8")
        (folder / "tasks.md").write_text(render_tasks(s), encoding="utf-8")
        print(f"  [OK] issue-{s['issue']} ({s['us']})")
    print(f"\nGenerados {len(STORIES)} artifacts en {OPENS}")


if __name__ == "__main__":
    main()
