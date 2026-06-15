# IC Phase 1 Freeze (2026-04-15)

## Objetivo
Congelar el proceso por 6 semanas para validar edge real sin sobre-optimizacion.

## Estados operativos
- `combo_pullback_entry`: `PAPER_TRADING_ACTIVE` (capital paper: `100000`)
- `combo_pure_momentum`: `INCUBATOR_OBSERVATIONAL` (sin capital)
- `combo_aggressive_momentum`: `NO_GO_ARCHIVED`

## Reglas de freeze
- Sin retuneo de parametros.
- Sin nuevos combos.
- Sin re-torneo de optimizacion.
- Universo y horario de trading congelados.

## Siguiente paso operativo (Fase 2)
1. Ejecutar walk-forward con fold 2025 incluido:
   - `python3 scripts/walk_forward_combos.py --all`
2. Ejecutar sensibilidad a costos:
   - `python3 scripts/cost_sensitivity.py --all`

## Nota de evidencia OOS
- Evidencia principal: 2023, 2024, 2025.
- Evidencia de stress: 2022.
- Si hay muestra insuficiente, accion por defecto: `HOLD_NO_GO`.
