# Master Universe + Paper Runbook

## Objetivo
Flujo manual (consola/scripts) para:
1) sincronizar universo maestro
2) escanear combos
3) generar alertas
4) simular paper execution
5) generar reporte de performance

## Flujo diario recomendado

```bash
# 1) Universo maestro fresco
python3 scripts/sync_universe.py --force

# 2) Scanner multi-combo sobre universo estable
python3 scripts/run_combo_scanner.py --universe-source stable

# 3) Validar schema de señales
python3 scripts/validate_signals.py outputs/live_signals/$(date +%F)/combined.csv --verbose

# 4) Alertas consola (top 20)
python3 scripts/send_signal_alerts.py --date $(date +%F) --top 20

# 5) Simulación paper (genera ledger)
python3 scripts/paper_execution_loop.py --date $(date +%F)

# 6) Reporte de performance del run
python3 scripts/paper_report.py --date $(date +%F)
```

## Modos útiles

### Dry run (sin escribir archivos)
```bash
python3 scripts/run_combo_scanner.py --universe-source stable --dry-run
python3 scripts/paper_execution_loop.py --date 2026-04-24 --dry-run
```

### Combo puntual
```bash
python3 scripts/run_combo_scanner.py --universe-source stable --agents combo_pure_momentum --dry-run
python3 scripts/send_signal_alerts.py --date 2026-04-24 --agents combo_pure_momentum
```

### Alertas exportadas a markdown
```bash
python3 scripts/send_signal_alerts.py --date 2026-04-24 --top 20 --export-md
```

### Reporte agregado de todos los runs
```bash
python3 scripts/paper_report.py --all
```

## Artefactos esperados

- Universo maestro
  - `data/stable_universe.csv`
  - `data/stable_universe.meta.json`
- Señales scanner
  - `outputs/live_signals/<date>/combined.csv`
  - `outputs/live_signals/<date>/<agent>.csv`
  - `outputs/live_signals/<date>/run_summary.json`
- Alertas
  - `outputs/alerts/alerts_<date>.md` (si `--export-md`)
- Paper run
  - `outputs/paper_trading/runs/<date>/orders.csv`
  - `outputs/paper_trading/runs/<date>/fills.csv`
  - `outputs/paper_trading/runs/<date>/positions.csv`
  - `outputs/paper_trading/runs/<date>/equity_curve.csv`
  - `outputs/paper_trading/runs/<date>/run_report.json`
  - `outputs/paper_trading/runs/<date>/performance_report.json` (si export)

## Nota operativa

Si no hay barras para la fecha del run (ej. señales más nuevas que la data de DB),
el loop paper marca salida `no_data` y cierra al precio de entrada para mantener
consistencia contable sin inventar precios.
