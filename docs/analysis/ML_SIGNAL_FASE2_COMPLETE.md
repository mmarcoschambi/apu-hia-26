# 📊 Reporte: Correcciones y Mejoras en el Pipeline de ML Signal Quality (Fase 2)

## 🎯 Resumen de las Modificaciones Realizadas
Hemos corregido de forma quirúrgica los cuatro bugs y áreas de mejora identificados en el subsistema de ML Signal Quality (Fase 2) bajo la rama `ml-score`. Todo el pipeline de modelado de calidad de señales ha sido alineado con las mejores prácticas cuantitativas (evitando leakages, corrigiendo el orden de las operaciones rolling de mercado y enriqueciendo los reportes financieros).

---

## 🛠️ Correcciones Técnicas Aplicadas

### 1. ⚡ Cálculo de Features Rolling sobre Días de Mercado Real (`features.py`)
* **Problema:** En `src/ml_signal/features.py`, el pipeline original fusionaba primero el DataFrame de señales con el de mercado y **después** calculaba las métricas rolling y de momento (`pct_change(5)`, `rolling(20)`, etc.) sobre las filas resultantes. Esto provocaba que las métricas de mercado (SPY, VIX, Amplitud) se calcularan erróneamente a través de las filas de los trades, lo cual destruía la integridad temporal (debido a múltiples trades en un mismo día o días sin trades).
* **Solución:** Reestructuramos el flujo para que **todos los cálculos rolling y de momentum del mercado se computen primero sobre el DataFrame diario y secuencial de mercado (`mk`)**. Únicamente tras tener estas features perfectamente calculadas, realizamos el merge con el DataFrame de señales (`sig`) a través del `entry_date` exacto:
  ```python
  # Calculate rolling market features on the daily market frame FIRST
  if "Close" in mk.columns:
      mk["spy_return_5d"] = mk["Close"].pct_change(5)
      ...
  
  # Merge AFTER computing daily market rolling features
  features = sig.merge(
      mk, how="left", left_on=signal_date_col, right_index=True, suffixes=("", "_mkt")
  )
  ```
  Esto garantiza que múltiples trades ejecutados el mismo día compartan exactamente la misma lectura del mercado (sin leakage ni distorsiones de fila).

### 2. 🛡️ Selección Dinámica de Thresholds por Fold sin Leakage (`trainer.py`)
* **Problema:** El código original de `trainer.py` utilizaba un umbral fijo en test (`pred_score >= 70.0`). Esto violaba el diseño de "cero leakage", ya que los umbrales de percentiles óptimos deben determinarse únicamente dentro de la muestra de entrenamiento de cada fold y luego aplicarse "congelados" en el conjunto de prueba correspondiente.
* **Solución:** Implementamos el método `_find_best_threshold` dentro de `SignalWalkForwardTrainer`. Este método:
  1. Convierte las predicciones de entrenamiento (`train_pred`) a percentiles sobre sí mismas.
  2. Evalúa umbrales candidatos (`50.0`, `60.0`, `70.0`, `80.0`).
  3. Selecciona el umbral que maximiza el **Sharpe Ratio** de la selección dentro del conjunto de entrenamiento (requiriendo al menos 15 trades y un 10% del total de trades de entrenamiento para evitar el sobreajuste a micro-muestras).
  4. Congela dicho umbral (`best_threshold`) y lo aplica a la predicción del conjunto de test OOS, adaptando dinámicamente las reglas de tamaño y selección de trades de forma no-lineal:
  ```python
  best_threshold = self._find_best_threshold(train_pred, y_train)
  test_pred["best_threshold"] = best_threshold
  test_pred["take_trade"] = test_pred["pred_score"] >= best_threshold
  test_pred["risk_multiplier"] = np.select(
      [
          test_pred["pred_score"] >= (best_threshold + 10.0),
          test_pred["pred_score"] >= best_threshold,
          test_pred["pred_score"] >= (best_threshold - 20.0),
      ],
      [2.0, 1.0, 0.5],
      default=0.0,
  )
  ```
  Adicionalmente, guardamos la columna `best_threshold` en los resultados de folds (`signal_folds.parquet`) para mantener una total trazabilidad.

### 3. 📈 Reporte Decisivo: Gold Standard vs. ML Filter/Sizing (`run_ml_signal_quality.py`)
* **Problema:** El runner original guardaba predicciones y folds, pero carecía de una comparación directa entre el rendimiento de las señales del sistema original sin filtrar (Gold Standard) frente a las filtradas y dimensionadas por ML.
* **Solución:**
  * Implementamos `calculate_trade_metrics` que computa métricas financieras a nivel de trade: **Trade Count, Win Rate, Profit Factor, Total PnL, Mean Return, Sharpe Ratio y Max Drawdown %** (calculado sobre curvas de equidad simuladas chronológicamente con capital inicial de $100,000, soportando tanto R-multiples como retornos porcentuales mediante capitalización).
  * Implementamos `calculate_decile_analysis` que clasifica las predicciones OOS en deciles (`D1` a `D10`) y calcula el rendimiento medio y volumen de cada decil, evaluando la capacidad de ordenamiento monótono del modelo.
  * Añadimos la generación automática de los archivos `signal_results.json` y del reporte comparativo decisivo `ml_vs_original_report.json` que contiene las métricas side-by-side de las tres estrategias:
    1. **`original_gold_standard`**: El rendimiento de operar todas las señales del sistema.
    2. **`ml_filtered`**: Solo tomar operaciones que superen el `best_threshold` dinámico.
    3. **`ml_sized`**: Operaciones dimensionadas dinámicamente según la convicción del modelo (`risk_multiplier`).

### 4. Detalles Menores Corregidos
* **`backtest.py`**: Eliminamos la definición duplicada de la función `score_to_percentile`, conservando únicamente la segunda versión mejorada que cuenta con la estrategia inteligente de relleno `.fillna(train.min())` para evitar fugas y NaNs.
* **`trainer.py`**: Limpiamos las dependencias eliminando el import no utilizado `TimeSeriesSplit`.
* **`audit.py`**: Modificamos el validador `audit_signal_dataset` para soportar limpiamente el fallback a `return_pct` cuando `r_multiple` no está presente, previniendo advertencias de error ruidosas en el runner.
* **scikit-learn Compatibility**: Reemplazamos el parámetro obsoleto `squared=False` en las llamadas a `mean_squared_error` por un cálculo directo con `np.sqrt()`, garantizando compatibilidad total con las versiones modernas de scikit-learn (1.4+).

---

## 🧪 Pruebas Unitarias Integrales (`pytest` exitoso)

Creé el archivo [tests/test_ml_signal_quality.py](file:///home/marcos/trade/momentum-v2/tests/test_ml_signal_quality.py) que valida quirúrgicamente cada una de estas implementaciones:
1. `test_build_signal_features_correct_rolling`: Comprueba que las features rolling de mercado se calculen idénticas para trades del mismo día y correspondan exactamente al DataFrame diario secuencial original.
2. `test_trainer_dynamic_threshold_no_leakage`: Valida que el threshold se optimice por fold en train y se congele y aplique correctamente en el test OOS, comprobando que las predicciones respeten el umbral dinámico.
3. `test_calculate_trade_metrics`: Valida la precisión de los cálculos de Win Rate, P&L total y deciles en datos controlados.

**Resultado de la corrida de pruebas (Suite Completa ML):**
```bash
tests/test_regime_detection.py ....                                      [ 57%]
tests/test_ml_signal_quality.py ...                                       [100%]
======================== 7 passed, 33 warnings in 8.94s ========================
```
¡Todos los tests pasaron exitosamente al 100%!

---

## 📁 Archivos Modificados y Guardados en Git
* `src/ml_signal/features.py` (Orden de cálculo rolling)
* `src/ml_signal/trainer.py` (Detección dinámica de umbrales, compatibilidad scikit-learn y limpieza de imports)
* `src/ml_signal/backtest.py` (Eliminación de duplicados)
* `src/ml_signal/audit.py` (Fallback de target en auditoría)
* `scripts/run_ml_signal_quality.py` (Cálculo de deciles y reporte decisivo side-by-side)
* `tests/test_ml_signal_quality.py` (Nueva suite de tests de calidad de señal)
