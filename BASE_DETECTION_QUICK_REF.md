# Base Detection - Quick Reference

## 🎯 Sistema Actual (En Uso)

**Archivo:** `src/core/screener.py` línea 104

### Definición Simple:
```python
base_high = hist.iloc[-21:-1]['high'].max()  # Max de últimos 20 días
is_breakout = current['close'] > base_high
```

### Entry y Stop:
```python
entry_trigger = current['high']  # High del día de breakout
stop_loss = current['low']       # Low del día de breakout
```

### Filtros Requeridos:
- ✅ Precio > SMA20 AND SMA20 > SMA50 (Uptrend)
- ✅ Volumen actual > SMA_Volume_20
- ✅ RVOL > 1.5x
- ✅ ADR > 1.5%

---

## 📊 Sistema Completo (Disponible, No Usado)

**Archivo:** `src/indicators/triad.py`

### Criterios Obligatorios (3/3):
1. **Prior Advance:** +30% rally antes de la base
2. **Compression:** Rango de base ≤ 15%
3. **Near Highs:** Precio dentro de 3% del high

### Criterios Deseables (2/3):
4. **Volume Dry:** Rojos < 75% volumen de verdes
5. **Tightness:** Últimos 5 días 20% más apretados
6. **MAs Aligned:** EMA10 > EMA20 > SMA50 > SMA200

### Uso:
```python
from src.indicators.triad import TriadIndicators

indicators = TriadIndicators()
base_data = indicators.detect_base(df, lookback=20)

if base_data['detected']:
    print(f"Quality Score: {base_data['quality_score']}/3")
    print(f"Base Range: {base_data['compression_pct']*100:.1f}%")
```

---

## 🔄 Flujo de Detección Actual

```
1. Screener filtra por:
   - ADR > 1.5%
   - RVOL > 1.5x
   - Volume > 300k
   - Uptrend (SMA20 > SMA50)

2. Screener detecta breakout:
   - Close > Max(High últimos 20 días)
   - Volume > Promedio

3. Strategy valida:
   - Trend != 'Weak' (para Blue Sky)
   - RVOL >= 1.5x
   - Convergencia Base + AVWAP

4. Crea señal:
   - Entry = base_high + $0.05
   - Stop = max(base_low, entry - 1ADR)
```

---

## 📈 Ejemplo Visual

```
Precio ($)
    |
 16 |                           * <- Breakout (Entry)
    |                         /
 15 |----****BASE****--------/  <- Base High ($15.01)
    |   *            *      /
 14 |  *              *    /
    |                 *   /
 13 | ________________*__/______ <- 20 días atrás
    |
    +--------------------------------> Tiempo
```

**Base High** = Máximo de las últimas 20 barras  
**Entry** = Base High + offset  
**Stop** = Low del día de breakout o Entry - 1ADR

---

## 💡 Tips Prácticos

### Para Bases de Mayor Calidad:
```python
# Agregar check de compresión en screener.py
range_pct = (base_high - base_low) / base_low
if range_pct > 0.20:  # 20% max
    return None, "Base too wide"
```

### Para Bases Más Tight:
```python
# Agregar check de tightness
last_5_ranges = recent.tail(5)
avg_recent = ((last_5_ranges['high'] - last_5_ranges['low']) / last_5_ranges['low']).mean()
avg_base = ((recent_20['high'] - recent_20['low']) / recent_20['low']).mean()

if avg_recent >= avg_base * 0.8:
    return None, "Not tight enough"
```

### Para Mejor Volumen:
```python
# Verificar volumen seco en rojos
red_days = recent_20[recent_20['close'] < recent_20['open']]
green_days = recent_20[recent_20['close'] >= recent_20['open']]

if red_days['volume'].mean() > green_days['volume'].mean() * 0.75:
    return None, "Volume not dried up"
```

---

## 🎓 Conceptos Clave

### ¿Qué es una Base?
Consolidación donde:
- Supply se agota (volumen seco)
- Precio se comprime (rango estrecho)
- Institucionales acumulan
- Breakout con volumen libera energía

### Señales de Calidad:
- ✅ Rango < 15%
- ✅ Volumen decreciente en correcciones
- ✅ Últimas velas tight (coiling)
- ✅ MAs alineadas en orden

### Red Flags:
- ❌ Rango > 20% (demasiado loose)
- ❌ Volumen alto en rojos (distribución)
- ❌ MAs cruzadas (sin tendencia clara)
- ❌ Precio lejos del high (>5%)

---

## 🛠️ Modificar Lookback

**Actual:** 20 días

**Para cambiar:**
```python
# src/core/screener.py línea 104
base_high = hist.iloc[-31:-1]['high'].max()  # 30 días
base_high = hist.iloc[-11:-1]['high'].max()  # 10 días
```

**Recomendación:** 20 días es óptimo para swing trading mid-cap

---

## 📊 Métricas de Calidad

Si implementas sistema completo:

| Metric | Excellent | Good | Poor |
|--------|-----------|------|------|
| Prior Advance | >50% | 30-50% | <30% |
| Compression | <10% | 10-15% | >15% |
| Volume Dry Ratio | <0.60 | 0.60-0.75 | >0.75 |
| Distance from High | <1% | 1-3% | >3% |
| Quality Score | 3/3 | 2/3 | 1/3 or less |

---

## ⚡ Quick Commands

```bash
# Ver código de base detection completa
vim src/indicators/triad.py +18

# Ver código de screener simple (actual)
vim src/core/screener.py +97

# Ver integración en strategy
vim src/strategies/triad_protocol.py +104
```

---

## 📝 Archivos Relacionados

- `BASE_DETECTION_SYSTEM.md` - Documentación completa
- `src/indicators/triad.py` - Sistema institucional completo
- `src/core/screener.py` - Sistema simplificado en uso
- `src/strategies/triad_protocol.py` - Validación y filtros
