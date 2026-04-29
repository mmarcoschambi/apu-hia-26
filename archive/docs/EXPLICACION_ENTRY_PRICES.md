# 🧠 ENTRY PRICES FIJOS - EXPLICACIÓN TÉCNICA

## ❓ **TU PREGUNTA**

> "exits_tp1 = (self.close >= tp1_target.shift(1)) estas seguro de que funciona? el self.close no cambia cada día me explicas para entender"

**Respuesta:** ¡Excelente catch! Tenías razón, la implementación inicial era incorrecta.

---

## ❌ **EL PROBLEMA ORIGINAL**

### **Código incorrecto:**
```python
# Calculamos target basado en close actual
tp1_target = self.close + (1.5 * risk_per_share)

# Comparamos
exits_tp1 = (self.close >= tp1_target.shift(1))
```

### **¿Por qué está mal?**

`self.close` es un **DataFrame de TODOS los días**:

```python
Date       | Close | Entry
2024-01-01 | $100  | True   ← Entry aquí, queremos TP1 = $107.5
2024-01-02 | $105  | False
2024-01-03 | $110  | False
```

**Cálculo que hacía el código malo:**
```python
# Día 1: tp1_target = $100 + $7.5 = $107.5 ✅
# Día 2: tp1_target = $105 + $7.5 = $112.5 ❌ (RECALCULADO!)
# Día 3: tp1_target = $110 + $7.5 = $117.5 ❌ (RECALCULADO!)
```

**Problema:** El target "se mueve" con el precio → No es un TP fijo!

---

## ✅ **LA SOLUCIÓN CORRECTA**

### **Código correcto:**
```python
# 1. Capturar precio de ENTRADA únicamente
entry_prices = pd.DataFrame(np.nan, index=self.close.index, columns=self.close.columns)
entry_prices[entries] = self.close[entries]  # Solo llena donde hay entry

# Ejemplo:
Date       | Close | Entry | entry_prices
2024-01-01 | $100  | True  | $100    ← Capturado
2024-01-02 | $105  | False | NaN
2024-01-03 | $110  | False | NaN

# 2. Forward-fill para mantener entry price durante toda la posición
entry_prices_filled = entry_prices.ffill()

Date       | Close | entry_prices_filled
2024-01-01 | $100  | $100    ← Entry
2024-01-02 | $105  | $100    ← Mantiene entry price
2024-01-03 | $110  | $100    ← Mantiene entry price

# 3. Calcular targets basados en entry price FIJO
risk_per_share = entry_prices_filled * (stop_loss_pct / 100)
tp1_target = entry_prices_filled + (1.5 * risk_per_share)

Date       | entry_price | tp1_target (FIJO)
2024-01-01 | $100        | $107.5   ← Calculado una vez
2024-01-02 | $100        | $107.5   ← MISMO target
2024-01-03 | $100        | $107.5   ← MISMO target

# 4. Comparar precio actual con target fijo
exits_tp1 = (self.close >= tp1_target)

Date       | Close | tp1_target | Exit?
2024-01-01 | $100  | $107.5     | False
2024-01-02 | $105  | $107.5     | False
2024-01-03 | $110  | $107.5     | True ✅
```

---

## 🎯 **CÓMO FUNCIONA PASO A PASO**

### **Entry Day (Día 1):**
```python
# Compramos AAPL a $100
entry_price = $100
risk = $100 * 0.05 = $5
tp1_target = $100 + (1.5 * $5) = $107.5  # FIJO
tp2_target = $100 + (3.0 * $5) = $115.0  # FIJO
stop = $100 - $5 = $95
```

### **Day 2:**
```python
# Precio sube a $105
current_price = $105
tp1_target = $107.5  # NO cambia!

# Check: ¿$105 >= $107.5? → No → Mantenemos posición
```

### **Day 3:**
```python
# Precio sube a $110
current_price = $110
tp1_target = $107.5  # SIGUE sin cambiar!

# Check: ¿$110 >= $107.5? → SÍ → ¡EXIT TP1! ✅
```

---

## 📊 **COMPARACIÓN: Antes vs Después**

### **Antes (MALO - target móvil):**
```python
Day | Price | tp1_target (calculado cada día) | Exit?
1   | $100  | $107.5                          | No
2   | $105  | $112.5 ❌ (recalculado!)        | No
3   | $110  | $117.5 ❌ (recalculado!)        | No  ← Nunca sale!
```

### **Después (BUENO - target fijo):**
```python
Day | Price | tp1_target (FIJO desde entry) | Exit?
1   | $100  | $107.5                        | No
2   | $105  | $107.5 ✅ (mismo)             | No
3   | $110  | $107.5 ✅ (mismo)             | Sí ← Sale correctamente!
```

---

## 🔧 **IMPLEMENTACIÓN TÉCNICA**

### **Key components:**

1. **Entry Price Matrix:**
```python
entry_prices = pd.DataFrame(np.nan, ...)  # Matriz vacía
entry_prices[entries] = self.close[entries]  # Solo llena en entries
```

2. **Forward-fill:**
```python
entry_prices_filled = entry_prices.ffill()
# Propaga el entry price hacia adelante (mantiene durante posición)
```

3. **Position Active Mask:**
```python
position_active = entry_prices_filled.notna()
# True mientras entry_price existe (= estamos en posición)
```

4. **Fixed Targets:**
```python
tp1_target = entry_prices_filled + (1.5 * risk)
# Usa entry_price (fijo), no close (variable)
```

5. **Exit Logic:**
```python
exits_tp1 = (
    (self.close >= tp1_target) &  # Precio alcanza target
    position_active               # Y estamos en posición
)
```

---

## 💡 **POR QUÉ ES IMPORTANTE**

### **Con target móvil (malo):**
- ✗ Nunca alcanzas TP en stocks que suben gradualmente
- ✗ Target siempre está "adelante" del precio
- ✗ No matches comportamiento real de trading

### **Con target fijo (bueno):**
- ✅ TP se alcanza cuando precio sube X% desde entrada
- ✅ Matches exactamente cómo operas en real
- ✅ Runners pueden correr libremente (target no se mueve)

---

## 🧪 **VALIDACIÓN**

### **Test simple:**
```python
# Entry en día 1 a $100
# TP1 = $107.5 (1.5R)

# Día 2: Precio = $108
# ¿Sale? → SÍ ✅ (porque $108 > $107.5)

# Con código viejo:
# tp1_target recalculado = $108 + $8 = $116
# ¿Sale? → NO ❌ (porque $108 < $116)
```

**El código correcto sale cuando debe, el viejo se queda forever.**

---

## 🎯 **RESUMEN**

**Problema:** Calculábamos TP basado en precio ACTUAL (que cambia cada día)

**Solución:** Calculamos TP basado en precio de ENTRADA (fijo durante posición)

**Técnica:**
1. Capturar entry prices solo en días de entrada
2. Forward-fill para mantener durante posición
3. Calcular targets desde entry price (no desde close)
4. Comparar close actual vs target fijo

**Resultado:** Sistema de TP/SL funciona correctamente, runners pueden correr.

---

**Gracias por el catch! 🏎️**

La pregunta era 100% correcta: `self.close` sí cambia cada día, y necesitábamos fijar el entry price.

---

**Autor:** Built for the Bugatti 🏎️  
**Fecha:** 2026-01-08  
**Fix:** Entry Prices FIXED
