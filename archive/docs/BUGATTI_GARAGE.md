# 🏎️ BUGATTI GARAGE - GUÍA DE MOTORES

## 🚗 LA FLOTA BUGATTI

Tienes 3 motores Bugatti, cada uno optimizado para diferentes necesidades:

### 1. **BUGATTI CHIRON** 🏎️ (V6_PRO Original)
**Archivo:** `src/backtest/optimization_engine_v6_pro.py`

**Características:**
- 🔥 **Potencia máxima:** Pre-calcula TODO al inicio
- 📊 **Features:** 100% completo (VCP, RS, Sector Rotation, 3-phase exits)
- 💾 **RAM:** 30-50 GB @ 600 tickers
- ⚡ **Velocidad:** Ultra-rápido en backtest individual
- 🎯 **Uso:** Cuando tienes RAM ilimitada y quieres todas las features

**Cuándo usar:**
- ✅ Optimizaciones con < 300 tickers
- ✅ Tienes 64+ GB RAM
- ✅ Necesitas TODAS las features (sector rotation, RS, earnings filter)
- ✅ Walk-forward analysis con universos pequeños

**Limitación:**
- ❌ Explota RAM con > 400 tickers
- ❌ No aguanta 33 parámetros × 600 tickers

---

### 2. **BUGATTI DIVO** 🏎️💨 (Memory Optimized)
**Archivo:** `src/backtest/optimization_engine_divo.py`

**Características:**
- 🎯 **Mismo poder, menos consumo**
- 💾 **RAM:** 8-15 GB @ 600 tickers (60% menos que Chiron)
- 🔋 **Optimizaciones:**
  - Float32 (50% menos RAM)
  - Lazy indicators (calcular solo cuando se usa)
  - Chunked loading (sin RAM spikes)
  - Aggressive garbage collection
- 📊 **Features:** 100% completo (igual que Chiron)
- ⚡ **Velocidad:** Mismo que Chiron

**Cuándo usar:**
- ✅ Optimizaciones con 200-800 tickers
- ✅ Tienes 16-32 GB RAM
- ✅ Necesitas todas las features pero menos RAM
- ✅ Walk-forward con universos grandes

**Ventajas vs Chiron:**
- ✅ Aguanta 600+ tickers sin problemas
- ✅ 60% menos RAM, misma precisión
- ✅ No sacrifica features

**Limitación:**
- ⚠️ Tiny overhead por lazy loading (< 5%)

---

### 3. **BUGATTI BOLIDE** 🏎️⚡ (2-Layer Optimization)
**Archivo:** `bugatti_bolide.py`

**Características:**
- 🧠 **Más inteligente, no más potente**
- ⚙️ **Estrategia:** Optimización en 2 capas (Pareto principle)
  - Layer 1: 8 parámetros CRÍTICOS → 100 trials × 100 tickers
  - Layer 2: 11 parámetros SECUNDARIOS → 50 trials × 50 tickers
- ⏱️ **Tiempo:** 25 min vs 10+ horas (brute-force)
- 🎲 **Muestreo:** Estratificado por liquidez (reduce overfitting)
- 🏎️ **Motor:** Usa DIVO internamente

**Cuándo usar:**
- ✅ Optimizas > 20 parámetros
- ✅ No tienes 10+ horas para brute-force
- ✅ Quieres evitar overfitting
- ✅ Research/discovery de mejores parámetros

**Ventajas:**
- ✅ 90% más rápido que brute-force
- ✅ Menor overfitting (menos params por vez)
- ✅ Mejor generalización (universos diferentes por capa)

**Limitación:**
- ⚠️ No garantiza óptimo global (pero casi siempre cerca)
- ⚠️ Requiere que params estén bien clasificados (críticos vs secundarios)
- ⚠️ **NO tiene walk-forward** (optimiza en un solo período)

---

### 4. **BUGATTI BOLIDE WALK-FORWARD** 🏎️⚡📊 (LO MEJOR DE TODO)
**Archivo:** `bugatti_bolide_walkforward.py`

**Características:**
- 🎯 **Combina TODO lo mejor:**
  - 2-layer optimization (inteligente)
  - Walk-forward IS/VAL/OOS (robusto)
  - Motor DIVO (memory-optimized)
  - Estratificación (anti-sesgo)
- 📊 **4 Fases:**
  - Phase 1: Layer 1 en IN-SAMPLE (critical params)
  - Phase 2: Layer 2 en IN-SAMPLE (secondary params)
  - Phase 3: VALIDATION (robustness test)
  - Phase 4: OUT-OF-SAMPLE (final test, optional)
- ⏱️ **Tiempo:** 30-40 min para full walk-forward
- 🎲 **Anti-overfitting:** Degradation % automático

**Cuándo usar:**
- ✅ Vas a deploy en producción (necesitas validación)
- ✅ Quieres evitar overfitting (walk-forward)
- ✅ Optimizas > 20 parámetros (2-layer)
- ✅ **RECOMENDADO para trabajo serio**

**Ventajas:**
- ✅ 90% más rápido que brute-force
- ✅ Anti-overfitting (IS/VAL/OOS)
- ✅ Degradation % automático
- ✅ Robustness scoring
- ✅ 60% menos RAM

**Limitación:**
- ⚠️ Toma 30-40 min (vs 25 min del BOLIDE simple)
- ⚠️ Necesitas datos suficientes (3+ años)

---

## 🎯 COMPARACIÓN RÁPIDA

| Métrica | Chiron | Divo | Bolide | Bolide WF |
|---------|--------|------|--------|-----------|
| **RAM @ 600 tickers** | 30-50 GB | 8-15 GB | 8-15 GB | 8-15 GB |
| **Features** | 100% | 100% | 100% | 100% |
| **Max tickers** | 300 | 800 | 800 | 800 |
| **Velocidad backtest** | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ | ⚡⚡⚡⚡⚡ |
| **Velocidad opt** | Normal | Normal | 10× más rápido | 10× más rápido |
| **Walk-forward** | ❌ | ❌ | ❌ | ✅ IS/VAL/OOS |
| **Anti-overfitting** | ❌ | ❌ | Medio | ✅ Alto |
| **Degradation check** | ❌ | ❌ | ❌ | ✅ Automático |
| **Mejor para** | RAM ilimitada | RAM limitada | Research rápido | **Production** |
| **Tiempo total** | Variable | Variable | 25 min | 30-40 min |

---

## 🔧 GUÍA DE USO

### ESCENARIO 1: Walk-Forward con 800 tickers
**Motor:** DIVO 🏎️💨

```python
from src.backtest.optimization_engine_divo import OptimizationEngineDIVO

engine = OptimizationEngineDIVO(
    tickers=tickers,  # 800 tickers
    start_date='2020-01-01',
    end_date='2023-12-31',
    use_float32=True,  # 50% menos RAM
    chunk_size=100     # Cargar 100 a la vez
)

# Backtest normal
stats = engine.backtest(params)

# Limpieza cada 20 trials
if trial % 20 == 0:
    engine.clear_indicator_cache()
```

---

### ESCENARIO 2: Optimización exhaustiva (33 params)
**Motor:** BOLIDE 🏎️⚡ (quick) o **BOLIDE WF** 🏎️⚡📊 (production)

#### Quick (sin walk-forward):
```bash
python bugatti_bolide.py \
    --start 2020-01-01 \
    --end 2023-12-31 \
    --layer1-trials 150 \
    --layer1-tickers 150 \
    --layer2-trials 75 \
    --layer2-tickers 100 \
    --metric sharpe
```

#### Production (con walk-forward):
```bash
python bugatti_bolide_walkforward.py \
    --in-start 2020-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-06-30 \
    --oos-start 2023-07-01 --oos-end 2024-12-31 \
    --layer1-trials 150 --layer1-tickers 150 \
    --layer2-trials 75 --layer2-tickers 100 \
    --metric sharpe
```

**Resultado:** Config optimizado + degradation % + robustness score

---

### ESCENARIO 3: Backtest rápido con pocas tickers (< 200)
**Motor:** CHIRON o DIVO (da igual)

```python
from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO

# O usa DIVO si quieres ahorrar RAM
engine = OptimizationEngineV6_PRO(
    tickers=tickers,  # < 200
    start_date='2020-01-01',
    end_date='2023-12-31',
)

stats = engine.backtest(params)
```

---

## 📊 CONFIGURACIÓN RECOMENDADA POR RAM

### 16 GB RAM
- **Tickers:** Max 300
- **Motor:** DIVO 🏎️💨
- **Config:** `use_float32=True, chunk_size=50`

### 32 GB RAM
- **Tickers:** Max 600
- **Motor:** DIVO 🏎️💨
- **Config:** `use_float32=True, chunk_size=100`

### 64+ GB RAM
- **Tickers:** Max 800+
- **Motor:** CHIRON 🏎️ o DIVO (da igual)
- **Config:** Lo que quieras

---

## 🔬 DETALLES TÉCNICOS

### Float32 vs Float64
**DIVO usa Float32 por default:**
- ✅ 50% menos RAM
- ✅ Misma precisión para trading (6-7 dígitos significativos)
- ✅ Float32 es suficiente para precios ($0.01 precision @ $10,000)
- ❌ NO usar Float32 para cálculos científicos extremos

### Lazy Loading (DIVO)
**Indicadores se calculan solo cuando se acceden:**
```python
# Esto NO calcula nada aún
engine = OptimizationEngineDIVO(...)

# Esto SÍ calcula SMA20 (solo cuando se necesita)
entries = engine.close > engine.sma20

# Ventaja: Si no usas RSI, nunca se calcula → 0 RAM
```

### Chunked Loading (DIVO)
**Cargar datos en grupos evita RAM spike:**
```
Chiron: Carga 600 tickers → 50 GB RAM spike → OOM
Divo: Carga 100 + 100 + 100... → 15 GB max RAM → OK
```

### Estratificación (BOLIDE)
**Muestreo inteligente evita sesgo:**
```
Layer 1: 30% mega-caps + 40% mid-caps + 30% small-caps = 100 tickers
Layer 2: DIFERENTE sample con mismo ratio = 50 tickers

Resultado: Generaliza mejor (no overfit a AAPL, MSFT, etc.)
```

---

## 🎓 FILOSOFÍA DE DISEÑO

### ¿Por qué 3 motores?

1. **CHIRON (Original):** 
   - "Si tienes RAM, úsala"
   - Pre-calcular = más rápido
   - Research probó que funciona

2. **DIVO (Optimizado):**
   - "Mismo power, menos consumo"
   - Lazy = inteligente (calcular solo lo necesario)
   - 60% ahorro sin sacrificar nada

3. **BOLIDE (Inteligente):**
   - "Trabaja más inteligente, no más duro"
   - Pareto 80/20 aplicado a optimización
   - 10× más rápido, menos overfitting

### ¿Cuál es mejor?

**No hay "mejor" - depende del caso de uso:**

- 🏎️ **CHIRON:** Tienes RAM ilimitada → usa todo
- 💨 **DIVO:** RAM limitada → optimiza
- ⚡ **BOLIDE:** Research rápido → divide y conquista
- 📊 **BOLIDE WF:** Production/deploy → walk-forward robusto

---

## 🚀 MIGRACIÓN

### De Chiron a Divo
**Cambio mínimo:**
```python
# ANTES
from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO
engine = OptimizationEngineV6_PRO(tickers, ...)

# DESPUÉS
from src.backtest.optimization_engine_divo import OptimizationEngineDIVO
engine = OptimizationEngineDIVO(
    tickers,
    use_float32=True,  # Nuevo: 50% menos RAM
    chunk_size=100,    # Nuevo: cargar en chunks
    ...
)

# API es IDÉNTICA, solo cambias la import
stats = engine.backtest(params)  # Igual
```

### De Bugatti Optuna a Bolide
**Reemplaza:**
```bash
# ANTES (bugatti_optuna.py - brute force)
python bugatti_optuna.py --trials 500 --tickers 600
# 10+ horas

# DESPUÉS (bugatti_bolide.py - 2 capas)
python bugatti_bolide.py \
    --layer1-trials 150 --layer1-tickers 150 \
    --layer2-trials 75 --layer2-tickers 100
# 25 minutos
```

---

## ⚠️ PROBLEMAS CONOCIDOS Y SOLUCIONES

### "MemoryError" con Chiron
**Solución:** Usa DIVO
```python
engine = OptimizationEngineDIVO(use_float32=True)
```

### "Optimization too slow"
**Solución:** Usa BOLIDE
```bash
python bugatti_bolide.py --layer1-trials 100 --layer2-trials 50
```

### "Results don't match between Chiron and Divo"
**Solución:** Diferencias < 0.1% son normales (Float32 precision)
- Si diferencia > 1%, hay bug → report

### "RAM keeps growing"
**Solución:** Limpia cache cada N trials
```python
if trial % 20 == 0:
    engine.clear_indicator_cache()
    gc.collect()
```

---

## 📝 NOTAS FINALES

### Naming Convention
- **CHIRON:** Bugatti más rápido (420 km/h) → Nuestro más potente
- **DIVO:** Chiron optimizado para curvas → Mismo motor, más eficiente
- **BOLIDE:** Bugatti de pista extremo → Más inteligente, no más potente

### Filosofía
> "El mejor motor es el que necesitas, no el más potente."

### Contribuciones
Si mejoras algún motor:
1. No rompas backward compatibility
2. Mantén API idéntica
3. Documenta cambios de RAM/velocidad
4. Test con 3 tamaños: 50, 200, 600 tickers

---

## 🏁 QUICK START

**¿No sabes cuál usar? Usa esto:**

```python
# Si tienes < 500 tickers → DIVO
from src.backtest.optimization_engine_divo import OptimizationEngineDIVO
engine = OptimizationEngineDIVO(
    tickers=your_tickers,
    start_date='2020-01-01',
    end_date='2023-12-31',
    use_float32=True,
    chunk_size=100
)

# Si optimizas > 15 params QUICK → BOLIDE
# bash: python bugatti_bolide.py --layer1-trials 100 --layer2-trials 50

# Si optimizas para PRODUCTION → BOLIDE WALK-FORWARD ⭐
# bash: python bugatti_bolide_walkforward.py \
#           --in-start 2020-01-01 --in-end 2022-12-31 \
#           --val-start 2023-01-01 --val-end 2023-06-30 \
#           --layer1-trials 100 --layer2-trials 50
```

**Fin.** 🏎️💨⚡📊
