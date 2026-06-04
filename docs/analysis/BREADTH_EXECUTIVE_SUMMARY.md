# Breadth Market-Wide Experiment - Executive Summary

## Objective
Validate a binary market breadth gate on the PIT universe and determine whether it improves OOS Sharpe without worsening drawdown materially.

## Final Verdict
NO-GO.

The breadth gate was technically broken at first due to an undefined `PROJECT_ROOT` reference in `_build_breadth_mask()`. After fixing the path resolution, the gate became active and materially filtered entries.

## Method
- Universe: `pit.get_superset(2025-01-01, 2026-04-30)`
- Data source: `data/ticker_cache.db`
- PIT universe size used for breadth: `509` tickers
- IS window: `2025-01-01` to `2025-09-30`
- OOS window: `2025-10-01` to `2026-04-30`
- Baseline: `S0_Baseline` with `use_sector_etf_filter=False`, `use_breadth_filter=False`
- Breadth A/B tested as `% universe above SMA20`
- Thresholds tested: `0.40`, `0.45`, `0.50`, `0.55`, `0.60`

## Technical Validation
Before the fix, breadth failed with:
- `Error computing breadth mask: name 'PROJECT_ROOT' is not defined`

After the fix, the gate produced real filtering:
- Threshold `0.40`: `56` blocked days, `51` entries blocked
- Threshold `0.45`: `66` blocked days, `77` entries blocked
- Threshold `0.50`: `80` blocked days, `116` entries blocked
- Threshold `0.55`: `99` blocked days, `163` entries blocked
- Threshold `0.60`: `116` blocked days, `199` entries blocked

## Breadth Behavior
For the PIT universe, `% close > SMA20` was not saturated:
- Mean breadth: `0.489` (IS), `0.470` (OOS)
- Median breadth: `0.528` (IS), `0.567` (OOS)
- At threshold `0.50`, gate passed `106/186` IS days and `88/146` OOS days

## Results
### Baseline
- `S0_Baseline` IS Sharpe: `-0.7159027132`
- `S0_Baseline` IS max drawdown: `-0.2897237774` (`-28.97%`)
- `S0_Baseline` IS total trades: `3863`
- `S0_Baseline` OOS Sharpe: `0.4935599885`
- `S0_Baseline` OOS max drawdown: `-0.0862309632` (`-8.62%`)
- `S0_Baseline` OOS total trades: `878`

### Sector Only
- `S1_SectorOnly` IS Sharpe: `-0.7789923843`
- `S1_SectorOnly` IS max drawdown: `-0.2562880271` (`-25.63%`)
- `S1_SectorOnly` IS total trades: `3745`
- `S1_SectorOnly` OOS Sharpe: `0.6088487438`
- `S1_SectorOnly` OOS max drawdown: `-0.0862309632` (`-8.62%`)
- `S1_SectorOnly` OOS total trades: `850`

### Breadth Solo
- `B1_BreadthSolo_040` = threshold `0.40`
- `B1_BreadthSolo_040` IS Sharpe: `0.0132219057`
- `B1_BreadthSolo_040` OOS Sharpe: `0.9393432093`
- `B1_BreadthSolo_040` OOS max drawdown: `-0.0377651420` (`-3.78%`)
- `B1_BreadthSolo_040` OOS total trades: `811`
- `B1_BreadthSolo_040` OOS PF: `23.9241250396` (inflated)

- `B1_BreadthSolo_045` = threshold `0.45`
- `B1_BreadthSolo_045` IS Sharpe: `0.0334913574`
- `B1_BreadthSolo_045` IS max drawdown: `-0.2183575375` (`-21.84%`)
- `B1_BreadthSolo_045` OOS Sharpe: `1.1224768680`
- `B1_BreadthSolo_045` OOS max drawdown: `-0.0385123413` (`-3.85%`)
- `B1_BreadthSolo_045` OOS total trades: `770`
- `B1_BreadthSolo_045` OOS PF: `1.8568224996`

- `B1_BreadthSolo_050` = threshold `0.50`
- `B1_BreadthSolo_050` IS Sharpe: `0.2623097745`
- `B1_BreadthSolo_050` OOS Sharpe: `0.8440697768`
- `B1_BreadthSolo_050` OOS max drawdown: `-0.0473184128` (`-4.73%`)
- `B1_BreadthSolo_050` OOS total trades: `709`
- `B1_BreadthSolo_050` OOS PF: `1.7224831241`

- `B1_BreadthSolo_055` = threshold `0.55`
- `B1_BreadthSolo_055` IS Sharpe: `-0.3247013155`
- `B1_BreadthSolo_055` OOS Sharpe: `0.9364423527`
- `B1_BreadthSolo_055` OOS max drawdown: `-0.0377651420` (`-3.78%`)
- `B1_BreadthSolo_055` OOS total trades: `620`
- `B1_BreadthSolo_055` OOS PF: `25.5775911715` (inflated)

- `B1_BreadthSolo_060` = threshold `0.60`
- `B1_BreadthSolo_060` IS Sharpe: `-0.2958578832`
- `B1_BreadthSolo_060` OOS Sharpe: `0.4940440843`
- `B1_BreadthSolo_060` OOS max drawdown: `-0.0834592896` (`-8.35%`)
- `B1_BreadthSolo_060` OOS total trades: `500`

### Breadth + Sector
- `B2_BreadthPlusSector_040` OOS Sharpe: `1.3121762798`
- `B2_BreadthPlusSector_040` OOS max drawdown: `-0.0741815880` (`-7.42%`)
- `B2_BreadthPlusSector_040` OOS total trades: `825`

- `B2_BreadthPlusSector_050` OOS Sharpe: `1.7380941998`
- `B2_BreadthPlusSector_050` OOS max drawdown: `-0.0202193421` (`-2.02%`)
- `B2_BreadthPlusSector_050` OOS total trades: `782`

- `B2_BreadthPlusSector_055` OOS Sharpe: `2.9695371997`
- `B2_BreadthPlusSector_055` OOS max drawdown: `-0.0478619506` (`-4.79%`)
- `B2_BreadthPlusSector_055` OOS total trades: `744`

- `B2_BreadthPlusSector_060` OOS Sharpe: `1.2176776009`
- `B2_BreadthPlusSector_060` OOS max drawdown: `-0.0476357307` (`-4.76%`)
- `B2_BreadthPlusSector_060` OOS total trades: `602`

## Interpretation
- Breadth is not a no-op on the PIT universe.
- It blocks real signal days: `51` to `199` blocked entries depending on threshold.
- It improves OOS Sharpe vs baseline by a wide margin in the tested sweep.
- In the walk-forward validation, the edge did not survive robustly.
- The apparent static-split edge was not production-grade.

## Caveats
- Profit Factor inflation is present in `0.40` and `0.55`.
- The walk-forward folds showed the same OOS window repeated, so the original WF implementation was not a clean rolling OOS test.
- The resulting fold outputs did not support production deployment.
- The candidate naming in the JSON remains the source of truth: `B1_BreadthSolo_045` means threshold `0.45`.

## Recommendation
Close breadth as `NO-GO` for production. Move the research focus to regime handling and the active `combo_pullback_entry` workflow.

## Relevant Files
- `src/backtest/vectorbt_engine_advanced.py`
- `experiments/breadth_sandbox.py`
- `docs/analysis/BREADTH_EXPERIMENT_PROTOCOL.md`
- `outputs/experiments/breadth_sandbox_20260507_154521.json`
