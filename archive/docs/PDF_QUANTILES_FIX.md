# Fix: PDF Return Quantiles Bug

## 🐛 Problema Identificado

En algunos PDFs generados, la página de "Snapshot" con la sección "Return Quantiles" (daily/weekly) muestra gráficos bugueados o vacíos. Este es un problema conocido de QuantStats cuando:

1. Los datos tienen periodicidad irregular
2. Hay pocos datos (menos de 60 días)
3. Los retornos tienen características especiales (muchos zeros, outliers extremos)

## ✅ Solución Implementada

Se agregaron **dos mejoras** al sistema de generación de PDFs:

### 1. Manejo Robusto de Errores

Cada página del PDF ahora se genera en un bloque `try-except` independiente:
- Si una página falla, se registra un warning y se continúa
- El PDF se genera con todas las páginas que funcionan
- No se pierde todo el reporte por un gráfico problemático

### 2. Opción para Saltar el Snapshot

Nueva opción `skip_snapshot` en `generate_pdf_report()`:

```python
# Generar PDF sin la página problemática de Snapshot
pdf_path = analyzer.generate_pdf_report(
    output_dir='outputs/quantstats',
    benchmark_ticker='SPY',
    skip_snapshot=True  # 👈 Nueva opción
)
```

## 📊 Páginas del PDF

### Con Snapshot (Default)
1. ✅ Metrics Summary Table (nueva)
2. ⚠️  Snapshot con Return Quantiles (puede tener bugs)
3. ✅ Returns Chart
4. ✅ Drawdown Chart
5. ✅ Monthly Heatmap
6. ✅ Yearly Returns
7. ✅ Rolling Sharpe
8. ✅ Rolling Volatility
9. ✅ Rolling Beta (si hay benchmark)
10. ✅ Distribution

### Sin Snapshot (`skip_snapshot=True`)
1. ✅ Metrics Summary Table (nueva)
2. ❌ Snapshot **OMITIDO**
3. ✅ Returns Chart
4. ✅ Drawdown Chart
5. ✅ Monthly Heatmap
6. ✅ Yearly Returns
7. ✅ Rolling Sharpe
8. ✅ Rolling Volatility
9. ✅ Rolling Beta (si hay benchmark)
10. ✅ Distribution

## 🎯 Cuándo Usar Cada Opción

### Usar Default (con Snapshot)
```python
pdf_path = analyzer.generate_pdf_report(
    benchmark_ticker='SPY'
)
```
**Cuando:**
- Tienes datos completos (90+ días)
- Los retornos son limpios sin outliers extremos
- Quieres el reporte completo estándar de QuantStats

### Usar skip_snapshot=True
```python
pdf_path = analyzer.generate_pdf_report(
    benchmark_ticker='SPY',
    skip_snapshot=True
)
```
**Cuando:**
- Ves bugs en la página de Return Quantiles
- Tienes pocos datos (menos de 60 días)
- Los gráficos de quantiles salen vacíos o distorsionados
- Prefieres un PDF más corto y confiable

## 📝 Logging Mejorado

Ahora el sistema reporta claramente qué páginas se generaron:

```
📊 Generating QuantStats PDF tearsheet...
✅ Page 1: Metrics Summary
✅ Page 2: Snapshot
✅ Page 3: Returns
✅ Page 4: Drawdown
✅ Page 5: Monthly Heatmap
✅ Page 6: Yearly Returns
✅ Page 7: Rolling Sharpe
✅ Page 8: Rolling Volatility
⚠️  Skipped Rolling Beta: insufficient data
✅ Page 10: Distribution
✅ PDF Report saved: outputs/quantstats/tearsheet_20260303_231437.pdf
```

Si una página falla:
```
⚠️  Skipped Snapshot page (known quantiles issue): KeyError: 'daily'
   💡 Tip: Use skip_snapshot=True to avoid this warning
```

## 🔧 Uso en Streamlit

El botón de "Generate Full PDF Tearsheet" en la app usará el default (con snapshot). Si ves problemas, puedes modificar en `app.py`:

```python
# En app.py, línea ~1471
report_path = analyzer.generate_pdf_report(
    benchmark_ticker=benchmark_ticker,
    skip_snapshot=True  # 👈 Agregar esta línea si hay problemas
)
```

## 💡 Recomendaciones

### Para Usuarios
1. **Primero intenta el default** - la mayoría de las veces funciona bien
2. **Si ves bugs en Return Quantiles** - usa `skip_snapshot=True`
3. **Con datos de menos de 60 días** - considera usar `skip_snapshot=True`

### Para Desarrolladores
Si necesitas más control sobre qué páginas incluir, puedes extender el método con más opciones:

```python
def generate_pdf_report(
    self, 
    output_dir: str = 'outputs/quantstats',
    benchmark_ticker: str = None,
    skip_snapshot: bool = False,
    skip_rolling: bool = False,  # Nueva opción
    skip_heatmaps: bool = False  # Nueva opción
) -> str:
    # ...
```

## 🐛 Causa Raíz del Bug

El bug viene de QuantStats cuando intenta crear los gráficos de quantiles con:
- `returns.resample('D')` y `returns.resample('W')`
- Si los datos ya tienen frecuencia diaria, el resample puede fallar
- Si hay gaps o fechas irregulares, los quantiles pueden ser incorrectos

Nuestro fix evita que esto rompa todo el PDF.

## ✅ Verificación

Probado con:
- ✅ Datos completos (365 días) - Funciona con y sin snapshot
- ✅ Datos escasos (60 días) - Funciona mejor con `skip_snapshot=True`
- ✅ Datos con gaps - Maneja errores gracefully
- ✅ Sin benchmark - Genera PDF correctamente
- ✅ Con benchmark - Incluye todas las comparaciones

## 📚 Archivos Modificados

- **src/analytics/quantstats_analyzer.py**
  - Agregado `skip_snapshot` parameter
  - Agregado try-except por página
  - Agregado logging detallado
  - Agregado tips en warnings

## 🚀 Próximos Pasos (Opcional)

Si quieres investigar más el bug de QuantStats:

1. **Actualizar QuantStats:**
   ```bash
   pip install --upgrade quantstats
   ```

2. **Reportar el bug:** 
   - https://github.com/ranaroussi/quantstats/issues
   - Incluir ejemplo de datos que causan el problema

3. **Workaround alternativo:**
   - Pre-procesar returns antes de pasarlos a QuantStats
   - Asegurar frecuencia diaria exacta sin gaps
   - Filtrar outliers extremos

---

**Resumen:** El PDF ahora es mucho más robusto y no fallará completamente por un gráfico problemático. Si ves bugs en Return Quantiles, usa `skip_snapshot=True`.
