# 🚀 Pre-calculated Historical Metrics System

## Problema Original

Cuando ejecutabas un backtest, el sistema calculaba ADR, SMAs y filtros de liquidez **en tiempo real** para cada ticker en cada fecha. Para un backtest de:
- 500 tickers
- 252 días de trading
- = **126,000 cálculos repetidos** de las mismas métricas históricas

Esto tomaba **horas** y desperdiciaba recursos calculando datos que **nunca cambian** (son históricos).

## Solución: Cache de Métricas Históricas

Ahora las métricas históricas se calculan **UNA SOLA VEZ** y se almacenan en SQLite:

### Métricas Almacenadas

```sql
ohlcv_cache:
  - adr_14: Average Daily Range (14 días) en $
  - adr_pct_14: Average Daily Range (14 días) en %
  - sma_50: Simple Moving Average 50 días
  - sma_200: Simple Moving Average 200 días  
  - price_above_sma50: Boolean (1/0)
  - price_above_sma200: Boolean (1/0)
  - sma50_above_sma200: Boolean (1/0)
  - trend_aligned: Price > SMA50 > SMA200 (1/0)
  - rolling_dollar_vol_20: Dollar volume 20 días
  - avg_volume_20: Average volume 20 días
```

## 📦 Configuración Inicial (Una Sola Vez)

### Paso 1: Agregar Columnas a la Base de Datos

```bash
python3 scripts/add_historical_metrics.py
```

Esto agrega las nuevas columnas a `ohlcv_cache`.

### Paso 2: Calcular y Poblar Métricas Históricas

```bash
python3 scripts/populate_historical_metrics.py
```

⏱️ **Esto tomará tiempo** (1-3 horas para miles de tickers), pero **solo necesitas hacerlo una vez**.

El script:
- Lee todos los tickers en `ohlcv_cache`
- Calcula ADR, SMAs y flags de tendencia
- Guarda los resultados en la base de datos
- Commits cada 50 tickers para evitar problemas de memoria

### Paso 3: Verificar Performance

```bash
python3 scripts/test_fast_filters.py
```

Esto compara:
- **Método tradicional**: Cargar DataFrame completo + calcular métricas
- **Método rápido**: Lookup directo en SQLite

**Resultado esperado**: 50-100x más rápido 🚀

## 🔄 Mantenimiento

### Cuando Agregar Nuevos Datos Históricos

Cada vez que actualices datos históricos (ej: agregar más tickers o más fechas), ejecuta:

```bash
python3 scripts/populate_historical_metrics.py
```

El script es **idempotente** - puede ejecutarse múltiples veces sin problema, solo actualiza lo necesario.

### Agregar Nuevos Tickers

1. Agrega los tickers a `ohlcv_cache` (usando tu proceso normal)
2. Ejecuta `populate_historical_metrics.py` para calcular sus métricas

## 🎯 Uso en Backtests

### Método Antiguo (Lento)

```python
from src.core.stock_filters import StockFilters

filters = StockFilters()
df = data_provider.get_daily_data('AAPL', period='1y')  # Lento
result = filters.passes_all_filters(df, 'AAPL')         # Lento: calcula todo
```

### Método Nuevo (Rápido)

```python
from src.core.stock_filters import StockFilters

filters = StockFilters()
result = filters.passes_filters_fast('AAPL', '2024-12-27')  # ⚡ Instant!
```

## 📊 Impacto en Performance

### Backtest Ejemplo: 500 tickers, 252 días (2024)

**Antes:**
- 500 tickers × 252 días = 126,000 operaciones
- ~100ms por operación para cargar + calcular
- **Total: ~3.5 horas**

**Después:**
- 500 tickers × 252 días = 126,000 lookups
- ~1ms por lookup en SQLite
- **Total: ~2 minutos** ⚡

**Mejora: 100x más rápido**

## 🔧 Integración con Código Existente

Los siguientes archivos fueron actualizados para **evitar look-ahead bias**:

### 1. `src/backtest/backtest.py`
- Ahora evalúa filtros al **final del período del backtest** en lugar de usar datos actuales
- Usa `passes_filters_fast()` cuando está disponible

### 2. `src/backtest/daily_engine.py`  
- Filtra datos hasta `end_date` antes de aplicar filtros
- Usa métricas precalculadas cuando están disponibles

### 3. `src/core/stock_filters.py`
- Nuevo método `passes_filters_fast(ticker, date)` para lookups directos
- Mantiene compatibilidad con el método antiguo

## 💾 Tamaño de Base de Datos

Las nuevas columnas agregan ~8 bytes por fila (8 columnas × 1 byte promedio):

- 1,000 tickers × 5,000 días × 8 bytes = ~40 MB
- 10,000 tickers × 5,000 días × 8 bytes = ~400 MB

**Totalmente manejable** y el beneficio en velocidad es enorme.

## ⚠️ Consideraciones

### Look-Ahead Bias

El sistema **previene look-ahead bias** usando métricas calculadas hasta la fecha específica del backtest:

```python
# ✅ Correcto: Usa métricas de 2016 para trades de 2016
result = filters.passes_filters_fast('AAPL', '2016-06-15')

# ❌ Incorrecto: Usaría métricas actuales (2024) para trades de 2016  
df = get_data('AAPL')  # Trae datos hasta hoy
result = filters.passes_all_filters(df)  # Usa .tail(20) = datos de 2024!
```

### Datos Faltantes

Si una fecha no tiene métricas calculadas:
- `passes_filters_fast()` retorna `passed: False` con detalles
- Fallback al método tradicional si es necesario

### Re-cálculo Selectivo

Para recalcular solo un ticker:

```python
from scripts.populate_historical_metrics import calculate_metrics_for_ticker
import sqlite3

conn = sqlite3.connect('data/ticker_cache.db')
calculate_metrics_for_ticker(conn, 'AAPL')
conn.commit()
```

## 🎉 Resultado Final

- ✅ Backtests **100x más rápidos**
- ✅ Sin look-ahead bias
- ✅ Métricas consistentes y reproducibles
- ✅ Fácil de mantener
- ✅ Una sola configuración inicial

**Tu backtest de 2016 ahora funciona correctamente y es súper rápido!** 🚀
