# Project Instructions: Momentum V2

## Overview
This project implements a high-conviction momentum trading system based on growth niches and thematic divergence.

## Architectural Patterns
- **Signal Engine**: Canonical truth for all signal logic (`src/signals/signal_engine.py`). Shared between live and backtest.
- **Tier 2 Filters**: Multi-layered validation including RS, ADR, Sector ETF, and Thematic Groups.
- **Thematic Divergence**: Variant E (Theme OK, Sector NO) is the current high-conviction filter for swing setups (horizon >= 10 days).

## Thematic Divergence Verification (Plan E11 - In Progress)
- **Status**: SHADOW MODE (Verification phase).
- **Consolidation**: Canonical logic implemented in `src/signals/thematic_logic.py`.
- **Target Rule**: `theme_above_sma20 AND NOT sector_etf_ok` (Variant E).
- **Monitoring**: Active in Shadow Logger and Telegram Views (Theme RS).
- **Gate GO/NO-GO**: Requires 15 real rounds with PF > 3.0 and WR > 55%.
- **Documentation**: Detailed plan in `docs/analysis/THEMATIC_DIVERGENCE_VERIFICATION_E11.md`.

## Phase 3: Paper Trading (Current)
- **Research**: Use `experiments/` for sandbox validation.
- **Strategy**: Document IS/OOS metrics before core integration.
- **Execution**: Feature-flag all new filters (`config/production_config.json`).
- **Validation**: Parallel observation (Local PIT vs Finviz Live) during paper trading.

## Phase 3: Paper Trading (Current)
- **Primary Universe**: Local PIT (ADV Top 200 Dollar Volume).
- **Secondary Universe**: Finviz Live (Observation only in `rejection_audit.csv`).
- **Monitoring**: Check `outputs/live_signals/YYYY-MM-DD/rejection_audit.csv` for allowed/blocked signals and drift.

## Critical Fixes (2026-05-18)
- **Signal Engine**: Fixed ATR propagation bug (stops now use 2xATR correctly).
- **Sizing**: Risk-per-trade now correctly read from `production_config.json` ($2,878).
- **Backtest Parity**: Engine now implements full A/B combo merge and liquidity-based universe selection.
- **Gold Standard Baseline**: +2.5% Return, -16.07% MDD, 100 trades (2Y PIT).

## Environment Separation (Laboratory vs VPS)
The system is **Auto-Aware** of its environment:
- **Laboratory (Local)**: If `data/ticker_cache.db` exists, it runs in **Hybrid Mode**. It uses the PIT universe for primary decisions (Fase 3) and Finviz for observation.
- **Torre de Control (VPS)**: Since the DB is excluded via `deploy_vps.sh`, the scanner automatically promotes **Finviz Live** to be the primary decision source. This allows for 24/7 autonomous monitoring without the heavy DB.
- **Sync**: Use `./deploy_vps.sh` to push logic and taxonomy updates to the VPS.
