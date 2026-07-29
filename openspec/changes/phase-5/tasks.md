# Tasks: Phase 5 — Purged CV, Convergence Audit, Dynamic Switch & VPS Harden

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 850-1200 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Purged CV) → PR 2 (Convergence) → PR 3 (Dynamic Switch) → PR 4 (VPS) |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Purged CV (Track A) | PR 1 | `pytest tests/validation/test_purged_walk_forward.py -v` | `python3 -c "from src.validation.purged_walk_forward import PurgedWalkForwardValidator; print('OK')"` | Revert `purged_walk_forward.py`, `research_gate.py`, `s4_gates.py` |
| 2 | Convergence (Track B) | PR 2 | `pytest tests/test_convergence_check.py -v` | `python3 scripts/convergence_check.py --start 2026-05 --end 2026-06` | Revert `convergence_check.py`, `daily_scan.py` |
| 3 | Dynamic Switch (Track C) | PR 3 | `pytest tests/ -v -k "dynamic"` | `python3 scripts/run_dynamic_switch_backtest.py --years 2023-2024` | Revert `run_dynamic_switch_backtest.py` |
| 4 | VPS Harden (Track D) | PR 4 | `bash scripts/sv/health_check.sh; echo $?` | `bash deploy_vps.sh --dry-run` | Remove systemd units, revert deploy scripts |

## Phase 0: Upstream Prep

- [x] 0.1 **Create test stubs** for `PurgedWalkForwardValidator` at `tests/validation/test_purged_walk_forward.py`
- [x] 0.2 **Create test stubs** for `convergence_check.py` at `tests/test_convergence_check.py` (32 tests: module, convergence scoring, price discrepancies, categorization, reports, integration)
- [x] 0.3 **Verify `daily_health_scores` table coverage** (2023-2024) — DB has 8195 rows covering 1993-11-11 to 2026-06-04, 2023-2024 fully covered ✅

## Phase 1: Core Implementation (Track A — Purged CV)

- [x] 1.1 **Create `src/validation/purged_walk_forward.py`**: `PurgedWalkForwardValidator` class with expanding-window fold generator, purge/embargo windows (10/5 days), IS/OOS Sharpe aggregation, degradation gate (25%)
- [x] 1.2 **Update `src/validation/research_gate.py`**: Add purged CV as optional Phase 2b step in `validate_strategy()` after CSCV
- [x] 1.3 **Update `src/optimization/s4_gates.py`**: Change `GATE_DEGRADATION = 0.25` (was 0.20)

## Phase 2: Convergence & Dynamic Switch (Tracks B & C)

- [x] 2.1 **Create `scripts/convergence_check.py`**: Read backtest + live signal outputs, compute Jaccard overlap, detect >2% price discrepancies, generate root-cause report with VPS_UNAVAILABLE fallback
- [x] 2.2 **Patch `scripts/daily_scan.py`**: Add scan_metadata.json output capturing all scanned ticker counts, universe sources, and regime info for convergence audit completeness
- [x] 2.3 **Create `scripts/run_dynamic_switch_backtest.py`**: Three-way comparison (ATTACK vs DEFENSE vs dynamic), read health_scores from DB, output JSON verdict

## Phase 3: VPS Infrastructure (Track D)

- [x] 3.1 **Create systemd unit files** at `scripts/sv/momentum-trader.service` and `scripts/sv/momentum-telegram.service` with `Restart=always`, `EnvironmentFile=/.env`, PID files in `run/` directory
- [x] 3.2 **Create `scripts/sv/health_check.sh`**: Report process status, DB connection, last trade timestamp; exit 0 (healthy) / 1 (degraded) / 2 (critical)
- [x] 3.3 **Update `deploy_vps.sh`**: Add `git status --porcelain` check, SHA match vs remote, systemd reload, preflight health hook, `--dry-run` mode
- [x] 3.4 **Update `start_live_session.sh`**: Switch from `pkill -f` to systemd/PID-based lifecycle management, add `--status`, `--stop`, `--headless` flags

## Phase 4: Testing & Verification

- [x] 4.1 **Test purge/embargo fold partitioning**: Assert windows exclude correct data per PCV-REQ-02 scenarios
- [x] 4.2 **Test degradation gate boundary**: Assert ≤25% passes, >25% rejects per PCV-REQ-03 scenarios
- [x] 4.3 **Test `convergence_check.py`**: Integration test with synthetic overlapping + divergent signal sets per SCA-REQ-01/02 (part of test_convergence_check.py)
- [x] 4.4 **Test dynamic switch backtest**: Run 3 modes, assert result structure per DRS-REQ-04 scenarios
- [x] 4.5 **Test VPS deploy validation**: Assert `health_check.sh` exit codes (0/1/2), assert `deploy_vps.sh` blocks dirty git per VPS-REQ-04

## Phase 5: Documentation

- [ ] 5.1 **Update `SYSTEM_CONTEXT.md`**: Move Dynamic Switch from 🔴 Bloqueado to 🟢 Activo
- [ ] 5.2 **Verify `pytest` passes** with all new tests
- [ ] 5.3 **Commit and push** to origin/main before VPS sync declaration
