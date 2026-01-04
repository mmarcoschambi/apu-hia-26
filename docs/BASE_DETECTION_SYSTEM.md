# Sistema de Detección de Base y Estructura

**Sistema de Trading Momentum v2**  
**Última actualización:** 2025-12-22

---

## 🏗️ Arquitectura del Sistema

El sistema tiene **dos implementaciones** de detección de base:

### 1. **Sistema Completo (Triad Indicators)** - `src/indicators/triad.py`
Análisis profesional institucional (no usado en backtest actual)

### 2. **Sistema Simplificado (Screener)** - `src/core/screener.py`
Implementación práctica para backtesting diario

---

## 📊 Sistema Completo: Triad Indicators

**Archivo:** `src/indicators/triad.py` - Función `detect_base()`

### Criterios de Detección (Institucionales)

#### ✅ **Criterios OBLIGATORIOS** (3/3 requeridos)

1. **Tendencia Previa (Prior Advance)**
   - **Requisito:** Subida de al menos **30%** antes de la consolidación
   - **Lookback:** 60 días antes de la base
   - **Lógica:** 
     ```python
     prior_low = prior_period['Low'].min()
     base_start_price = df.iloc[-lookback]['Close']
     prior_advance = (base_start_price - prior_low) / prior_low
     has_prior_advance = prior_advance >= 0.30  # 30%
     ```
   - **Razón:** Una base legítima solo se forma después de un rally fuerte

2. **Compresión de Rango (Range Compression)**
   - **Requisito:** Rango de la base ≤ **15%**
   - **Cálculo:**
     ```python
     range_high = recent['High'].max()
     range_low = recent['Low'].min()
     range_pct = (range_high - range_low) / range_low
     is_compressed = range_pct <= 0.15  # 15%
     ```
   - **Razón:** Bases apretadas indican equilibrio supply/demand

3. **Proximidad a Máximos (Near Highs)**
   - **Requisito:** Precio actual dentro de **3%** del high de la base
   - **Cálculo:**
     ```python
     distance_from_high = (range_high - current_price) / current_price
     near_highs = distance_from_high < 0.03  # 3%
     ```
   - **Razón:** Solo operar si el precio está "tight" cerca de resistencia

#### 🎯 **Criterios DESEABLES** (2/3 requeridos para validar)

4. **Volumen Seco en Rojos (Volume Dry Up)**
   - **Requisito:** Volumen en días rojos < **75%** del volumen en verdes
   - **Cálculo:**
     ```python
     avg_red_volume = red_days['Volume'].mean()
     avg_green_volume = green_days['Volume'].mean()
     volume_dry_ratio = avg_red_volume / avg_green_volume
     volume_dried_up = volume_dry_ratio < 0.75
     ```
   - **Razón:** Selling pressure desaparece = institucionales dejan de distribuir

5. **Tightness (Apretamiento)**
   - **Requisito:** Últimos 5 días tienen rango **20% menor** que el promedio
   - **Cálculo:**
     ```python
     last_days_ranges = (last_days['High'] - last_days['Low']) / last_days['Low']
     avg_recent_range = last_days_ranges.mean()
     all_ranges = (recent['High'] - recent['Low']) / recent['Low']
     avg_base_range = all_ranges.mean()
     is_tight = avg_recent_range < avg_base_range * 0.8
     ```
   - **Razón:** Precio "coiling" = energía acumulada para breakout

6. **Moving Averages Alineadas (MAs Aligned)**
   - **Requisito:** EMA10 > EMA20 > SMA50 > SMA200 (con tolerancia 1%)
   - **Cálculo:**
     ```python
     mas_aligned = (
         ema10 >= ema20 * 0.99 and
         ema20 >= sma50 * 0.99 and
         sma50 >= sma200 * 0.99
     )
     price_above_ema20 = current_price >= ema20 * 0.98
     ```
   - **Razón:** Confirma estructura de uptrend en múltiples timeframes

### Decisión Final

```python
mandatory_met = has_prior_advance and is_compressed and near_highs
quality_score = sum([volume_dried_up, is_tight, mas_aligned and price_above_ema20])

is_valid_base = mandatory_met and quality_score >= 2
```

**Una base es válida si cumple los 3 obligatorios + al menos 2 de los 3 deseables.**

---

## 🚀 Sistema Simplificado: Screener

**Archivo:** `src/core/screener.py` - Función `scan()`

Este es el sistema **ACTUALMENTE EN USO** en el backtest diario.

### Lógica de Detección

#### 1. **Filtros Previos (Pre-Base)**

Antes de buscar estructura:
- ✅ Precio > $5
- ✅ ADR(20) > 1.5%
- ✅ Volumen promedio > 300k
- ✅ Dollar volume > $15M
- ✅ RVOL > 1.5x
- ✅ Relative Strength vs SPY > 0

#### 2. **Detección de Tendencia**

```python
is_trending = current['close'] > current['sma_20'] and current['sma_20'] > current['sma_50']
```

**Criterio estricto:** Precio sobre SMA20 Y SMA20 sobre SMA50

#### 3. **Detección de Breakout**

```python
# Base = High de los últimos 20 días (excluyendo hoy)
base_high = hist.iloc[-21:-1]['high'].max()

# Breakout = Precio actual supera base_high
is_breakout = current['close'] > base_high

# Confirmación de volumen
vol_confirm = current['volume'] > current['sma_volume_20']
```

**Concepto:** La "base" se define simplemente como el **máximo de los últimos 20 días**.

#### 4. **Cálculo de Entry y Stop**

```python
return {
    'entry_trigger': current['high'],  # High del día de breakout
    'stop_loss': current['low']        # Low del día de breakout
}
```

---

## 🎯 Diferencias Clave Entre Sistemas

| Aspecto | Sistema Completo (Triad) | Sistema Simplificado (Screener) |
|---------|--------------------------|----------------------------------|
| **Prior Advance** | ✅ Requiere +30% antes | ❌ No verifica |
| **Compresión** | ✅ Max 15% de rango | ❌ No mide |
| **Volumen Seco** | ✅ Analiza red vs green | ❌ Solo confirma > promedio |
| **Tightness** | ✅ Últimos 5 días apretados | ❌ No mide |
| **MAs Alineadas** | ✅ 4 MAs ordenadas | ⚠️ Solo verifica 2 MAs (SMA20/50) |
| **Base Definition** | Max de 20 días consolidación | Max de 20 días (simple) |
| **Uso Actual** | ❌ No usado en backtest | ✅ Usado en backtest diario |

---

## 🔧 Flujo de Ejecución en Backtest Diario

**Archivo:** `src/backtest/daily_engine.py`

### Paso 1: Screener Identifica Candidatos

```python
# En _run_daily_screener()
res = self.screener.scan(symbol, df, self.spy_data, today)
if res:
    res['hist_data'] = df.loc[:today]
    raw_candidates.append(res)
```

### Paso 2: Refinar con Triad Strategy

```python
# Para cada candidato del screener:
base_high = cand['entry_trigger']  # Del screener

# Construir base_data simplificado
base_data = {
    'detected': True,
    'base_high': base_high,
    'base_low': cand['stop_loss'],
    'current_price': current_bar['close']
}

# Strategy valida con filtros adicionales
signal = self.triad_strategy.analyze(
    base_data=base_data,
    avwap_data=avwap_data,
    vwap_data=vwap_data,
    gap_data=gap_data,
    market_context=market_context,
    adr=adr_value
)
```

### Paso 3: Triad Strategy Aplica Filtros Finales

**Archivo:** `src/strategies/triad_protocol.py`

#### Validaciones Adicionales:

1. **Rechazo por Tendencia Weak:**
   ```python
   if trend == 'Weak':
       return Signal(action='NO_SETUP', reasoning="Weak trend")
   ```

2. **Rechazo por RVOL Bajo:**
   ```python
   if rvol < 1.5:
       return Signal(action='NO_SETUP', reasoning="Low RVOL")
   ```

3. **Aprobación Blue Sky Breakout:**
   ```python
   # Si pasa filtros:
   entry = base_high + 0.05  # 5 cents offset
   stop = max(base_low, entry - adr)
   return Signal(
       camino=Camino.BLUE_SKY,
       action='BUY_STOP',
       entry_price=entry,
       stop_loss=stop
   )
   ```

---

## 📈 Ejemplo Real: EGO 2024-04-03

### Datos del Screener:
- **Date:** 2024-04-03
- **Close:** $15.01
- **High:** $15.49 (entry_trigger)
- **Low:** $14.54 (stop_loss)
- **Base High (20d):** ~$15.01
- **Trend:** Weak (precio cerca de SMA20)
- **RVOL:** 1.88x ✅

### Decisión de Strategy:
- ✅ Base detectada (precio rompió high de 20 días)
- ⚠️ Trend = Weak (precio no firmemente sobre SMA20)
- ✅ RVOL > 1.5x (volumen institucional confirmado)
- **Resultado:** ~~RECHAZADO~~ por Weak trend

**NOTA:** En backtests antiguos, Weak trend era filtrado. Pero según tu estrategia actual, **sí se opera en Weak con gestión risk-free** (salidas escalonadas).

---

## 🎓 Filosofía de la Base

### ¿Qué es una "Base"?

Una **base** es un período de consolidación donde:
1. El precio oscila en un rango estrecho
2. Los vendedores se agotan (volumen seco en rojos)
3. Los compradores acumulan posiciones
4. El precio se "comprime" como un resorte
5. Un breakout con volumen libera la energía acumulada

### Metáfora del Lanzador Olímpico

Imagina un lanzador de martillo:
- **Base = Giros previos** (acumulando momentum)
- **Tightness = Últimas vueltas** (máxima velocidad angular)
- **Breakout = Suelta el martillo** (explosión de movimiento)

### ¿Por Qué Funciona?

Los institucionales necesitan:
- **Acumulación:** Comprar sin mover el precio (base tight)
- **Confirmación:** Ver supply agotado (volumen seco)
- **Timing:** Entrar cuando retailers entran (breakout con volumen)

**El retail compra el breakout. Los institucionales compraron la base.**

---

## 🔍 Cómo Mejorar la Detección

### Opción 1: Integrar Sistema Completo

Usar `TriadIndicators.detect_base()` en lugar del screener simple:

```python
# En daily_engine.py
from src.indicators.triad import TriadIndicators

indicators = TriadIndicators()
base_data = indicators.detect_base(df, lookback=20)

if base_data['detected'] and base_data['quality_score'] >= 2:
    # Proceder con entry
```

**Ventaja:** Bases de mayor calidad, menos false breakouts  
**Desventaja:** Menos señales (más estricto)

### Opción 2: Híbrido (Screener + Validación)

Mantener screener simple pero agregar checks de calidad:

```python
# Después del screener
if screener_found_breakout:
    # Validar compresión
    range_pct = (base_high - base_low) / base_low
    if range_pct > 0.20:  # Demasiado amplio
        reject("Base too wide")
    
    # Validar tightness
    last_5_days_range = ...
    if not is_tight:
        reject("Not tight enough")
```

**Ventaja:** Balance entre cantidad y calidad  
**Desventaja:** Complejidad media

### Opción 3: Mantener Simple (Actual)

Confiar en:
- Filtros de volumen (RVOL > 1.5x)
- Filtros de tendencia (SMA20/50)
- Sistema de salidas escalonadas para protección

**Ventaja:** Simple, rápido, probado  
**Desventaja:** Puede entrar en breakouts prematuros

---

## 📊 Métricas de Calidad de Base

Si usas el sistema completo, obtienes estos KPIs:

```python
base_metrics = {
    'prior_advance_pct': 0.45,        # 45% rally previo
    'compression_pct': 0.08,          # 8% range (tight)
    'distance_from_high_pct': 0.015,  # 1.5% del high
    'volume_dry_ratio': 0.60,         # Rojos 60% de verdes
    'is_tight': True,                 # Últimas velas apretadas
    'mas_aligned': True,              # MAs ordenadas
    'quality_score': 3                # 3/3 criterios deseables
}
```

**Score de 3/3 = Base institucional de alta probabilidad**

---

## ⚙️ Configuración Actual

```python
# En daily_backtest_runner.py
parser.add_argument('--min_adr', type=float, default=1.5)
parser.add_argument('--min_rvol', type=float, default=1.5)
parser.add_argument('--min_volume', type=int, default=300000)

# En screener.py
base_high = hist.iloc[-21:-1]['high'].max()  # 20 días lookback
```

**Para cambiar lookback de base:**
```python
# Modificar línea 104 en src/core/screener.py
base_high = hist.iloc[-31:-1]['high'].max()  # 30 días en vez de 20
```

---

## 📚 Referencias

### Archivos Clave:
1. `src/indicators/triad.py` - Sistema completo de detección
2. `src/core/screener.py` - Sistema simplificado (en uso)
3. `src/strategies/triad_protocol.py` - Validación y filtros finales
4. `src/backtest/daily_engine.py` - Integración en backtest

### Conceptos Relacionados:
- **Consolidation Patterns** (Cup & Handle, Flat Base)
- **Volume Price Analysis (VPA)**
- **Institutional Accumulation**
- **Coiling/Compression**

---

## ✅ Conclusión

**Sistema Actual:** Simple pero efectivo
- Usa high de 20 días como base
- Valida con RVOL, tendencia, y volumen
- Protegido por salidas escalonadas (FASE 1→2→3)

**Sistema Completo:** Más sofisticado pero no usado
- 6 criterios de calidad institucional
- Detecta bases tipo Minervini/O'Neil
- Disponible para implementar si se desea mayor precisión

**Recomendación:** El sistema actual funciona bien. Si quieres mejorar, empieza por agregar validación de **compresión** (<15% range) antes de entrar.
