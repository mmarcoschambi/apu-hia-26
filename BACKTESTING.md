# 📊 Backtesting Guide - Historical Analysis

El sistema de backtesting te permite revisar cómo habrían funcionado los 3 Caminos en datos históricos, con gráficos detallados de cada entrada.

## 🎯 Objetivo

**NO es predecir el futuro**, sino:
1. Familiarizarte con los patrones de entrada
2. Entender cómo se ven los setups en gráficos reales
3. Estudiar qué configuraciones tienen mejor win rate
4. Aprender a identificar señales rápidamente

---

## 🚀 Método 1: Runner Interactivo (Recomendado)

El método más fácil y guiado:

```bash
python3 backtest_runner.py
```

Te guiará paso a paso:
1. Elige símbolos (watchlist)
2. Selecciona rango de fechas
3. Decide si generar gráficos

**Ejemplo de sesión:**

```
📝 CONFIGURACIÓN
================================================================================

1. Watchlist (símbolos separados por espacio):
   Ejemplo: RDDT NVDA TSLA CEG PLTR
   Símbolos: AAPL NVDA TSLA

2. Rango de fechas:
   a) Último mes
   b) Últimos 3 meses  ← RECOMENDADO PARA EMPEZAR
   c) Últimos 6 meses
   d) Todo 2024
   e) Custom (ingresar fechas)
   Opción (a/b/c/d/e): b

3. Archivo de resultados:
   Nombre (Enter = backtest_results.csv): [Enter]

4. Generar gráficos?
   a) Sí, todos
   b) Sí, solo primeros 10  ← RECOMENDADO
   c) Sí, solo primeros 5
   d) Solo dashboard resumen
   e) No generar gráficos
   Opción (a/b/c/d/e): b
```

---

## ⚡ Método 2: Línea de Comandos (Avanzado)

Para usuarios que prefieren control directo:

### Paso 1: Ejecutar Backtest

```bash
python3 src/backtest/backtest.py \
  --symbols AAPL NVDA TSLA RDDT \
  --start 2024-01-01 \
  --end 2024-06-30 \
  --output my_backtest.csv
```

**Parámetros:**
- `--symbols`: Lista de símbolos separados por espacio
- `--start`: Fecha inicio (YYYY-MM-DD)
- `--end`: Fecha fin (YYYY-MM-DD)
- `--output`: Nombre del archivo CSV de salida

### Paso 2: Generar Visualizaciones

```bash
python3 src/backtest/visualizer.py my_backtest.csv --max-trades 15
```

**Opciones:**
- `--max-trades N`: Generar solo N gráficos individuales (default: 20)
- `--summary-only`: Solo dashboard, sin gráficos individuales

---

## 📈 Interpretando los Resultados

### 1. Summary Dashboard (`summary_dashboard.png`)

Muestra 4 cuadrantes:

#### A. Returns Distribution
- Histograma de retornos
- Verde = Wins, Rojo = Losses
- ¿Están los wins más a la derecha que los losses a la izquierda?

#### B. Win Rate by Camino
- ¿Qué Camino tiene mejor win rate?
- **Importante:** Más signals = más confianza estadística

#### C. Equity Curve
- Si hicieras todos los trades, ¿cuál sería el retorno acumulado?
- **Línea ascendente = Sistema profitable**
- **Línea descendente = Ajustar parámetros**

#### D. Statistics Table
- **Win Rate:** Target > 50%
- **Avg Win vs Avg Loss:** Ideal Avg Win > 2x Avg Loss
- **Total Return:** Acumulado del período

### 2. Gráficos Individuales

Cada archivo: `SYMBOL_DATE_CAMINO.png`

**Elementos del gráfico:**
- 📦 **Candlesticks:** Precio (Verde=up, Rojo=down)
- 🟦 **Línea azul punteada:** Base High
- 🟧 **Línea naranja punteada:** AVWAP ATH (El Peaje)
- 🟩 **Triángulo verde:** Entry point
- 🔴 **Línea roja punteada:** Stop Loss
- ⭕/🔻 **Círculo o triángulo:** Exit (Verde=WIN, Rojo=LOSS)

**Volumen (abajo):**
- Barras verdes/rojas
- Línea verde vertical = Día de entrada

---

## 🔍 Cómo Estudiar los Gráficos

### Sesión de Estudio (30 minutos)

1. **Abre `summary_dashboard.png`**
   - Identifica qué Camino tuvo mejor performance
   - Anota el win rate general

2. **Filtra por Camino**
   - Abre solo los gráficos del mejor Camino
   - Ejemplo: Si Blue_Sky fue mejor, abre solo `*_BLUE_SKY.png`

3. **Estudia los WINS primero**
   - ¿Qué tenían en común?
   - ¿La Base estaba muy comprimida?
   - ¿El AVWAP estaba cerca?
   - ¿Había gap up o volumen alto?

4. **Estudia los LOSSES después**
   - ¿Por qué fallaron?
   - ¿AVWAP estaba demasiado lejos?
   - ¿Stop muy ajustado?
   - ¿Mercado en caída general?

5. **Identifica patrones**
   - Anota 3-5 características de los setups ganadores
   - Anota 3-5 "red flags" de los perdedores

---

## 📊 Archivo CSV (Análisis Detallado)

El CSV contiene todas las señales. Ábrelo en Excel/LibreOffice para:

### Columnas Importantes:

- **date:** Fecha de entrada
- **symbol:** Ticker
- **camino:** Qué Camino activó (BLUE_SKY, VWAP_RECLAIM, SAFETY_CHECK)
- **entry_price:** Precio de entrada
- **stop_loss:** Precio de stop
- **outcome:** WIN o LOSS
- **return_pct:** Retorno en %
- **hold_days:** Cuántos días duró el trade
- **base_high:** Nivel de la base
- **avwap:** Nivel del AVWAP ATH
- **gap_pct:** % de gap (para Camino 2)

### Análisis Sugeridos:

#### 1. Win Rate por Mes
```
Filtrar por mes → Calcular win rate
¿Hay meses mejores? (Ej. Jan-Feb mejor que Jul-Ago)
```

#### 2. Mejor Hold Time
```
Agrupar por hold_days → Calcular avg return
¿Los trades de 2 días son mejores que los de 10?
```

#### 3. Distance to AVWAP
```
Calcular: (entry_price - avwap) / avwap
¿Los setups con AVWAP más cerca tienen mejor win rate?
```

#### 4. Gap Analysis (Camino 2)
```
Para VWAP_RECLAIM → Correlación entre gap_pct y return
¿Gaps más grandes = mejores recoveries?
```

---

## ⚠️ Limitaciones del Backtest

### 1. Simulación Simplificada
- **NO** usa datos intraday reales (simula con daily data)
- El "VWAP reclaim" es una aproximación
- Los fills pueden ser diferentes en real

### 2. Trade Outcome
- Asume que el trade se ejecuta exactamente en entry_price
- Stop hit = salida exacta en stop_loss
- Target 2R hit = salida exacta
- En realidad hay slippage

### 3. No Considera
- Comisiones
- Taxes
- Slippage
- Impacto emocional

### 4. Data Quality
- Yahoo Finance puede tener gaps o datos erróneos
- Splits no siempre se ajustan correctamente

---

## 💡 Mejores Prácticas

### Para Principiantes

1. **Empieza con 3 meses recientes**
   - Suficientes datos
   - No abrumador

2. **Usa 3-5 símbolos conocidos**
   - AAPL, NVDA, TSLA, MSFT, META

3. **Genera solo 10 gráficos**
   - Estudia calidad > cantidad

4. **Sesión de 30 min**
   - Dedica tiempo a entender cada gráfico

### Para Avanzados

1. **Backtest 1 año completo**
   - Mayor muestra estadística

2. **Watchlist de 10-20 símbolos**
   - Incluye sectores diferentes

3. **CSV analysis profundo**
   - Excel pivot tables
   - Busca correlaciones

4. **Optimización de parámetros**
   - Ajusta `config/settings.py`
   - Re-run backtest
   - Compara resultados

---

## 🎓 Ejemplos de Comandos

### Ejemplo 1: Quick Test (Last Month)
```bash
python3 src/backtest/backtest.py \
  --symbols AAPL \
  --start 2024-11-01 \
  --end 2024-11-30 \
  --output nov_test.csv

python3 src/backtest/visualizer.py nov_test.csv --max-trades 5
```

### Ejemplo 2: Full 2024 Analysis
```bash
python3 src/backtest/backtest.py \
  --symbols AAPL NVDA TSLA META GOOGL MSFT \
  --start 2024-01-01 \
  --end 2024-12-01 \
  --output full_2024.csv

python3 src/backtest/visualizer.py full_2024.csv --max-trades 30
```

### Ejemplo 3: Momentum Stocks Focus
```bash
python3 src/backtest/backtest.py \
  --symbols RDDT PLTR COIN MSTR SMCI \
  --start 2024-03-01 \
  --end 2024-09-01 \
  --output momentum_stocks.csv

python3 src/backtest/visualizer.py momentum_stocks.csv
```

### Ejemplo 4: Only Dashboard (Fast)
```bash
python3 src/backtest/backtest.py \
  --symbols AAPL NVDA TSLA \
  --start 2024-01-01 \
  --end 2024-06-30 \
  --output q1_q2.csv

python3 src/backtest/visualizer.py q1_q2.csv --summary-only
```

---

## 🔧 Troubleshooting

### "No signals found"
- **Rango muy corto:** Usa al menos 2-3 meses
- **Símbolos no momentum:** Prueba con stocks más volátiles
- **Parámetros muy estrictos:** Ajusta `config/settings.py`

### "No data in range"
- **Limpia cache:** `rm -rf data/cache/*.pkl`
- **Stock muy nuevo:** Usa símbolos con más historia
- **Rango en el futuro:** Verifica las fechas

### "Graficos no se generan"
- **Falta directorio:** `mkdir -p backtest_charts`
- **Matplotlib error:** Re-install: `pip install -U matplotlib`

### "Win rate muy bajo (< 30%)"
- **Normal en backtests básicos**
- Los parámetros default son conservadores
- En real, esperarías 40-60% win rate con selección manual

---

## 📚 Próximos Pasos

Después de estudiar tus primeros backtests:

1. **Ajusta parámetros** en `config/settings.py`
   - `AVWAP_TOLERANCE`
   - `BLUE_SKY_OFFSET`
   - Base compression thresholds

2. **Re-run** con los nuevos parámetros

3. **Compara** resultados (CSV side-by-side)

4. **Implementa** lo aprendido en tu trading real

5. **Paper trade** con los patrones que identificaste

---

## 🎯 Objetivo Final

Al terminar 3-5 sesiones de backtest analysis, deberías poder:

✅ Identificar un setup de Camino 1 en < 10 segundos
✅ Saber qué características tienen los mejores setups
✅ Evitar "red flags" que indican baja probabilidad
✅ Tener confianza en el sistema antes de arriesgar capital

**Recuerda:** El backtest es tu laboratorio. Úsalo para aprender sin riesgo.

---

**"El backtest no predice. El backtest enseña."**

---

## 🌐 Dashboard Web Interactivo (✨ NUEVO)

### Generar Dashboard

```bash
python3 src/backtest/dashboard.py backtest_results.csv
```

Se abre automáticamente en tu navegador.

**Características:**
- 📊 **Gráficos interactivos** con Plotly (zoom, hover, pan)
- 🎯 **Tabs por símbolo** - Ve análisis individual de cada ticker
- 📈 **Candlesticks interactivos** - Top/Bottom trades con indicadores
- 💡 **Sin necesidad de instalar nada adicional** - Solo abre el HTML

### Navegación

**Tab Overview:**
- Returns distribution (wins vs losses)
- Win rate por Camino
- Equity curve
- Returns por símbolo
- Risk vs Reward scatter

**Tabs por Símbolo (AAPL, NVDA, etc):**
- Cumulative P&L del símbolo
- Estadísticas específicas
- Timeline de returns
- Distribución win/loss

**Tab Best/Worst Trades:**
- Gráficos completos de top 5 mejores trades
- Gráficos completos de top 5 peores trades
- Con candlesticks + AVWAP + Base + Entry/Exit markers

### Funcionalidades Interactivas

- **Hover** sobre cualquier punto → Ver detalles
- **Click y drag** → Zoom in en área específica
- **Doble click** → Reset zoom
- **Click en leyenda** → Mostrar/ocultar series
- **Botones de tabs** → Cambiar entre vistas

### Comparado con Matplotlib

| Feature | Matplotlib (PNG) | Plotly (HTML) |
|---------|-----------------|---------------|
| Interactividad | ❌ | ✅ |
| Zoom | ❌ | ✅ |
| Hover info | ❌ | ✅ |
| File size | Más pesado | Más ligero |
| Share | Imagen estática | HTML compartible |
| Mobile friendly | ⚠️ | ✅ |

**Recomendación:** Usa el dashboard HTML para análisis interactivo, y los PNGs de matplotlib para imprimir/presentaciones.

---

**Tip:** El dashboard HTML es un solo archivo. Puedes compartirlo por email/Dropbox y se abre en cualquier navegador moderno sin instalar nada.
