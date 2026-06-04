# Fase 2: Signal Quality Scoring

## Objetivo
Puntuar la calidad de cada señal del sistema Gold Standard para filtrar ruido y ajustar sizing, sin cambiar reglas de entrada, stops o exits.

## Hallazgo Crítico de Datos
Se auditó el histórico disponible y el volumen es limitado:

- `outputs/backtests/complete_trades_clean.csv`: 100 trades
- `outputs/backups/pre_ml_fix/complete_trades_clean.csv`: 451 trades
- `outputs/paper_trading/paper_trades.csv`: 1 trade

### Conclusión de Dataset
- `<200 trades`: no usar boosters como modelo principal
- `200-500 trades`: usar `Ridge` / `ElasticNet` o árboles muy restringidos
- `>500 trades`: recién ahí considerar `LightGBM` como modelo principal

## Implementación Base
- `src/ml_signal/audit.py`
- `src/ml_signal/features.py`
- `src/ml_signal/trainer.py`
- `src/ml_signal/backtest.py`
- `scripts/run_ml_signal_quality.py`

## Diseño Adoptado
### Target principal
- `r_multiple` o `return_pct` del trade real

### Score
- Predicción convertida a percentil `0-100` dentro del fold
- Thresholds congelados por fold, no por dataset completo

### Modelos
- Default: `Ridge`
- Alternativa: `ElasticNet`
- Booster (`LightGBM`) solo si el dataset supera el umbral de volumen

## Riesgos Detectados
- Dataset demasiado pequeño para XGBoost/boosters por defecto
- Alto riesgo de overfit por ticker si se usa un modelo demasiado flexible
- `forward_return_10d` no debe ser el target principal si hay trades reales con stops/TP

## Resultado Técnico
- Pipeline compilado correctamente
- Auditoría de datos implementada
- Scoring por percentiles implementado

## Recomendación
### Go/No-Go
- **GO** para análisis y baseline lineal
- **NO GO** para booster por defecto hasta que el dataset de trades supere 500 filas útiles

## Siguiente Paso
Ejecutar `scripts/run_ml_signal_quality.py` sobre el histórico más grande disponible y comparar:
- correlación predicción/realidad
- deciles de score
- Sharpe con y sin filtro
