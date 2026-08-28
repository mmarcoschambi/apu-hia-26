# Proposal: US-01 Base Docker Engine Setup & Docker Compose Orchestration

## 1. Overview & Summary
This proposal formalizes the foundational container orchestration specification for the **Plataforma Modular de Automatización y Microservicios Cloud con Docker (PMA-Docker 2026)** under User Story **US-01** (Epic **EP-01: Entorno de Contenedores y Gateway Web**).

The objective is to establish a declarative, reproducible, and secure multi-service orchestration baseline using Docker Compose v2, ensuring strict network segmentation, state persistence across container lifecycles, and complete prevention of unauthorized host-level database port exposures.

---

## 2. Motivation & Problem Statement
Traditional software deployments suffer from runtime environment discrepancies ("it works on my machine"), manual configuration friction, unmanaged service dependencies, and critical security vulnerabilities caused by default port publishing.

By establishing a declarative orchestration baseline:
- All services (`nginx-gateway`, `n8n-automation`, `mysql`) are provisioned in deterministic isolated environments.
- Network perimeters are formally divided into public ingress (`gateway-net`) and isolated internal communication (`app-network`).
- Secrets and configuration are decoupled into environment templates (`.env.example`) and local overrides (`docker-compose.override.yml.example`) protected by `.gitignore`.

---

## 3. Scope Definition

### In-Scope
- **Declarative Compose Stack**: Root `docker-compose.yml` defining version, networks, volumes, and core service topology.
- **Dual-Network Segmentation**:
  - `gateway-net`: External-facing bridge network for reverse proxy routing.
  - `app-network`: Internal backend bridge network configured with `internal: true` to prevent WAN routing.
- **State Persistence**: Declarative named volumes (`mysql_data`, `n8n_data`) preventing data loss upon container teardown.
- **Environment & Secret Hygiene**:
  - `.env.example` with comprehensive default placeholders.
  - `docker-compose.override.yml.example` documenting optional local development host port forwarding (e.g. `127.0.0.1:3306:3306` for DBeaver).
  - `.gitignore` hardening against committing `.env` and local overrides.
- **Schema Validation**: Automated syntax and structure validation via `docker compose config`.

### Out-of-Scope
- Multi-host orchestration clusters (e.g., Kubernetes, Docker Swarm).
- Production SSL/TLS certificate procurement (specified in US-02/US-12).
- Scheduled backup cron jobs and dumps (specified in US-06).

---

## 4. User Story & Team Alignment
- **Epic**: EP-01 (Entorno de Contenedores y Gateway Web)
- **User Story**: US-01 — Configuración de Docker Engine y Orquestación Base con Docker Compose v2
- **Priority**: Must Have (MoSCoW)
- **Estimation**: 5 Story Points (Fibonacci)
- **Assigned Role**: Integrante 3 (DevOps / QA)
- **Sprint**: Sprint 1
- **Reference Documentation**: `docs/informe_tp_scrum_2026.md` (Sections 1.6, 3.1, 7.2)
