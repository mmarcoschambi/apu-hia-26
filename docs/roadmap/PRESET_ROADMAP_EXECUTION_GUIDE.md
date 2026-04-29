# Preset Roadmap Execution Guide

## Objetivo
Dejar lista la arquitectura de backtest del screener para ejecutar por fases cuando `ticker_cache.db` deje de estar lockeada.

## Archivos base
- Spec de presets: `config/presets/screener_presets_v1.yaml`
- Libreria de filtros: `src/strategies/preset_filter_library.py`
- Check de readiness: `scripts/preset_roadmap_readiness.py`

## Estado de implementacion
- Implementado (simple/medio):
  - `market_cap_min`
  - `avg_volume_50_min`
  - `adr_50_min`
  - `rs_1m_percentile_min`
  - `trend_base`
  - `rel_volume_min`
  - `power_play`
  - `power_play_cluster_20d_min3`
  - `vcs_score_min`
  - `near_52w_high_band`
  - `weekly_return_min`
- Scaffold (complejo):
  - `ll_hl_confirmed`
  - `fib_0618_break_between_hl_and_swing_high`
  - `second_pivot_break_swing_high`
  - `downtrend_line_break`

## Ejecucion recomendada por fases
1. Ver readiness:
   - `python3 scripts/preset_roadmap_readiness.py`
2. Poblar rankings diarios (cuando DB se destrabe):
   - `python3 scripts/populate_rankings_daily.py --start 2019-01-01 --end 2024-12-31 --workers 1`
3. Correr backtest/ablation de etapa 1 (presets 05-08).
4. Correr etapa 2 (presets 09-12).
5. Implementar bloqueadores complejos y correr etapa 3 (presets 01-04).
6. Gate final:
   - `python3 scripts/walk_forward_combos.py`
   - `python3 scripts/cost_sensitivity.py`
   - `python3 scripts/decision_gate.py`

## Nota de riesgo
No promover presets que dependan de filtros en scaffold hasta tener validacion out-of-sample + walk-forward + costos.
