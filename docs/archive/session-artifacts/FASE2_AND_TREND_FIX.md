# 🔧 Fix: FASE_2 Missing + Trend "Weak" Colandose

## 🚨 Problemas Identificados

### Problema 1: FASE_2 Desaparece

**Ejemplo CVNA (2023-02-02):**

```
Initial shares: 114
FASE_1 vendió: 45 (39%)   ✓
FASE_2 vendió: ???        ❌ FALTA
FASE_3 restante: 69 (61%) ← Incorrecto, debería ser ~30%

¿Qué pasó con el 30% de FASE_2?
```

**Causa:** Línea 380 usaba **`elif`** en lugar de **`if`**:

```python
# ❌ CÓDIGO INCORRECTO
if not pos.tp1_hit:
    # FASE 1 logic
    ...
elif pos.tp1_hit and not pos.tp2_hit:  # ❌ elif bloquea ejecución
    # FASE 2 logic
```

**Problema:**
- Si FASE_1 se ejecuta en un día (línea 350-376)
- El `elif` de FASE_2 **NO se evalúa** ese mismo día
- Resultado: Stock sube de +1R a +2.5R **el mismo día**, pero FASE_2 nunca se ejecuta

---

### Problema 2: Trend "Weak" se cuela

**Ejemplo CVNA:**

```
Dashboard muestra:
📈 Tendencia: Weak
⚠️ "Solo operamos stocks en Uptrend"

Pero el trade entró igual ❌
```

**Causa:** Discrepancia entre screener y contexto guardado:

**Screener (línea 99 - CORRECTO):**
```python
is_trending = current['close'] > current['sma_20'] and current['sma_20'] > current['sma_50']
if not is_trending:
    return None  # Rechaza
```

**Context saving (línea 628 - INCORRECTO):**
```python
trend_status = 'Uptrend' if current_bar['close'] > sma_20 else 'Weak'
# ❌ Solo verifica Price > SMA20, NO verifica SMA20 > SMA50
```

**Resultado:**
- Trade pasa screener (Uptrend correcto)
- Pero contexto se guarda como "Weak" (criterio más débil)
- Dashboard muestra "Weak" aunque el trade SÍ cumplía Uptrend al entrar

---

## ✅ Soluciones Aplicadas

### Fix 1: FASE_2 puede ejecutarse mismo día que FASE_1

**Archivo:** `src/backtest/daily_engine.py` (línea 380)

```python
# ✅ CÓDIGO CORREGIDO
if not pos.tp1_hit:
    # FASE 1 logic
    ...

# Usar 'if' no 'elif' para permitir ejecución el mismo día
if pos.tp1_hit and not pos.tp2_hit:  # ✅ if permite ambas fases el mismo día
    # FASE 2 logic
```

**Efecto:**
- FASE_1 se ejecuta si precio alcanza +1R
- **Inmediatamente después**, se verifica si alcanzó +2.5R para FASE_2
- Ambas fases pueden ejecutarse el mismo día

**Escenario típico:**
```
Día 0 (2023-02-02):
- Stock abre en $17.43
- Sube a $22.32 (+28%) ← Alcanza +1R Y +2.5R el mismo día
- 09:00: FASE_1 ejecuta → Vende 40%
- 10:00: FASE_2 ejecuta → Vende 30%
- Cierre: Queda 30% para runner
```

---

### Fix 2: Trend Context coherente con Screener

**Archivo:** `src/backtest/daily_engine.py` (líneas 626-632)

```python
# ✅ CÓDIGO CORREGIDO
sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
sma_50 = df['close'].rolling(window=50).mean().iloc[-1]

# Uptrend estricto: Price > SMA20 AND SMA20 > SMA50 (mismo criterio que screener)
is_uptrend = (current_bar['close'] > sma_20) and (sma_20 > sma_50)
trend_status = 'Uptrend' if is_uptrend else 'Weak'
```

**Efecto:**
- Contexto guardado usa **mismo criterio** que screener
- Si trade pasó filtro → contexto muestra "Uptrend"
- Elimina contradicción en dashboard

---

## 🎯 Resultado Esperado

### Trade CVNA (Después del fix)

**Antes:**
```
FASE_1 | 2023-02-02 | $22.32 | 45 sh (39%) | $220
FASE_2 | ❌ NO APARECE
FASE_3 | 2023-02-03 | $12.95 | 69 sh (61%) | -$309

Total: -$88.96
Trend: Weak ❌
```

**Después:**
```
FASE_1 | 2023-02-02 | $22.32 | 45 sh (40%) | $220
FASE_2 | 2023-02-02 | $XX.XX | 34 sh (30%) | $XXX  ✅ APARECE
FASE_3 | 2023-02-03 | $12.95 | 35 sh (30%) | -$XXX ✅ Correcto

Total: Recalculado
Trend: Uptrend ✅ (si pasó screener)
```

---

## 📊 Validación

### Test Case 1: Ejecución mismo día

**Condición:** Stock sube de +1R a +2.5R en un día

- [ ] ✅ FASE_1 ejecuta al tocar +1R
- [ ] ✅ FASE_2 ejecuta al tocar +2.5R (mismo día)
- [ ] ✅ `partial_exits.csv` muestra ambas fases con misma fecha

### Test Case 2: Trend Context coherente

**Condición:** Trade pasa screener con Uptrend

- [ ] ✅ `context_trend` guardado como "Uptrend"
- [ ] ✅ Dashboard muestra "Uptrend" (no "Weak")
- [ ] ✅ Coherencia entre filtro de entrada y contexto guardado

### Test Case 3: FASE_2 en días separados

**Condición:** Stock alcanza +1R día 1, +2.5R día 3

- [ ] ✅ FASE_1 ejecuta día 1
- [ ] ✅ FASE_2 ejecuta día 3
- [ ] ✅ Ambas fases aparecen en `partial_exits.csv`

---

## 📝 Notas Técnicas

### ¿Por qué usar `if` en lugar de `elif`?

**Concepto:** FASE_1 y FASE_2 son **eventos independientes** que pueden ocurrir:
- El mismo día (si hay volatilidad alta)
- En días diferentes (normal)

**Solución:**
```python
if condicion_fase1:
    ejecutar_fase1()

if condicion_fase2:  # ✅ 'if' permite chequear independientemente
    ejecutar_fase2()
```

**No usar:**
```python
if condicion_fase1:
    ejecutar_fase1()
elif condicion_fase2:  # ❌ 'elif' solo ejecuta si fase1 NO se ejecutó
    ejecutar_fase2()
```

---

### ¿Por qué el trend context estaba mal?

**Problema:** Dos lugares calculaban trend con criterios diferentes:

1. **Screener** (filtro de entrada):
   - `Price > SMA20 AND SMA20 > SMA50` ← Estricto

2. **Context saving** (para dashboard):
   - `Price > SMA20` ← Débil

**Solución:** Usar **mismo criterio** en ambos lugares.

---

## 🎯 Impacto

**Tipo:** Bug Fix - Lógica de ejecución y contexto  
**Severidad:** 🔴 **CRÍTICA**
- FASE_2 missing afecta **performance real** del sistema de salidas
- Trend context incorrecto causa **confusión** en análisis

**Beneficio:**
- ✅ Sistema de salidas funciona como diseñado (40% / 30% / 30%)
- ✅ Dashboard coherente con filtros de entrada
- ✅ Métricas precisas de fase 2

---

**Fecha**: 2025-12-22  
**Archivos modificados**: 
- `src/backtest/daily_engine.py` (líneas 380, 626-632)

**Testing URGENTE**: Re-ejecutar backtest completo
```bash
python3 daily_backtest_runner.py
```

**Verificar:**
1. Trades con FASE_1 ahora tienen FASE_2 (si alcanzaron +2.5R)
2. Contexto "Uptrend" para todos los trades que entraron
3. Distribución correcta de shares: 40% / 30% / 30%
