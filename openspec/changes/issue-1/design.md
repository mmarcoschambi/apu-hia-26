# Design Specification: US-01 Docker Compose Base Architecture

## 1. Architecture Topology

The platform architecture follows a 3-tier containerized microservices model structured with defense-in-depth network segregation.

```mermaid
graph TD
    subgraph Host["Host Machine / Docker Engine"]
        subgraph GatewayNet["Docker Network: gateway-net (Bridge, Ingress)"]
            NGINX["nginx-gateway<br/>(Image: nginx:1.27-alpine)<br/>Ports: 80, 443"]
        end

        subgraph AppNet["Docker Network: app-network (Bridge, internal: true)"]
            N8N["n8n-automation<br/>(Image: n8nio/n8n:1.45.1)<br/>Expose: 5678"]
            MYSQL["mysql<br/>(Image: mysql:8.0.36-bookworm)<br/>Expose: 3306<br/>Aliases: ['mysql', 'mysql-db']"]
        end

        NGINX -->|HTTP Reverse Proxy / WebSockets| N8N
        N8N -->|Internal DNS 'mysql:3306'| MYSQL

        MYSQL -.->|Persist Data| V_MYSQL[(Named Volume: mysql_data)]
        N8N -.->|Persist Config & Workflows| V_N8N[(Named Volume: n8n_data)]
    end

    CLIENT["External Clients / Web Browser"] -->|HTTP / HTTPS| NGINX
    CLIENT -.->|❌ REJECTED (Port 3306 not bound to host)| MYSQL
```

---

## 2. Technical Decisions & Trade-Offs

| Decision | Chosen Solution | Alternative Evaluated | Trade-Off & Rationale |
| :--- | :--- | :--- | :--- |
| **Compose Format** | Compose Spec / 3.8 standard | Docker Swarm stack / Compose v1 | Broad compatibility with modern Docker Engine 26.x + Compose v2 plugin without cluster management overhead. |
| **Network Isolation** | Dual Bridge (`gateway-net` + `app-network` with `internal: true`) | Single default bridge network | Default network exposes all containers to all ports within the bridge and permits outbound WAN traffic. `internal: true` prevents database egress and external lateral movement. |
| **Database Port Publishing** | `expose: ["3306"]` | `ports: ["3306:3306"]` | Publishing ports binds them to host `0.0.0.0`, bypassing Docker firewall isolation. `expose` allows container-to-container traffic inside `app-network` while keeping host interface completely closed. |
| **Local Dev DB Access** | `docker-compose.override.yml.example` (`127.0.0.1:3306:3306`) | Permanent host binding in base `docker-compose.yml` | Base file remains production-hardened. Devs can opt-in locally by copying the override file, which is ignored by `.gitignore`. |
| **Startup Ordering** | `depends_on` with `condition: service_healthy` | Unordered startup with application retries | Prevents n8n from failing and crash-looping while MySQL initializes schemas and grants during initial setup. |

---

## 3. Configuration & Interface Contracts

### 3.1. Network Contracts
- **`gateway-net`**:
  - Driver: `bridge`
  - Name: `pmai_gateway_net`
  - Connected Services: `nginx-gateway`, `n8n-automation`
  - Purpose: Ingress routing and public web traffic handling.
- **`app-network`**:
  - Driver: `bridge`
  - Name: `pmai_app_net`
  - Directive: `internal: true`
  - Connected Services: `n8n-automation`, `mysql`
  - Purpose: Isolated inter-service communication; no internet access, no host port exposure.

### 3.2. Persistence Volume Contracts
- **`mysql_data`**:
  - Name: `pmai_mysql_data`
  - Mount Path: `/var/lib/mysql` inside `mysql` service.
- **`n8n_data`**:
  - Name: `pmai_n8n_data`
  - Mount Path: `/home/node/.n8n` inside `n8n-automation` service.

### 3.3. Environment Variables Contract (`.env.example`)
| Variable | Default Placeholder | Purpose |
| :--- | :--- | :--- |
| `GATEWAY_HTTP_PORT` | `80` | Host port for Nginx HTTP |
| `GATEWAY_HTTPS_PORT` | `443` | Host port for Nginx HTTPS |
| `MYSQL_ROOT_PASSWORD` | `secret_root_password_change_me` | Root credential for MySQL admin |
| `MYSQL_DATABASE` | `pmai_db` | Primary database name |
| `MYSQL_USER` | `pmai_app` | Dedicated application DB user |
| `MYSQL_PASSWORD` | `pmai_app_secure_password` | Dedicated application DB password |
| `N8N_ENCRYPTION_KEY` | `default_secret_encryption_key_32b` | AES key for encrypting n8n credentials |
| `N8N_PROTOCOL` | `http` | External protocol |
| `N8N_HOST` | `localhost` | External host header |
| `WEBHOOK_URL` | `http://localhost/` | Public webhook endpoint |
| `TZ` / `GENERIC_TIMEZONE` | `America/Argentina/Jujuy` | System and application timezone |

---

## 4. Edge Cases, Failure Modes & Mitigations

### 4.1. Missing `.env` File at Runtime
- **Failure Mode**: Variables evaluated as empty strings, potentially causing auth failures or unbound ports.
- **Mitigation**: All environment variable interpolations in `docker-compose.yml` utilize default fallbacks (`${VAR:-fallback_value}`).

### 4.2. Host Port Collision (80 / 443 already in use)
- **Failure Mode**: `docker compose up` fails with `bind: address already in use`.
- **Mitigation**: Ports mapped via variables `${GATEWAY_HTTP_PORT:-80}:80`, allowing developers to set `GATEWAY_HTTP_PORT=8080` in `.env` without modifying versioned compose definitions.

### 4.3. MySQL Startup Latency during First Initialization
- **Failure Mode**: n8n boots immediately, fails to connect to MySQL, and exits with error code.
- **Mitigation**: `n8n-automation` declares `depends_on: mysql: condition: service_healthy`. The `mysql` service implements an active healthcheck using `mysqladmin ping` with a `start_period: 30s` grace window.

### 4.4. Secret Leakage via Version Control
- **Failure Mode**: Developer commits `.env` or `docker-compose.override.yml` containing real production secrets or host bindings.
- **Mitigation**: `.gitignore` explicitly excludes `.env`, `*.env`, `.secrets/`, and `docker-compose.override.yml`. Only sanitized `.env.example` and `docker-compose.override.yml.example` are committed.
