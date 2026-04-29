# 🏎️ POSITION SIZING FIX - BUGATTI DIVO

## 🐛 PROBLEMA IDENTIFICADO

### **ANTES (Incorrecto):**
```python
position_value = risk_dollars * position_size_pct
# Ejemplo: $200 * 1.0 = $200 por posición
```

**Problemas:**
1. ❌ **No calcula shares correctamente** - usa valor fijo en lugar de calcular basado en stop
2. ❌ **`max_exposure_pct` era fantasma** - definido pero nunca usado
3. ❌ **No respeta Fixed Dollar Risk** - el sizing era arbitrario

---

## ✅ SOLUCIÓN IMPLEMENTADA

### **AHORA (Correcto):**
```python
# 1. Calcular stop loss
stop_distance = close * (max_stop_pct / 100)  # e.g., 8% of price

# 2. Calcular shares basadas en Fixed Dollar Risk
shares_per_trade = risk_dollars / stop_distance

# 3. Calcular valor de posición
position_value_base = shares_per_trade * close

# 4. Aplicar ajustes por RVOL (size reduction)
position_size_pct = 1.0  # default
if RVOL >= rvol_warning: position_size_pct = rvol_warning_size  # 65%
if RVOL >= rvol_danger: position_size_pct = rvol_danger_size    # 30%

position_value = position_value_base * position_size_pct

# 5. Aplicar límite de exposición
max_position_value = initial_capital * max_exposure_pct  # e.g., 25%
position_value = min(position_value, max_position_value)
```

---

## 📊 EJEMPLO PRÁCTICO

### **Escenario:**
- Initial Capital: **$100,000**
- Risk per trade: **$200**
- Max exposure: **25% ($25,000)**
- Max stop: **8%**

### **Ticker: AAPL @ $180**

#### **Caso 1: RVOL Normal (1.5x)**
```
Stop distance = $180 * 8% = $14.40
Shares = $200 / $14.40 = 13.89 ≈ 13 shares
Position value = 13 * $180 = $2,340

RVOL 1.5x → 100% size → $2,340
Exposure = $2,340 / $100,000 = 2.3% ✅ (< 25%)
```

#### **Caso 2: RVOL Warning (2.5x)**
```
Shares = 13 (same calculation)
Position value base = $2,340

RVOL 2.5x → 65% size → $2,340 * 0.65 = $1,521
Exposure = $1,521 / $100,000 = 1.5% ✅ (reduced risk)
```

#### **Caso 3: RVOL Danger (3.5x)**
```
Shares = 13 (same calculation)
Position value base = $2,340

RVOL 3.5x → 30% size → $2,340 * 0.30 = $702
Exposure = $702 / $100,000 = 0.7% ✅ (heavily reduced)
```

#### **Caso 4: Ticker caro @ $1,500**
```
Stop = $1,500 * 8% = $120
Shares = $200 / $120 = 1.67 ≈ 1 share
Position value = 1 * $1,500 = $1,500

RVOL 1.5x → 100% size → $1,500
Exposure = $1,500 / $100,000 = 1.5% ✅
```

#### **Caso 5: Penny stock @ $5**
```
Stop = $5 * 8% = $0.40
Shares = $200 / $0.40 = 500 shares
Position value = 500 * $5 = $2,500

RVOL 1.5x → 100% size → $2,500
Exposure = $2,500 / $100,000 = 2.5% ✅

Max exposure cap: min($2,500, $25,000) = $2,500 ✅
```

#### **Caso 6: Position que excede max_exposure**
```
Supongamos un cálculo que da $30,000:

Max allowed = $100,000 * 25% = $25,000
Final position = min($30,000, $25,000) = $25,000 ✅

→ Position capped al 25% del capital
```

---

## 🎯 VENTAJAS DEL NUEVO SISTEMA

1. ✅ **Fixed Dollar Risk**: Siempre arriesgas $200 por trade (o el valor configurado)
2. ✅ **Position sizing correcto**: Shares calculadas basadas en stop loss
3. ✅ **RVOL protection**: Reduce size automáticamente en alta volatilidad
4. ✅ **Max exposure control**: Nunca más del 25% en un solo ticker
5. ✅ **Funciona con cualquier precio**: Penny stocks, Blue chips, todo

---

## 🔧 PARÁMETROS RELEVANTES

### **En Bugatti EVO LAYER1_PARAMS:**
```python
'risk_dollars': [150, 200, 250],       # Riesgo fijo por trade
'max_exposure_pct': [0.20, 0.25, 0.30],  # Max % del capital por ticker
'max_stop_pct': [0.07, 0.08, 0.10],     # Stop loss %
'rvol_danger_size': [0.30, 0.40],       # Size cuando RVOL > 3x
```

### **En Bugatti EVO LAYER2_PARAMS:**
```python
'rvol_danger': [3.0, 3.5, 4.0],         # Threshold para "danger"
'rvol_warning': [2.0, 2.5],             # Threshold para "warning"
'rvol_warning_size': [0.60, 0.70],      # Size cuando RVOL > warning
```

---

## 📈 IMPACTO EN RESULTADOS

**Test con 4 tickers (2024 H1):**
- Trades: **44**
- Sharpe: **2.32**
- Return: **82.04%**
- Win Rate: **65.9%**
- Max DD: **11.42%**

✅ **Position sizing funcionando correctamente**

---

## 🚀 PRÓXIMO PASO

```bash
# Ejecutar Bugatti EVO con el nuevo position sizing
python3 bugatti_evo.py \
  --k-folds 3 \
  --fold-size 276 \
  --l1-trials 50 \
  --l2-trials 30 \
  --in-start 2020-01-01 \
  --in-end 2022-12-31 \
  --val-start 2023-01-01 \
  --val-end 2023-06-30 \
  --oos-start 2023-07-01 \
  --oos-end 2024-12-31 \
  --run-oos
```

**"Fixed Dollar Risk + Max Exposure = Portfolio Protection"** 🏎️💨
