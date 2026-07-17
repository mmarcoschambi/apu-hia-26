# Technical Backlog & Design Decisions

This document outlines ongoing observations, technical debt, and non-blocking issues registered for future quant research and engineering cycles.

---

## 1. Optimizer Export Bug (Staging Metadata)
* **Status**: Logged / Non-blocking
* **Observation**: 
  When `optimize_combo.py` finishes and exports the results, `universe_size: 39` and `period: N/A` are written in `combo_pure_momentum_optimized.json`.
* **Impact**: 
  This causes incorrect staging metadata representation. The canonical loaders bypass this gracefully, but the export logic in `optimize_combo.py` should be corrected to properly capture the actual run dates (`start_date`, `end_date`) and the real size of the filtered universe instead of falling back to default values.

## 2. Drop in Relative Strength Coverage (`rs_coverage_pct`)
* **Status**: Logged / Under Investigation
* **Observation**: 
  The Relative Strength coverage percentage (`rs_coverage_pct`) dropped significantly from `96.81%` to `66.15%`.
* **Impact**: 
  A lower coverage means the screener is assessing fewer tickers than expected, potentially due to missing data points in the cache database (`ticker_cache.db`) or strict filter intersections.
* **Next Steps**: 
  Perform a data audit on the historical caching pipelines. Verify database population script outputs and identify whether certain tickers fail data validation, leading to exclusions from the RS calculations.

## 3. Loader Reconciliation (YAML vs JSON/Canonical)
* **Status**: Tech Debt
* **Observation**: 
  The configuration loader in `app.py` uses a custom YAML loading implementation, whereas the core system's canonical loader (`src/integration/combo_loader.py`) loads JSON configs from `outputs/best_combos_run/`.
* **Impact**: 
  Risk of drift between how variables are hydrated in the Streamlit UI dashboard and how the live signal engine runs.
* **Next Steps**: 
  Refactor `app.py` to use `src/integration/combo_loader.py` as its single source of truth for configuration loading, ensuring identical parameter parsing and fallback mechanisms.

## 4. Production Monitoring: Dynamic Sizing E25
* **Status**: Production Watchlist
* **Observation**: 
  The E25 sizing model and the Atlas v2 curve are active in production on the VPS (`max_dist_sma20: 13.60%`, `max_exposure_pct: 0.294%`).
* **Next Steps**: 
  Monitor the performance of E25 sizing during the first few weeks. Track metric deviations, drawdowns, and execution parameters against the baseline (Russell + E25: 96.12% Return, -35.09% MDD) to verify that local sandbox results match live execution in the production environment.
