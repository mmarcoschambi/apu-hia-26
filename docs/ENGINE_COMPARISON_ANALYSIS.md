# 🔬 THOR vs Advanced Engine: Análisis de Convergencia

## 📊 Resultados del Test (5 tickers, 2023)

| Métrica | THOR | Advanced | Divergencia | Normalizado | Estado |
|---------|------|----------|-------------|-------------|---------|
| Sharpe     | 0.587 | -1.510 | 2.097 | **351%** | ❌ CRÍTICO |
| Return     | 2.56% | -0.69% | 3.24% | **91%** | ❌ CRÍTICO |
| Trades     | 9 | 8 | 1 | **10%** | ✅ OK |
| Max DD     | 2.78% | 0.75% | 3.53% | **93%** | ❌ CRÍTICO |
| Win Rate   | 66.7% | 12.5% | 54.2% | N/A | ❌ CRÍTICO |

**Veredicto:** 🔴 **NO transferir parámetros directamente** - POOR CONVERGENCE

---

## 🚧 Diferencias Críticas Identificadas

### 1. ENTRY SIGNAL LOGIC (ALTO IMPACTO)

#### THOR (optimization_engine_thor.py:428-550)
```python
# Líneas 475-504: FILTROS BASE
liquidity_filters = (
    (self.rvol >= min_rvol) &
    (self.adr >= min_adr) &
    (self.vol_sma20 >= min_volume) &
    (avg_dollar_volume >= min_dollar_volume)
)

trend_filters = (
    (self.dist_sma20 <= max_dist_sma20)  # Solo controla distancia
)

base_filters = liquidity_filters & trend_filters

# Líneas 526-549: ENTRY POR SIGNAL TYPE
if signal_type == 'breakout':
    entries = base_filters & consolidation_quality & (
        self.close > self.high.shift().rolling(20).max()
    )
```

**Características:**
- ✅ Entrada vectorizada (pura y rápida)
- ✅ 3 filtros principales: liquidez + tendencia + consolidación
- ✅ Sin filtros dearnings, sector, RS
- ❌ Menos selectivo (más entradas)

#### Advanced (vectorbt_engine_advanced.py:12738-12760)
```python
# Líneas 12712-12736: FILTRO ENTRADA (ticker por ticker)

# 3. Consolidation Check
if consol_days < self.min_consolidation_days:
    continue

# 4. Earnings Check
days_to_earnings = -1
if ticker in earnings_cache:
    # Check earnings proximity
    if 0 <= days_to < self.earnings_days:
        continue

# Sector Strength Check
if self.require_positive_rs and sector_strength <= 0:
    continue
```

**Características:**
- ⚠️ Entrada loop ticker-by-ticker (más lento pero detallado)
- ⚠️ Múltiples filtros adicionales:
  - 🔸 Calendar de earnings
  - 🔸 Sector strength (RS sectorial)
  - 🔸 Sector concentration (max 50% por sector)
  - 🔸 Max 3 entries por día
- ✅ Más selectivo (menos entradas de mejor calidad)

**Impacto en divergencia:** 🔴 CRÍTICO
- THOR: 9 trades
- Advanced: 8 trades (similar)
- Pero calidad DIFERENTE: THOR 66.7% win rate vs Advanced 12.5%

---

### 2. POSITION SIZING (MEDIO IMPACTO)

#### THOR (optimization_engine_thor.py:552-574)
```python
# Líneas 556-573
stop_distance = self.close * (max_stop_pct / 100)
shares_per_trade = (risk_dollars / stop_distance)

# Ajuste RVOL (3 niveles)
position_size_pct = pd.DataFrame(1.0, index=self.close.index, columns=self.close.columns)
position_size_pct = position_size_pct.where(self.rvol < rvol_warning, rvol_warning_size)
position_size_pct = position_size_pct.where(self.rvol < rvol_danger, rvol_danger_size)

position_value = (position_value_base * position_size_pct)
```

**Lógica:**
- Fixed dollar risk → shares
- Reduce por RVOL (Warning: 65%, Danger: 30%)

#### Advanced (vectorbt_engine_advanced.py:1072-1157)
```python
# Líneas 1072-1157
risk_amt = self.risk_dollars
if not mkt_bullish: risk_amt *= 0.5  # Half risk en mal mercado

# RVOL Adjustment
reduction = 1.0
if rvol >= self.rvol_danger: reduction = self.rvol_danger_size
elif rvol >= self.rvol_warning: reduction = self.rvol_warning_size

shares = int(shares * reduction)

# ADR Adjustment (adicional)
cost = shares * entry_price
# Límite de exposición
if cost > (cash * current_max_exposure):
    shares = int((cash * current_max_exposure) / entry_price)
```

**Lógica:**
- Fixed dollar risk → shares
- Reduce por RVOL (Warning: 60%, Danger: 25%)
- ❌ **ADICIONAL:** Half risk if !mkt_bullish
- ❌ **ADICIONAL:** Max exposure limit (25% default, 50% growth mode)

**Diferencia clave:**
Parámetro | THOR | Advanced
----------|------|----------
rvol_warning_size | 0.65 | 0.60
rvol_danger_size  | 0.30 | 0.25
max_exposure_pct  | 0.25 | 0.25-0.50 (dynamic)
Regime adjustment | NO  | YES (half risk)

**Impacto en divergencia:** 🟡 MEDIO
- Size reduction más agresiva en Advanced
- Advanced ajusta por régimen de mercado

---

### 3. EXIT LOGIC (BAJO IMPACTO - similar pero no igual)

#### THOR (optimization_engine_thor.py:584-814)
```python
# Líneas 654-714: 3-PHASE EXITS
if use_phases:
    # Phase 1: 50% @ TP1 or stop
    exits_tp1 = (
        ((valid_close >= tp1_target) | (valid_close < stop_target)) &
        position_active
    )
    pf1 = vbt.Portfolio.from_signals(..., size=position_value * 0.5, init_cash=self.initial_capital * 0.5)

    # Phase 2: 30% @ TP2 or stop
    exits_tp2 = (
        ((valid_close >= tp2_target) | (valid_close < stop_target)) &
        position_active
    )
    pf2 = vbt.Portfolio.from_signals(..., size=position_value * 0.3, init_cash=self.initial_capital * 0.3)

    # Phase 3: 20% Runner
    exits_runner = (
        ((self.ema8 < self.ema21) | (valid_close < stop_target)) &
        position_active
    )
    pf3 = vbt.Portfolio.from_signals(..., size=position_value * 0.2, init_cash=self.initial_capital * 0.2)
```

**Características:**
- ✅ 3 portfolio instances simuladas
- ✅ TP1: 50% @ 1.5R or stop
- ✅ TP2: 30% @ 3R or stop
- ✅ Runner: 20% con EMA8 crossover EMA21
- ❌ NO trailing stop a break-even

#### Advanced (vectorbt_engine_advanced.py:879-979)
```python
# Líneas 879-902: TRAILING STOP A BREAK-EVEN
if self.use_trailing_stop:
    unrealized_pnl = (current_price - pos['entry_price']) / pos['risk_per_share']
    be_trailing_done = pos.get('be_trailing_done', False)
    be_threshold = self.be_trailing_threshold  # Default: 0.8

    if not be_trailing_done and unrealized_pnl >= be_threshold and not pos['tp1_done']:
        pos['stop_price'] = pos['entry_price']  # Move to BE
        pos['be_trailing_done'] = True

# Líneas 908-979: 3-PHASE WITH TRAILING
if ticker_low <= stop_price:
    exit_signal = True
    exit_price = stop_price
    # Check BE
    if stop_price >= pos['entry_price']:
        exit_reason = 'STOP_BE'  # Break-even exit
    else:
        exit_reason = 'STOP'
```

**Características:**
- ✅ 3-phase IDENTICO (50%/30%/20%)
- ✅ TP1: 1.5R, TP2: 3R
- ✅ Runner: EMA8 cross EMA21
- ✅ **ADICIONAL:** Trailing stop a break-even @ 0.8R
- ✅ Clasifica stops como 'STOP_BE' vs 'STOP'

**Diferencia clave:**
Feature | THOR | Advanced
--------|------|----------
Trailing BE | NO  | YES (0.8R default)
Stop classification | Simple | BE vs Regular
Simulation | Vectorized (vbt) | Loop manual

**Impacto en divergencia:** 🟢 BAJO
- Same core logic
- Advanced exits earlier at break-even (win rate más bajo PERO less painful losses)

---

### 4. MARKET REGIME FILTER (ALTO IMPACTO)

#### THOR (optimization_engine_thor.py:509-520)
```python
# Líneas 509-520: SIMPLE FILTER
if require_bullish_spy:
    base_filters &= (self.spy_close > self.spy_ema20)

if require_sma_trend:
    base_filters &= (self.vix_close <= max_vix)

if require_positive_rs:
    base_filters &= (self.rs_21d > 0)
```

**Características:**
- ❓ Opcional (default: OFF)
- 📏 Umbrales simples (VIX < 40, SPY > EMA20)
- ❓ No usa clasificación de régimen

#### Advanced (vectorbt_engine_advanced.py:14-96, 174-305)
```python
# Líneas 32-75: DYNAMIC THRESHOLDS
def get_dynamic_thresholds(current_vix: float):
    if current_vix < 20:
        return {'regime_name': 'BULL', 'min_rvol': 1.5, ...}
    elif current_vix < 30:
        return {'regime_name': 'NEUTRAL', 'min_rvol': 1.5, ...}
    else:
        return {'regime_name': 'BEAR', 'min_rvol': 1.8, ...}

# Líneas 142-305: MARKET REGIME CLASSIFIER
class MarketRegimeClassifier:
    """4-Stage classification based on SPY + VIX"""
    # Stage 1: Bull market (SPY > SMA200 & VIX < 20)
    # Stage 2: Accumulation
    # Stage 3: Distribution
    # Stage 4: Bear market

# Líneas 14128-14762: ADAPTIVE FILTER ENGINE
if self.use_adaptive_filtering:
    # TIER 1: Market Safety Filter
    should_trade = should_trade_long(spy_price, spy_sma50, vix_val, 35.0)
    if not should_trade:
        # Block ALL entries
    # TIER 2: Dynamic Quality (thresholds by regime)
    # TIER 3: Optional filters
```

**Características:**
- ✅ AdaptiveFilterEngine con 3 TIERs
- ✅ Dynamic thresholds por VIX (min_rvol, min_adr, max_dist cambian)
- ✅ MarketRegimeClassifier (4 stages)
- ✅ Block trades en Stage 3/4, reduce risk

**Impacto en divergencia:** 🔴 CRÍTICO
- Advanced usa thresholds DINÁMICOS (no estáticos)
- Bloquea completely en bear market
- THOR usa same thresholds siempre

---

## ✅ Parámetros Transferibles (Safe)

Estos parámetros tienen MISMA lógica en ambos motores:

| Categoría | Parámetro | THOR Line | Advanced Line | Status |
|-----------|-----------|-----------|---------------|--------|
| **Liquidity** | `min_rvol` | 442 | 139 | ✅ Transferible |
| | `min_adr` | 443 | 145 | ✅ Transferible |
| | `min_dollar_volume` | 445 | 150 | ✅ Transferible |
| **Quality** | `max_dist_sma20` | 448 | 137 | ✅ Transferible |
| | `min_consolidation_days` | 450 | 168 | ✅ Transferible |
| **Risk** | `risk_dollars` | 453 | 134 | ✅ Transferible |
| | `max_exposure_pct` | 455 | 135 | ✅ Transferible |
| | `max_stop_pct` | 454 | 151 | ✅ Transferible |
| **Exits** | `tp1_r` | 458 | N/A | ✅ Transferible* |
| | `tp2_r` | 459 | N/A | ✅ Transferible* |
| | `use_phases` | 462 | N/A | ✅ Transferible* |
| **RVOL Size** | `rvol_danger` | 469 | 140 | ⚠️ Ajustar tamaño |
| | `rvol_warning` | 470 | 141 | ⚠️ Ajustar tamaño |
| | `rvol_danger_size` | 471 | 142 | ⚠️ Ajustar (THOR: 0.30, Adv: 0.25) |
| | `rvol_warning_size` | 472 | 143 | ⚠️ Ajustar (THOR: 0.65, Adv: 0.60) |

*\* Advanced usa hardcoded values pero acepta params*

---

## ❌ Parámetros NO Transferibles (Engine-Specific)

### THOR-Only (optimization_engine_thor.py)
```python
# Líneas 58-73
offline_mode=True      # Advanced usa cache + yfinance fallback
use_float32=True       # Advanced siempre float64
chunk_size=100         # Advanced no usa chunks
lookback_days=365      # Advanced fijo en 365 (línea 310)
```

### Advanced-Only (vectorbt_engine_advanced.py)
```python
# Líneas 156-169 (Market Regime)
use_dynamic_thresholds=True       # Ajusta thresholds por VIX
use_market_regime_filter=True     # 4-stage classification
block_trades_in_stage3=True
block_trades_in_stage4=True

# Líneas 169-219 (Advanced Filters)
use_adaptive_filtering=True       # TIER 1-2-3 filtering
use_earnings_calendar=True        # Check earnings proximity
require_spy_above_sma50=True      # Primary filter
require_positive_rs=True          # Sector RS filter
use_rs_percentile=False           # IBD-style RS ranking

# Líneas 177-180 (Trailing Stop)
use_trailing_stop=True            # Move stop to BE
be_trailing_threshold=0.8

# Líneas 170-176 (SMA50/ATR)
use_sma50_atr_filter=False        # Filter overextended stocks
```

---

## 📝 Cómo Usar Ambos Motores

### Estrategia 1: THOR para Discovery, Advanced para Validación
```
1. Optimizar en THOR
   → Identificar RANGOS de parámetros robustos
   → NO confiar en valores exactos
   → Ejemplo: min_rvol [1.8, 2.2], no min_rvol=2.0

2. Transferir RANGES a Advanced
   → Usar mismo período de datos
   → Desactivar features exclusivas de Advanced:
     - use_dynamic_thresholds=False
     - use_market_regime_filter=False
     - use_adaptive_filtering=False
     - use_earnings_calendar=False
     - use_trailing_stop=False

3. Re-optimizar en Advanced
   → Validar que rangos siguen siendo óptimos
   → Ajustar rvol_warning_size/danger_size (-0.05 para Advanced)

4. Validación final con features ON
   → Reactivar features de Advanced
   → Esperar divergencia de 10-20% (esperado)
```

### Estrategia 2: THOR para screening, Advanced para backtesting
```
1. Descubrir mejores tickers con THOR
   → Optimizar por tickers
   → Identificar qué tickers funcionan mejor

2. Validar estrategia en Advanced
   → Usar solo tickers seleccionados
   → Aplicar todos los filters de Advanced
   → Analizar quality metrics (profit factor, MAR, etc.)
```

### Estrategia 3: Parallel validation (recomendada)
```
1. Optimizar en AMBOS simultáneamente
   → THOR: fast, memory-efficient for many trials
   → Advanced: detailed for fewer trials

2. Comparar top 5 params de cada engine
   → Si convergencia > 15%: Confianza ALTA
   → Si 15-30%: Confianza MEDIA (revisar)
   → Si < 30%: Descartar params

3. Validar en out-of-sample
   → Usar params que convergen en AMBOS
   → Test en período diferente (ej. 2024)
```

---

## 🎯 Recomendaciones Prácticas

### Para optimización de rangos robustos (TU caso):
```python
# ✅ Usar THOR para discovery rápido
thor = OptimizationEngineTHOR(
    tickers=universe_size,  # 600 tickers
    start_date='2020-01-01',
    end_date='2023-12-31',
    use_float32=True,  # Save RAM
)

# Optuna con 500 trials (rápido)
study = optuna.create_study(direction='maximize')
# ...

# Extraer TOP 10 params
top_params = top_10_params_from_study

# 🔄 Transferir RANGOS a Advanced
param_ranges = extract_ranges(top_params)
# Ejemplo: min_rvol: [1.8, 2.2], tp1_r: [1.4, 1.6]

# ✅ Validar en Advanced con features desactivadas
adv = AdvancedVectorBTEngine(
    universe=top_100_tickers,  # Subset
    start_date='2020-01-01',
    end_date='2023-12-31',
    use_dynamic_thresholds=False,      # CRÍTICO
    use_market_regime_filter=False,    # CRÍTICO
    use_adaptive_filtering=False,      # CRÍTICO
    use_earnings_calendar=False,       # CRÍTICO
    use_trailing_stop=False,           # CRÍTICO
)

# Run Optuna con narrowed ranges (100 trials, más detallado)
study_2 = optuna.create_study(direction='maximize')
# ...

# ✅ Validación final con features ON
final_params = best_params_from_study_2
adv_final = AdvancedVectorBTEngine(
    universe=top_100_tickers,
    use_dynamic_thresholds=True,       # Reactivar
    use_market_regime_filter=True,
    use_adaptive_filtering=True,
    **final_params
)
result = adv_final.run_backtest()

# ⚠️ Esperar divergencia de 10-20% vs THOR
```

### Parámetros que SÍ transferen sin modificación:
```python
params = {
    # ✅ Liquidity (safe)
    'min_rvol': 2.0,
    'min_adr': 2.5,
    'min_dollar_volume': 5e6,

    # ✅ Quality (safe)
    'max_dist_sma20': 12.5,
    'min_consolidation_days': 10,

    # ✅ Risk (safe)
    'risk_dollars': 150,
    'max_exposure_pct': 0.25,
    'max_stop_pct': 7.0,  # THOR usa 0.07 decimal, Advanced usa %

    # ✅ Exits (safe)
    'tp1_r': 1.5,
    'tp2_r': 3.0,
    'use_phases': True,
}
```

### Parámetros que requieren AJUSTE al transferir:
```python
# ⚠️ RVOL size reduction: Advanced más conservador
params_thor = {
    'rvol_warning_size': 0.65,
    'rvol_danger_size': 0.30,
}

# ✅ Ajustar para Advanced
params_advanced = {
    'rvol_warning_size': 0.60,  # -0.05 vs THOR
    'rvol_danger_size': 0.25,   # -0.05 vs THOR
}
```

---

## 📌 Conclusión

### ¿Se pueden transferir params de THOR a Advanced?
**Respuesta:** 🟡 **PARCIALMENTE - con condiciones**

**Puedes transferir:**
- ✅ Parámetros de liquidity (min_rvol, min_adr, min_dollar_volume)
- ✅ Parámetros de quality (max_dist_sma20, min_consolidation_days)
- ✅ Parámetros de risk base (risk_dollars, max_exposure_pct)
- ✅ Parámetros de exits (tp1_r, tp2_r, use_phases)

**Requieren ajuste:**
- ⚠️ rvol_warning_size: -0.05 (THOR 0.65 → Advanced 0.60)
- ⚠️ rvol_danger_size: -0.05 (THOR 0.30 → Advanced 0.25)

**NO transferibles:**
- ❌ Features exclusivas de Advanced (dynamic thresholds, adaptive filtering, etc.)
- ❌ Configuraciones de implementation (float32 vs float64, chunked loading)

### Estrategia recomendada:
1. 🔍 **THOR:** Optimizar ranges (no valores exáctos)
2. 🎯 **Advanced:** Validar ranges con features OFF
3. ✅ **Final:** Activar features y aceptar 10-20% divergencia

**Divergencia esperada:**
- Same params, both engines: 15-20% (acceptable)
- Transfer THOR→Advanced without adjustment: 50%+ (not acceptable)
- With features ON in Advanced: 20-30% (acceptable but expect different behavior)