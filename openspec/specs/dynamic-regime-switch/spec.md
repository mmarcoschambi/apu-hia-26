# Dynamic Regime Switch Specification

## Purpose

Map health_score (0-7) to ATTACK / DEFENSE_PARTIAL / DEFENSE_FULL modes that adjust risk sizing and theme filters dynamically. Validate via backtest that the dynamic mode does not regress vs the best static mode.

## Requirements

### Requirement: DRS-REQ-01 — Health Score to Mode Mapping

The system SHALL map health_score to mode using `get_active_mode()`: score ≥ 6 → ATTACK, score 4-5 → DEFENSE_PARTIAL, score < 4 → DEFENSE_FULL. The health_score SHALL be computed from SPY/VIX indicators (SPY>EMA20, SPY>SMA50, SPY>SMA200, VIX<20, VIX stability, sector breadth) as defined in `calculate_health_score_pit()`.

| Mode | Health Score | Theme Filter | Risk Multiplier |
|------|-------------|--------------|-----------------|
| ATTACK | ≥ 6 | OFF | 1.0 |
| DEFENSE_PARTIAL | 4-5 | ON | 0.75 |
| DEFENSE_FULL | < 4 | ON | 0.35 |

#### Scenario: Full range mapping
- GIVEN health_score = 7
- WHEN get_active_mode(7) is called
- THEN mode = ATTACK, risk_multiplier = 1.0, theme_filter = OFF

#### Scenario: Edge boundary at 6
- GIVEN health_score = 6
- WHEN get_active_mode(6) is called
- THEN mode = ATTACK (≥ 6 threshold is inclusive)

#### Scenario: Edge boundary at 4
- GIVEN health_score = 4
- WHEN get_active_mode(4) is called
- THEN mode = DEFENSE_PARTIAL

#### Scenario: Defense full activation
- GIVEN health_score = 2
- WHEN get_active_mode(2) is called
- THEN mode = DEFENSE_FULL, risk_multiplier = 0.35, theme_filter = ON

### Requirement: DRS-REQ-02 — Risk Sizing Application

The system SHALL apply risk_multiplier to the base risk per trade (from `risk_fraction * capital`). The system SHALL also apply `risk_pct_by_regime` from `production_config.json` when available, falling back to ATTACK baseline × risk_multiplier.

| Mode | risk_pct_by_regime | Effective risk per $100k |
|------|-------------------|--------------------------|
| ATTACK | 0.0364 | $3,640 |
| DEFENSE_PARTIAL | 0.028 | $2,800 |
| DEFENSE_FULL | 0.0168 | $1,680 |

#### Scenario: Risk scaling
- GIVEN base risk = $2,878 per trade and health_score = 3
- WHEN risk is applied in DEFENSE_FULL mode (multiplier = 0.35)
- THEN effective risk = $2,878 × 0.35
- AND the backtest engine SHALL use the reduced value

### Requirement: DRS-REQ-03 — Theme Filter Control

When mode is ATTACK, the system SHALL disable theme filter (`use_theme_group_filter = False`). When mode is DEFENSE_PARTIAL or DEFENSE_FULL, the system SHALL enable theme filter.

#### Scenario: Theme filter toggling
- GIVEN a daily scan with dynamic mode
- WHEN health_score transitions from 6 to 4
- THEN theme filter toggles from OFF to ON
- AND the signal output SHALL reflect the new filter state

### Requirement: DRS-REQ-04 — Backtest Mode Comparison

The system SHALL run a three-way backtest comparison: always ATTACK, always DEFENSE (or best static), and dynamic switching. The comparison SHALL cover 2023-2024 on the Russell 1000 universe. Dynamic mode MUST NOT regress beyond -10% relative return vs the best static mode.

#### Scenario: Dynamic mode passes
- GIVEN three backtests on 2023-2024
- WHEN ATTACK returns 12%, DEFENSE returns 8%, dynamic returns 11%
- THEN dynamic (11%) is within 10% of best (12%) → PASS

#### Scenario: Dynamic mode fails
- GIVEN ATTACK returns 15%, DEFENSE returns 5%, dynamic returns 4%
- WHEN dynamic is compared to best static (ATTACK at 15%)
- THEN (4% - 15%) / 15% = -73% regression → REJECT

### Requirement: DRS-REQ-05 — Historical Mode Persistence

The system SHALL persist daily mode decisions to the `daily_health_scores` table alongside health_score and regime_mode. The DB schema SHALL include `date`, `health_score`, `regime_mode`, `risk_mult`, and `theme_filter_enabled`.

#### Scenario: DB persistence
- GIVEN a daily scan completion with health_score = 5
- WHEN mode is computed and persisted
- THEN the daily_health_scores table SHALL contain a row with date, score=5, regime_mode="DEFENSE_PARTIAL", risk_mult=0.75, theme_filter_enabled=1
