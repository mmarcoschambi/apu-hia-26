# 🔧 Optimization Scripts Suite

Suite de scripts para encontrar los parámetros óptimos de tu estrategia de trading.

## 🎯 Dos Enfoques de Optimización

### 📊 **Método 1: POST-MORTEM** (Actual - Rápido)
Analiza UN backtest ya ejecutado y re-filtra los trades históricos:

**Ventajas:**
- ✅ Muy rápido (segundos)
- ✅ No necesita re-ejecutar backtests
- ✅ Ideal para análisis exploratorio

**Limitaciones:**
- ❌ Solo puede hacer filtros MÁS RESTRICTIVOS
- ❌ No puede relajar filtros (no tiene trades rechazados)
- ❌ No prueba diferentes lógicas de entrada/salida

**Scripts:**
- `quick_diagnostics.py` - Diagnóstico rápido
- `range_finder.py` - Encuentra rangos óptimos
- `optimize_parameters.py` - Grid search sobre CSV existente

---

### 🚀 **Método 2: MULTI-BACKTEST** (Nuevo - Completo)
Ejecuta MÚLTIPLES backtests con diferentes parámetros y compara resultados:

**Ventajas:**
- ✅ Prueba rangos completos (relaja Y restringe)
- ✅ Métricas REALES de cada configuración
- ✅ Puede optimizar cualquier parámetro
- ✅ Resultados más confiables

**Limitaciones:**
- ⚠️ Más lento (N backtests × 30 seg)
- ⚠️ Riesgo de overfitting con demasiadas combinaciones

**Script:**
- `run_multi_backtest_optimization.py` - **✨ NUEVO - RECOMENDADO**

---

## 📂 Scripts Disponibles

### 🎯 POST-MORTEM (Análisis de CSV Existente)

#### 1. `quick_diagnostics.py` 
Diagnóstico rápido de 30 segundos.
```bash
python3 scripts/optimization/quick_diagnostics.py
# O especificar archivo:
python3 scripts/optimization/quick_diagnostics.py --file cvs/complete_trades.csv
```
- Winners vs Losers comparison
- Identificación de problemas
- Métricas por rango

#### 2. `range_finder.py`
Encuentra rangos óptimos para cada parámetro.
```bash
python3 scripts/optimization/range_finder.py
```
- Análisis por buckets (RVOL, ADR, Distance SMA20, etc.)
- Win rate por rango
- Expectancy por rango
- Sugiere valores óptimos

#### 3. `optimize_parameters.py`
Grid search sobre CSV existente (re-filtra trades).
```bash
python3 scripts/optimization/optimize_parameters.py --method grid
python3 scripts/optimization/optimize_parameters.py --method correlations
```
- Prueba combinaciones de filtros
- Correlaciones con rentabilidad
- Top N configuraciones

#### 4. `inspect_csv_data.py` ✨ NUEVO
Inspecciona qué datos están disponibles para optimización.
```bash
python3 scripts/optimization/inspect_csv_data.py
```
- Muestra columnas en CSV
- Identifica limitaciones (qué filtros NO se pueden relajar)
- Rangos de valores disponibles

---

### 🚀 MULTI-BACKTEST (Optimización Completa)

#### 5. `run_multi_backtest_optimization.py` ✨ NUEVO - ⭐ RECOMENDADO
Ejecuta múltiples backtests automáticamente con diferentes parámetros.

```bash
# Optimización rápida (grid pequeño, ~5-10 min)
python3 scripts/optimization/run_multi_backtest_optimization.py --mode quick

# Optimización completa (grid grande, ~30-60 min)
python3 scripts/optimization/run_multi_backtest_optimization.py --mode full

# Custom dates
python3 scripts/optimization/run_multi_backtest_optimization.py \
    --mode quick \
    --start-date 2020-01-01 \
    --end-date 2023-12-31
```

**Qué hace:**
1. Define grid de parámetros (ej. min_rvol: [1.0, 1.5, 2.0])
2. Genera todas las combinaciones (ej. 36 configs en modo 'quick')
3. Ejecuta backtest COMPLETO para cada combinación
4. Compara métricas reales (Win Rate, PF, Sharpe, etc.)
5. Guarda resultados en `outputs/optimization/`
6. Muestra Top 5 configuraciones óptimas

**Grids Disponibles:**

- **Quick Mode** (~36 combinaciones, ~10 min):
  ```python
  {
      'min_rvol': [1.0, 1.5, 2.0],
      'max_dist_sma20': [7.0, 10.0],
      'min_adr': [1.0, 1.5],
      'min_consolidation': [5, 10, 15],
  }
  ```

- **Full Mode** (~720 combinaciones, ~6 horas):
  ```python
  {
      'min_rvol': [1.0, 1.3, 1.5, 1.8, 2.0],
      'max_dist_sma20': [5.0, 7.0, 10.0, 12.0],
      'min_adr': [1.0, 1.5, 2.0],
      'min_consolidation': [5, 10, 15, 20],
      'max_stop_pct': [6.0, 8.0, 10.0],
  }
  ```

---

## 🔄 Workflow Completo Recomendado

### Estrategia Híbrida (Mejor de ambos mundos):

```bash
# FASE 1: EXPLORACIÓN (Post-Mortem)
# ====================================
# 1. Ejecuta backtest en Streamlit con filtros RELAJADOS
#    - min_rvol: 0.5
#    - max_dist_sma20: 20.0
#    - min_consolidation: 0

# 2. Diagnóstico rápido
python3 scripts/optimization/quick_diagnostics.py
# → Identifica problemas (ej. "Winners tienen mayor RVOL")

# 3. Encuentra rangos prometedores
python3 scripts/optimization/range_finder.py
# → Sugiere: min_rvol ≈ 1.5-2.0, max_dist ≈ 7-10%


# FASE 2: OPTIMIZACIÓN (Multi-Backtest)
# ======================================
# 4. Multi-backtest con grid pequeño
python3 scripts/optimization/run_multi_backtest_optimization.py --mode quick
# → Prueba 36 combinaciones
# → Encuentra: min_rvol=1.5, max_dist=7.0 es óptimo (PF=2.1)


# FASE 3: FINE-TUNING (Post-Mortem)
# ==================================
# 5. Backtest con rango óptimo (ligeramente relajado)
#    Streamlit: min_rvol=1.0, max_dist=10.0

# 6. Grid search fino
python3 scripts/optimization/optimize_parameters.py --method grid
# → Prueba valores exactos: [1.3, 1.5, 1.7, 2.0]
# → Afina a: min_rvol=1.5


# FASE 4: VALIDACIÓN
# ===================
# 7. Backtest final con parámetros óptimos en diferentes periodos
# 8. Confirma robustez (evita overfitting)


# FASE 5: PRODUCCIÓN
# ===================
# 9. Aplica mejor config en Streamlit
# 10. Trade real o paper trading
```

---

## 📊 Outputs

Todos los scripts guardan resultados en:
```
outputs/optimization/
  ├── optimization_results_YYYYMMDD_HHMMSS.csv  ← Multi-backtest
  ├── diagnostics_YYYYMMDD_HHMMSS.txt          ← Quick diagnostics
  ├── ranges_YYYYMMDD_HHMMSS.csv               ← Range finder
  └── grid_results_YYYYMMDD_HHMMSS.csv         ← Grid search
```

---

## 🔍 Comparación de Métodos

| Método | Tiempo | Precisión | Flexibilidad | Overfitting | Caso de Uso |
|--------|--------|-----------|--------------|-------------|-------------|
| **Post-Mortem** | 30 seg | Media | Baja | Bajo | Exploración rápida |
| **Multi-Backtest** | 5-30 min | Alta | Alta | Medio | Optimización seria |
| **Híbrido** | 3-5 min | Alta | Media-Alta | Bajo | ⭐ RECOMENDADO |

---

## 💡 Tips Importantes

### ✅ DO:
- Usa Multi-Backtest para encontrar rangos óptimos
- Usa Post-Mortem para fine-tuning rápido
- Ejecuta backtest inicial con filtros MUY RELAJADOS
- Limita grid a 3-4 valores por parámetro (evita overfitting)
- Valida en diferentes periodos (walk-forward)

### ❌ DON'T:
- No confíes solo en Post-Mortem para optimización seria
- No uses grids gigantes (>100 combinaciones) sin validación
- No optimices más de 3-4 parámetros a la vez
- No uses el mismo periodo para optimizar Y validar

---

## 📁 Dónde Buscan los Scripts

Los scripts buscan CSVs en este orden:

1. `outputs/backtests/trade_log.csv` (último backtest)
2. `trade_log.csv` (root)
3. `outputs/backtests/*trade_log*.csv` (timestamped)
4. **NO buscan en `cvs/` automáticamente**

Para usar archivos de `cvs/`:
```bash
# Opción 1: Especificar manualmente
python3 quick_diagnostics.py --file cvs/complete_trades_20260107.csv

# Opción 2: Copiar a ubicación estándar
cp cvs/complete_trades.csv outputs/backtests/
```

---

## ⚠️ Sobre VectorBT

Los scripts usan VectorBT cuando es apropiado (backtests completos).
Los scripts de análisis estadístico usan pandas optimizado.

**No pierdes velocidad** - cada herramienta para lo que es mejor.

---

## 🚀 Quick Start

```bash
# 1. Diagnóstico rápido del último backtest
python3 scripts/optimization/quick_diagnostics.py

# 2. Si los resultados son malos → Multi-backtest
python3 scripts/optimization/run_multi_backtest_optimization.py --mode quick

# 3. Aplica mejores parámetros en Streamlit

# 4. Valida con nuevo backtest
```

---

## 📚 Documentación Adicional

- `OPTIMIZACION_WORKFLOW_EXPLICADO.md` - Flujo completo explicado
- `OPTIMIZACION_STRATEGIES_EXPLAINED.md` - Comparación de estrategias
- `FIX_RVOL_BUG.md` - Problemas comunes y fixes
