# Setup Quality: Consolidation Range

## Objetivo
Evaluar si una consolidación más tight antes del breakout mejora la calidad de las entradas de `combo_pure_momentum`.

## Setup
- Variable modificada: `max_consolidation_range`
- Baseline: `15.0`
- Sweep: `12.0`, `10.0`, `8.0`, `6.0`
- Fijo: `min_consolidation_days`, `min_rvol`, `min_adr`, exits, sizing y stops

## Resultado
- `15.0` fue el mejor resultado.
- `12.0` degradó Sharpe y win rate.
- `10.0` ya destruyó el perfil.
- `8.0` y `6.0` colapsaron el universo.

## Bucket Check
- `consolidation_range` no mostró relación útil con retorno.
- Correlación con retorno: ~0.048.
- Correlación con win rate: ~0.019.

## Decisión
- `NO-GO`
- No hay sweet spot monótono ni no-monótono que valga la pena perseguir.

## Conclusión
El pipeline upstream ya está limpiando bien la calidad del setup. Más filtros de entrada sobre consolidación no agregan edge medible.
