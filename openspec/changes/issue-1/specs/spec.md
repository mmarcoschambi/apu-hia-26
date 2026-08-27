# Spec: US-01: Configuración de Docker Engine y Orquestación Base con Docker Compose v2

## Requirements

### Requirement: REQ-1 - Docker Compose Base Schema & Orchestration Validation
The root `docker-compose.yml` file MUST define a valid Docker Compose v2 configuration (version 3.8) declaring all primary microservices (`nginx-gateway`, `n8n-automation`, `mysql`), networks (`gateway-net`, `app-network`), and named volumes (`mysql_data`, `n8n_data`).

#### Scenario: SCEN-1 - Valid compose schema parsing and service listing
- **Given** the repository root containing `docker-compose.yml` and `.env.example`
- **When** the developer executes `docker compose config`
- **Then** the command exits with return code 0, prints the resolved configuration without syntax errors or warnings, and lists services `nginx-gateway`, `n8n-automation`, and `mysql`.

#### Scenario: SCEN-1-EDGE-1 - Malformed YAML syntax rejection
- **Given** a `docker-compose.yml` file with invalid YAML indentation or unclosed quote strings
- **When** `docker compose config` is executed
- **Then** the command fails with a non-zero exit code and outputs a parsing error indicating the invalid line and column.

#### Scenario: SCEN-1-EDGE-2 - Missing environment file graceful fallback
- **Given** a host environment without a `.env` file present
- **When** `docker compose config` is executed
- **Then** all environment variables interpolate to their defined fallback defaults (e.g. `GATEWAY_HTTP_PORT=80`, `MYSQL_DATABASE=pmai_db`) without throwing undefined variable errors.

---

### Requirement: REQ-2 - Dual Network Topology and Strict Internal Isolation
The orchestration MUST establish two distinct networks: `gateway-net` (public bridge) and `app-network` (private bridge with `internal: true`). The MySQL database service MUST NOT expose port 3306 to the host in the base compose definition.

#### Scenario: SCEN-2 - Dual network attachment and internal routing
- **Given** running containers defined in `docker-compose.yml`
- **When** inspecting network attachments via `docker inspect`
- **Then** `nginx-gateway` is connected solely to `pmai_gateway_net`, `mysql` is connected solely to `pmai_app_net` with aliases `mysql` and `mysql-db`, and `n8n-automation` is connected to both `pmai_gateway_net` and `pmai_app_net`.

#### Scenario: SCEN-2-EDGE-1 - Verification of zero host port publishing for MySQL
- **Given** the MySQL container running under base `docker-compose.yml`
- **When** a client on the host attempts a TCP connection to `127.0.0.1:3306` or `localhost:3306`
- **Then** the connection is refused or times out, confirming that port 3306 is not published to the host network interface.

#### Scenario: SCEN-2-EDGE-2 - Private network external isolation (`internal: true`)
- **Given** the `app-network` created with driver `bridge` and `internal: true`
- **When** inspecting Docker network configuration via `docker network inspect pmai_app_net`
- **Then** the `Internal` attribute is set to `true`, preventing outbound WAN traffic and blocking inbound external ingress directly into the database tier.

---

### Requirement: REQ-3 - Named Volume Persistence Across Container Lifecycle
The orchestration MUST declare persistent named volumes `pmai_mysql_data` and `pmai_n8n_data` ensuring state preservation across container recreation.

#### Scenario: SCEN-3 - Data persistence across container destroy and recreate
- **Given** running `mysql` and `n8n-automation` services with stored database records and workflow state
- **When** containers are stopped and removed with `docker compose down` (without `-v`) and recreated with `docker compose up -d`
- **Then** the existing named volumes are reattached and all previous data, tables, and workflows remain intact.

#### Scenario: SCEN-3-EDGE-1 - Explicit volume destruction lifecycle
- **Given** active named volumes `pmai_mysql_data` and `pmai_n8n_data`
- **When** `docker compose down -v` is explicitly executed
- **Then** the containers are stopped, and Docker deletes the named volumes, enabling clean initial state bootstrapping upon subsequent runs.

---

### Requirement: REQ-4 - Healthchecks and Deterministic Service Boot Ordering
The database service MUST provide a native healthcheck (`mysqladmin ping`), and dependent microservices MUST respect startup condition gates (`condition: service_healthy`).

#### Scenario: SCEN-4 - Ordered startup sequence
- **Given** all services initialized via `docker compose up -d`
- **When** Docker evaluates the service startup dependency tree
- **Then** `mysql` initiates healthchecks until reporting `healthy`, `n8n-automation` waits for MySQL's healthy state before starting, and `nginx-gateway` starts after `n8n-automation` has spawned.

#### Scenario: SCEN-4-EDGE-1 - Healthcheck failure handling
- **Given** a MySQL container failing healthcheck queries (e.g. invalid credentials or startup hang)
- **When** the healthcheck retries exceed the configured limit (5 retries)
- **Then** `mysql` status transitions to `unhealthy`, and dependent service `n8n-automation` is blocked from starting, preventing cascading initialization errors.

---

### Requirement: REQ-5 - Configuration Environment and Local Dev Override
The orchestration MUST supply a `.env.example` template with documented parameters and a `docker-compose.override.yml.example` template for non-intrusive local development database access.

#### Scenario: SCEN-5 - Standard environment template loading
- **Given** `.env.example` copied to `.env`
- **When** customized environment variables are supplied
- **Then** `docker compose config` parses and applies the custom variables to container ports, service credentials, and timezones.

#### Scenario: SCEN-5-EDGE-1 - Local development port override
- **Given** a developer utilizing `docker-compose.override.yml` containing `mysql.ports: ["127.0.0.1:3306:3306"]`
- **When** `docker compose up -d` is executed locally
- **Then** MySQL port 3306 binds strictly to the local loopback address `127.0.0.1` on the developer machine (enabling DBeaver), while keeping production configs intact.
