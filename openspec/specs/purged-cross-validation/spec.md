# Purged Cross-Validation Specification

## Purpose

Prevent data leakage in walk-forward validation by applying purge and embargo windows around test periods. Gate strategy promotion on IS-to-OOS Sharpe degradation ≤ 25%.

## Requirements

### Requirement: PCV-REQ-01 — Expanding Window Walk-Forward

The system SHALL implement expanding-window walk-forward with N folds (default: 4). Each fold SHALL use all available data from a fixed start date (e.g., 2019-01-01) through the fold's IS cutoff as training. The OOS period SHALL be one year forward.

| Field | Specification |
|-------|---------------|
| N folds | 4 (configurable via `WF_N_FOLDS`) |
| Train start | Fixed: `2019-01-01` |
| OOS window | 1 year per fold |
| Universe | Top N by data availability, identical across folds |

#### Scenario: Standard 4-fold execution
- GIVEN a strategy config with 2019-2025 data
- WHEN walk-forward runs with 4 folds (OOS: 2022, 2023, 2024, 2025)
- THEN each fold trains on expanding window from 2019 and tests on one OOS year
- AND all 4 folds complete with measurable IS/OOS metrics

### Requirement: PCV-REQ-02 — Purge and Embargo Windows

The system SHALL apply purge_days (default: 10 trading days) immediately before each test period. The system SHALL apply embargo_days (default: 5 trading days) immediately after each test period. Data within purge/embargo windows MUST be excluded from the training set.

#### Scenario: Leakage prevention
- GIVEN a fold with OOS starting 2023-01-01
- WHEN training data is assembled
- THEN no trades from 10 trading days before 2023-01-01 appear in training
- AND no trades from 5 trading days after 2022-12-31 appear in training

#### Scenario: Configurable windows
- GIVEN a config override for purge_days=20, embargo_days=10
- WHEN walk-forward is executed
- THEN the purge/embargo windows use the overridden values

### Requirement: PCV-REQ-03 — Degradation Gate

The system SHALL compute IS Sharpe (mean across folds of IS Sharpe per fold) and OOS Sharpe (mean across folds of OOS Sharpe per fold). The gate SHALL reject if `(IS_sharpe - OOS_sharpe) / IS_sharpe > 0.25`.

#### Scenario: Gate pass
- GIVEN a strategy with IS Sharpe = 1.20 and OOS Sharpe = 1.00
- WHEN degradation is computed
- THEN (1.20 - 1.00) / 1.20 = 0.167 ≤ 0.25 → PASS

#### Scenario: Gate reject (degradation > 25%)
- GIVEN a strategy with IS Sharpe = 1.50 and OOS Sharpe = 0.90
- WHEN degradation is computed
- THEN (1.50 - 0.90) / 1.50 = 0.40 > 0.25 → REJECT

#### Scenario: Insufficient trades
- GIVEN a fold with fewer than 30 OOS trades
- WHEN degradation is computed
- THEN that fold MUST be flagged as statistically insignificant
- AND the gate SHALL include a warning in the validation report

### Requirement: PCV-REQ-04 — Aggregate Reporting

The system SHALL produce a validation report containing per-fold IS/OOS Sharpe, mean IS/OOS Sharpe, degradation %, trades per fold, and gate verdict (PASS/REJECT).

#### Scenario: Report completeness
- GIVEN a completed purged walk-forward run
- WHEN the report is generated
- THEN it MUST include all 4 fold metrics, aggregate stats, and final gate verdict
