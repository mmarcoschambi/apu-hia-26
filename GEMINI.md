# Project Instructions: Momentum V2

## Overview
This project implements a high-conviction momentum trading system based on growth niches and thematic divergence.

## Architectural Patterns
- **Signal Engine**: Canonical truth for all signal logic (`src/signals/signal_engine.py`). Shared between live and backtest.
- **Tier 2 Filters**: Multi-layered validation including RS, ADR, Sector ETF, and Thematic Groups.
- **Thematic Divergence**: Variant E (Theme OK, Sector NO) is the current high-conviction filter for swing setups (horizon >= 10 days).

## Gold Standard Candidate: ex-XLV (Healthcare Exclusion)
- **Status**: SHADOW MODE (Promoted as Gold Standard Candidate / Shadow Candidate).
- **Target Strategy**: Russell 1000 + E25 Dynamic Extension Sizing + Sector Exclusion (XLV blacklisted).
- **Variant E Filter**: Kept out of the core config for now.
- **Monitoring**: Exclusions active in daily scans and backtests.
- **Documentation**: Detailed reports in `docs/analysis/` and `russell_e25_robustness_report.md`.

## Phase 3: Paper Trading (Current)
- **Research**: Use `experiments/` for sandbox validation.
- **Strategy**: Document IS/OOS metrics before core integration.
- **Execution**: Feature-flag all new filters (`config/production_config.json`).
- **Validation**: Parallel observation (Local PIT vs Finviz Live) during paper trading.

## Phase 3: Paper Trading (Current)
- **Primary Universe**: Local PIT (ADV Top 200 Dollar Volume).
- **Secondary Universe**: Finviz Live (Observation only in `rejection_audit.csv`).
- **Monitoring**: Check `outputs/live_signals/YYYY-MM-DD/rejection_audit.csv` for allowed/blocked signals and drift.

## Verified System State (2026-05-18)
- **Fixed Production Bugs**: Corrected ATR propagation (stops now use 2xATR correctly) and dynamic sizing ($2,878 risk-per-trade read from config). Live paper trading is now accurate.
- **Canonical Backtest Engine**: `scripts/backtest_via_signal_engine.py` is now the single source of truth for simulation. Implements full A/B merge, PIT universe (ADV20), and real Portfolio Manager (6 positions, 2/sector).
- **Gold Standard Baseline**: +2.5% Return, -16.1% MDD, 0.45 Sharpe (2023-2024 PIT).
- **ex-XLV Candidate (Shadow)**: Sector exclusion (ex-XLV) validated over 2019-2025: Net PnL $77,105.43, Max Drawdown -16.26%, temporal consistency passed (3/4 windows positive). Promoted to Shadow Candidate.

## Pending Roadmap
- **Dynamic Switch (Ataque/Defensa)**: Blocked until historical `health_score` is pre-calculated in DB.
- **Variant E Promotion**: Blocked until Shadow Mode accumulates ~30-40 real signals.

## Environment Separation (Laboratory vs VPS)
The system is **Auto-Aware** of its environment:
- **Laboratory (Local)**: If `data/ticker_cache.db` exists, it runs in **Hybrid Mode**. It uses the PIT universe for primary decisions (Fase 3) and Finviz for observation.
- **Torre de Control (VPS)**: Since the DB is excluded via `deploy_vps.sh`, the scanner automatically promotes **Finviz Live** to be the primary decision source. This allows for 24/7 autonomous monitoring without the heavy DB.
- **Deploy to VPS**: Use `./deploy_vps.sh` to push logic, taxonomy updates, and crontabs to the VPS.
- **Data Sync from VPS**: Use `./sync_from_vps.sh` on the local machine (WSL2) to pull `outputs/` down for research without inflating GCP snapshot costs.
- **VPS Automated Archive**: The VPS runs `deploy/weekly_archive_vps.sh` every Friday to compress old logs and JSONs before the local machine syncs them, maintaining disk hygiene.
