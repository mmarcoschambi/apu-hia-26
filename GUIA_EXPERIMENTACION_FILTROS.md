# 🔬 GUÍA: Filtro de Sectores - Top 40% Methodology

## 🎯 NUEVO SISTEMA IMPLEMENTADO

Ahora tienes **DOS métodos** de filtrado de sectores:

### Método 1: Simple (Actual)
```python
use_composite_sector_scoring=False
```
- Compara sector vs SPY en un solo timeframe (20 días)
- Threshold: sector > SPY (cualquier ventaja)
- **Simple y rápido**

### Método 2: Top 40% Composite (NUEVO) ⭐
```python
use_composite_sector_scoring=True
sector_top_percentile=0.40
```
- **Puntuación compuesta** con múltiples métricas
- Solo opera **top 40% de sectores más fuertes**
- **Profesional - usado por traders institucionales**

---

## 📊 CÓMO FUNCIONA EL TOP 40%

### Fórmula de Puntuación Compuesta

```
Score = (RS_Weekly × 40%) + (RS_Monthly × 30%) + (Momentum × 20%) + (RVOL × 10%)
```

Donde:
- **RS Weekly** (40%): Performance últimos 5 días vs SPY
- **RS Monthly** (30%): Performance últimos 20 días vs SPY
- **Momentum** (20%): Rate of Change últimos 20 días
- **RVOL** (10%): Volumen relativo vs promedio

---

## 💡 EJEMPLO PRÁCTICO

### Escenario: 11 Sectores SPDR

```
Fecha: 2026-01-06
Sectores disponibles: 11 (XLK, XLF, XLV, XLE, XLY, XLP, XLI, XLB, XLRE, XLU, XLC)
```

### Paso 1: Calcular Puntuación para cada Sector

| Sector | RS Week | RS Month | Momentum | RVOL | **Score** |
|--------|---------|----------|----------|------|-----------|
| **XLK (Tech)** | 98.2 | 96.5 | 92.0 | 85.0 | **94.1** |
| **XLY (ConsD)** | 95.7 | 97.3 | 89.5 | 88.0 | **93.8** |
| **XLB (Mater)** | 92.0 | 90.1 | 88.0 | 82.0 | **89.4** |
| **XLF (Financ)** | 89.4 | 86.2 | 86.5 | 80.0 | **86.8** |
| **XLI (Indust)** | 87.5 | 85.0 | 84.0 | 78.0 | **84.5** |
| XLV (Health) | 82.1 | 80.5 | 79.0 | 75.0 | 80.3 |
| XLC (Comm) | 78.5 | 77.0 | 76.0 | 72.0 | 76.5 |
| XLP (Staples) | 75.0 | 73.5 | 72.0 | 68.0 | 72.8 |
| XLE (Energy) | 70.5 | 68.0 | 67.0 | 65.0 | 68.3 |
| XLRE (RealEst) | 65.0 | 63.5 | 62.0 | 60.0 | 63.3 |
| XLU (Util) | 60.0 | 58.5 | 57.0 | 55.0 | 58.3 |

### Paso 2: Calcular Top 40%

```
Total sectores: 11
Top 40% = 11 × 0.40 = 4.4 → Redondear a 4 sectores
```

### Paso 3: Identificar Top Tier

✅ **Top 40% (LEADERS)**:
1. XLK (Tech) - Score 94.1
2. XLY (Consumer Discretionary) - Score 93.8
3. XLB (Materials) - Score 89.4
4. XLF (Financials) - Score 86.8

❌ **Fuera del Top 40%**:
5. XLI (Industrials) - Score 84.5
6. XLV (Healthcare) - Score 80.3
7-11. Resto de sectores

### Paso 4: Aplicar Filtro

```python
Ticker: AAPL (Technology - XLK)
Sector Score: 94.1
Rank: 1/11
Percentile: 100%
is_top_tier: True ✅
Resultado: TRADE PERMITIDO

Ticker: JNJ (Healthcare - XLV)
Sector Score: 80.3
Rank: 6/11
Percentile: 54.5%
is_top_tier: False ❌
Resultado: TRADE RECHAZADO
```

---

## 🎛️ CONFIGURACIÓN

### En el Engine

```python
from src.backtest.vectorbt_engine_advanced import VectorBTEngineAdvanced

engine = VectorBTEngineAdvanced(
    ...
    use_composite_sector_scoring=True,  # ← Activar Top 40%
    sector_top_percentile=0.40,  # ← Top 40% (ajustable)
    ...
)
```

### Opciones de Percentiles

```python
# Muy Estricto (Solo élite)
sector_top_percentile=0.20  # Top 20% (2-3 sectores)

# Estricto (Recomendado)
sector_top_percentile=0.40  # Top 40% (4-5 sectores)

# Moderado
sector_top_percentile=0.50  # Top 50% (5-6 sectores)

# Permisivo
sector_top_percentile=0.60  # Top 60% (6-7 sectores)
```

---

## 📊 CLASIFICACIÓN DE SECTORES

El sistema clasifica sectores en 4 categorías:

### 1. LEADER (Top percentile)
- **Top 40%** de sectores
- Los únicos tradeables con filtro activo
- Ejemplo: XLK (rank 1/11, percentile 100%)

### 2. STRONG (40-70%)
- Sectores con fuerza moderada
- NO tradeables con filtro activo
- Ejemplo: XLI (rank 5/11, percentile 63.6%)

### 3. NEUTRAL (70-85%)
- Sectores sin momentum claro
- NO tradeables
- Ejemplo: XLC (rank 7/11, percentile 45.5%)

### 4. WEAK (Bottom 15%)
- Sectores débiles
- Claramente evitables
- Ejemplo: XLU (rank 11/11, percentile 9.1%)

---

## 🆚 COMPARACIÓN: Simple vs Top 40%

### Método Simple (Actual)

```python
use_composite_sector_scoring=False
```

**Pros**:
- ✅ Rápido de calcular
- ✅ Simple de entender
- ✅ Menos datos requeridos

**Contras**:
- ❌ Un solo timeframe (puede perder contexto)
- ❌ No pondera múltiples factores
- ❌ Threshold binario (>0 o ≤0)

**Ejemplo**:
```
XLK (Tech): RS = +2.5% vs SPY → ✅ PERMITIDO
XLE (Energy): RS = +0.1% vs SPY → ✅ PERMITIDO (aunque débil)
XLU (Utils): RS = -0.5% vs SPY → ❌ RECHAZADO
```

---

### Método Top 40% (NUEVO)

```python
use_composite_sector_scoring=True
sector_top_percentile=0.40
```

**Pros**:
- ✅ Múltiples timeframes (weekly + monthly)
- ✅ Pondera varios factores (RS + momentum + volumen)
- ✅ Ranking relativo (top 40% dinámico)
- ✅ Más selectivo (solo mejores sectores)

**Contras**:
- ❌ Más complejo
- ❌ Requiere más cálculos
- ❌ Menos trades (más restrictivo)

**Ejemplo**:
```
XLK (Tech): Score 94.1, Rank 1/11 → ✅ PERMITIDO (TOP TIER)
XLE (Energy): Score 68.3, Rank 9/11 → ❌ RECHAZADO (WEAK)
XLU (Utils): Score 58.3, Rank 11/11 → ❌ RECHAZADO (WEAK)
```

---

## 🔬 EXPERIMENTACIÓN SUGERIDA

### Experimento 1: Comparar Métodos

**Backtest A (Simple)**:
```python
use_composite_sector_scoring=False
```

**Backtest B (Top 40%)**:
```python
use_composite_sector_scoring=True
sector_top_percentile=0.40
```

**Métricas a Comparar**:
- Total de trades (B debería tener menos)
- Win rate (B debería tener mayor)
- Profit factor (B debería ser mejor)
- R-multiple promedio (B debería ser mayor)

**Hipótesis**: Top 40% mejora win rate +5-10% pero reduce trades -20-30%

---

### Experimento 2: Ajustar Percentiles

```python
# Test 1: Muy estricto
sector_top_percentile=0.20  # Solo 2 sectores

# Test 2: Estricto (recomendado)
sector_top_percentile=0.40  # 4-5 sectores

# Test 3: Moderado
sector_top_percentile=0.60  # 6-7 sectores
```

**Objetivo**: Encontrar el sweet spot entre selectividad y cantidad de trades

---

### Experimento 3: Ajustar Pesos

Modificar en `calculate_composite_score()`:

```python
# Actual (balanced)
composite = (
    rs_weekly * 0.40 +
    rs_monthly * 0.30 +
    momentum * 0.20 +
    rvol * 0.10
)

# Variante A: Enfoque momentum
composite = (
    rs_weekly * 0.30 +
    rs_monthly * 0.20 +
    momentum * 0.40 +  # ← Mayor peso
    rvol * 0.10
)

# Variante B: Enfoque largo plazo
composite = (
    rs_weekly * 0.20 +
    rs_monthly * 0.50 +  # ← Mayor peso
    momentum * 0.20 +
    rvol * 0.10
)
```

---

## 📈 RESULTADO ESPERADO

### Con Método Simple (Actual)

```
Backtest: 2015-2021 (397 trades)
- Trades rechazados por sector: ~45 (11%)
- Win rate: ~47%
- Sectores traded: 8-9 de 11
```

### Con Top 40% (Esperado)

```
Backtest: 2015-2021
- Trades totales: ~280 trades (-30%)
- Trades rechazados por sector: ~120 (30%)
- Win rate: ~55-58% (+8-11 pts)
- Sectores traded: 4-5 de 11 (solo top tier)
- Profit factor: 1.4-1.6 (vs 1.2)
```

---

## 🚀 CÓMO USAR

### Paso 1: Activar en Streamlit (futuro)

```python
# Agregar checkbox en app.py
use_top40 = st.checkbox("Usar Top 40% Sector Filter", value=False)
percentile = st.slider("Top Percentile", 0.2, 0.6, 0.4, 0.1)
```

### Paso 2: Ejecutar Backtest

```python
results = engine.simulate_with_partial_exits()
```

### Paso 3: Analizar Resultados

```
📊 Filter Stats:
   weak_sector: 120 rejections  ← Más rechazos (bueno!)
   
📈 Performance:
   Win rate: 57%  ← Mejor calidad
   Trades: 280  ← Menos cantidad
   R-multiple: +0.85R  ← Mejor expectativa
```

---

## 💡 REGLA DE ORO PROFESIONAL

> **"Nunca compres la acción más fuerte de un sector débil.  
> Siempre prefiere la acción promedio de un sector fuerte."**

### Ejemplo Práctico:

```
Candidatos:
1. $XOM (Energy) - RS individual: 95, Sector score: 68.3, Rank: 9/11
2. $NVDA (Tech) - RS individual: 85, Sector score: 94.1, Rank: 1/11

❌ Con método simple: Ambos permitidos (ambos sectores > SPY)
✅ Con Top 40%: Solo NVDA permitido (Energy fuera del top 40%)

Resultado: NVDA tiene mejor probabilidad de éxito aunque RS individual sea menor
```

---

## 📝 RESUMEN

✅ **Sistema Implementado**:
- Top 40% methodology con composite scoring
- Configurable via parámetros del engine
- Clasificación automática en 4 tiers

⚙️ **Parámetros**:
- `use_composite_sector_scoring`: True/False
- `sector_top_percentile`: 0.20 - 0.60

📊 **Beneficios Esperados**:
- +8-11 pts win rate
- Menos trades (-30%)
- Mejor profit factor (+20-30%)
- Solo opera sectores líderes

🔬 **Próximo Paso**:
Ejecutar backtests comparativos y medir impacto real

---

**Fecha**: 2026-01-06
**Estado**: ✅ IMPLEMENTADO Y LISTO PARA EXPERIMENTAR
**Documentación**: GUIA_EXPERIMENTACION_FILTROS.md
