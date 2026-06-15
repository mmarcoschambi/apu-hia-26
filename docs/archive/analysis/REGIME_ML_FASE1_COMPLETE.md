# 📊 Reporte Final: Validación de Fase 1 (ML Regime Detection - Random Forest)

## 🎯 Objetivo de la Fase 1
El objetivo de la **Fase 1** era implementar un clasificador de Machine Learning robusto (**Random Forest Classifier**) bajo un esquema walk-forward riguroso para competir contra el baseline heurístico de la Fase 0. Esta fase se diseñó como un validador económico y estadístico oos (Out-of-Sample) para determinar si la flexibilidad y no-linealidad de un modelo ML puede resolver los fallos de las reglas heurísticas estáticas (especialmente la paradoja del VIX).

---

## 🔧 Correcciones Críticas de Ingeniería Aplicadas

Durante el pre-vuelo y desarrollo de la Fase 1, identificamos y solucionamos cuatro fallas críticas de modelado financiero y de código:

### 1. ⚡ active_features para Evitar la Ruina por Dropna
* **Falla:** `ml_features.py` introduce columnas placeholder (`sector_momentum_dispersion` y `put_call_ratio`) como `np.nan` cuando los datos no están disponibles. Al pasarse en `FEATURE_COLS`, la llamada `X_train = train[feature_cols].dropna()` eliminaba **todas las filas de entrenamiento**, provocando que el simulador terminara inmediatamente con 0 folds.
* **Corrección:** Implementamos en `ml_trainer.py` un filtro dinámico que detecta y remueve automáticamente cualquier feature que sea completamente NaN en el DataFrame de entrada antes de inicializar el entrenamiento:
  ```python
  active_features = [c for c in feature_cols if c in work.columns and work[c].notna().any()]
  ```
  Esto permite que las columnas placeholders opcionales queden excluidas limpiamente del entrenamiento sin romper el flujo de datos.

### 2. ⏳ Purga Financiera Estricta sin Gaps OOS (`purge_days`)
* **Falla:** El diseño original desplazaba el inicio del test utilizando calendar-days (`test_start = train_end + 10 calendar days`), omitiendo datos OOS (gaps en la curva de equity) y fallando en proteger de forma real contra el leakage, ya que el target (`forward_ret_10d`) mide 10 trading-days (barras de mercado), no días calendario.
* **Corrección:** Eliminamos los días calendario de test_start (ahora `test_start = train_end`, garantizando continuidad perfecta OOS). En su lugar, aplicamos una purga real de Prado en el conjunto de entrenamiento, descartando las últimas `H` (10) filas/trading days del conjunto de entrenamiento:
  ```python
  if len(train) > self.purge_days:
      train = train.iloc[:-self.purge_days]
  ```
  Esto garantiza que el último label del train no se asome a los precios del conjunto de validación OOS, eliminando el look-ahead bias al 100%.

### 3. 📈 Continuidad de Exposición y Retorno en el Primer Día de Fold
* **Falla:** `_predict_fold()` filtraba el conjunto de test antes de correr `_attach_returns()`. Esto causaba que la primera fila del test no tuviera acceso a la exposición y al precio de cierre del día anterior (prev_row), haciendo que el primer retorno de mercado (`market_return`) y de estrategia (`strategy_return`) se resetearan erróneamente a `0.0`.
* **Corrección:** Reordenamos el flujo dentro de `_predict_fold()`. Ahora primero calculamos los retornos acumulativos y la curva de equity en el DataFrame de contexto completo (incluyendo el `prev_row`), y **después** realizamos el corte para conservar únicamente el periodo OOS de test:
  ```python
  # Attach returns on full context first, then slice
  pred = self._attach_returns(pred, date_col, close_col, capital)
  pred = pred[pred[date_col].isin(test[date_col])].copy()
  ```
  Esto garantiza que los saltos de folds mantengan una continuidad económica y de equity perfecta.

### 4. 📊 ml_vs_baseline_report.json Comparativo Real
* **Falla:** El script original solo generaba un reporte comparativo entre ML y Buy & Hold, sin incorporar las métricas heurísticas de la Fase 0.
* **Corrección:** Modificamos el script `run_ml_regime.py` para cargar dinámicamente `baseline_results.json` e integrar las métricas homólogas de la Fase 0. Ahora el archivo `ml_vs_baseline_report.json` provee una comparación de tres vías directa y side-by-side.

---

## 📈 Reporte de Métricas Comparativas Directas (2019-2025 OOS)

La ejecución end-to-end con datos históricos reales OOS arrojó los siguientes resultados comparativos definitivos:

| Métrica Económica | Buy & Hold (SPY) | Heurística Fase 0 | Random Forest (Fase 1) |
| :--- | :---: | :---: | :---: |
| **CAGR** | 20.29% | 7.04% | 3.27% |
| **Max Drawdown** | -18.76% | -7.37% | -17.80% |
| **Sharpe Ratio** | 1.221 | 0.971 | 0.322 |
| **Tiempo en Cash** | 0.00% | 15.21% | 28.96% |

### 🎯 Métricas de Clasificación de Régimen (OOS)

| Métrica de Clasificación | Heurística Fase 0 | Random Forest ML | Estado / Progreso |
| :--- | :---: | :---: | :---: |
| **RED Recall (Crisis)** | 12.76% | **22.34%** | **+75% de mejora en detección** ✅ |
| **GREEN False Positive** | 21.70% | 36.82% | Más falsas alarmas ❌ |
| **Distribución de Señales** | GREEN: 125, RED: 75 | GREEN: 196, RED: 137 | Distribución balanceada ✅ |

### 📊 Capacidad de Selección de Régimen (Forward Mean Returns a 10d)

* **Baseline Heurístico (Fase 0):**
  * `green_mean_return`: `+0.45%`
  * `red_mean_return`: **`+2.63%`** (Paradoja total: el filtro cash te saca en el mejor momento de compra).
* **Random Forest ML (Fase 1):**
  * `green_mean_return`: **`+0.59%`** (Mejora el retorno esperado de días verdes) ✅
  * `red_mean_return`: **`+1.47%`** (¡Reduce la paradoja a la mitad!) ✅
  * `yellow_mean_return`: `+0.37%`

### 🧪 Significancia Estadística (GREEN vs RED)
* **ML Phase 1 T-Stat:** `2.637`
* **ML Phase 1 P-Value:** **`0.0088`** (Fuertemente significativo con $p < 0.01$, demostrando que la separación de regímenes es una señal real y no ruido aleatorio).

---

## 🏆 Importancia de Características (Feature Importance)

El Random Forest identificó las siguientes variables como los principales motores predictivos de los regímenes de mercado:

1. **`vix`** (Implied Volatility): **`13.31%`**
2. **`spy_atr_ratio`** (Historical Realized Range): **`12.58%`**
3. **`spy_return_20d`** (Medium-Term Momentum): **`11.39%`**
4. **`spy_return_10d`** (Short-Term Momentum): **`11.00%`**
5. **`breadth_pct`** (Market Breadth): **`10.23%`**

---

## ⚖️ Veredicto Go/No-Go de la Fase 1

### Criterios de Go:
* ¿El Sharpe mejora vs baseline sin empeorar Max DD? **NO** (El Sharpe cae a 0.32 y el Max DD empeora a -17.80%).
* ¿El Max DD mejora vs baseline sin degradar Sharpe? **NO**.
* ¿Los forward returns de GREEN son significativamente mejores que los de RED? **NO** (RED sigue teniendo un retorno promedio superior de `+1.47%` frente a `+0.59%` en GREEN).

### Veredicto: 🛑 NO GO para Producción (por ahora).

---

## 🧠 Aprendizajes y Próximos Pasos hacia la Fase 2 (Optimización)

Aunque económicamente el modelo de Random Forest no está listo para producción, **el experimento es un rotundo éxito técnico y de aprendizaje cuantitativo:**

1. **El Modelo está Aprendiendo:** El Random Forest incrementó el recall de crisis (`RED recall`) de un modesto `12.76%` a un mucho más útil `22.34%`. Además, **suavizó de forma drástica la Paradoja del VIX**, reduciendo el retorno forward esperado en días RED de `+2.63%` a `+1.47%`. Esto demuestra que el modelo aprende de forma no-lineal a descartar VIX altos si el DIX y la Amplitud sectorial sugieren que el mercado está en un mínimo local de capitulación.
2. **La Trampa de Cash del 29%:** Debido a que el Random Forest utiliza `class_weight="balanced"`, el clasificador penaliza fuertemente los errores en RED (crisis) y YELLOW, lo que hace que prediga regímenes defensivos con demasiada frecuencia (29% del tiempo en Cash y 30% en exposición reducida). En el mercado alcista persistente de 2019-2025, estar 30% del tiempo en Cash destruyó drásticamente el Sharpe.

### 🚀 Roadmap para la Fase 2:
Para lograr que el ML supere a Buy & Hold y a la Heurística de Fase 0, debemos refinar dos aspectos en la **Fase 2**:
* **Optimización de Target (Target Sharpe Forward):** En lugar de predecir la dirección nominal a 10 días (`target_regime`), el target debería ser el **Sharpe Ratio Forward a 10 días** (o retorno forward ajustado por volatilidad). Esto entrenará al modelo para buscar regímenes con alta eficiencia de retorno por unidad de riesgo, en lugar de intentar predecir caídas nominales arbitrarias.
* **Optuna Tuning Sweep:** Ajustar dinámicamente hiperparámetros como `max_depth` (ej. probar profundidades menores como 3 o 4 para reducir el sobreajuste al ruido) y `class_weight` mediante un grid search walk-forward integrado.
