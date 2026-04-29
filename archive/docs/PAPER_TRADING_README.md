# Paper Trading Setup — 2026-04-09

## Estado Inicial

### Benchmark Congelado
- **Snapshot**: `baseline_snapshots/2026-04-09_paper_launch/`
- содержит:
  - `baseline_metrics.json`
  - `run_config.json`
  - `*_wf.json` (walk-forward results)
  - `*_costs.json` (cost sensitivity)
  - `decision_gate_report.md`

### Portfolio Asignado
| Combo | Role | Allocation |
|-------|------|------------|
| combo_pullback_entry | GO-PAPER | 70% |
| combo_aggressive_momentum | WATCH-PAPER | 30% |
| combo_pure_momentum | SHADOW | 0% |
| combo_stage2_breakout | SHADOW | 0% |
| combo_universal_any | SHADOW | 0% |

## Scripts Operativos

### Daily Runbook
```bash
# Pre-market
python3 scripts/paper_trading_runbook.py --phase pre

# Intraday (optional)
python3 scripts/paper_trading_runbook.py --phase intra

# End of day
python3 scripts/paper_trading_runbook.py --phase eod

# Full day (all phases)
python3 scripts/paper_trading_runbook.py --phase all
```

### Weekly Review
```bash
python3 scripts/paper_weekly_review.py --weeks 2
```

## Config Files
- `config/paper_portfolio_config.json` — portfolio definition

## Outputs
- `outputs/paper_trading/daily_pnl_YYYYMMDD.json` — daily P&L
- `outputs/paper_trading/weekly_report_YYYYMMDD.json` — weekly KPIs

## Gates Activos

### Walk-Forward (Regime-Aware)
- Min trades/fold: 30
- Folds válidos: >= 2 con muestra suficiente
- Positive folds: >= 2
- PF mean: > 1.0
- Sharpe mean: > 0.25

### Decision Gate
- wf_verdict = GO (from walk-forward)
- baseline checks: trades >= 50, PBO <= 0.85, PF >= 1.2
- cost: breakeven >= 10 bps

## Known Issues
1. Cost sensitivity block no aplica costos reales (métricas idénticas en todos los bps)
2. Regime check en pre-market puede fallar con VIX (yfinance API change)
3. Total return muestra 0.0 en WF reports (key mismatch)

## Next Steps
1. Implementar signal generation real en pre-market phase
2. Conectar con paper broker / simulator
3. Recalibrar gates tras 4-6 semanas de paper real