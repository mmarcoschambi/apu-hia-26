# Project Instructions: Momentum V2

## Overview
This project implements a high-conviction momentum trading system based on growth niches and thematic divergence.

## Architectural Patterns
- **Signal Engine**: Canonical truth for all signal logic (`src/signals/signal_engine.py`). Shared between live and backtest.
- **Tier 2 Filters**: Multi-layered validation including RS, ADR, Sector ETF, and Thematic Groups.
- **Thematic Divergence**: Variant E (Theme OK, Sector NO) is the current high-conviction filter for swing setups (horizon >= 10 days).

## Thematic Divergence Experiment (Completed 2026-05-12)
- **Status**: GO (Validated in OOS with Delta Sharpe +0.452).
- **Taxonomy**: Frozen at `v1.0-2026-05-12` (~100 tickers).
- **Core Edge**: Captures capital rotation into strong niches during broad sector weakness.
- **Key Caveats**:
    - Sniper setup (30% retention).
    - Requires horizon >= 10 days.
    - 5d Sharpe is negative (needs time to unfold).

## Development Workflow
- **Research**: Use `experiments/` for sandbox validation.
- **Strategy**: Document IS/OOS metrics before core integration.
- **Execution**: Feature-flag all new filters (`config/production_config.json`).
- **Validation**: Parallel observation (Local PIT vs Finviz Live) during paper trading.

## Phase 3: Paper Trading (Current)
- **Primary Universe**: Local PIT (ADV Top 200).
- **Secondary Universe**: Finviz Live (Observation only in `rejection_audit.csv`).
- **Monitoring**: Check `outputs/live_signals/YYYY-MM-DD/rejection_audit.csv` for allowed/blocked signals and drift.
