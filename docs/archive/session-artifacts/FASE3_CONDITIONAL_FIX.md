# 🔧 Fix: FASE_3 Solo para Trades con Salidas Parciales

## 🚨 Problema Identificado

**TODOS los trades se registraban como FASE_3**, incluso los que nunca ejecutaron salidas parciales:

### Ejemplo: Trade con Stop Loss (-2.72%)

```
❌ ANTES:
Dashboard decía: "✅ Este trade ejecutó salidas escalonadas (Fase 1, Fase 2, Fase 3)"

Pero el trade:
- Nunca llegó a +1R (requiere +1R para FASE_1)
- Se cerró en STOP_LOSS a -2.72%
- No hubo salidas parciales

Resultado: FASE_3 sin FASE_1/FASE_2 → Contradictorio
```

---

## 🔍 Causa Raíz

Mi fix anterior registraba **TODOS los cierres** como FASE_3:

```python
# ❌ CÓDIGO ANTERIOR (incorrecto)
def _close_position(self, symbol, price, date, reason):
    # ...
    # SIEMPRE registra FASE_3 (mal)
    self._register_partial_exit(
        phase='FASE_3',  # ❌ Sin validar si hubo FASE_1
        ...
    )
```

**Lógica incorrecta:**
- FASE_3 = Runner exit (después de convertir a risk-free)
- Si nunca hubo FASE_1, **no puede haber FASE_3**

---

## ✅ Solución Implementada

### 1. **Engine (`src/backtest/daily_engine.py`)**

FASE_3 solo se registra **si el trade ejecutó FASE_1**:

```python
# ✅ CÓDIGO CORREGIDO
def _close_position(self, symbol, price, date, reason):
    # ...
    
    # **REGISTRAR FASE_3 SOLO si hubo salidas parciales**
    if pos.tp1_hit:  # ✅ Solo si ejecutó FASE_1
        self._register_partial_exit(
            symbol=symbol,
            phase='FASE_3',
            ...
        )
```

**Lógica corregida:**
- `pos.tp1_hit = True` → Trade alcanzó +1R → FASE_1 ejecutada → OK registrar FASE_3
- `pos.tp1_hit = False` → Trade nunca alcanzó +1R → NO registrar FASE_3

---

### 2. **Dashboard (`app.py`)**

Actualizado para distinguir entre **trades con parciales** vs **cierres normales**:

#### a) Detección de salidas parciales:

```python
# Verificar si realmente hubo salidas parciales
has_partial_exits = any(partial_for_trade['phase'].isin(['FASE_1', 'FASE_2']))

if has_partial_exits:
    st.success("✅ Este trade ejecutó salidas escalonadas (Fase 1, Fase 2, Fase 3)")
else:
    st.info("ℹ️ Este trade se cerró sin ejecutar salidas parciales (no alcanzó +1R)")
```

#### b) Timeline adaptativo:

```python
# Salida Final
if has_partial_exits:
    st.markdown("##### 🏁 FASE 3 (Runner)")
    st.write("🎯 Trailing Stop")
else:
    st.markdown("##### 🔴 CIERRE")
    st.write(f"⚠️ {reason}")  # STOP_LOSS, MOMENTUM_FAIL, etc.
```

#### c) Métricas ajustadas:

```python
with col_t2:
    if has_partial_exits:
        st.metric("📊 Parciales P&L", f"${total_pnl:.2f}", delta="Fases 1-2")
    else:
        st.metric("📊 Parciales P&L", "$0.00", delta="No ejecutadas")

with col_t3:
    if has_partial_exits:
        st.metric("🏃 Runner P&L", f"${final_pnl:.2f}", delta="Fase 3")
    else:
        st.metric("�� Cierre Directo", f"${final_pnl:.2f}", delta="Sin parciales")
```

---

## 🎯 Resultado Final

### Trade CON Salidas Parciales (SSRM - Winner)

```
📤 Progresión de Salidas Parciales
✅ Este trade ejecutó salidas escalonadas (Fase 1, Fase 2, Fase 3) - Sistema de Risk-Free

📊 Timeline:
🟢 ENTRADA → 🔵 FASE_1 (+1R) → 🟡 FASE_2 (+2.5R) → 🏁 FASE_3 (Runner)

📋 Resumen de Ejecución:
FASE_1 | $196   | +3.73%  | 40%
FASE_2 | $457   | +11.58% | 30%
FASE_3 | $1,269 | +32.03% | 30%
---------------------------------
TOTAL: $1,922 ✅

🎯 Métricas:
💰 Total P&L: $1,922
📊 Parciales P&L: $653
🏃 Runner P&L: $1,269
✅ Fases Ejecutadas: 2/2
⚖️ R Total: +3.88R
```

### Trade SIN Salidas Parciales (RVOL - Loser)

```
📤 Cierre de Posición
ℹ️ Este trade se cerró sin ejecutar salidas parciales (no alcanzó +1R para risk-free)

📊 Timeline:
🟢 ENTRADA → 🔴 CIERRE (STOP_LOSS)

🎯 Métricas:
💰 Total P&L: -$265
📊 Parciales P&L: $0.00 (No ejecutadas)
🏃 Cierre Directo: -$265 (Sin parciales)
✅ Fases Ejecutadas: 0/2 (Sin risk-free)
⚖️ R Total: -0.53R
```

---

## 📊 Impacto en Datos

### `partial_exits.csv` antes del fix:

```csv
symbol,phase,pnl
SSRM,FASE_1,196
SSRM,FASE_2,457
SSRM,FASE_3,1269  ✅ Correcto (trade con parciales)
RVOL,FASE_3,-265  ❌ Incorrecto (trade sin parciales)
```

### `partial_exits.csv` después del fix:

```csv
symbol,phase,pnl
SSRM,FASE_1,196
SSRM,FASE_2,457
SSRM,FASE_3,1269  ✅ Correcto (trade con parciales)
                  ✅ RVOL no aparece (correcto, no hubo parciales)
```

**Resultado:**
- Trades con parciales → 3 entradas (FASE_1, FASE_2, FASE_3)
- Trades sin parciales → 0 entradas en `partial_exits.csv`

---

## 🔬 Validación

### Test Cases:

1. **Trade Winner con parciales** (SSRM)
   - [ ] ✅ Aparece FASE_1 en `partial_exits.csv`
   - [ ] ✅ Aparece FASE_2 en `partial_exits.csv`
   - [ ] ✅ Aparece FASE_3 en `partial_exits.csv`
   - [ ] ✅ Dashboard muestra "salidas escalonadas"
   - [ ] ✅ Timeline: ENTRADA → FASE_1 → FASE_2 → FASE_3

2. **Trade Loser sin parciales** (Stop Loss)
   - [ ] ✅ NO aparece en `partial_exits.csv`
   - [ ] ✅ Dashboard muestra "cerrado sin salidas parciales"
   - [ ] ✅ Timeline: ENTRADA → CIERRE
   - [ ] ✅ Métricas muestran "$0.00 Parciales"

3. **Trade con FASE_1 pero sin FASE_2** (TP1 ejecutado, luego stop BE)
   - [ ] ✅ Aparece FASE_1 en `partial_exits.csv`
   - [ ] ✅ Aparece FASE_3 en `partial_exits.csv` (porque `tp1_hit=True`)
   - [ ] ✅ Dashboard muestra "salidas escalonadas"
   - [ ] ✅ Fases Ejecutadas: 1/2

---

## 📝 Notas Técnicas

### ¿Qué pasa con trades que solo llegan a FASE_1?

**Ejemplo:** Trade alcanza +1R, ejecuta FASE_1 (40%), luego stop breakeven cierra el resto.

```
FASE_1: Vende 40% en +1R
Stop → Breakeven
FASE_3: Cierra 60% restante en BE (0% return)
```

**Resultado:**
- ✅ `tp1_hit = True` → Se registra FASE_3
- ✅ Coherente: FASE_1 convirtió a risk-free, FASE_3 es el runner (aunque cerró en BE)

### ¿Por qué no verificar `tp2_hit`?

Porque:
- FASE_2 es opcional (solo si alcanza +2.5R)
- FASE_3 puede ocurrir después de FASE_1 sin FASE_2
- La condición clave es **"¿se convirtió a risk-free?"** → `tp1_hit`

---

## 🎯 Impacto

**Tipo:** Bug Fix - Lógica de clasificación  
**Severidad:** 🔴 Alta (afectaba interpretación de resultados)  
**Beneficio:** Claridad total - Distingue trades con/sin sistema de salidas

---

**Fecha**: 2025-12-22  
**Archivos modificados**: 
- `src/backtest/daily_engine.py` (líneas 461-473)
- `app.py` (líneas 780-945)

**Testing**: Re-ejecutar backtest y verificar dashboard con diferentes tipos de trades
