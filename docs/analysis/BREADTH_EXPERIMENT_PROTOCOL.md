# Breadth Market-Wide Experiment Protocol

## Hypothesis
Adding a binary market breadth gate improves OOS Sharpe without worsening risk.

## Variables Modified
- `use_breadth_filter`
- `breadth_filter_mode`
- `breadth_filter_threshold`

## Dataset
- Source: `data/ticker_cache.db`
- Universe: `pit.get_superset(START_DATE, END_DATE)`
- Price fields: `open`, `high`, `low`, `close`, `volume`, `dollar_volume`

## Baseline
- `S0_Baseline`
- `use_sector_etf_filter=False`
- `use_breadth_filter=False`

## Metrics Expected
- Sharpe
- Max drawdown
- Total trades
- Win rate
- Profit factor

## GO / NO-GO
- GO if OOS Sharpe is at least baseline
- GO if max drawdown is no worse than baseline
- GO if trades do not collapse
- GO if the edge appears across at least 2 thresholds
- Otherwise NO-GO

## Validation Status
- Technical validation: PASS after fixing `_build_breadth_mask()` path resolution.
- Production validation: NO-GO after walk-forward review.

## Scope
- Stage 1: Hypothesis A, `% universe above SMA20`
- Stage 2: Hypothesis B, `new highs / (new highs + new lows)` only if Stage 1 fails

## Executive Summary
- Detailed results and final verdict are documented in `docs/analysis/BREADTH_EXECUTIVE_SUMMARY.md`.

## Current Readout
- Breadth is closed as a production gate; focus shifts to regime handling and the active pullback workflow.
