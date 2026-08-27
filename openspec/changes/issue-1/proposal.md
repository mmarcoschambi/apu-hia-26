# Proposal: US-01: Configuración de Docker Engine y Orquestación Base con Docker Compose v2

## Intent
Establish the baseline containerized orchestration platform for the Modular Automation and Microservices Platform (PMA-Docker 2026). This change introduces the root `docker-compose.yml` specification, multi-tier network segmentation (`gateway-net` and `app-network`), persistent named volume declarations (`mysql_data`, `n8n_data`), and standardized environment configuration templates (`.env.example`, `docker-compose.override.yml.example`).

## Scope

### In Scope
1. **Docker Compose v2 Base Architecture**: Specification of version `3.8` declarative configuration defining core microservices (`nginx-gateway`, `n8n-automation`, `mysql`).
2. **Network Topology & Isolation**:
   - `gateway-net`: Public perimeter bridge network exposing Nginx reverse proxy to host ports 80/443.
   - `app-network`: Isolated private bridge network with `internal: true` blocking external routing to the MySQL data layer.
3. **Volume Persistence**: Named volumes `pmai_mysql_data` and `pmai_n8n_data` for state preservation across container lifecycle events.
4. **Service Healthchecks & Dependency Ordering**:
   - Native healthcheck for MySQL (`mysqladmin ping`).
   - Condition-based startup dependencies (`n8n-automation` depends on `mysql` healthy; `nginx-gateway` depends on `n8n-automation` started).
5. **Environment Configuration & Local Dev Override**:
   - `.env.example` defining centralized configuration tokens and defaults.
   - `docker-compose.override.yml.example` providing optional local development host port binding (`127.0.0.1:3306:3306`) without compromising production baseline security.

### Out of Scope
- Multi-host clustering (Docker Swarm / Kubernetes).
- CI/CD GitHub Actions workflow implementation (scoped to US-10).
- Production SSL certificate generation (Let's Encrypt / Certbot automation).

## Capabilities

### New / Validated Capabilities
- `compose-base-orchestration`: Declarative multi-container management via Docker Compose v2.
- `network-segmentation`: Dual-network architecture with strict private network isolation (`internal: true`).
- `schema-validation`: Zero-error declarative validation via `docker compose config`.
- `dev-override-pattern`: Non-intrusive local database debugging template.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `docker-compose.yml` | **New / Root** | Base multi-service orchestration manifest |
| `.env.example` | **New** | Environment variable defaults and secret placeholders |
| `docker-compose.override.yml.example` | **New** | Local development override template |
| `openspec/changes/issue-1/` | **New** | Formal SDD specification, design, requirements, and tasks |
| `tasks.md` | **Updated** | Worktree task execution checklist |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Syntax errors or invalid YAML indentation in compose file | Low | Automated schema validation via `docker compose config` before phase completion |
| Port collision on host port 80/443 | Low | Configurable port variables (`${GATEWAY_HTTP_PORT:-80}`, `${GATEWAY_HTTPS_PORT:-443}`) in `.env` |
| Inadvertent exposure of MySQL port 3306 on host | Medium | Strict use of `expose: ["3306"]` in base compose and `internal: true` on `app-network` |
| Service startup race conditions | Medium | Explicit `depends_on` with `condition: service_healthy` on MySQL health check |

## Rollback Plan
- Revert `docker-compose.yml`, `.env.example`, and `docker-compose.override.yml.example`.
- Remove created OpenSpec specification files under `openspec/changes/issue-1/`.

## Acceptance Criteria
- [ ] `docker compose config` validates the full compose definition with exit code 0 and zero syntax warnings.
- [ ] Network definitions `gateway-net` and `app-network` are declared, with `app-network` configured with `internal: true`.
- [ ] Persistent named volumes `mysql_data` and `n8n_data` are declared with custom names `pmai_mysql_data` and `pmai_n8n_data`.
- [ ] Services `nginx-gateway`, `n8n-automation`, and `mysql` are defined with proper image tags, restart policies (`unless-stopped`), and network bindings.
- [ ] MySQL is configured with `expose: ["3306"]` and DNS aliases `mysql` / `mysql-db` in `app-network`.
- [ ] `.env.example` and `docker-compose.override.yml.example` exist with complete documentation.

## Context
- **Issue**: https://github.com/mmarcoschambi/apu-hia-26/issues/1
- **Epic**: EP-01 (Entorno de Contenedores y Gateway Web)
- **Sprint**: Sprint 1
- **Story Points**: 5 SP
