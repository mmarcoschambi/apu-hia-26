# Technical Backlog & Design Decisions

This document outlines ongoing observations, technical debt, and non-blocking issues registered for future quant research and engineering cycles.

---

## 1. Optimizer Export Bug (Staging Metadata)
* **Owner**: Antigravity
* **Target Date**: 2026-07-17
* **Status**: Resolved ✅
* **Observation**: 
  When `optimize_combo.py` finished and exported the results, `universe_size: 39` and `period: N/A` were written due to missing properties in the JSON generator, triggering defaults in `sync_combo_config.py`.
* **Resolution**: 
  Corrected `export_combo_result` and its caller in `optimize_combo.py` to capture and write the actual `start_date`, `end_date`, and real size of the filtered universe (`len(screened_universe)`).

## 2. Drop in Relative Strength Coverage (`rs_coverage_pct`)
* **Owner**: Antigravity
* **Target Date**: 2026-07-31
* **Status**: Logged / Under Investigation
* **Observation**: 
  The Relative Strength coverage percentage (`rs_coverage_pct`) dropped significantly from `96.81%` to `66.15%`.
* **Impact**: 
  A lower coverage means the screener is assessing fewer tickers than expected, potentially due to missing data points in the cache database (`ticker_cache.db`) or strict filter intersections.
* **Next Steps**: 
  Perform a data audit on the historical caching pipelines. Verify database population script outputs and identify whether certain tickers fail data validation, leading to exclusions from the RS calculations.

## 3. Loader Reconciliation (YAML vs JSON/Canonical)
* **Owner**: Antigravity
* **Target Date**: 2026-07-17
* **Status**: Resolved ✅
* **Observation**: 
  Discrepancies and code duplication between how variables were loaded and validated in `app.py` vs the core system's canonical loader (`src/config/config_loader.py`).
* **Resolution**: 
  Refactored `src/config/dynamic_config.py` to delegate `load_production_config` directly to `src/config/config_loader.py`, enforcing canonical schema validation across all UI entries and live signal scripts.

## 4. Production Monitoring: Dynamic Sizing E25
* **Owner**: Antigravity
* **Target Date**: 2026-07-31
* **Status**: Active Watchlist
* **Observation**: 
  The E25 sizing model and the Atlas v2 curve are active in production on the VPS (`max_dist_sma20: 13.60%`, `max_exposure_pct: 0.294%`).
* **Next Steps**: 
  Monitor performance on a weekly basis using the metrics defined below to ensure VPS results converge with local laboratory baselines.

---

## 5. Production Monitoring Framework (E25 / Atlas v2)

To ensure the integrity of live execution, the E25 sizing model and Atlas v2 curve will be audited under the following framework:

* **Monitoring Cadence**: Weekly (every Saturday after market close).
* **Target Baseline**: Russell + E25 (96.12% Return, -35.09% MDD).
* **Key Metrics**:
  1. **Sharpe Ratio OOS**: Weekly and 30-day rolling (Target: `>= 1.50`).
  2. **Max Drawdown OOS**: Absolute drawdown during live tracking (Target: `<= 10.0%`).
  3. **Win Rate (WR)**: Percentage of profitable closed trades (Target: `>= 40.0%`).
  4. **Portfolio Exposure vs VIX**: Validation that `max_exposure_pct` correctly downscales when VIX rises above 25.0.
  5. **Parity Drift**: Variance in execution price/return between local simulation and VPS live logs (Target: `<= 0.50%` average drift per trade).

