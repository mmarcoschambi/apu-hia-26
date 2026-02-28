# Filtros de Riesgo Implementados

## 🎯 Objetivo
Eliminar trades con edge negativo basándose en análisis estadístico de backtests previos.

## 🛡️ Filtros Implementados

### 1. Filtro de Sobreextensión (Distancia a SMA20)

**Regla**: `IF dist_sma20_pct > 7% → RECHAZAR TRADE`

**Justificación**: 
- Análisis estadístico mostró que trades con >7% de extensión sobre SMA20 son los **peores perdedores**
- Estos setups tienen edge negativo - el precio está demasiado extendido para un entry seguro
- La probabilidad de pullback/reversión es muy alta

**Implementación**:
```python
# En screener.py - se calcula la métrica
dist_sma20_pct = ((current_close - sma_20) / sma_20 * 100)

# En daily_engine.py - se aplica el filtro DURO
if dist_sma20 > 7.0:
    logger.info(f"❌ {symbol} REJECTED: Sobreextendido {dist_sma20:.2f}% > 7%")
    continue  # NO ENTRAR
```

**Efecto**:
- ✅ Elimina trades con mayor probabilidad de pérdida
- ✅ Protege el capital de entradas tarde en el movimiento
- ✅ Mejora la calidad promedio de los setups

---

### 2. Filtro VolTrig (Clasificación de Riesgo por RVOL)

**Regla**: `IF VolTrig == 'Danger' → Reducir tamaño 50%`

**Clasificación VolTrig**:
- **Safe**: RVOL < 2.0x (Normal)
- **Warning**: RVOL 2.0x - 2.99x (Precaución)
- **Danger**: RVOL >= 3.0x (Alto Riesgo) → **Reducir 50%**

**Justificación**:
- Análisis mostró que el **edge desaparece** con volumen extremo (RVOL >= 3x)
- Volumen extremo indica:
  - Movimientos erráticos / whipsaw
  - Mayor probabilidad de gaps y slippage
  - Posible trampa institucional o "pump & dump"
  
**Implementación**:
```python
# En screener.py - se calcula VolTrig
if rvol >= 3.0:
    vol_trig = 'Danger'  # Alto riesgo
elif rvol >= 2.0:
    vol_trig = 'Warning'  # Riesgo medio
else:
    vol_trig = 'Safe'  # Riesgo bajo

# En daily_engine.py - se aplica reducción de tamaño
if vol_trig == 'Danger':
    vol_trig_reduction = 0.5  # Reducir a 50%
    vol_trig_note = f"⚠️ VolTrig=DANGER (RVOL={rvol:.2f}x) - Size reduced 50%"
    
# Se aplica ANTES de otras reducciones (earnings, ADR)
sizing['shares'] = int(original_shares * vol_trig_reduction)
```

**Efecto**:
- ⚠️ NO rechaza el trade (puede haber edge en algunos casos)
- ✅ Reduce exposición al riesgo de volatilidad extrema
- ✅ Protege el capital manteniendo la oportunidad de profit
- ✅ Mejora el ratio risk/reward general

---

## 📊 Ubicación en el Código

### Archivos Modificados:

1. **`src/core/screener.py`**
   - Líneas ~122-142: Cálculo de `dist_sma20_pct` y `vol_trig`
   - Se agregan al diccionario de resultados del screener

2. **`src/backtest/daily_engine.py`**
   - Líneas ~844-865: Filtros duros en `_prepare_orders()`
   - Línea ~862: Filtro de sobreextensión (REJECT)
   - Líneas ~867-872: Clasificación y nota de VolTrig
   - Líneas ~921-927: Aplicación de reducción por VolTrig
   - Líneas ~679-682: Guardado de métricas en trade_record

---

## 🧪 Testing

**Script de prueba**: `test_risk_filters.py`

Ejecutar:
```bash
python3 test_risk_filters.py
```

El script:
- ✅ Ejecuta backtest con 200 tickers en 2018
- ✅ Muestra estadísticas por categoría VolTrig
- ✅ Muestra estadísticas por bucket de distancia SMA20
- ✅ Guarda resultados detallados en CSV

**Métricas en el output CSV**:
- `dist_sma20_pct`: Distancia % del precio a SMA20 al entry
- `vol_trig`: Clasificación de riesgo (Safe/Warning/Danger)
- `context_rvol`: RVOL exacto al momento del setup

---

## 📈 Ejemplo de Análisis

### Antes de los Filtros:
```
Total trades: 150
Win Rate: 55%
Avg PnL: $150

Trades sobreextendidos (>7%): 20
  - Win Rate: 35%  ⚠️
  - Avg PnL: -$200  ❌

Trades con VolTrig=Danger: 15
  - Win Rate: 40%  ⚠️
  - Avg PnL: $50   (edge mínimo)
```

### Después de los Filtros:
```
Total trades: 130 (-20 rechazados)
Win Rate: 60% (+5%)
Avg PnL: $200 (+$50)

Trades sobreextendidos: 0 (eliminados)
Trades con VolTrig=Danger: 15 (tamaño reducido 50%)
  - Riesgo reducido sin perder oportunidad
```

---

## ⚙️ Personalización

### Ajustar el Umbral de Sobreextensión:
```python
# En daily_engine.py, línea ~862
if dist_sma20 > 7.0:  # Cambiar a 5.0 para ser más estricto
```

### Ajustar la Reducción de VolTrig:
```python
# En daily_engine.py, línea ~868
vol_trig_reduction = 0.5  # Cambiar a 0.33 para reducir más (33%)
```

### Ajustar los Umbrales de VolTrig:
```python
# En screener.py, líneas ~134-140
if rvol >= 3.0:      # Cambiar a 2.5 para ser más conservador
    vol_trig = 'Danger'
elif rvol >= 2.0:    # Cambiar a 1.8
    vol_trig = 'Warning'
```

---

## 🔍 Validación

Para validar que los filtros funcionan:

1. **Buscar en logs**:
```bash
grep "REJECTED: Sobreextendido" logs/backtest.log
grep "VolTrig=DANGER" logs/backtest.log
```

2. **Analizar el CSV de resultados**:
```python
import pandas as pd
df = pd.read_csv('outputs/backtests/test_risk_filters.csv')

# Verificar que no hay trades con >7%
extended = df[df['dist_sma20_pct'] > 7]
print(f"Trades sobreextendidos: {len(extended)}")  # Debe ser 0

# Ver distribución de VolTrig
print(df['vol_trig'].value_counts())
```

---

## 🎯 Próximos Pasos

1. ✅ Ejecutar backtest completo 2018-2024
2. ✅ Comparar métricas antes/después de filtros
3. ✅ Ajustar umbrales si es necesario
4. ✅ Validar en live trading

---

## 📝 Notas

- Los filtros NO afectan posiciones ya abiertas (solo aplican al entry)
- Los filtros se evalúan ANTES del risk sizing
- La reducción por VolTrig es MULTIPLICATIVA con otras reducciones (earnings, ADR)
- Las métricas se guardan en cada trade para análisis post-backtest

---

**Última actualización**: 2025-01-05
**Versión**: 1.0
