# Shadow Convergence Audit Specification

## Purpose

Quantify alignment between shadow trading signals and backtest signals. Detect timing, price, and signal discrepancies. Root-cause analysis when convergence score falls below 80%.

## Requirements

### Requirement: SCA-REQ-01 — Signal Overlap Scoring

The system SHALL compute convergence score as `|signals_backtest ∩ signals_shadow| / |signals_backtest ∪ signals_shadow|` for each trading session. Backtest signals SHALL originate from `backtest_via_signal_engine.py` using `evaluate_ticker()` on historical data. Shadow signals SHALL originate from `daily_scan.py` using the same `evaluate_ticker()` on live/VPS data.

| Field | Specification |
|-------|---------------|
| Convergence score | Overlap / Union |
| Minimum threshold | 80% |
| Signal source (backtest) | `scripts/backtest_via_signal_engine.py` |
| Signal source (shadow) | `scripts/daily_scan.py` → `signal_engine.evaluate_ticker()` |

#### Scenario: High convergence
- GIVEN a day where shadow captured 18 tickers and backtest generated 20 tickers
- WHEN 16 tickers appear in both sets
- THEN convergence = 16 / 22 = 0.727 (72.7%)
- AND the system SHALL flag this as below the 80% threshold

#### Scenario: Empty union edge case
- GIVEN a day where both shadow and backtest produced zero signals
- WHEN convergence is computed
- THEN convergence score SHALL be 1.0 (perfect agreement, no action needed)

### Requirement: SCA-REQ-02 — Entry Price Discrepancy Check

For matching signals, the system SHALL compare entry timestamps and prices. A discrepancy > 2% of entry price SHALL be flagged as a timing/price anomaly.

#### Scenario: Price anomaly detection
- GIVEN a matching ticker in both signal sets
- WHEN backtest entry = $105.20 and shadow entry = $108.50
- THEN |105.20 - 108.50| / 105.20 = 3.14% > 2%
- AND the system SHALL flag this discrepancy for root-cause analysis

### Requirement: SCA-REQ-03 — Root-Cause Report

When convergence score < 80% or any price anomaly > 2%, the system SHALL generate a root-cause report. The report SHALL categorize discrepancies as: data freshness (VPS snapshot stale), universe mismatch, config drift, or unexplained.

#### Scenario: Root-cause with identified category
- GIVEN convergence score = 65% with 3 price anomalies
- WHEN root-cause analysis runs
- THEN each missing/anomalous signal SHALL be assigned a category
- AND the report SHALL recommend corrective action per category

### Requirement: SCA-REQ-04 — Degraded Fallback Mode

If VPS snapshots are unavailable or unfixable, the system MAY run a degraded audit that reports the convergence gap without fixing it. The degraded report SHALL clearly state that VPS-side data was unavailable.

#### Scenario: VPS snapshot unavailable
- GIVEN VPS daily_scan.py fails to produce shadow signals
- WHEN convergence check runs
- THEN the report SHALL document the gap as "VPS_UNAVAILABLE"
- AND the degradation gate SHALL be marked as "NOT_APPLICABLE"

### Requirement: SCA-REQ-05 — Output Persistence

The system SHALL persist convergence reports to `outputs/shadow_sandbox/convergence_report.md` (summary) and `outputs/live_signals/<date>/rejection_audit.csv` (detailed discrepancies).

#### Scenario: Persistence
- GIVEN a completed convergence check
- WHEN the report is written
- THEN `convergence_report.md` SHALL contain the daily score, threshold result, and anomaly count
- AND `rejection_audit.csv` SHALL contain one row per flagged discrepancy
