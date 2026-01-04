# 🔧 Fix: Cálculo de P&L Total en Salidas Parciales

## 🚨 Problema Identificado

**Dashboard mostraba métricas incorrectas** para trades con salidas parciales:

### Ejemplo: SSRM (2025-08-25)

| Métrica | Dashboard (ANTES) | **Correcto** | Error |
|---------|-------------------|--------------|-------|
| **Total P&L** | $1,269.55 | **$1,919.22** | ❌ -$649.67 |
| **R Multiple** | +2.54R | **+3.88R** | ❌ -1.34R |
| **Días FASE 3** | 0 | **45 días** | ❌ |

---

## 🔍 Causa Raíz

### 1. **Bug en `_close_position()` (daily_engine.py)**

**Código anterior (línea 441):**
```python
pnl = (price - pos.entry_price) * pos.shares  # ❌ Solo shares finales
```

**Problema:**
- Solo calculaba PnL de las **shares restantes** al cierre
- **Ignoraba completamente** el PnL de salidas parciales previas (Fase 1 y Fase 2)
- Resultado: PnL total subestimado en trades con parciales

**Ejemplo con SSRM:**
```python
# ❌ Cálculo INCORRECTO
pnl = (22.85 - 17.31) × 229 shares = $1,268.66  # Solo runner

# ✅ Cálculo CORRECTO
Fase 1: (17.95 - 17.31) × 304 = $194.56
Fase 2: (19.31 - 17.31) × 228 = $456.00
Fase 3: (22.85 - 17.31) × 229 = $1,268.66
---------------------------------------
TOTAL:                        $1,919.22 ✅
```

### 2. **Bug en Dashboard (app.py)**

**Código anterior (línea 888):**
```python
total_result = trade_data['Result']  # ❌ Tomaba PnL incorrecto del CSV
```

- Usaba directamente el valor del CSV (que ya estaba mal)
- No sumaba las salidas parciales

**Código anterior (línea 830):**
```python
final_days = trade_data.get('days_held', 0)  # ❌ Siempre retornaba 0
```

- `days_held` no existe en el CSV
- Mostraba 0 días en lugar de los días totales del trade

---

## ✅ Solución Aplicada

### 1. **Fix en `src/backtest/daily_engine.py` (líneas 439-472)**

```python
def _close_position(self, symbol, price, date, reason):
    pos = self.portfolio.positions.pop(symbol)
    
    # PnL del cierre final (solo shares restantes)
    final_exit_pnl = (price - pos.entry_price) * pos.shares
    self.portfolio.cash += (pos.shares * price)
    
    # **CALCULAR PNL TOTAL**: Suma de salidas parciales + cierre final
    total_pnl = final_exit_pnl
    
    # Buscar salidas parciales de este símbolo y sumar su PnL
    for partial_exit in self.portfolio.partial_exits:
        if partial_exit['symbol'] == symbol and partial_exit['entry_date'] == pos.entry_date:
            total_pnl += partial_exit['pnl']
    
    trade_record = {
        ...
        'pnl': total_pnl,  # ✅ PnL TOTAL (parciales + cierre final)
        ...
    }
```

**Cambios:**
- ✅ Itera sobre `self.portfolio.partial_exits`
- ✅ Suma PnL de todas las salidas parciales del mismo trade
- ✅ Guarda PnL total correcto en el CSV

### 2. **Fix en `app.py` (líneas 826-902)**

**a) Total Días (línea 832):**
```python
# Calcular días totales desde entrada hasta salida final
total_days_held = (trade_data['exit_date'] - trade_data['entry_date']).days
st.write(f"**⏱️ Total Días:** {total_days_held}")
```

**b) Total P&L (línea 891):**
```python
# Total P&L = Suma de parciales + runner
total_result = total_pnl + final_pnl
st.metric("💰 Total P&L", f"${total_result:.2f}", delta="Final")
```

**c) R Multiple (línea 898):**
```python
# Recalcular R Multiple con PnL total correcto
R_inicial = trade_data.get('R_inicial', 1)
initial_shares = trade_data.get('initial_shares', trade_data.get('shares', 0))
total_risk = R_inicial * initial_shares
total_r = total_result / total_risk if total_risk > 0 else 0
st.metric("⚖️ R Total", f"{total_r:+.2f}R", delta=None, delta_color=r_color)
```

---

## 🎯 Resultado Esperado

### Después del fix, para SSRM:

```
📤 Progresión de Salidas Parciales
✅ Este trade ejecutó salidas escalonadas (Fase 1, Fase 2, Fase 3)

🎯 Métricas Totales
💰 Total P&L:      $1,919.22  ✅ (antes: $1,269.55)
📊 Parciales P&L:  $650.56    ✅
🏃 Runner P&L:     $1,268.66  ✅
⚖️ R Total:        +3.88R     ✅ (antes: +2.54R)

🏁 FASE 3 (Runner)
⏱️ Total Días: 45  ✅ (antes: 0)
```

---

## 📊 Impacto en Métricas Generales

**Este fix afecta:**
1. ✅ **Win Rate** - Más preciso (trades parcialmente exitosos ahora muestran PnL real)
2. ✅ **Average Winner** - Incrementa (winners con parciales tenían PnL subestimado)
3. ✅ **Total PnL del backtest** - Incrementa (se suma todo correctamente)
4. ✅ **R Multiples** - Más realistas (refleja verdadero retorno)
5. ✅ **Expectancy** - Mejora (profit real era mayor de lo reportado)

---

## 🧪 Testing

```bash
# 1. Verificar sintaxis
python3 -m py_compile src/backtest/daily_engine.py app.py

# 2. Re-ejecutar backtest
python3 daily_backtest_runner.py

# 3. Verificar en dashboard
streamlit run app.py
# Buscar trades con tp1_executed=True o tp2_executed=True
```

---

## 📝 Notas Técnicas

### ¿Por qué pasó desapercibido?

1. **Trades sin parciales funcionaban bien** - El bug solo afectaba trades con Fase 1/2
2. **Dashboard mostraba parciales por separado** - La tabla de fases se veía correcta
3. **El cash del portfolio era correcto** - Solo el reporte en CSV estaba mal

### Coherencia del Sistema

Ahora todo es coherente:
```
Portfolio.cash ✅ (siempre estuvo bien)
    ↓
partial_exits.csv ✅ (siempre estuvo bien)
    ↓
trade_record['pnl'] ✅ (FIXED - ahora suma parciales)
    ↓
backtest_results.csv ✅ (FIXED - PnL total correcto)
    ↓
Dashboard Métricas ✅ (FIXED - usa PnL correcto)
```

---

**Fecha**: 2025-12-22  
**Archivos modificados**: 
- `src/backtest/daily_engine.py` (líneas 439-472)
- `app.py` (líneas 826-902)

**Severidad**: 🔴 **ALTA** - Afectaba métricas clave de performance  
**Tipo**: Bug de cálculo - Subestimación de PnL en trades parciales
