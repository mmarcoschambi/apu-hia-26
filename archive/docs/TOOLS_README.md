# 🎯 HERRAMIENTAS PARA AUDITAR MOTOR DE PRODUCCIÓN

Este directorio contiene herramientas para auditar y verificar el motor de producción `vectorbt_engine_advanced.py` tanto vía Streamlit UI como vía CLI.

## 📋 HERRAMIENTAS DISPONIBLES

### 1. **audit_production_engine.py** - Auditor de parámetros del motor
Muestra todos los parámetros disponibles del motor de producción y cómo usarlos.

```bash
python3 audit_production_engine.py
```

**Salida:**
- Todos los parámetros disponibles del motor
- Valores por defecto
- Ejemplos de uso
- Comparación con parámetros del Streamlit UI
- Consejos para auditar

---

### 2. **convergence_test_streamlit_cli.py** - Verifica convergencia entre Streamlit y CLI
Compara resultados entre Streamlit UI y ejecución vía CLI.

```bash
python3 convergence_test_streamlit_cli.py
```

**Salida:**
- Resultados de backtest vía CLI
- Resultados de backtest vía Streamlit (simulado)
- Comparación por ticker, retornos, win rate
- Análisis de convergencia (dentro del umbral del 2% para retornos y 5 trades)

**Es útil para:**
- Verificar que Streamlit UI produce los mismos resultados que CLI
- Identificar divergencias entre UI y motor
- Garantizar consistencia en resultados

---

### 3. **example_quick_backtest.py** - Ejemplo rápido de uso
Ejemplo de backtest con parámetros que coinciden con los de la UI de Streamlit.

```bash
python3 example_quick_backtest.py
```

**Salida:**
- Resultados del backtest
- Métricas clave (Sharpe, Win Rate, Drawdown, etc.)
- Análisis de trades (R-multiples, fases de salida)
- Guarda trades en `example_backtest_results.csv`

**Es útil para:**
- Entender cómo opera el motor
- Probar parámetros específicos
- Ver ejemplos de uso

---

### 4. **reproduce_validated_results.py** - Reproduce resultados validados
Reproduce exactamente los resultados de la validación Walk Forward.

```bash
python3 reproduce_validated_results.py
```

**Salida:**
- Resultados reproducidos con exactitud
- Comparación con la validación original
- Detección de divergencias significativas

**Es útil para:**
- Verificar que el motor reproduce correctamente la validación
- Identificar si los resultados cambian entre versiones

---

### 5. **verify_engine_equivalence.py** - Verifica equivalencia de motores
Compara resultados entre el motor de producción (AdvancedVectorBTEngine) y el motor de optimización (Bugatti).

```bash
python3 verify_engine_equivalence.py
```

**Salida:**
- Comparación de métricas (trades, return, sharpe, etc.)
- Diferencias porcentuales
- Confirmación de convergencia

**Es útil para:**
- Garantizar que la optimización rápida produce parámetros válidos
- Verificar que no hay errores en la optimización

---

## 🚀 FLUJO DE TRABAJO RECOMENDADO

### Para auditar tu motor de producción:

1. **Ver parámetros disponibles:**
   ```bash
   python3 audit_production_engine.py
   ```

2. **Probar backtest rápido:**
   ```bash
   python3 example_quick_backtest.py
   ```

3. **Verificar convergencia Streamlit vs CLI:**
   ```bash
   python3 convergence_test_streamlit_cli.py
   ```

4. **Reproducir validación:**
   ```bash
   python3 reproduce_validated_results.py
   ```

5. **Comparar motores:**
   ```bash
   python3 verify_engine_equivalence.py
   ```

---

## 📊 PARÁMETROS KEY DEL MOTOR (Streamlit UI)

Los parámetros que usa la UI de Streamlit:

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `max_dist_sma20` | 7.0% | Distancia máxima de SMA20 |
| `min_rvol` | 1.0x | Mínimo RVOL |
| `min_adr` | 2.0% | Mínimo ADR |
| `min_dollar_volume` | $5M | Mínimo volumen en dólares |
| `max_stop_pct` | 3.0% | Stop loss máximo |
| `min_consolidation_days` | 10 | Días mínimos de consolidación |
| `tp1_r` | 1.25R | TP1 (33%) |
| `tp2_r` | 3.0R | TP2 (33%) |
| `runner_pct` | 34% | Runner (34%) |

---

## 🔧 USO AVANZADO

### Modo Production (Compounding)

```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

engine = AdvancedVectorBTEngine(
    universe=['AAPL', 'MSFT', 'NVDA'],
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_pct=0.005,  # 0.5%
    mode='production'  # Compounding
)

result = engine.run_backtest()
```

### Modo Convergence (igual que THOR)

```python
engine = AdvancedVectorBTEngine(
    universe=['AAPL', 'MSFT', 'NVDA'],
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=150.0,  # $150 fixed risk
    mode='convergence'  # Fixed dollar risk
)

result = engine.run_backtest()
```

---

## 📋 RESPUESTA AL CUESTIONARIO DEBUG

Para responder al cuestionario en `CUESTIONARIO_DEBUG.md`, necesitas:

1. **Ejecutar el ejemplo rápido:**
   ```bash
   python3 example_quick_backtest.py
   ```
   → Esto te da los parámetros actuales del motor

2. **Verificar convergencia:**
   ```bash
   python3 convergence_test_streamlit_cli.py
   ```
   → Confirma que Streamlit y CLI dan los mismos resultados

3. **Auditar parámetros:**
   ```bash
   python3 audit_production_engine.py
   ```
   → Muestra todos los parámetros disponibles

4. **Reproducir validación:**
   ```bash
   python3 reproduce_validated_results.py
   ```
   → Verifica que el motor reproduce correctamente la validación

---

## 🎯 PROBLEMAS COMUNES Y SOLUCIONES

### No hay suficientes trades

**Causa:** Filtros demasiado estrictos

**Solución:** Afloja filtros:
- Aumenta `min_rvol` (ej: 1.0 → 0.8)
- Aumenta `min_adr` (ej: 2.0 → 1.5)
- Aumenta `max_dist_sma20` (ej: 7.0 → 10.0)
- Aumenta `min_dollar_volume` (ej: $5M → $3M)

### Divergencia significativa entre Streamlit y CLI

**Causa:** Parámetros diferentes en UI vs CLI

**Solución:**
1. Verifica que ambos usen los mismos parámetros
2. Usa `convergence_test_streamlit_cli.py` para comparar
3. Asegúrate de usar los mismos valores en `example_quick_backtest.py`

### R-multiples todos son 0

**Causa:** Problema en cálculo de position sizing

**Solución:**
- Verifica `max_stop_pct` no es demasiado grande
- Asegúrate de tener `stop_price` en los trades
- Usa `reproduce_validated_results.py` para verificar

---

## 📚 RECURSOS ADICIONALES

- **CUESTIONARIO_DEBUG.md**: Cuestionario de debugging del motor
- **debug-convergence.py**: Compara resultados con THOR
- **validate_top_params_with_advanced.py**: Valida parámetros óptimos
- **walk_forward_validation.py**: Walk forward validation

---

## 🤝 REPORTAR BUGS

Si encuentras problemas:

1. Ejecuta `audit_production_engine.py` para ver los parámetros
2. Ejecuta `reproduce_validated_results.py` para verificar
3. Compara con los resultados esperados
4. Documenta la divergencia

---

**Última actualización:** 2026-02-07
