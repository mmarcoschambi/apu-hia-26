# Design: US-01: Configuración de Docker Engine y Orquestación Base con Docker Compose v2

## Architecture & System Overview

The platform uses a containerized multi-tier architecture orchestrated through Docker Compose v2. Services are partitioned across two isolated network zones to prevent unauthorized external access to the persistent storage layer.

```mermaid
graph TD
    subgraph Host["Host Environment (Docker Engine 26.x / Docker Compose v2)"]
        subgraph GatewayNet["Public Perimeter Network: gateway-net (pmai_gateway_net)"]
            NGINX["nginx-gateway (nginx:1.27-alpine)<br>Ports: 80, 443"]
        end

        subgraph AppNet["Private Isolated Network: app-network (pmai_app_net, internal: true)"]
            N8N["n8n-automation (n8nio/n8n:1.45.1)<br>Expose: 5678"]
            MYSQL["mysql (mysql:8.0.36-bookworm)<br>Expose: 3306 (No Host Port Binding)"]
        end

        NGINX -->|HTTP Reverse Proxy / Webhooks| N8N
        N8N -->|DNS Resolution: 'mysql:3306'| MYSQL

        MYSQL -.->|Persist Data| V_DB[(Named Volume: pmai_mysql_data)]
        N8N -.->|Persist Data| V_N8N[(Named Volume: pmai_n8n_data)]
    end

    CLIENT["Client / Web Browser"] -->|HTTP/HTTPS :80/:443| NGINX
    CLIENT -.->|❌ BLOCKED (Port 3306 NOT Published)| MYSQL
    DEV_DBEAVER["Dev Tools (DBeaver)"] -.->|Optional Local Override (127.0.0.1:3306)| MYSQL
```

### Component Structure

```
.
├── docker-compose.yml                  # Root multi-service composition definition
├── .env.example                        # Canonical template of environment variables
├── docker-compose.override.yml.example # Local development port binding override template
├── nginx/
│   └── nginx.conf                      # Nginx reverse proxy configuration & routing rules
├── mysql/
│   └── init/                           # Automated initialization SQL scripts (schema.sql)
└── openspec/
    └── changes/
        └── issue-1/                    # OpenSpec SDD artifacts for US-01
            ├── proposal.md
            ├── design.md
            ├── specs/
            │   └── spec.md
            └── tasks.md
```

## Detailed Technical Decisions

### 1. Dual Network Segmentation & Zero-Trust Isolation
- **`gateway-net` (`pmai_gateway_net`)**: Standard bridge driver. Connects `nginx-gateway` and `n8n-automation`. Exposes ingress traffic from host ports 80/443.
- **`app-network` (`pmai_app_net`)**: Custom bridge driver with `internal: true`. This disables default gateway routing and external egress/ingress, strictly restricting communication to inter-container traffic between `n8n-automation` and `mysql`.
- **Port Exposure Directive**:
  - `nginx-gateway`: `ports: ["${GATEWAY_HTTP_PORT:-80}:80", "${GATEWAY_HTTPS_PORT:-443}:443"]`
  - `n8n-automation`: `expose: ["5678"]` (reachable only within Docker networks)
  - `mysql`: `expose: ["3306"]` with explicit aliases `['mysql', 'mysql-db']` (zero host port mapping in base compose).

### 2. State Persistence Strategy
- **Named Volume Management**:
  - `mysql_data` mapped to `pmai_mysql_data` storing `/var/lib/mysql`.
  - `n8n_data` mapped to `pmai_n8n_data` storing `/home/node/.n8n`.
- **Lifecycle Guarantees**: Volumes survive `docker compose down` operations and only purge upon explicit `-v` / `--volumes` flags.

### 3. Startup Ordering & Resilient Healthchecks
- **MySQL Healthcheck**: Executes `mysqladmin ping -h 127.0.0.1 -u$$MYSQL_USER -p$$MYSQL_PASSWORD` every 10s with 5 retries and 30s start period.
- **Dependency Graph**:
  - `n8n-automation` declares `depends_on.mysql.condition: service_healthy`, preventing boot failures caused by uninitialized database tables.
  - `nginx-gateway` declares `depends_on.n8n-automation.condition: service_started`.

### 4. Configuration Templating & Dev Override
- **Parameter Fallbacks**: All variables in `docker-compose.yml` utilize POSIX shell expansion with safe defaults (e.g. `${MYSQL_DATABASE:-pmai_db}`).
- **Local Dev Decoupling**: Database administration via external GUI tools (DBeaver, DataGrip) is provided through `docker-compose.override.yml.example` using loopback binding `127.0.0.1:3306:3306`, keeping production definitions pristine.

## Failure Modes & Mitigations

| Failure Mode | Root Cause | Architectural Mitigation |
|--------------|------------|--------------------------|
| **Database Port Leakage** | Accidentally defining `ports: 3306:3306` instead of `expose` | Hard enforce `expose: ["3306"]` + `app-network.internal: true`. Verified via automated BDD tests |
| **Premature Service Boot** | n8n starts before MySQL is accepting connections | Healthcheck-driven dependency (`condition: service_healthy`) |
| **Data Loss on Re-creation** | Relying on anonymous container layers | Explicit named volumes (`pmai_mysql_data`, `pmai_n8n_data`) |
| **Config Drift across Devs** | Hardcoded environment values in compose file | Comprehensive `.env.example` template with deterministic fallbacks |
| **Port Conflicts on Host** | Port 80 or 443 occupied by existing host services | Environment variables for port mapping (`GATEWAY_HTTP_PORT`, `GATEWAY_HTTPS_PORT`) |
