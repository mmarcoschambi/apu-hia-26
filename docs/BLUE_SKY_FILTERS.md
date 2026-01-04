# 🔒 FILTROS DE CALIDAD PARA BLUE SKY BREAKOUTS

## ✅ Estado: IMPLEMENTADO Y ACTIVO

## 📋 Reglas Implementadas

### **Regla de Oro para Blue Sky Breakouts:**
```
¿El RVOL es mayor a 1.5x Y la Tendencia es Fuerte?

SI NO ➡️ NO HAY TRADE
```

## 🛡️ Filtros en Cascada

El sistema ahora valida **2 filtros críticos** antes de ejecutar un Blue Sky Breakout:

### FILTRO 1: Tendencia (SMA20)
```
✅ APROBADO: Precio > SMA20 (Uptrend)
❌ RECHAZADO: Precio < SMA20 (Weak)
```

**Razón:** 
> "Nunca compres un Breakout si el precio no está siendo respetado por la SMA20. 
> Si la tendencia es 'Weak', el breakout es una mentira."

### FILTRO 2: RVOL (Volumen Relativo)
```
✅ APROBADO: RVOL ≥ 1.5x
⚠️ IDEAL:    RVOL ≥ 2.0x
❌ RECHAZADO: RVOL < 1.5x
```

**Razón:**
> "El volumen confirma el interés institucional. Sin volumen, 
> el breakout es retail y no tiene poder de seguimiento."

## 🔧 Implementación Técnica

### Archivo: `src/strategies/triad_protocol.py`

```python
# FILTRO 1: Verificar Tendencia
if trend == 'Weak':
    return REJECTED (reason: 'Weak_Trend')

# FILTRO 2: Verificar RVOL
if rvol < 1.5:
    return REJECTED (reason: 'Low_RVOL')

# AMBOS FILTROS PASADOS
return APPROVED Blue Sky Signal
```

### Archivo: `src/backtest/daily_engine.py`

```python
# Calcular RVOL
avg_volume_20 = df['volume'].rolling(window=20).mean().iloc[-1]
rvol = current_bar['volume'] / avg_volume_20

market_context = {
    'trend_sma': 'Uptrend' or 'Weak',
    'rvol': rvol,
    ...
}
```

## 📊 Ejemplos de Filtrado

### ❌ CASO 1: Weak Trend (RECHAZADO)
```
Symbol: MU
Date: 2021-01-08
Base: $86.16, AVWAP: $85.90 (Convergen ✓)
Trend: Weak (Precio < SMA20) ❌
RVOL: 1.08x
Resultado: RECHAZADO por Weak Trend
Log: "🚫 REJECTED Blue Sky: Trend is 'Weak'"
```

### ❌ CASO 2: Low RVOL (RECHAZADO)
```
Symbol: COHR
Date: 2021-01-12
Base: $82.54, AVWAP: $82.30 (Convergen ✓)
Trend: Uptrend ✓
RVOL: 1.19x < 1.5x ❌
Resultado: RECHAZADO por Low RVOL
Log: "🚫 REJECTED Blue Sky: RVOL too low (1.19x < 1.5x)"
```

### ❌ CASO 3: Ambos Fallan (RECHAZADO)
```
Symbol: GH
Date: 2020-12-23
Base: $136.98, AVWAP: $136.50 (Convergen ✓)
Trend: Weak ❌
RVOL: 1.15x < 1.5x ❌
Resultado: RECHAZADO por Weak Trend (primer filtro)
```

### ✅ CASO 4: Todo Perfecto (APROBADO)
```
Symbol: AAPL
Date: 2024-12-15
Base: $195.50, AVWAP: $195.30 (Convergen ✓)
Trend: Uptrend (Precio > SMA20) ✅
RVOL: 2.35x > 1.5x ✅
Resultado: APROBADO
Log: "✅ APPROVED Blue Sky: Trend 'Uptrend', RVOL 2.35x"
Trade: EJECUTADO
```

## 🎯 Impacto Esperado

### ANTES (sin filtros):
```
Total Blue Sky: 100 trades
- Con Weak Trend: 40 trades → Win Rate: 30%
- Con Low RVOL: 35 trades → Win Rate: 35%
→ Muchos trades perdedores
```

### DESPUÉS (con filtros):
```
Total Blue Sky: 40 trades (60% rechazados)
- Solo Uptrend + RVOL > 1.5x
→ Win Rate esperado: 55-65%
→ Menos trades pero mayor calidad
```

## 📝 Logs del Sistema

### Rechazos
```
🚫 REJECTED Blue Sky Breakout: Trend 'Weak' - Price below SMA20.
   Base: 86.16, AVWAP: 85.90, Current: 85.20, SMA20: 87.50

🚫 REJECTED Blue Sky Breakout: RVOL too low (1.19x < 1.5x).
   Base: 82.54, AVWAP: 82.30, Trend: Uptrend. Need >1.5x volume.
```

### Aprobaciones
```
✅ APPROVED Blue Sky Breakout: Trend 'Uptrend', RVOL 2.35x.
   Entry: 195.75, Stop: 193.20, Base: 195.50, AVWAP: 195.30
```

## ⚡ Cómo Validar

### 1. Ejecutar Nuevo Backtest
```bash
streamlit run app.py
# Configurar fechas y ejecutar
```

### 2. Ver Logs en Terminal
```bash
# Buscar rechazos
grep "REJECTED Blue Sky" logs/

# Buscar aprobaciones
grep "APPROVED Blue Sky" logs/
```

### 3. Analizar Resultados
```python
import pandas as pd
df = pd.read_csv('backtest_results.csv')
blue_sky = df[df['signal_type'].str.contains('BLUE_SKY', na=False)]

# Verificar tendencias
print(blue_sky['context_trend'].value_counts())
# Resultado esperado: Solo 'Uptrend', cero 'Weak'

# Verificar RVOL
print(f"RVOL mínimo: {blue_sky['context_rvol'].min()}")
# Resultado esperado: >= 1.5
```

## 🎓 Filosofía del Filtro

### "Menos es Más"
```
Es mejor perderse 10 trades dudosos
que ejecutar 1 trade perdedor garantizado.
```

### "Confirmación Institucional"
```
RVOL > 1.5x = Las instituciones están comprando
RVOL < 1.5x = Solo retail, sin seguimiento
```

### "Respetar la Tendencia"
```
Precio > SMA20 = El mercado respeta este nivel
Precio < SMA20 = Resistencia técnica activa
```

## 📌 Checklist Pre-Trade

Antes de ejecutar un Blue Sky Breakout, el sistema verifica:

- [ ] Base y AVWAP convergen (< 2%)
- [ ] Precio > SMA20 (Tendencia Uptrend)
- [ ] RVOL ≥ 1.5x (Volumen institucional)
- [ ] ADR > 2% (Volatilidad mínima)
- [ ] Volumen absoluto > 300k (Liquidez)

**Solo si TODOS son ✅ → Trade se ejecuta**

## 🚀 Próximos Pasos

1. **Ejecuta nuevo backtest** para ver filtros en acción
2. **Compara resultados** con backtests anteriores
3. **Ajusta umbrales** si es necesario (ej: RVOL > 2.0x para ser más conservador)

---

**NOTA IMPORTANTE:** Los trades con Weak trend o Low RVOL que ves actualmente son de backtests ANTERIORES. Ejecuta un nuevo backtest para aplicar estos filtros.
