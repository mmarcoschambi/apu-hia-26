# Tasks: US-01: Configuración de Docker Engine y Orquestación Base con Docker Compose v2

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~200-350 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | direct-inline |
| Chain strategy | single-branch |

### Suggested Work Units

| Unit | Goal | Focus | Focused test / validation command | Rollback boundary |
|------|------|-------|-----------------------------------|-------------------|
| 1 | Base Compose & Schema | `docker-compose.yml` definition | `docker compose config` | Revert `docker-compose.yml` |
| 2 | Network & Volume Architecture | `gateway-net`, `app-network`, named volumes | `docker compose config --networks` / `--volumes` | Revert network/volume blocks |
| 3 | Config Templates & Overrides | `.env.example`, `override.yml.example` | Inspect template parsing & defaults | Remove example files |

---

## Phase 0: Upstream Prep & Environment Setup

- [x] 0.1 **Verify workspace isolation**: Confirm execution inside worktree `mmarcoschambi__apu-hia-26/1`.
- [x] 0.2 **Verify Docker Engine availability**: Ensure Docker Engine / Desktop and Docker Compose v2 are installed and reachable.

## Phase 1: RED Tests & Automated Validation Matrix

- [ ] 1.1 **Test compose schema validation (REQ-1 / SCEN-1)**: Validate that `docker compose config` exits with code 0.
- [ ] 1.2 **Test syntax error handling (REQ-1 / SCEN-1-EDGE-1)**: Validate that invalid indentation returns non-zero exit code.
- [ ] 1.3 **Test default environment fallback (REQ-1 / SCEN-1-EDGE-2)**: Validate variable substitution without `.env`.
- [ ] 1.4 **Test network isolation configuration (REQ-2 / SCEN-2 & EDGE-2)**: Validate `app-network` is configured with `internal: true`.
- [ ] 1.5 **Test zero host port publishing for MySQL (REQ-2 / SCEN-2-EDGE-1)**: Verify `mysql` service uses `expose: ["3306"]` instead of host port mapping.
- [ ] 1.6 **Test named volume declarations (REQ-3 / SCEN-3)**: Verify `mysql_data` (`pmai_mysql_data`) and `n8n_data` (`pmai_n8n_data`).
- [ ] 1.7 **Test healthcheck & dependency graph (REQ-4 / SCEN-4)**: Verify MySQL healthcheck definition and `depends_on` conditions.

## Phase 2: Implementation & Base Manifest Construction

- [ ] 2.1 **Create `docker-compose.yml`**: Declare version `3.8`, services (`nginx-gateway`, `n8n-automation`, `mysql`), networks, and volumes.
- [ ] 2.2 **Create `.env.example`**: Document all configurable parameters with secure default fallbacks.
- [ ] 2.3 **Create `docker-compose.override.yml.example`**: Document developer loopback override for DBeaver.

## Phase 3: Verification & Edge Case Testing

- [ ] 3.1 **Execute `docker compose config`**: Validate entire manifest tree.
- [ ] 3.2 **Simulate local dev override**: Validate that combining base compose with override exposes `127.0.0.1:3306:3306`.
- [ ] 3.3 **Verify alignment with project report**: Confirm consistency with `docs/informe_tp_scrum_2026.md` and Scrum backlog.

## Phase 4: Artifact Audit & Phase Closure

- [ ] 4.1 **Sync root `tasks.md`**: Update root checklist with completed milestones.
- [ ] 4.2 **Audit OpenSpec integrity**: Confirm completeness of `proposal.md`, `design.md`, `specs/spec.md`, and `tasks.md`.
