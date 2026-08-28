# Herramientas Informáticas Avanzadas (HIA 2026) — APU / UNJu

## 📌 Trabajo Práctico: Gestión Ágil de Proyectos con Scrum e Inteligencia Artificial

Este repositorio contiene la planificación metodológica, documentación técnica y artefactos declarativos de la **Plataforma Modular de Automatización y Microservicios Cloud con Docker (PMA-Docker 2026)** para la carrera de *Analista Programador Universitario (Facultad de Ingeniería – Universidad Nacional de Jujuy)*.

---

## 👥 Scrum Team

- **Product Owner (Puro Negocio):** Marcos (APU-08421)
- **Scrum Master & Backend Dev:** Integrante 2 (APU-08512)
- **Developer & DevOps/QA:** Integrante 3 (APU-08633)

---

## 📁 Estructura del Repositorio

```
.
├── docker-compose.yml                      # Orquestación declarativa completa (Nginx, n8n, MySQL, mysql-backup)
├── docker-compose.override.yml.example     # Plantilla para desarrollo local (127.0.0.1:3306)
├── .env.example                            # Variables de entorno documentadas
├── .gitignore                              # Exclusión de secretos, overrides y datos
├── .yamllint.yml                           # Config de lint para CI
├── nginx/
│   └── nginx.conf                          # Gateway Proxy inverso + soporte WebSockets
├── mysql/
│   └── init/
│       └── 01-init.sql                     # Schema inicial y seed data
├── n8n/
│   └── workflows/
│       ├── README.md                       # Guía de importación de workflows
│       └── webhook-alert-flow.json         # Workflow US-09 (receptor + alerta SMTP)
├── docker/
│   └── n8n/
│       ├── Dockerfile                      # Imagen custom n8n-pmai con auto-import
│       ├── entrypoint.sh                   # Espera MySQL + handoff upstream
│       └── README.md
├── scripts/
│   ├── backup/mysqldump.sh                 # US-06: dump lógico periódico
│   ├── lint/compose-lint.sh                # Validación local equivalente a CI
│   ├── lint/yamllint.sh                    # (stub)
│   ├── health/compose-health.sh            # US-14: healthcheck de stack
│   ├── deploy/deploy.sh                    # US-12: deploy server-side
│   ├── gen-openspec.py                     # Generador de artifacts SDD
│   └── validate-compose.py                 # Validador estructural de compose
├── .github/
│   └── workflows/
│       ├── ci-validation.yml               # US-10: pipeline CI (lint + compose + secrets)
│       ├── docker-build.yml                # US-11: build + push a GHCR
│       └── deploy-production.yml           # US-12: CD a servidor de producción
├── docs/
│   ├── enunciados/                         # Enunciado oficial de la cátedra
│   ├── teoria/                             # Apuntes de cátedra y manuales Scrum
│   ├── runbooks/                           # Guías operativas
│   ├── informe_tp_scrum_2026.md            # Informe maestro integral (26 SP)
│   ├── citas_teoria_desarrollo_scrum.md    # Mapeo epistemológico
│   ├── tablero_scrum_backlog.json          # Backlog Scrum en JSON
│   └── walkthrough.md                      # Resumen ejecutivo
├── openspec/
│   └── changes/
│       ├── issue-1/                        # US-01: orquestación base
│       ├── issue-2/                        # US-02: Nginx gateway
│       ├── issue-3/                        # US-03: redes aisladas
│       ├── issue-4/                        # US-04: MySQL persistente
│       ├── issue-5/                        # US-05: schemas + healthchecks
│       ├── issue-6/                        # US-06: backups mysqldump
│       ├── issue-7/                        # US-07: n8n deployment
│       ├── issue-8/                        # US-08: n8n+MySQL DNS
│       ├── issue-9/                        # US-09: webhooks + alertas
│       ├── issue-10/                       # US-10: pipeline CI
│       ├── issue-11/                       # US-11: build GHCR
│       ├── issue-12/                       # US-12: CD producción
│       └── issue-15/                       # US-15: secretos centralizados
└── README.md
```

---

## 🚀 Despliegue del Entorno de Microservicios

### 1. Configurar variables
```bash
cp .env.example .env
# Editar .env con secretos reales (NUNCA commitear)
```

### 2. Levantar el stack
```bash
docker compose up -d
```

### 3. Acceso
- **Gateway Web:** `http://localhost`
- **Healthcheck Gateway:** `http://localhost/healthz`
- **Healthcheck Stack:** `bash scripts/health/compose-health.sh`
- **Base de Datos:** Aislada internamente en `app-network` (`internal: true`).

### 4. Validar aislamiento
```bash
bash scripts/lint/compose-lint.sh
```

---

## 🔐 Historias de Usuario Implementadas

| US | Título | Estado | Artefacto clave |
|----|--------|--------|-----------------|
| US-01 | Orquestación base con Docker Compose v2 | ✅ Done | `docker-compose.yml` |
| US-02 | Nginx Reverse Proxy como Gateway | ✅ Done | `nginx/nginx.conf` |
| US-03 | Redes aisladas y restart policies | ✅ Done | `docker-compose.yml` (3 redes) |
| US-04 | MySQL 8.0 con volumen persistente | ✅ Done | `docker-compose.yml` (mysql) |
| US-05 | Schemas, usuario app, healthchecks | ✅ Done | `mysql/init/01-init.sql` |
| US-06 | **Backups mysqldump automatizados** | ✅ Done | `scripts/backup/mysqldump.sh` |
| US-07 | n8n en Docker Compose | ✅ Done | `docker-compose.yml` (n8n) |
| US-08 | Integración n8n+MySQL vía DNS | ✅ Done | aliases `mysql`, `mysql-db` |
| US-09 | **Webhooks y alertas SMTP** | ✅ Done | `n8n/workflows/webhook-alert-flow.json` |
| US-10 | **Pipeline CI validación** | ✅ Done | `.github/workflows/ci-validation.yml` |
| US-11 | **Build imágenes + GHCR** | ✅ Done | `.github/workflows/docker-build.yml` |
| US-12 | **CD a producción** | ✅ Done | `.github/workflows/deploy-production.yml` |
| US-13 | Hardening containers | ✅ Done | `expose` + `internal: true` |
| US-14 | **Monitoreo healthchecks + logs** | ✅ Done | `scripts/health/compose-health.sh` |
| US-15 | Gestión centralizada de secretos | ✅ Done | `.env.example` + `.gitignore` |

---

## 🔁 Pipelines CI/CD

| Workflow | Trigger | Acción |
|----------|---------|--------|
| `ci-validation.yml` | PR a main/develop | Lint YAML, valida compose, ejecuta shellcheck, escanea secretos con Trufflehog |
| `docker-build.yml` | Push a main / tag v* | Construye n8n-pmai, publica en GHCR con tags semánticos, escaneo Trivy |
| `deploy-production.yml` | Release publicado | SSH al host, `git pull` + `docker compose pull/up`, healthcheck 10× |

### Secrets requeridos (Settings → Secrets)
- `DEPLOY_HOST` — usuario@host de producción
- `DEPLOY_SSH_KEY` — clave privada SSH
- `DEPLOY_PATH` — path en el host (ej: `/srv/apu-hia-26`)
- `DEPLOY_HEALTH_URL` — URL completa al `/healthz` público
- `SLACK_WEBHOOK` (opcional) — notificaciones de resultado

---

## 📚 Documentación adicional

- [`docs/walkthrough.md`](docs/walkthrough.md) — Resumen ejecutivo y bitácora técnica
- [`docs/informe_tp_scrum_2026.md`](docs/informe_tp_scrum_2026.md) — Informe maestro del TP
- [`docs/tablero_scrum_backlog.json`](docs/tablero_scrum_backlog.json) — Backlog Scrum estructurado
- [`docs/runbooks/`](docs/runbooks/) — Procedimientos operativos (operación, incidentes, recuperación)
- [`openspec/changes/`](openspec/changes/) — Artefactos SDD por historia de usuario
