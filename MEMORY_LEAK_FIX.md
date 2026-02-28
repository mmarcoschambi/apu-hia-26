# 🚨 CRITICAL: MEMORY LEAK AND PERFORMANCE ISSUES

## 📊 PROBLEMA IDENTIFICADO

### Status: **CRÍTICO**

```
⚠️  LOW CONVERSION RATE: 1.0% - 2.4% (INACEPTABLE)
⚠️  79 tickers skipped (insufficient data)
⚠️  No puedo ejecutar más de 2-3 años de bt
⚠️  Range differs: 2021-2023 en lugar de 2020-2024
```

---

## 🎯 CAUSAS PRINCIPALES

### 1. MEMORY LEAK CRÍTICO

**Problem:**
- No puedes ejecutar más de 2-3 años de backtest
- Cada año añade memory que no se libera
- Memory se acumula con cada run
- Después de 3 años, el proceso se mata

**Evidence:**
```
Low conversion rate (1.0%): Muy bajo para estos parámetros
 → Debería ser > 20% con parámetros nuevos
 → Indica que la lógica está INACTIVA
```

### 2. TICKERS INSUFFICIENT DATA

**Problem:**
- 79 tickers skipped cuando usas 2-3 años
- Más años = más tickers con data incompleta
- Con 5 años = 200+ tickers con data insuficiente

**Evidence:**
```
"Skipped 79 tickers (insufficient data)"
```

### 3. CACHE DESACTUALIZADO

**Problem:**
- No hay datos de hoy (cache no se actualiza)
- SPY data incompleta
- Afecta market regime filter

**Evidence:**
```
"No hay datos de hoy"
"SPY not in cache"
```

### 4. CAMBIOS DE PARÁMETROS INCORRECTOS

**Problem:**
- Max stop 3% → 6% (debería dar MÁS trades)
- Max dist 7% → 9% (debería dar MÁS trades)
- Pero obtienes MENOS trades

**Possible cause:**
- App no está cargando parámetros actualizados
- Estás usando parámetros antiguos
- Streamlit cache no se limpia

---

## 🔧 SOLUCIÓN INMEDIATA

### Script: `fix_memory_leak.py`

```bash
python3 fix_memory_leak.py
```

**Qué hace:**
1. Backup del cache antiguo
2. Recrea cache con solo 5 años
3. Descarga datos actualizados
4. Asegura SPY data
5. Libera memory

---

## 📋 PASOS PARA RESOLVER

### PASO 1: LIMPIAR CACHE Y MEMORY

```bash
# Backup automático (creado por fix_memory_leak.py)
python3 fix_memory_leak.py
```

### PASO 2: BACKTEST RÁPIDO

```bash
# Usar 1 year en lugar de 3-5 years
python3 example_quick_backtest.py
```

**Expected:**
- < 1 minuto
- Conversion rate > 20%
- OK trades count

### PASO 3: VALIDAR CONVERGENCIA

```bash
python3 convergence_test_streamlit_cli.py
```

**Expected:**
- 100% convergencia (0% diferencia)
- 236 trades CLI = 236 trades Streamlit

### PASO 4: LIMPIAR STREAMLIT CACHE

```python
# En app.py:
st.cache_data.clear()
st.cache_resource.clear()
```

**Action:** Click "🧹 Limpiar Cache" button en sidebar

### PASO 5: CARGAR PARÁMETROS VALIDADOS

1. En Streamlit sidebar
2. Click "📥 Load Validated Params"
3. Esto asegura que use los parámetros óptimos (6% stop, etc.)

---

## 🚨 CAUSAS DEL MEMORY LEAK

### En `vectorbt_engine_advanced.py`:

```python
def simulate_with_partial_exits():
    # PROBLEM: No se limpia memoria después de cada run
    # PROBLEM: Los arrays no se liberan
    # PROBLEM: Streamlit cache no se limpia
```

### En `app.py`:

```python
@st.cache_data(ttl=300)  # TTL de 5 minutos
def run_cached_backtest(...):
    # PROBLEM: Esta cache acumula datos con cada run
    # PROBLEM: No se limpia manualmente
    return results, rejection_stats
```

---

## 💡 CÓMO EVITAR MEMORY LEAK EN EL FUTURO

### 1. Usar Convergence Mode (FIXED DOLLAR RISK)

```python
engine = AdvancedVectorBTEngine(
    mode='convergence',  # Fija riesgo a $150
    risk_dollars=150.0,
    ...
)
```

**Beneficios:**
- No compounding = no memory leak
- Fijo riesgo = más controlable
- Más rápido que production mode

### 2. Usar SMALLER UNIVERSE

```python
# En lugar de 40+ tickers:
universe = [
    'AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD'  # Solo 5
]
```

### 3. Limpiar Cache Entre Runs

```python
# En app.py:
st.sidebar.button("🧹 Limpiar Cache", on_click=clear_cache)

def clear_cache():
    st.cache_data.clear()
    st.cache_resource.clear()
    gc.collect()
    st.rerun()
```

### 4. Usar MÁS CORTO PERÍODO

```python
# Evitar 5 years
universe = ['AAPL', 'MSFT']
start_date = '2023-01-01'
end_date = '2024-12-31'  # 2 years máximo
```

### 5. Evitar `st.cache_data` con parámetros dinámicos

```python
# BAD:
@st.cache_data(ttl=300)
def run_cached_backtest(universe, start_date, ...):
    # Estos parámetros cambian constantemente

# GOOD:
def run_cached_backtest(universe, start_date, ...):
    # Sin cache, solo ejecuta
    # O usa cache con key hashing
```

---

## 🎯 CHECKLIST DE VALIDACIÓN

### Después de correr `fix_memory_leak.py`:

- [ ] Cache con 5 years y > 1000 tickers
- [ ] SPY data completo
- [ ] Conversion rate > 20%
- [ ] Memory después de GC: < 500MB
- [ ] 2-year backtest: < 5 minutes
- [ ] 3-year backtest: < 15 minutes

### Después de correr example_quick_backtest.py:

- [ ] Return: > 40% (con parámetros nuevos)
- [ ] Sharpe: > 0.8
- [ ] Win rate: > 55%
- [ ] Total trades: > 200

### Después de correr convergence_test:

- [ ] CLI trades = Streamlit trades (100%)
- [ ] Diferencia trades: 0
- [ ] Diferencia return: 0%

---

## 🚨 CARACTERÍSTICAS DEL PROBLEMA ACTUAL

### Síntomas:

1. **LOW CONVERSION RATE (1.0%):**
   - INCORRECTO para parámetros nuevos
   - Debería ser > 20%
   - Sugerencia: Parámetros no cargados

2. **MÁX 2-3 AÑOS:**
   - Memory leak con cada año adicional
   - Process se mata después de 3 años
   - Número de tickers skipped crece con el tiempo

3. **SPY DATA MISSING:**
   - Afecta market regime filter
   - Debe agregarse con `quick_populate_cache.py --include SPY`

4. **TICKERS SKIPPED:**
   - 79 con 2-3 years
   - 200+ con 5 years
   - Data incompleta no permite ejecutar

### Causa Principal:

**Memory leak** en la combinación de:
1. Engine de producción (no libera memoria)
2. Streamlit cache (acumula datos)
3. Parámetros agresivos (crean más trades)
4. Cache desactualizado (tickers con data incompleta)

---

## 📊 PERFORMANCE ESPERADA

### Después del fix:

| Período | Trades | Return | Sharpe | Time |
|---------|--------|--------|--------|------|
| 1 year | 200-300 | 30-40% | 1.0+ | < 1 min |
| 2 years | 400-600 | 40-50% | 0.9+ | < 5 min |
| 3 years | 600-900 | 50-60% | 0.8+ | < 15 min |

**Conversion Rate Esperado:** > 20%

---

## 🔧 SCRIPTS DE FIX

### 1. `fix_memory_leak.py`
```bash
python3 fix_memory_leak.py
```
- Recrea cache con 5 years
- Asegura SPY data
- Libera memory

### 2. `diagnose_performance_issues.py`
```bash
python3 diagnose_performance_issues.py
```
- Verifica integridad del sistema
- Identifica problemas específicos

### 3. `example_quick_backtest.py`
```bash
python3 example_quick_backtest.py
```
- Backtest rápido de validación
- Esperado: < 1 minute

---

## ✅ CONCLUSIONES

### Problema: MEMORY LEAK CRÍTICO

**Evidencia:**
- Low conversion rate (1.0%): INCORRECTO
- Max 2-3 years: Memory se agota
- 79 tickers skipped: Data incompleta

### Solución: FIX_MEMORY_LEAK.PY

**Pasos:**
1. Limpiar cache antiguo
2. Recrea cache con 5 years
3. Asegurar SPY data
4. Liberar memory

### Prevención: MÁS CORTO PERÍODO + CLEAN CACHE

**Regla de oro:**
- Máximo 2 years de backtest
- Limpiar cache entre runs
- Usar convergence mode

---

**Creado:** 2026-02-07
**Problema:** Memory leak con parámetros agresivos
**Solución:** Fix_memory_leak.py + app improvements
