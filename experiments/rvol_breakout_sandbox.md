# RVOL Breakout Filter

## Objetivo
Validar si exigir `rvol_breakout_threshold` en el día exacto del breakout mejora la calidad de las entradas del combo `pure_momentum` sin recortar demasiado el universo.

## Setup
- Baseline: `combo_pure_momentum` con `min_rvol = 1.5`
- Variable modificada: `rvol_breakout_threshold`
- Configuraciones: `S0=None`, `S1=1.0`, `S2=1.2`, `S3=1.5`, `S4=2.0`
- Dataset:
  - IS: `2022-01-01` to `2024-06-30`
  - OOS: `2024-07-01` to `2025-06-30`
  - Holdout: `2025-07-01` to hoy

## Resultado
- `S0-S3` quedaron idénticos al baseline.
- `S4=2.0` redujo trades y empeoró el desempeño.
- No hubo threshold ganador.

## Decisión
- `NO-GO`
- No integrar `rvol_breakout_min` en `combo_pure_momentum.yaml`.

## Notas técnicas
- El engine soporta `rvol_breakout_threshold` como feature flag.
- `offline_mode=True` evita descargas de SPY/VIX en el sandbox.
