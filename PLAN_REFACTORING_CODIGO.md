# 🏗️ PLAN DE REFACTORING - CÓDIGO DUPLICADO

## 📊 ANÁLISIS ACTUAL (Ene 26, 2025)

### **Estado del código:**

```
📏 THOR Engine:     929 líneas
📏 Advanced Engine: 2,283 líneas
📏 App.py:          ~1,500 líneas (estimado)
📏 Tests:           ~800 líneas
─────────────────────────────────────
📏 TOTAL:           ~5,500 líneas
```

### **Duplicación detectada:**

| Cálculo/Lógica | THOR bloques | Advanced bloques | Severidad |
|----------------|--------------|------------------|-----------|
| **SMA calculation** | 6 | 9 | 🔴 CRÍTICO |
| **RVOL** | 6 | 17 | 🔴 CRÍTICO |
| **ADR** | 5 | 21 | 🔴 CRÍTICO |
| **Consolidation** | 4 | 10 | 🔴 CRÍTICO |
| **Filters** | 6 | 18 | 🔴 CRÍTICO |
| **Liquidity** | 2 | 6 | 🟡 MEDIO |
| **Distance to SMA** | 1 | 3 | 🟡 MEDIO |
| **Bollinger Bands** | 1 | 2 | 🟢 BAJO |

**Potencial ahorro:** ~1,000-1,500 líneas (20-30% del código)

---

## 🎯 ESTRATEGIA DE REFACTORING

### **Fase 1: Indicators Library (Crítico)** ⭐

**Crear:** `src/indicators/technical.py`

**Consolidar cálculos técnicos:**

```python
# src/indicators/technical.py

import pandas as pd
import numpy as np

class TechnicalIndicators:
    """
    Biblioteca centralizada de indicadores técnicos
    Compatible con pandas y numpy
    """
    
    @staticmethod
    def rvol(volume: pd.Series, period: int = 20) -> pd.Series:
        """Relative Volume"""
        avg_vol = volume.rolling(period).mean()
        return volume / avg_vol
    
    @staticmethod
    def adr(high: pd.Series, low: pd.Series, close: pd.Series, 
            period: int = 20) -> pd.Series:
        """Average Daily Range %"""
        daily_range = (high - low) / close
        return daily_range.rolling(period).mean() * 100
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return data.rolling(period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def distance_to_sma(price: pd.Series, sma: pd.Series) -> pd.Series:
        """Distance from price to SMA in %"""
        return ((price - sma) / sma) * 100
    
    @staticmethod
    def bollinger_bands(close: pd.Series, period: int = 20, 
                       std_dev: float = 2.0) -> tuple:
        """Bollinger Bands (upper, middle, lower)"""
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
```

**Uso en engines:**

```python
# THOR Engine
from src.indicators.technical import TechnicalIndicators as TI

# Antes (8 líneas):
avg_volume = data['volume'].rolling(20).mean()
rvol = data['volume'] / avg_volume
daily_range = (data['high'] - data['low']) / data['close']
adr = daily_range.rolling(20).mean() * 100
sma20 = data['close'].rolling(20).mean()
dist_sma20 = ((data['close'] - sma20) / sma20) * 100

# Después (3 líneas):
rvol = TI.rvol(data['volume'])
adr = TI.adr(data['high'], data['low'], data['close'])
dist_sma20 = TI.distance_to_sma(data['close'], TI.sma(data['close'], 20))
```

**Ahorro:** ~100-150 líneas por engine = **300 líneas totales**

---

### **Fase 2: Filter Engine (Crítico)** ⭐

**Crear:** `src/filters/liquidity.py`

**Consolidar filtros de liquidez:**

```python
# src/filters/liquidity.py

class LiquidityFilters:
    """Filtros de liquidez reutilizables"""
    
    @staticmethod
    def apply_rvol_filter(entries: pd.Series, rvol: pd.Series, 
                          min_rvol: float = 2.0) -> pd.Series:
        """Filtra por RVOL mínimo"""
        return entries & (rvol >= min_rvol)
    
    @staticmethod
    def apply_adr_filter(entries: pd.Series, adr: pd.Series,
                         min_adr: float = 2.5) -> pd.Series:
        """Filtra por ADR mínimo"""
        return entries & (adr >= min_adr)
    
    @staticmethod
    def apply_volume_filter(entries: pd.Series, volume: pd.Series,
                           min_vol: int = 300_000) -> pd.Series:
        """Filtra por volumen mínimo"""
        return entries & (volume >= min_vol)
    
    @staticmethod
    def apply_dollar_volume_filter(entries: pd.Series, volume: pd.Series,
                                   price: pd.Series, 
                                   min_dollar_vol: int = 5_000_000) -> pd.Series:
        """Filtra por dollar volume mínimo"""
        dollar_vol = volume * price
        return entries & (dollar_vol >= min_dollar_vol)
    
    @staticmethod
    def apply_all_liquidity_filters(entries: pd.Series, 
                                    rvol: pd.Series, adr: pd.Series,
                                    volume: pd.Series, price: pd.Series,
                                    min_rvol: float = 2.0, 
                                    min_adr: float = 2.5,
                                    min_vol: int = 300_000,
                                    min_dollar_vol: int = 5_000_000) -> pd.Series:
        """Aplica todos los filtros de liquidez"""
        filtered = entries.copy()
        filtered = LiquidityFilters.apply_rvol_filter(filtered, rvol, min_rvol)
        filtered = LiquidityFilters.apply_adr_filter(filtered, adr, min_adr)
        filtered = LiquidityFilters.apply_volume_filter(filtered, volume, min_vol)
        filtered = LiquidityFilters.apply_dollar_volume_filter(
            filtered, volume, price, min_dollar_vol
        )
        return filtered
```

**Uso:**

```python
# Antes (15 líneas):
entries = base_entries.copy()
entries &= (rvol >= params['min_rvol'])
entries &= (adr >= params['min_adr'])
entries &= (volume >= 300_000)
dollar_vol = volume * price
entries &= (dollar_vol >= 5_000_000)

# Después (1 línea):
from src.filters.liquidity import LiquidityFilters as LF
entries = LF.apply_all_liquidity_filters(
    base_entries, rvol, adr, volume, price,
    min_rvol=params['min_rvol'], min_adr=params['min_adr']
)
```

**Ahorro:** ~200-250 líneas totales

---

### **Fase 3: Position Sizing (Medio)** 

**Crear:** `src/risk/position_sizing.py`

```python
# src/risk/position_sizing.py

class PositionSizing:
    """Cálculo centralizado de position sizing"""
    
    @staticmethod
    def fixed_dollar_risk(risk_dollars: float, atr: float, 
                         stop_pct: float = 0.05) -> int:
        """Fixed dollar risk per trade"""
        stop_amount = atr * stop_pct
        shares = int(risk_dollars / stop_amount)
        return max(shares, 1)
    
    @staticmethod
    def percent_risk(capital: float, risk_pct: float, 
                    atr: float, stop_pct: float = 0.05) -> int:
        """Percentage risk per trade"""
        risk_dollars = capital * risk_pct
        return PositionSizing.fixed_dollar_risk(risk_dollars, atr, stop_pct)
    
    @staticmethod
    def apply_volatility_scaling(base_shares: int, rvol: float,
                                 danger_threshold: float = 3.0,
                                 warning_threshold: float = 2.0) -> int:
        """Scale position by volatility"""
        if rvol >= danger_threshold:
            return int(base_shares * 0.30)  # 30% size
        elif rvol >= warning_threshold:
            return int(base_shares * 0.65)  # 65% size
        else:
            return base_shares  # 100% size
```

**Ahorro:** ~100-150 líneas totales

---

### **Fase 4: Market Regime (Medio)**

**Crear:** `src/filters/market_regime.py`

```python
# src/filters/market_regime.py

class MarketRegimeFilters:
    """Filtros de régimen de mercado"""
    
    @staticmethod
    def spy_above_sma50(spy_close: pd.Series, 
                       spy_sma50: pd.Series) -> pd.Series:
        """SPY > SMA50 filter"""
        return spy_close > spy_sma50
    
    @staticmethod
    def vix_below_threshold(vix_close: pd.Series, 
                           threshold: float = 25.0) -> pd.Series:
        """VIX < threshold filter"""
        return vix_close < threshold
    
    @staticmethod
    def bullish_regime(spy_close: pd.Series, spy_sma50: pd.Series,
                      vix_close: pd.Series, vix_threshold: float = 25.0) -> pd.Series:
        """Combined bullish market regime"""
        spy_ok = MarketRegimeFilters.spy_above_sma50(spy_close, spy_sma50)
        vix_ok = MarketRegimeFilters.vix_below_threshold(vix_close, vix_threshold)
        return spy_ok & vix_ok
```

**Ahorro:** ~80-100 líneas totales

---

## 📁 ESTRUCTURA PROPUESTA

```
src/
├── indicators/
│   ├── __init__.py
│   ├── technical.py           ⭐ Fase 1 (indicadores)
│   └── consolidation.py       (opcional)
│
├── filters/
│   ├── __init__.py
│   ├── liquidity.py           ⭐ Fase 2 (liquidez)
│   ├── market_regime.py       ⭐ Fase 4 (régimen)
│   └── quality.py             (opcional)
│
├── risk/
│   ├── __init__.py
│   └── position_sizing.py     ⭐ Fase 3 (sizing)
│
└── backtest/
    ├── optimization_engine_thor.py      (simplificado)
    └── vectorbt_engine_advanced.py      (simplificado)
```

---

## 💰 BENEFICIOS ESTIMADOS

### **Reducción de código:**

| Fase | Líneas eliminadas | % del total |
|------|-------------------|-------------|
| Fase 1: Indicators | 300 | 5.5% |
| Fase 2: Filters | 250 | 4.5% |
| Fase 3: Position Sizing | 150 | 2.7% |
| Fase 4: Market Regime | 100 | 1.8% |
| **TOTAL** | **800** | **14.5%** |

### **Beneficios adicionales:**

✅ **Mantenibilidad:** Fix un bug en 1 lugar vs 3+ lugares  
✅ **Testing:** Test indicadores en aislamiento  
✅ **Reutilización:** Usar en otros scripts (live scanner, etc)  
✅ **Claridad:** Engines más cortos y legibles  
✅ **Performance:** Cache de indicadores más eficiente  

---

## ⚡ PLAN DE IMPLEMENTACIÓN

### **Prioridad 1: Indicators** (2-3 horas) 🔴

**Impacto:** ALTO - Afecta THOR, Advanced, App, Tests

```bash
# 1. Crear biblioteca
mkdir -p src/indicators
touch src/indicators/__init__.py

# 2. Implementar technical.py
# → RVOL, ADR, SMA, EMA, Distance, Bollinger

# 3. Actualizar THOR
# → Reemplazar cálculos inline con TI.method()

# 4. Actualizar Advanced
# → Reemplazar cálculos inline con TI.method()

# 5. Test
python3 test_convergence_quick.py
python3 -m pytest tests/test_indicators.py
```

**Archivos a modificar:**
- `src/backtest/optimization_engine_thor.py`
- `src/backtest/vectorbt_engine_advanced.py`
- `validation_baseline.py` (si usa cálculos directos)

**Ahorro:** ~300 líneas

---

### **Prioridad 2: Filters** (2-3 horas) 🔴

**Impacto:** ALTO - Simplifica lógica de filtrado

```bash
# 1. Crear biblioteca
mkdir -p src/filters
touch src/filters/__init__.py

# 2. Implementar liquidity.py
# → RVOL filter, ADR filter, Volume, Dollar Volume

# 3. Implementar market_regime.py
# → SPY > SMA50, VIX < threshold, Bullish regime

# 4. Actualizar engines
# → Reemplazar bloques de filtros con LF.apply_all()

# 5. Test
python3 test_convergence_quick.py
```

**Ahorro:** ~350 líneas

---

### **Prioridad 3: Position Sizing** (1-2 horas) 🟡

**Impacto:** MEDIO - Menos duplicación pero importante

```bash
# 1. Crear biblioteca
mkdir -p src/risk
touch src/risk/__init__.py

# 2. Implementar position_sizing.py
# → Fixed dollar, Percent risk, Volatility scaling

# 3. Actualizar engines

# 4. Test
python3 test_convergence_quick.py
```

**Ahorro:** ~150 líneas

---

### **Prioridad 4: Utilities** (1 hora) 🟢

**Crear:** `src/utils/data.py`, `src/utils/metrics.py`

**Consolidar:**
- Data loading helpers
- Performance metrics calculations
- Validation helpers

**Ahorro:** ~100 líneas

---

## 📊 ANTES vs DESPUÉS

### **ANTES (Código duplicado):**

```python
# THOR Engine (líneas 150-180)
avg_volume = data['volume'].rolling(20).mean()
rvol = data['volume'] / avg_volume

daily_range = (data['high'] - data['low']) / data['close']
adr = daily_range.rolling(20).mean() * 100

sma20 = data['close'].rolling(20).mean()
dist_sma20 = ((data['close'] - sma20) / sma20) * 100

# Liquidity filters
filters = base_entries.copy()
filters &= (rvol >= params['min_rvol'])
filters &= (adr >= params['min_adr'])
filters &= (data['volume'] >= 300_000)
dollar_vol = data['volume'] * data['close']
filters &= (dollar_vol >= 5_000_000)

# Position sizing
if rvol >= 3.0:
    size_pct = 0.30
elif rvol >= 2.0:
    size_pct = 0.65
else:
    size_pct = 1.0
shares = int(base_shares * size_pct)

# 25+ líneas
```

```python
# Advanced Engine (líneas 450-490)
# MISMO CÓDIGO REPETIDO (con sintaxis VectorBT)
avg_volume = self.volume.rolling(20).mean()
rvol = self.volume / avg_volume

daily_range = (self.high - self.low) / self.close
adr = daily_range.rolling(20).mean() * 100

# ... EXACTAMENTE LO MISMO ...
# 25+ líneas más
```

**Total duplicado:** ~50 líneas

---

### **DESPUÉS (Refactorizado):**

```python
# THOR Engine (líneas 150-160)
from src.indicators.technical import TechnicalIndicators as TI
from src.filters.liquidity import LiquidityFilters as LF
from src.risk.position_sizing import PositionSizing as PS

# Indicadores (3 líneas)
rvol = TI.rvol(data['volume'])
adr = TI.adr(data['high'], data['low'], data['close'])
dist_sma20 = TI.distance_to_sma(data['close'], TI.sma(data['close'], 20))

# Filtros (1 línea)
filtered = LF.apply_all_liquidity_filters(
    base_entries, rvol, adr, data['volume'], data['close'],
    min_rvol=params['min_rvol'], min_adr=params['min_adr']
)

# Position sizing (1 línea)
shares = PS.apply_volatility_scaling(base_shares, rvol)

# 10 líneas totales
```

```python
# Advanced Engine (líneas 450-460)
# MISMO CÓDIGO - solo imports
from src.indicators.technical import TI
from src.filters.liquidity import LF
from src.risk.position_sizing import PS

# Resto idéntico
rvol = TI.rvol(self.volume)
# ...

# 10 líneas totales
```

**Total refactorizado:** ~20 líneas (vs 50 antes)

**Ahorro:** 60% del código + lógica centralizada

---

## 🚀 TIMELINE IMPLEMENTACIÓN

### **Opción A: Todo de una vez (Full Day)**

```
Fase 1: Indicators       → 3 horas
Fase 2: Filters          → 3 horas
Fase 3: Position Sizing  → 2 horas
Fase 4: Utilities        → 1 hora
Testing completo         → 1 hora
────────────────────────────────────
TOTAL:                     10 horas
```

### **Opción B: Incremental (1 fase/día)**

```
Día 1: Indicators        → 3h + test convergence
Día 2: Filters           → 3h + test convergence
Día 3: Position Sizing   → 2h + test convergence
Día 4: Walk forward      → Validar todo
────────────────────────────────────
TOTAL:                     4 días
```

**Recomendación:** Opción B (más seguro)

---

## ✅ CHECKLIST DE REFACTORING

### **Por cada fase:**

```
□ Crear nueva biblioteca/módulo
□ Implementar funciones con tests unitarios
□ Actualizar THOR Engine
□ Actualizar Advanced Engine
□ Correr test_convergence_quick.py
□ Verificar métricas idénticas (Sharpe, Trades, Win Rate)
□ Commit changes
□ Actualizar documentación
```

### **Criterio de éxito:**

```
✅ test_convergence_quick.py pasa
✅ Sharpe diff < 0.05
✅ Trades diff = 0
✅ Win Rate diff < 2%
✅ Max DD diff < 0.1%
```

---

## 🎯 MÓDULOS A CREAR

### **Alta prioridad (hacer primero):**

```python
src/indicators/technical.py         # RVOL, ADR, SMA, EMA, RSI, BB
src/filters/liquidity.py            # Volume, RVOL, ADR filters
src/risk/position_sizing.py         # Fixed $, % risk, scaling
```

### **Media prioridad (siguiente):**

```python
src/filters/quality.py              # Consolidation, breakout, trend
src/filters/market_regime.py        # SPY, VIX, regime detection
src/utils/data.py                   # Data loading, validation
```

### **Baja prioridad (opcional):**

```python
src/utils/metrics.py                # Performance metrics
src/utils/reporting.py              # Report generation
src/validation/convergence.py       # Convergence testing
```

---

## 💡 EJEMPLO COMPLETO

### **Implementación Gap Filter (con refactoring):**

```python
# 1. Agregar a src/indicators/technical.py
@staticmethod
def gap_percent(open_price: pd.Series, prev_close: pd.Series) -> pd.Series:
    """Calculate gap % from previous close"""
    return ((open_price - prev_close) / prev_close) * 100

# 2. Crear filtro en src/filters/quality.py
@staticmethod
def apply_gap_filter(entries: pd.Series, gap: pd.Series,
                     min_gap: float = 2.0) -> pd.Series:
    """Filter for minimum gap up %"""
    return entries & (gap >= min_gap)

# 3. Usar en THOR (2 líneas)
from src.indicators.technical import TI
from src.filters.quality import QualityFilters as QF

gap = TI.gap_percent(data['open'], data['close'].shift(1))
if params['use_gap_filter']:
    entries = QF.apply_gap_filter(entries, gap, params['min_gap_pct'])

# 4. Usar en Advanced (2 líneas - IDÉNTICO)
gap = TI.gap_percent(self.open, self.close.shift(1))
if self.use_gap_filter:
    entries = QF.apply_gap_filter(entries, gap, self.min_gap_pct)
```

**Beneficio:** Lógica idéntica garantizada, fácil de mantener

---

## 🎯 PRÓXIMOS PASOS RECOMENDADOS

### **Paso 1: Análisis detallado (30 min)**

```bash
# Generar reporte completo de duplicación
python3 scripts/analyze_code_duplication.py > duplication_report.txt
```

### **Paso 2: Implementar Fase 1 - Indicators (3 horas)**

```bash
# Crear módulo
mkdir -p src/indicators
# Implementar technical.py
# Actualizar engines
# Test convergence
```

### **Paso 3: Validar (30 min)**

```bash
python3 test_convergence_quick.py
python3 validation_baseline.py --phase 1
```

### **Paso 4: Repeat para Fases 2-4**

---

## ❓ PREGUNTAS PARA DECIDIR

**¿Empiezo el refactoring?**

**Opción A:** ✅ SÍ - Haz Fase 1 hoy (3h)
- Beneficio inmediato
- Reduce 300 líneas
- Mejora mantenibilidad

**Opción B:** ⏸️ DESPUÉS - Post walk forward
- Finish walk forward primero
- Implementar params production
- Luego refactorizar

**Opción C:** 📅 INCREMENTAL - 1 fase/semana
- Bajo riesgo
- No bloquea otros trabajos
- Progreso constante

---

## 📚 DOCUMENTACIÓN A CREAR

Si procedes con refactoring:

```
✅ REFACTORING_GUIDE.md          (esta guía)
✅ src/indicators/README.md      (uso de indicators)
✅ src/filters/README.md         (uso de filters)
✅ tests/test_indicators.py      (unit tests)
✅ tests/test_filters.py         (unit tests)
```

---

## ✅ RESUMEN EJECUTIVO

| Aspecto | Estado | Acción |
|---------|--------|--------|
| Duplicación actual | 🔴 14.5% código duplicado | Refactorizar |
| Esfuerzo estimado | ⏱️ 10 horas / 4 días | Planificar |
| Ahorro líneas | 💰 800 líneas (-14.5%) | Significativo |
| Riesgo | ⚠️ Medio (afecta 2 engines) | Test exhaustivo |
| Beneficio | ✅ ALTO (mantenibilidad++) | Vale la pena |

---

**¿PROCEDER CON REFACTORING?** Tu decides:
1. Ahora (3h Fase 1)
2. Después del walk forward
3. Incremental (1 fase/semana)

**Mi recomendación:** Opción 2 o 3 (no bloquear walk forward)

