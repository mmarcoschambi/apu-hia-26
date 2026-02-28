# 🎯 Optimización de Parámetros - Guía Completa

## ✅ Lo Que Creé Para Ti

He creado una suite de scripts de optimización **modernos y autónomos** que:

1. ✅ **Buscan automáticamente el último trade_log.csv**
2. ✅ **Agrupan salidas parciales correctamente** (TP1+TP2+RUNNER = 1 trade)
3. ✅ **Incluyen contexto** en todos los outputs (qué parámetros se usaron)
4. ✅ **Son rápidos** - usan vectorización donde es posible
5. ✅ **Generan outputs con timestamp** para comparar diferentes runs

## 📂 Scripts Creados

### `quick_diagnostics.py` ⚡ (30 segundos)
**El más importante - siempre empieza aquí**

¿Qué hace?
- Winners vs Losers comparison
- Identifica problemas automáticamente
- Da recomendaciones específicas

```bash
python3 scripts/optimization/quick_diagnostics.py
```

**Output ejemplo:**
```
🔴 RVOL tiene valores enormes - Posible bug en cálculo
🟡 Win Rate bajo (38.5%) - Objetivo: >40%
💡 RECOMMENDATIONS:
   - Aumenta min_rvol (prueba 2.0x)
   - Reduce max_dist_sma20 (prueba 7%)
```

###  `range_finder.py` 📊 (1-2 minutos)
**Encuentra qué rangos funcionan mejor**

¿Qué hace?
- Divide cada parámetro en buckets
- Calcula win rate y R-multiple por bucket
- Te dice qué rangos son mejores

```bash
python3 scripts/optimization/range_finder.py
```

**Output ejemplo:**
```
dist_sma20_pct:
  0-3%:   45% WR, +0.8R   ← MEJOR
  3-5%:   42% WR, +0.6R
  5-7%:   38% WR, +0.3R
  >7%:    35% WR, -0.1R   ← EVITAR
```

## 🔍 Tu Problema Específico: RVOL

Según tu output:
```
WINNERS:  Avg RVOL: 1178619.86x
LOSERS:   Avg RVOL: 1070270.72x
```

**Este es un BUG**. RVOL debería ser 1-5x, no 1 millón.

### Dónde está el bug probablemente:

```python
# INCORRECTO:
rvol = volume_today  # ← Solo volumen absoluto

# CORRECTO:
rvol = volume_today / avg_volume_20d  # ← Ratio relativo
```

## 🎯 Workflow Recomendado

### Paso 1: Diagnóstico (SIEMPRE)
```bash
python3 scripts/optimization/quick_diagnostics.py
```
- Te dice QUÉ está mal
- Te da recomendaciones específicas

### Paso 2: Encontrar Rangos
```bash
python3 scripts/optimization/range_finder.py
```
- Te muestra qué valores de cada parámetro funcionan
- Guarda CSV con todos los rangos

### Paso 3: Fix Issues
Si quick_diagnostics dice "RVOL bug":
1. Ir a `src/backtest/vectorbt_engine_advanced.py`
2. Buscar dónde se calcula `context_rvol`
3. Verificar que sea: `volume / avg_volume_20d`

### Paso 4: Iterar
```bash
# Ejecuta backtest con parámetros ajustados
streamlit run app.py

# Re-ejecuta diagnóstico
python3 scripts/optimization/quick_diagnostics.py

# Compara resultados
diff outputs/optimization/diagnostics_OLD.txt \
     outputs/optimization/diagnostics_NEW.txt
```

## 💡 Sobre VectorBT vs Pandas

### ¿Cuándo usar cada uno?

**VectorBT** (motor de backtest):
- ✅ Simular miles de operaciones
- ✅ Backtesting masivo
- ✅ Walk-forward optimization
- ✅ Cuando tienes OHLCV data

**Pandas** (análisis post-backtest):
- ✅ Analizar resultados YA generados
- ✅ Estadísticas y correlaciones
- ✅ Agrupaciones complejas
- ✅ Cuando trabajas con CSVs de trades

### No pierdes velocidad

Los scripts de optimización usan pandas porque:
1. Ya tienes el trade_log.csv generado
2. Son análisis estadísticos (no simulaciones)
3. Pandas es perfecto para esto

**El motor VectorBT ya hizo su trabajo** (generó el trade_log en 2 segundos).
**Ahora pandas analiza esos resultados** (toma 30 segundos).

## 🚀 Ejemplo de Uso Completo

```bash
# 1. Ejecuta backtest (VectorBT - rápido)
streamlit run app.py  # 2 segundos generando 460 trades

# 2. Diagnóstico inmediato
python3 scripts/optimization/quick_diagnostics.py
# Output: "RVOL bug detectado"

# 3. Analiza rangos
python3 scripts/optimization/range_finder.py
# Output: "dist_sma20 óptimo: 3-5%"

# 4. Fix RVOL en el motor
vim src/backtest/vectorbt_engine_advanced.py
# Corrige: rvol = volume / avg_volume_20d

# 5. Re-ejecuta backtest
streamlit run app.py

# 6. Verifica mejora
python3 scripts/optimization/quick_diagnostics.py
# Output: "✅ RVOL correcto (1-3x), Win Rate mejoró a 42%"
```

## 📊 Outputs Generados

Todos los scripts guardan en `outputs/optimization/`:
```
diagnostics_20260107_162230.txt    ← Diagnóstico completo
ranges_20260107_162245.csv         ← Rangos óptimos por parámetro
```

Cada archivo incluye:
- Timestamp de cuándo se generó
- Qué trade_log se usó
- Parámetros del backtest (si están disponibles)

## 🔧 Siguiente Paso Inmediato

```bash
# 1. Ejecuta diagnóstico AHORA
cd /home/marcos/trade/momentum-v2
python3 scripts/optimization/quick_diagnostics.py

# 2. Lee el output - te dirá exactamente qué hacer
# 3. Sigue las recomendaciones
# 4. Re-ejecuta backtest
# 5. Compara resultados
```

## ✅ Resumen Ejecutivo

**Problema**: No sabes qué "perrillas" ajustar
**Solución**: Scripts que te dicen exactamente qué ajustar

**Scripts creados**:
1. ✅ `quick_diagnostics.py` - Diagnóstico en 30seg
2. ✅ `range_finder.py` - Rangos óptimos en 2min
3. ✅ `README.md` - Documentación completa
4. ✅ Este resumen

**Estado**: ✅ Listo para usar

**Acción inmediata**:
```bash
python3 scripts/optimization/quick_diagnostics.py
```

¡Eso es todo! Los scripts te guiarán desde ahí. 🎯
