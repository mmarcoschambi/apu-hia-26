# Design: Phase 5 — Purged CV, Convergence Audit, Dynamic Switch & VPS Harden

## Technical Approach

Four independent tracks sharing the same change context, no wiring between them:

- **Track A**: New class `PurgedWalkForwardValidator` added as a new Phase 2b step in `ResearchGate.validate_strategy()`, then calls the degradation gate from `s4_gates.py` (threshold recalibrated to 25%).
- **Track B**: Convergence audit script reads backtest + live signal outputs; VPS patch captures all scanned tickers in snapshot.
- **Track C**: Three-way backtest runner reusing existing `backtest_via_signal_engine.py` with mode override.
- **Track D**: systemd units, PID lifecycle, health check script, deploy validation hook.

---

## Architecture Decisions

### Decision: Class-based validator vs. function for Purged CV

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Standalone function | Lightweight, no state | **Class** — needs to hold fold results, aggregate metrics, produce report. Same pattern as `CSCVAnalyzer`/`BootstrapAnalyzer` in `research_gate.py`. |
| Class `PurgedWalkForwardValidator` | More code, testable, chainable | Aligns with project patterns. Accepts `engine_class` (same interface as `ResearchGate.validate_strategy`). |

### Decision: Separate systemd units vs. one combined

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single `momentum-all.service` | Simple, parallel in one unit | **Two units** — trader+scanner fail together, Telegram fail independently. Different restart policies, separate health accountability. |
| `momentum-trader.service` + `momentum-telegram.service` | More units to manage | Correct isolation. Spec requires `Restart=always` for both. |

### Decision: Degraded audit as fallback

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Require VPS fix | Correct but blocked by external infra | **Degraded audit** — report the gap as `VPS_UNAVAILABLE`, ship convergence scoring on available data. |
| Fail closed | Honest but stalls delivery | Accept degraded until VPS-side fix lands. |

### Decision: No TDD for infrastructure scripts

| Option | Tradeoff | Decision |
|--------|----------|----------|
| pytest for bash/systemd | Requires bats/shellspec, new tooling | **No TDD** — `deploy_vps.sh` and `health_check.sh` validated via manual preflight + red/green exit code testing. |
| Manual testing | Slower iteration, no CI | Acceptable for deploy infra (bash/systemd). One-shot validation hook catches regressions. |

---

## Data Flow

```
Track A (Purged CV):
  Params/Folds → PurgedWalkForwardValidator → Engine per fold → Fold metrics → Degradation gate → Report

Track B (Convergence):
  daily_scan.py snapshots ─┐
                           ├→ convergence_check.py → convergence_score → report
  backtest outputs ────────┘

Track C (Dynamic Switch):
  daily_health_scores DB → run_dynamic_switch_backtest.py → 3x backtest signals → mode metrics → comparison

Track D (VPS):
  git push → deploy_vps.sh (validate git status) → rsync → install systemd units → health_check --preflight
```

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/validation/purged_walk_forward.py` | **Create** | `PurgedWalkForwardValidator` class: purged/embargoed expanding-window CV |
| `src/validation/research_gate.py` | **Modify** | Add purged CV phase as Phase 2b in `validate_strategy()` |
| `src/optimization/s4_gates.py` | **Modify** | `GATE_DEGRADATION = 0.25` (was 0.20) |
| `scripts/convergence_check.py` | **Create** | Signal overlap scoring, price discrepancy, root-cause report |
| `scripts/daily_scan.py` | **Modify** | Fix snapshot serialization to include ALL scanned tickers |
| `scripts/run_dynamic_switch_backtest.py` | **Create** | Three-way mode comparison: ATTACK vs DEFENSE vs dynamic |
| `scripts/sv/health_check.sh` | **Create** | Exit code 0/1/2 health endpoint for systemd |
| `scripts/start_live_session.sh` | **Create** | systemd-compatible session launcher (headless flag) |
| `deploy_vps.sh` | **Modify** | Git-status check, rsync, systemd reload, preflight hook |
| `config/production_config.json` | **Modify** | Update `risk_pct_by_regime` if DRS-REQ-02 mapping changes |

---

## Interfaces / Contracts

### PurgedWalkForwardValidator

```python
class PurgedWalkForwardValidator:
    def __init__(self, n_folds: int = 4, purge_days: int = 10, embargo_days: int = 5): ...
    def validate(self, engine_class, params, universe, fold_definitions) -> PurgedWFReport: ...

@dataclass
class PurgedWFReport:
    folds: list[FoldMetrics]
    is_sharpe_mean: float
    oos_sharpe_mean: float
    degradation_pct: float
    gate_passed: bool
    trades_per_fold: list[int]
```

### convergence_check.py

```
Input:  --start YYYY-MM-DD --end YYYY-MM-DD (reads backtest + live_signals dirs)
Output: convergence_score, price_anomalies[], root_cause report to stdout + shadow_sandbox/
```

### run_dynamic_switch_backtest.py

```
Input:  --start YYYY-MM-DD --end YYYY-MM-DD --universe-size N
Output: JSON with three mode results + verdict
Mode override: --static-mode ATTACK|DEFENSE_FULL (for baseline runs)
```

### health_check.sh contract

```
Exit 0: all services running, DB connected, last trade < 24h
Exit 1: one service down (degraded)
Exit 2: critical failure (DB down, both services down)
```

---

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `PurgedWalkForwardValidator` fold partitioning | Assert purge/embargo windows exclude correct data |
| Unit | Degradation gate formula | Assert (1.2-1.0)/1.2 ≤ 0.25 passes |
| Unit | `get_active_mode()` boundary cases | Score 4/5/6 edge cases |
| Integration | Convergence check on synthetic data | Generate overlapping + divergent signal sets |
| Integration | Dynamic switch backtest | Run 3 modes, assert result structure |
| E2E | `deploy_vps.sh --dry-run` | Assert git-dirty blocks; assert rsync would run |
| E2E | `health_check.sh` on test VPS | Assert exit codes match service states |

---

## Threat Matrix

| Boundary | Applicability | Design response |
|----------|---------------|-----------------|
| Documentation-like paths | **N/A** — no executable markdown | — |
| Git repository selection | **N/A** — `deploy_vps.sh` checks `git status --porcelain` (cwd, no `-C`) | — |
| Commit state | **N/A** — no staged/`-a` commit automation | — |
| Push state | **Applicable** — VPS-REQ-04 verifies `git push` SHA | Validate local SHA == remote before rsync; fail with exit 1 on mismatch |
| PR commands | **N/A** — no PR automation | — |

---

## Migration / Rollout

No data migration required. VPS rollout is live-side: push from CI, `deploy_vps.sh` from CI runner. Rollback per proposal: remove systemd units, revert to `pkill` lifecycle.

---

## Open Questions

- [ ] Track B: Can we patch `daily_scan.py` snapshot on the VPS remotely, or do we need to degrade?
- [ ] Track C: Does `daily_health_scores` table cover 2023-2024 fully? Run `build_health_scores.py` on full range first.
