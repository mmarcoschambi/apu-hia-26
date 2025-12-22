# Pattern Detection System - Guía Completa

**Sistema de Trading Momentum v2 - Pattern Recognition Module**  
**Fecha:** 2025-12-22

---

## 🎯 Resumen Ejecutivo

Sistema avanzado de reconocimiento de patrones técnicos de acumulación institucional. Detecta **4 estructuras principales** + **Pocket Pivots** para entradas anticipadas.

### Patrones Implementados

| Patrón | Características | Confianza Requerida | Rareza |
|--------|----------------|---------------------|--------|
| **High Tight Flag** | Rally 90%+ + consolidación tight | ≥60% | ⭐⭐⭐⭐⭐ Muy raro |
| **Cup & Handle** | U-shape + handle lateral | ≥50% | ⭐⭐⭐⭐ Raro |
| **Flat Base** | Consolidación rectangular tight | ≥50% | ⭐⭐⭐ Común |
| **VCP** | Contracciones progresivas | ≥50% | ⭐⭐⭐⭐ Raro |
| **Pocket Pivot** | Volumen > down days | ≥50% | ⭐⭐ Muy común |

---

## 🏗️ Arquitectura

```
src/indicators/pattern_detection.py
├── PatternDetectionEngine      # Motor principal
│   ├── detect_cup_and_handle()
│   ├── detect_flat_base()
│   ├── detect_high_tight_flag()
│   ├── detect_vcp()
│   └── detect_pocket_pivot()
│
src/core/pattern_screener.py
├── PatternScreener             # Integración con screener
│   ├── scan()                  # Combina base + patterns
│   └── get_pattern_summary()
│
test_pattern_detection.py       # Testing utility
```

---

## 📊 PATRÓN 1: Cup & Handle

### Definición
Corrección en forma de U seguida de consolidación lateral (handle).

### Criterios de Detección

#### Obligatorios:
1. **Cup Depth:** 12-50% (óptimo: 15-25%)
2. **Handle Depth:** ≤15% (óptimo: 8-12%)
3. **Right Peak:** 90-100% del left peak
4. **Duración:** 7-65 semanas para cup

#### Validaciones de Calidad:
- ✅ Volumen seco en handle (<85% promedio)
- ✅ Handle formado en segunda mitad del cup
- ✅ Precio cerca del pivot (<2%)

### Cálculo de Confianza

```python
confidence = 0.0

# Cup depth óptimo (15-25%): +0.25
# Handle depth óptimo (8-12%): +0.25
# Right peak fuerte (>95%): +0.20
# Volumen seco: +0.20
# Cerca del pivot: +0.10

# Total máximo: 1.00 (100%)
# Mínimo requerido: 0.50 (50%)
```

### Ejemplo Visual

```
Price
  ^
  |                    *      <- Right Peak
  |                  /   \
  |    *           /       \  <- Handle
  |   / \         /         *
  |  /   \       /
  | /     \     /
  |/       \   /
  |         \_/               <- Cup Bottom
  |
  +--------------------------> Time
      7-65 weeks
```

### Entry/Stop

- **Pivot:** High del handle
- **Entry:** Pivot + $0.10
- **Stop:** Low del handle
- **Target:** 20-25% típico (o más en breakouts explosivos)

---

## 📊 PATRÓN 2: Flat Base

### Definición
Consolidación lateral muy tight después de un rally previo.

### Criterios de Detección

#### Obligatorios:
1. **Base Depth:** 5-15% (óptimo: 8-12%)
2. **Duración:** 5-15 semanas
3. **Forma:** Rectangular, NO U-shaped
4. **Posición:** Precio dentro del top 15% de la base

#### Validaciones de Calidad:
- ✅ Volumen seco reciente (<85%)
- ✅ Tightness últimas barras (<3% diario)
- ✅ Cerca del high (<5%)

### Cálculo de Confianza

```python
# Depth óptimo (8-12%): +0.30
# Cerca del high (<5%): +0.25
# Volumen seco: +0.20
# Tightness: +0.15
# Duración óptima (7-12w): +0.10
```

### Características

```
Price
  ^
  |  _______________  <- Base High (tight range)
  |  ¯¯¯¯¯¯¯¯¯¯¯¯¯¯¯
  |
  |  5-15 weeks
  |
  +--------------------> Time
```

**Diferencia con Cup:** No tiene U-shape, es más rectangular.

---

## 📊 PATRÓN 3: High Tight Flag

### Definición
Rally explosivo (90-120%+) seguido de consolidación tight. **El más poderoso pero más raro.**

### Criterios de Detección (Mark Minervini)

#### Obligatorios:
1. **Rally:** 90-120%+ en 4-8 semanas
2. **Flag Depth:** 8-30% (óptimo: 10-20%)
3. **MAs:** Precio sobre TODAS las MAs (10, 20, 50)
4. **Volumen:** Expansión masiva en rally

#### Validaciones de Calidad:
- ✅ Volumen contraction en flag (<70%)
- ✅ Flag duration: 3-5 semanas
- ✅ Tightness: <3% diario

### Cálculo de Confianza

```python
# Rally masivo (>120%): +0.35
# Flag depth óptimo: +0.25
# Volume expansion: +0.15
# Volume contraction flag: +0.15
# Tightness: +0.10

# Minimum required: 0.60 (60%) - MÁS ESTRICTO
```

### Ejemplo Visual

```
Price
  ^
  |              ___   <- Flag
  |             /   \
  |            /     *
  |           /
  |          /       <- Rally 90-120%+
  |         /
  |        /
  |       /
  |______/
  |
  +-------------------> Time
      4-8 weeks rally
```

**Característica única:** Rally casi vertical seguido de pausa tight.

---

## 📊 PATRÓN 4: VCP (Volatility Contraction Pattern)

### Definición
Serie de contracciones progresivamente más pequeñas. **"Coiling spring effect".**

### Criterios de Detección (Mark Minervini)

#### Obligatorios:
1. **Contracciones:** Mínimo 2-4 sucesivas
2. **Progresión:** T1 > T2 > T3 (depth y duration)
3. **Última contracción:** <15% (óptimo <8%)
4. **Volumen:** Decreciente en cada contracción

#### Validaciones de Calidad:
- ✅ Depth ratio >2x (primera vs última)
- ✅ Última muy tight (<8%)
- ✅ Volumen contracting progresivamente

### Cálculo de Confianza

```python
# 3+ contracciones: +0.25
# Progresión fuerte (ratio >3): +0.25
# Última muy tight (<8%): +0.20
# Volumen contracting: +0.20
# Cerca del pivot: +0.10
```

### Ejemplo Visual

```
Price
  ^
  |      ___              <- T3 (smallest)
  |     /   \
  |    /     \_____       <- T2 (medium)
  |   /            \
  |  /              \___  <- T1 (largest)
  | /
  |/
  +------------------------> Time
```

**Característica única:** Cada contracción es más pequeña = volatilidad comprimiéndose.

---

## 📊 PATRÓN 5: Pocket Pivot

### Definición
Entrada anticipada DENTRO de una base. No espera breakout.

### Criterios de Detección (Gil Morales & Chris Kacher)

#### Obligatorio:
1. **Volumen:** Día actual > TODOS los down days en últimos 10 días
2. **Día verde:** Close > open O close > prev_close
3. **MAs:** Sobre SMA10 y/o SMA20

#### Validaciones de Calidad:
- ✅ Volume ratio >2x down days
- ✅ Ganancia del día >1-2%
- ✅ Sobre ambas MAs

### Cálculo de Confianza

```python
# Cumple criterio base: +0.30
# Sobre ambas MAs: +0.25
# Volume ratio >2x: +0.20
# Ganancia fuerte (>2%): +0.15
```

### Uso

**Entrada anticipada:** No espera breakout. Se compra EN la base cuando institucionales acumulan.

**Ventajas:**
- ✅ Entry más bajo = mejor R:R
- ✅ Anticipa el breakout
- ✅ Captura inicio del movimiento

**Desventajas:**
- ⚠️ Mayor riesgo (puede fallar)
- ⚠️ Requiere confirmación posterior

---

## 🔧 Uso del Sistema

### 1. Test Individual

```bash
python test_pattern_detection.py --symbol NVDA --start 2023-01-01
```

### 2. Test Múltiple

```bash
python test_pattern_detection.py --all
```

### 3. Integración con Screener

```python
from src.core.pattern_screener import PatternScreener

screener = PatternScreener(enable_patterns=True)

result = screener.scan(
    symbol='NVDA',
    df=historical_data,
    spy_df=spy_data,
    date=today
)

if result and result.get('pattern_detected'):
    pattern_type = result['pattern_type']
    confidence = result['pattern_confidence']
    entry = result['pattern_entry']
    stop = result['pattern_stop']
    
    print(f"Pattern: {pattern_type}")
    print(f"Confidence: {confidence:.1%}")
    print(f"Entry: ${entry:.2f}")
    print(f"Stop: ${stop:.2f}")
```

### 4. Integración con Daily Backtest

```python
# En daily_engine.py, modificar _run_daily_screener()

from src.core.pattern_screener import PatternScreener

# Reemplazar InstitutionalScreener con PatternScreener
self.screener = PatternScreener(
    adr_threshold=min_adr,
    min_price=min_price,
    min_avg_vol=min_avg_volume,
    min_dollar_vol=min_dollar_vol,
    min_rvol=min_rvol,
    enable_patterns=True  # Activar patterns
)
```

---

## 📈 Orden de Prioridad

El sistema escanea en este orden (de más agresivo a más conservador):

1. **High Tight Flag** - Más raro, más poderoso
2. **Flat Base** - Continuación fuerte
3. **Cup & Handle** - Clásico acumulación
4. **VCP** - Compresión de volatilidad
5. **Pocket Pivot** - Puede ocurrir en cualquiera

**Lógica:** Si detecta HTF, es el mejor. Si no, busca Flat Base, etc.

---

## 🎯 Interpretación de Confianza

| Confianza | Significado | Acción |
|-----------|-------------|--------|
| **90-100%** | Setup perfecto | ✅ Entrada agresiva |
| **70-89%** | Setup muy bueno | ✅ Entrada con gestión |
| **50-69%** | Setup aceptable | ⚠️ Entrada conservadora |
| **<50%** | Setup débil | ❌ Esperar confirmación |

---

## 🔍 Validación de Patrones

### Ejemplo: NVDA 2023

```bash
python test_pattern_detection.py --symbol NVDA --start 2023-01-01
```

**Output esperado:**

```
PATTERN #1: HIGH_TIGHT_FLAG
✓ Confidence: 85%
✓ Reasoning: Rally 145%, tight flag, volume expansion

📍 Entry: $256.50
🛑 Stop: $235.20
⚖️  Risk: 8.3% ($21.30)
```

---

## 📚 Referencias Teóricas

### Cup & Handle
- **William O'Neil** - "How to Make Money in Stocks"
- Forma clásica de acumulación institucional
- 7-65 semanas de formación típica

### High Tight Flag
- **Mark Minervini** - "Trade Like a Stock Market Wizard"
- Patrón más poderoso pero más raro
- Rally vertical + consolidación tight

### VCP
- **Mark Minervini** - "Think & Trade Like a Champion"
- Volatilidad comprimiéndose progresivamente
- 2-4+ contracciones típicas

### Pocket Pivot
- **Gil Morales & Chris Kacher** - "Trade Like an O'Neil Disciple"
- Entrada anticipada en bases
- Volumen institucional en días verdes

---

## ⚙️ Configuración

### Parámetros Ajustables

```python
# Cup & Handle
min_weeks=7          # Duración mínima
max_weeks=65         # Duración máxima

# Flat Base
min_weeks=5          # Mínimo 5 semanas
max_weeks=15         # Máximo 15 semanas

# High Tight Flag
min_gain_pct=90      # Rally mínimo 90%
max_weeks=8          # Rally en 4-8 semanas

# VCP
min_contractions=2   # Mínimo 2 contracciones

# Pocket Pivot
lookback_days=10     # Días para comparar volumen
```

---

## 🚀 Próximos Pasos

### Para Activar en Backtest:

1. Reemplazar `InstitutionalScreener` con `PatternScreener`
2. Habilitar `enable_patterns=True`
3. Ajustar filtros de confianza mínima
4. Ejecutar backtest y comparar resultados

### Mejoras Futuras:

- [ ] Integración con charting (matplotlib)
- [ ] Alertas automáticas por pattern
- [ ] Machine Learning para ajustar thresholds
- [ ] Pattern failure analysis
- [ ] Multi-timeframe validation

---

## ✅ Testing Checklist

- [x] Pattern Detection Engine implementado
- [x] 4 patrones principales + Pocket Pivot
- [x] Sistema de confianza
- [x] Integración con screener
- [x] Script de testing
- [ ] Backtest con patterns activados
- [ ] Comparación vs screener simple
- [ ] Validación con datos reales 2023-2024

---

**El sistema está listo para pruebas. Ejecuta `test_pattern_detection.py` para validar!**
