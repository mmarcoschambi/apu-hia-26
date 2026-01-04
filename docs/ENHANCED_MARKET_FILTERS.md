# 🛡️ Enhanced Market Filters - Requisitos Mejorados

## 📋 Resumen

El sistema ahora incluye **filtros de mercado más sofisticados** para asegurar que solo operes en las mejores condiciones posibles.

---

## 🎯 Los 5 Pilares del Market Health Check

### 1. **SPX/SPY en Tendencia Alcista** ✅

**Requisito:** SPY > EMA 20

- **Por qué:** Confirma que el mercado general está en tendencia alcista
- **Cómo se mide:** EMA 20 es la media exponencial de 20 días
- **Threshold:** El precio actual debe estar por encima de la EMA20
- **Weight:** 2 puntos (el más importante)

```python
spy_ema20 = SPY.Close.ewm(span=20).mean()
if SPY_current > spy_ema20:
    ✅ Tendencia alcista confirmada
```

**Ejemplo:**
- SPY precio: $605.50
- EMA20: $600.20
- Status: ✅ ABOVE (favorable)

---

### 2. **Volatilidad Favorable** ✅

**Requisito:** VIX < 20 Y bajando o estable

- **Por qué:** Baja volatilidad = menos riesgo de gaps + movimientos más predecibles
- **Cómo se mide:** 
  - VIX actual < 20
  - VIX actual ≤ VIX hace 5 días × 1.1
- **Weight:** 1 punto

```python
VIX < 20              → Volatilidad normal
VIX estable/bajando   → No está spike
```

**Interpretación VIX:**

| VIX Level | Significado | Trading Action |
|-----------|-------------|----------------|
| < 15 | Complacencia | ✅ Ideal para momentum |
| 15-20 | Normal | ✅ Favorable |
| 20-30 | Elevado | ⚠️ Cuidado |
| > 30 | Miedo/Pánico | ❌ No operar longs |

**Ejemplo:**
- VIX actual: 16.5
- VIX hace 5 días: 17.2
- Status: ✅ FAVORABLE (bajando y <20)

---

### 3. **Gamma Positiva (GEX)** ✅

**Requisito:** Estimación de GEX > 0

- **Por qué:** Gamma positiva → dealers hedgean vendiendo en subidas y comprando en caídas = mercado menos volátil con grind alcista
- **Cómo se estima:**
  - ATR(5) declinando (volatilidad comprimiéndose)
  - SPY > EMA10 (uptrend de corto plazo)
- **Weight:** 1 punto

```python
ATR declining   →  Vol comprimiéndose
SPY > EMA10     →  Short-term uptrend
= Positive GEX regime (grind alcista)
```

**Características de GEX Positivo:**
- Movimientos pequeños día a día
- Pullbacks shallow y rápidos
- Uptrend constante sin grandes swings
- Ideal para Camino 1 (Blue Sky)

---

### 4. **Market Breadth Mejorando** ✅

**Requisito:** % de acciones por encima de SMA20 está ascendiendo

- **Por qué:** Breadth fuerte = la mayoría de acciones subiendo = mercado saludable
- **Cómo se mide (proxy):**
  - SPY y QQQ ambos > SMA20
  - O precio promedio últimos 5 días > 5 días anteriores
- **Weight:** 2 puntos (muy importante)

```python
SPY > SMA20 AND QQQ > SMA20     → Internos fuertes
O
Recent_5d_avg > Previous_5d_avg → Breadth ascendiendo
```

**Interpretación:**
- ✅ Breadth improving: El mercado tiene internos fuertes
- ❌ Breadth declining: Solo pocas acciones lideran (peligroso)

---

### 5. **Sector Leadership** ✅ **NUEVO**

**Requisito:** El sector de la acción debe estar en el top 3 del día

- **Por qué:** Operar en sectores líderes aumenta probabilidad de éxito
- **Cómo se mide:**
  - Ranking diario de 10 sectores principales (XLK, XLE, XLF, etc)
  - Comparar performance % change del día
  - Acción debe pertenecer a top 3 sectores
- **Weight:** 1 punto (bonus)

**Sectores Trackeados:**

| Sector ETF | Nombre | Ejemplos |
|------------|--------|----------|
| XLK | Technology | AAPL, NVDA, MSFT, GOOGL |
| XLE | Energy | XOM, CVX, SLB |
| XLF | Financial | JPM, BAC, GS |
| XLV | Healthcare | UNH, JNJ, LLY |
| XLI | Industrial | BA, CAT, GE |
| XLY | Consumer Discr. | AMZN, TSLA, HD |
| XLP | Consumer Staples | PG, KO, WMT |
| XLB | Materials | LIN, APD |
| XLRE | Real Estate | AMT, PLD |
| XLU | Utilities | NEE, DUK |

**Ejemplo Output:**
```
Top 3 Sectors Today:
   Technology          +2.35%
   Consumer Discr.     +1.80%
   Financial           +1.25%
```

**Filtro en Acción:**
- Si tu setup es NVDA (Technology) → ✅ En sector líder
- Si tu setup es PG (Consumer Staples) → ❌ NO en top 3

---

## 📊 Health Score System (Mejorado)

**Sistema de puntos sobre 7:**

| Condición | Puntos |
|-----------|--------|
| SPY > EMA20 | +2 |
| Breadth improving | +2 |
| VIX favorable | +1 |
| Positive GEX | +1 |
| Sector data available | +1 |
| **TOTAL** | **7** |

---

## 🎯 Matriz de Decisión (Actualizada)

### Score 6-7: 🚀 AGGRESSIVE MODE

**Condiciones:**
- ✅ SPY > EMA20
- ✅ Breadth improving
- ✅ VIX < 20 y estable
- ✅ Positive GEX
- ✅ Sector leadership identificado

**Trading Parameters:**
- Risk per trade: **2%**
- Max positions: **5**
- Caminos activos: **Todos los 3**
- **Bonus:** Priorizar setups en sectores líderes

**Mentalidad:** Full confidence, toma todos los setups de calidad

---

### Score 4-5: 💪 STANDARD MODE

**Condiciones:**
- ✅ SPY > EMA20 O Breadth improving (al menos uno)
- ✅ VIX favorable
- Puede faltar GEX o sector data

**Trading Parameters:**
- Risk per trade: **1.5-2%**
- Max positions: **3-4**
- Caminos activos: **Preferir Camino 1**
- **Enfoque:** Setups en sectores líderes si están disponibles

**Mentalidad:** Confianza normal, ser selectivo

---

### Score 2-3: ⚠️ DEFENSIVE MODE

**Condiciones:**
- ⚠️ Alguna condición falla
- Mercado mixto o débil

**Trading Parameters:**
- Risk per trade: **0.5-1%**
- Max positions: **1-2**
- Caminos activos: **Solo Camino 1 perfecto**
- **Crítico:** SOLO en sectores líderes

**Mentalidad:** Ultra selectivo, esperar perfección

---

### Score 0-1: ❌ NO TRADE MODE

**Condiciones:**
- ❌ SPY < EMA20 Y Breadth declining
- ❌ VIX > 20 o spiking
- Múltiples factores negativos

**Trading Parameters:**
- Risk per trade: **0%**
- Max positions: **0**
- **Action:** GO TO CASH

**Mentalidad:** Paciencia, esperar mejores condiciones

---

## 🔍 Ejemplo Práctico Completo

### Escenario: Evaluando NVDA el 22 de Diciembre

**Step 1: Market Health Check**

```
📊 SPY TREND
   Current: $605.50
   EMA20: $600.20
   Status: ✅ ABOVE (+0.88%)
   Points: +2

📈 BREADTH
   SPY > SMA20: ✅
   QQQ > SMA20: ✅
   Status: ✅ IMPROVING
   Points: +2

⚡ VOLATILITY (VIX)
   Current: 16.5
   5 days ago: 17.2
   Status: ✅ FAVORABLE (< 20, declining)
   Points: +1

💎 GAMMA EXPOSURE
   ATR declining: ✅
   SPY > EMA10: ✅
   Status: ✅ POSITIVE
   Points: +1

🎯 SECTOR LEADERSHIP
   Top 3:
      Technology         +2.35% ✅
      Consumer Discr.    +1.80%
      Financial          +1.25%
   Points: +1

═══════════════════════════
TOTAL SCORE: 7/7 🟢🟢🟢🟢🟢🟢🟢
═══════════════════════════
```

**Step 2: Verdict**

```
🚀 EXCELLENT CONDITIONS - AGGRESSIVE MODE

Max positions: 5
Risk per trade: 2%
All 3 Caminos active
```

**Step 3: Setup Evaluation (NVDA)**

```
✅ Market health: PASSED (7/7)
✅ NVDA sector (Tech): IN TOP 3
✅ Pattern: Blue Sky Breakout
✅ Risk/Reward: 5:1

DECISION: ✅ TAKE THE TRADE
Entry: $875.50
Stop: $860.00
Size: 2% risk
```

---

## 🚨 Ejemplos de Filtros en Acción

### Ejemplo 1: Sector NO Líder (Filtrado)

**Setup:** PG (Procter & Gamble) - Consumer Staples

**Market Check:**
- Score: 6/7 (excelente)
- Sectores líderes: Tech, Energy, Financial
- Consumer Staples: #8 del día (-0.3%)

**Sector Check:**
```
❌ PG sector (Consumer Staples) NOT in top 3
   Current rank: #8
   Performance: -0.3%
```

**Decision:** ❌ SKIP (aunque todo lo demás está bien)

**Reasoning:** 
- Operar en sectores rezagados reduce probabilidad
- Mejor esperar setup en sector líder
- Disciplina > FOMO

---

### Ejemplo 2: VIX Spiking (Filtrado)

**Market Check:**
- SPY > EMA20: ✅
- Breadth: ✅
- VIX: **28.5** (↑ desde 18 hace 5 días)

**VIX Analysis:**
```
⚠️ VIX: 28.5 (ELEVATED)
   Above threshold: 28.5 > 20
   Spiking: +58% en 5 días

❌ MARKET NOT FAVORABLE
   Reason: VIX elevated/rising
```

**Decision:** ❌ NO TRADE (aunque SPY/Breadth OK)

**Reasoning:**
- VIX spiking = fear/volatility
- Alto riesgo de gaps y whipsaws
- Mejor esperar que VIX se calm

---

### Ejemplo 3: Todo Perfecto (Tomar Trade)

**Setup:** NVDA - Camino 1 Blue Sky

**Market Check:**
- SPY > EMA20: ✅ (7/7 score)
- VIX: 15.2 ✅
- GEX: Positive ✅
- Breadth: Strong ✅
- Sector: Tech (#1, +2.5%) ✅

**Verdict:**
```
🚀 AGGRESSIVE MODE
🎯 NVDA in leading sector
✅ ALL SYSTEMS GO

Entry: $875.50
Stop: $860.00
Risk: 2% ($500)
Shares: 32
```

**Decision:** ✅ FULL CONFIDENCE TRADE

---

## 🎓 Cómo Usar en Tu Workflow Diario

### 8:00 AM - Pre-Market

```bash
python market_health_check.py --detail
```

**Output te dirá:**
1. Health Score (0-7)
2. Mode (Aggressive/Standard/Defensive/No-Trade)
3. Top 3 sectores del día
4. VIX status
5. Recomendación específica

**Decision Tree:**

```
Score 6-7?
└─> ✅ Busca setups en TODOS los sectores líderes

Score 4-5?
└─> ⚠️ Busca solo setups perfectos en sectores líderes

Score 2-3?
└─> ⚠️⚠️ Solo Blue Sky perfecto en sector #1

Score 0-1?
└─> ❌ NO ESCANEAR - Go to cash
```

### Durante el Scan

Cuando el scanner encuentra un setup:

```python
# El sistema automáticamente verifica:
1. ¿Market health PASSED? (interno)
2. ¿Sector del stock en top 3?
3. ¿Patrón de calidad?
4. ¿R:R > 3:1?

Si TODOS ✅ → Setup accionable
Si CUALQUIERA ❌ → Setup filtrado
```

---

## 📈 Mejora Esperada en Resultados

### Sin Filtros Mejorados:

- Win rate: ~55%
- Avg R: ~1.8R
- **Problema:** Trades en mercado débil + sectores rezagados

### Con Filtros Mejorados:

- Win rate esperado: **60-65%**
- Avg R esperado: **2.0-2.5R**
- **Beneficio:** 
  - Evitas mercado bajista (VIX spike)
  - Solo operas sectores líderes
  - Mejor timing (GEX + Breadth)

### Costo: Menos Trades

- Antes: ~8-10 setups/semana
- Ahora: ~4-6 setups/semana
- **Pero:** Mucho mayor calidad

**Trade-off:** Calidad >>> Cantidad

---

## 🛠️ Implementación Técnica

### Código Integrado en:

1. **src/core/market_context.py**
   - `_analyze_vix()` - Análisis VIX
   - `_get_sector_leaders()` - Ranking sectores
   - `get_stock_sector()` - Mapeo stock → sector
   - `is_sector_leading()` - Filtro sector

2. **market_health_check.py**
   - Display mejorado con VIX y sectores
   - Score system actualizado (7 puntos)
   - Thresholds ajustados

3. **morning_workflow.py**
   - Integración automática
   - Usa todos los filtros sin configuración extra

---

## ⚙️ Configuración Avanzada (Opcional)

### Ajustar Sensibilidad VIX

En `src/core/market_context.py`:

```python
# Más estricto (solo VIX muy bajo)
VIX_THRESHOLD = 15  # Default: 20

# Más permisivo
VIX_THRESHOLD = 25
```

### Ajustar Sector Requirements

```python
# Require sector en top 1 (muy estricto)
TOP_N_SECTORS = 1  # Default: 3

# Más permisivo
TOP_N_SECTORS = 5
```

### Añadir Más Sectores/Stocks

Editar mapping en `get_stock_sector()`:

```python
tech_stocks = ['AAPL', 'NVDA', ... 'TU_STOCK']
```

---

## 📚 Referencias

- **VIX:** CBOE Volatility Index
- **GEX:** Gamma Exposure (SpotGamma, SqueezeMetrics)
- **Sector ETFs:** Select Sector SPDR ETFs
- **Breadth:** Market breadth indicators (Advance/Decline)

---

## ✅ Checklist de Verificación

Antes de cada trade, confirma:

- [ ] Market health score ≥ 4
- [ ] VIX < 20 y estable
- [ ] Stock sector en top 3 (o modo defensive)
- [ ] SPY > EMA20 O Breadth improving
- [ ] Pattern de calidad confirmado
- [ ] R:R > 3:1

**Si 6/6 ✅ → Trade con confianza**
**Si falta alguno → Reevaluar o skip**

---

**Última actualización:** Diciembre 2024

**Sistema de filtros mejorado implementado y operativo.** ✅
