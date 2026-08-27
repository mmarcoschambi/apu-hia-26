# Specification: US-01 Docker Compose Base Orchestration

## 1. Requirement Specifications

- **REQ-01 (Compose Compliance)**: The system must provide a declarative `docker-compose.yml` compliant with Docker Compose v2 and Compose Specification / Schema 3.8.
- **REQ-02 (Dual Network Segregation)**: The system must isolate network communication into two distinct bridges:
  - `gateway-net` (public proxy ingress).
  - `app-network` (configured with `internal: true` to prevent WAN egress/ingress).
- **REQ-03 (Service Topology)**: The Compose file must declare exactly three coordinated services:
  - `nginx-gateway`: reverse proxy gateway listening on host ports 80/443.
  - `n8n-automation`: workflow engine exposed on port 5678 to internal networks.
  - `mysql`: relational database engine exposed on port 3306 exclusively within `app-network`.
- **REQ-04 (Persistence)**: Named volumes `mysql_data` and `n8n_data` must be explicitly declared and bound to `/var/lib/mysql` and `/home/node/.n8n` respectively.
- **REQ-05 (Zero Public DB Exposure)**: The base `docker-compose.yml` must NOT expose or publish MySQL port 3306 on the host machine (`0.0.0.0` or `127.0.0.1`). It must use `expose: ["3306"]` exclusively.
- **REQ-06 (Environment Decoupling & Protection)**: Configuration must be driven through `.env.example` templates, with `.env` and `docker-compose.override.yml` strictly ignored in `.gitignore`.

---

## 2. Closed BDD Acceptance Matrix

### Scenario 1: Compose Schema & Configuration Validation
```gherkin
Feature: Docker Compose Syntax and Schema Validation

  Scenario: Developer validates base compose configuration
    Given the repository root contains "docker-compose.yml" and ".env.example"
    When the developer executes "docker compose config --quiet"
    Then the command exits with status code 0
    And the parsed configuration confirms valid YAML syntax and schema compliance
```

### Scenario 2: Database Port Isolation on Base Compose
```gherkin
Feature: MySQL Port Isolation

  Scenario: Verifying zero host port publication for MySQL in base configuration
    Given the "docker-compose.yml" is parsed by Docker Compose
    When inspecting the port bindings of the "mysql" service
    Then the "mysql" service defines "expose" on port 3306
    And the "mysql" service does NOT declare any "ports" mapped to host interfaces
    And the "mysql" service is connected strictly to "app-network"
```

### Scenario 3: Internal Network Quarantine (app-network)
```gherkin
Feature: App Network Isolation

  Scenario: Validating internal flag on app-network
    Given the network declarations in "docker-compose.yml"
    When inspecting the "app-network" definition
    Then "internal" is set to true
    And "driver" is set to "bridge"
    And "nginx-gateway" is NOT connected to "app-network"
```

### Scenario 4: Named Persistence Volumes
```gherkin
Feature: State Persistence Volume Mapping

  Scenario: Validating persistent volume declarations
    Given the volume declarations in "docker-compose.yml"
    When inspecting top-level volumes and service volume mounts
    Then top-level volumes include "mysql_data" and "n8n_data"
    And "mysql" service mounts "mysql_data" to "/var/lib/mysql"
    And "n8n-automation" service mounts "n8n_data" to "/home/node/.n8n"
```

### Scenario 5: Service Healthcheck and Startup Dependency Chain
```gherkin
Feature: Coordinated Service Startup

  Scenario: Verifying dependency ordering and healthcheck
    Given the service declarations in "docker-compose.yml"
    When inspecting service dependencies
    Then "mysql" service defines a healthcheck executing "mysqladmin ping"
    And "n8n-automation" declares "depends_on" with condition "service_healthy" targeting "mysql"
    And "nginx-gateway" declares "depends_on" with condition "service_started" targeting "n8n-automation"
```

### Scenario 6: Secret & Override File Hygiene in Version Control
```gherkin
Feature: Version Control Security Hygiene

  Scenario: Verifying gitignore rules for local overrides and secrets
    Given the root ".gitignore" file
    When checking ignore patterns
    Then ".env" is matched and ignored
    And "*.env" is matched and ignored
    And "docker-compose.override.yml" is matched and ignored
    And ".secrets/" directory is matched and ignored
```

---

## 3. Explicit Boundary & Edge Cases Matrix

| ID | Edge Case / Boundary Condition | Expected Behavior | Verification Check |
| :--- | :--- | :--- | :--- |
| **EC-01** | Missing `.env` file during invocation | `docker compose config` evaluates all variables with defined fallback defaults without fatal errors. | Execute `docker compose config` without local `.env`. Exit code must be 0. |
| **EC-02** | Custom host port override (e.g. `GATEWAY_HTTP_PORT=8080`) | Nginx binds to host port `8080` instead of default `80` while internal proxy continues routing to n8n port 5678. | Validate compose config output with `GATEWAY_HTTP_PORT=8080`. |
| **EC-03** | Local development DB access requirement | Dev creates local `docker-compose.override.yml` from `.example` file binding `127.0.0.1:3306:3306`. Production base compose remains unchanged. | Verify `docker-compose.override.yml.example` maps strictly to loopback `127.0.0.1`. |
| **EC-04** | Container restart under host reboot | All services specify `restart: unless-stopped` to ensure automatic recovery after host reboot or Docker daemon restart. | Inspect `restart` directive across all 3 services in `docker-compose.yml`. |
| **EC-05** | Internal DNS resolution aliases | MySQL service declares DNS aliases `mysql` and `mysql-db` in `app-network` ensuring n8n resolves host connection deterministically. | Inspect `networks.app-network.aliases` for service `mysql`. |
