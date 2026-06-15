# Fase 1: Regime Detection con Random Forest

## Objetivo
Reemplazar el baseline heurístico de Fase 0 por un clasificador de regímenes con Random Forest, manteniendo el mismo esquema walk-forward para evaluar valor económico real.

## Implementación
- `src/regime_detection/ml_features.py`
- `src/regime_detection/ml_trainer.py`
- `scripts/run_ml_regime.py`

### Diseño
- Features: `vix`, `vix_change_5d`, `breadth_pct`, `breadth_change_5d`, `dix`, `gex_net`, `spy_atr_ratio`, `spy_return_10d`, `sector_momentum_dispersion`, `put_call_ratio`
- Modelo: `RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)`
- Walk-forward: train 3 años, test 3 meses, step 3 meses, purge de 10 días
- Salidas: `regime_signal`, `p_green`, `p_yellow`, `p_red`, `equity_curve`, `fold_id`, `feature_importance`

## Resultados Reales 2019-2025 OOS

### Métrica de Negocio

| Métrica | Buy & Hold (SPY) | Heurística Fase 0 | Random Forest Fase 1 |
|---|---:|---:|---:|
| CAGR | 20.29% | 7.04% | 3.27% |
| Max Drawdown | -18.76% | -7.37% | -17.80% |
| Sharpe Ratio | 1.221 | 0.971 | 0.322 |
| Tiempo en Cash | 0.00% | 15.21% | 28.96% |

### Detección de Crisis y Calidad de Señal

| Métrica | Heurística | Random Forest | Estado |
|---|---:|---:|---|
| RED Recall | 12.76% | 22.34% | Mejora relevante |
| Retorno esperado en días RED (10d) | +2.63% | +1.47% | Menor paradoja |
| Retorno esperado en días GREEN (10d) | +0.45% | +0.59% | Mejora |
| p-value | 2.07e-06 | 0.0088 | Señal predictiva real |

### Variable Importance
1. `vix` - 13.31%
2. `spy_atr_ratio` - 12.58%
3. `spy_return_20d` - 11.39%
4. `spy_return_10d` - 11.00%
5. `breadth_pct` - 10.23%

## Bugs / Riesgos Detectados
- `class_weight='balanced'` aumenta el conservadurismo del modelo.
- El modelo mejora la detección de crisis, pero sacrifica demasiado retorno en un mercado alcista fuerte.
- La ganancia estadística no se traduce en mejora económica frente a Fase 0.

## Veredicto
**NO GO para producción.**

### Motivo
Aunque el modelo encuentra señal predictiva real, destruye la rentabilidad económica vs. el baseline heurístico:
- Sharpe cae a 0.322
- CAGR cae a 3.27%
- Max DD casi no mejora frente a Buy & Hold

## Recomendación para Fase 2
1. Cambiar el target a una etiqueta basada en retorno/riesgo futuro, no solo dirección nominal.
2. Probar `max_depth` más bajo y búsqueda walk-forward con Optuna.
3. Comparar variantes sin `class_weight='balanced'` o con pesos menos agresivos.
4. Mantener el baseline Fase 0 como referencia mínima obligatoria.

## Estado
- Fase 1 está implementada y validada end-to-end.
- Los reportes están listos para auditoría técnica.
- La conclusión es negativa para integración productiva por ahora.
