# 🎯 Guía de Optimización de Filtros

## Objetivo

Encontrar la **combinación óptima de ADR y Max Exposure (%)** que maximice las ganancias, en lugar de ajustar manualmente.

---

## 🚀 Uso Rápido

### Optimización Básica

```bash
python3 optimize_filters.py
```

Esto ejecuta un **grid search** probando todas las combinaciones de:
- **ADR**: 1.0%, 1.5%, 2.0%, 2.5%, 3.0%, 3.5%, 4.0%
- **Max Exposure**: 15%, 20%, 25%, 30%, 35%, 40%

**Total**: 42 combinaciones (7 × 6)

---

## 📊 Resultados

El optimizador genera:

### 1. **Reporte en Consola**

```
🏆 TOP 10 COMBINACIONES ÓPTIMAS
================================================================

#1
  ADR: 2.5% | Max Exposure: 30%
  Score: 85.42
  Trades: 45 | Win Rate: 67.5%
  Avg Return: 3.24% | Total PnL: $14,580.50
  Sharpe: 1.85 | Profit Factor: 2.45
  Max DD: 8.3%

#2
  ADR: 2.0% | Max Exposure: 35%
  Score: 82.15
  ...
```

### 2. **CSV de Resultados** (`optimization_results.csv`)

Todas las combinaciones probadas, ordenadas por score, con métricas completas.

### 3. **Heatmap Interactivo** (`optimization_heatmap.html`)

Visualización de color donde puedes ver gráficamente qué combinaciones funcionan mejor.

---

## 🔧 Personalización

### Cambiar Símbolos

Edita `optimize_filters.py` línea 212:

```python
symbols = ['AAPL', 'NVDA', 'TSLA', 'META', 'PLTR', 'AMD']
```

### Cambiar Período

Edita líneas 215-216:

```python
start_date = '2024-01-01'
end_date = '2024-12-20'
```

### Cambiar Rangos de Búsqueda

Edita líneas 219-220:

```python
adr_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]  # Más granular
max_exp_range = [10, 15, 20, 25, 30, 35, 40, 45]  # Más opciones
```

### Cambiar Parámetros de Riesgo

Edita líneas 223-227:

```python
optimizer = FilterOptimizer(
    symbols=symbols,
    start_date=start_date,
    end_date=end_date,
    equity=100000,      # Capital inicial
    risk_pct=0.5        # Riesgo por trade (%)
)
```

---

## 📈 Cómo Funciona el Score

El **Score** es un valor compuesto que considera:

| Métrica | Peso | Descripción |
|---------|------|-------------|
| **Win Rate** | 30% | % de trades ganadores |
| **Avg Return** | 25% | Retorno promedio por trade |
| **Sharpe Ratio** | 20% | Retorno ajustado por riesgo |
| **Profit Factor** | 15% | Ganancias/Pérdidas |
| **Max Drawdown** | 10% | Menor caída desde pico |

**Fórmula:**
```python
score = (
    win_rate * 0.30 +
    (avg_return / 10) * 0.25 +
    (sharpe / 2) * 0.20 +
    (profit_factor / 3) * 0.15 +
    (1 - max_dd/100) * 0.10
)
```

Puedes ajustar los pesos en la función `_calculate_metrics()` según tus preferencias.

---

## 🎯 Interpretación de Resultados

### Ejemplo de Output

```
✨ CONFIGURACIÓN ÓPTIMA RECOMENDADA:
   ADR: 2.5%
   Max Exposure: 30%
   Score Esperado: 85.42
```

**Significa:**
- Filtra stocks con **mínimo 2.5% ADR** (volatilidad moderada)
- Permite **hasta 30% del capital** en posiciones simultáneas
- Esta combinación históricamente produjo el mejor balance riesgo/retorno

### Análisis de Trade-offs

1. **ADR Alto (3.5-4.0%)** → Menos oportunidades, pero mayor volatilidad
2. **ADR Bajo (1.0-1.5%)** → Más oportunidades, pero menor movimiento
3. **Max Exp Alto (40%+)** → Mayor exposición, mayor riesgo
4. **Max Exp Bajo (15-20%)** → Menor riesgo, pero menos posiciones activas

---

## 🔍 Análisis Avanzado

### Correlación entre ADR y Max Exposure

Después de ejecutar la optimización, puedes analizar la correlación:

```python
import pandas as pd

df = pd.read_csv('optimization_results.csv')

# Ver correlación de Score con cada parámetro
print(df[['adr', 'max_exposure', 'score']].corr())

# Ver mejores combinaciones
best_adr = df.groupby('adr')['score'].mean().idxmax()
best_exp = df.groupby('max_exposure')['score'].mean().idxmax()

print(f"Mejor ADR promedio: {best_adr}%")
print(f"Mejor Max Exp promedio: {best_exp}%")
```

### Gráfico de Dispersión

```python
import plotly.express as px

df = pd.read_csv('optimization_results.csv')

fig = px.scatter(df, 
                 x='adr', 
                 y='max_exposure', 
                 size='score',
                 color='win_rate',
                 hover_data=['total_trades', 'avg_return', 'sharpe_ratio'])

fig.write_html('scatter_analysis.html')
```

---

## ⚡ Optimización Rápida (Pocos Recursos)

Si no quieres probar todas las combinaciones:

```python
# En optimize_filters.py, usa rangos más pequeños:
adr_range = [1.5, 2.5, 3.5]  # Solo 3 valores
max_exp_range = [20, 30, 40]  # Solo 3 valores
# Total: 9 combinaciones (mucho más rápido)
```

---

## 🛠️ Troubleshooting

### "No hay resultados disponibles"

**Causa:** Los filtros son demasiado restrictivos, no hay trades.

**Solución:**
- Baja el ADR mínimo (ej. 1.0%)
- Aumenta el período de backtest
- Usa más símbolos

### "Todos los scores son similares"

**Causa:** Los parámetros no afectan significativamente en tu universo.

**Solución:**
- Usa un universo más diverso de símbolos
- Amplía el rango de ADR (ej. 0.5% - 5.0%)
- Revisa si otros filtros están limitando demasiado

### "El backtest tarda mucho"

**Causa:** Muchas combinaciones × muchos símbolos × período largo.

**Solución:**
- Reduce el rango (3-4 valores por parámetro)
- Usa menos símbolos para optimizar
- Acorta el período de backtest

---

## 📋 Checklist de Uso

1. [ ] Definir universo de símbolos representativo
2. [ ] Elegir período de backtest (mínimo 6 meses)
3. [ ] Ejecutar optimización: `python3 optimize_filters.py`
4. [ ] Revisar top 10 combinaciones
5. [ ] Analizar heatmap para visualizar patrones
6. [ ] Seleccionar configuración óptima
7. [ ] Aplicar en `app.py` o configuración de sistema
8. [ ] Validar en forward testing (datos nuevos)

---

## 🎓 Ejemplo Completo

```bash
# 1. Ejecutar optimización
python3 optimize_filters.py

# 2. Ver resultados en CSV
cat optimization_results.csv | head -10

# 3. Abrir heatmap
xdg-open optimization_heatmap.html  # Linux
# open optimization_heatmap.html    # Mac

# 4. Aplicar mejor configuración en Streamlit
# Edita app.py con los valores óptimos encontrados
```

---

## 💡 Best Practices

### ✅ DO:
- Usa un período largo para optimización (1+ año)
- Incluye diferentes condiciones de mercado (bull, bear, sideways)
- Valida los resultados en período diferente (walk-forward)
- Considera múltiples métricas, no solo score

### ❌ DON'T:
- No sobre-optimices (overfitting)
- No uses datos muy recientes únicamente
- No ignores el número de trades (mínimo 20-30)
- No uses configuraciones con max drawdown >20%

---

## 🔗 Integración con Streamlit

Una vez que encuentres la configuración óptima, aplícala en `app.py`:

```python
# En app.py línea 147 y 158:
in_min_adr = st.number_input("Min ADR 20 (%)", value=2.5, step=0.1)  # ← Valor óptimo
in_max_exp = st.number_input("Max Exposure (%)", value=30.0, step=5.0)  # ← Valor óptimo
```

---

## 📊 Métricas Explicadas

### Win Rate
Porcentaje de trades ganadores. Ideal: >60%

### Avg Return
Retorno promedio por trade. Ideal: >2%

### Sharpe Ratio
Retorno ajustado por volatilidad. Ideal: >1.5

### Profit Factor
Ganancias totales / Pérdidas totales. Ideal: >2.0

### Max Drawdown
Mayor caída desde pico. Ideal: <15%

---

**Última actualización:** Diciembre 2024  
**Versión:** 1.0
