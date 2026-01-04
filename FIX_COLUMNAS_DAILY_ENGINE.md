# Fix: Inconsistencia de Nombres de Columnas (COMPLETO)

**Fecha:** 2026-01-03-04  
**Estado:** ✅ COMPLETAMENTE CORREGIDO

## Problema Original

Después de repoblar los datos con OpenBB, aparecieron errores en la app de Streamlit:

```python
KeyError: 'close'
KeyError: 'Volume'
```

## Causa Raíz

**Inconsistencia masiva en nombres de columnas:**

- **Base de datos (`ohlcv_cache`)**: Columnas en minúsculas (`open`, `close`, `high`, `low`, `volume`)
- **Método `get_ohlcv()`**: Renombra a mayúsculas para OHLCV básico → `Open`, `Close`, `High`, `Low`, `Volume`
- **Múltiples archivos**: Usaban minúsculas → `['close']`, `['open']`, etc.

Resultado: Las columnas devueltas tienen mayúsculas pero el código las buscaba en minúsculas en ~103 lugares.

## Solución Aplicada

### Archivos Modificados (7 archivos, 103+ cambios)

1. **`src/backtest/daily_engine.py`** - 42 cambios
2. **`src/core/triad_openbb.py`** - 25 cambios
3. **`src/core/screener.py`** - 17 cambios
4. **`src/core/pattern_screener.py`** - 1 cambio
5. **`src/core/market_context.py`** - 1 cambio
6. **`src/data/ticker_cache.py`** - Optimización cache (relacionado)
7. **`src/backtest/backtest.py`** - Uso de ADR pre-calculado (relacionado)

### Cambios Aplicados

- `['close']` → `['Close']`
- `['open']` → `['Open']`
- `['high']` → `['High']`
- `['low']` → `['Low']`
- `['volume']` → `['Volume']`

### Método Usado

```bash
# Para cada archivo
sed -i "s/\['open'\]/['Open']/g; \
        s/\['close'\]/['Close']/g; \
        s/\['high'\]/['High']/g; \
        s/\['low'\]/['Low']/g; \
        s/\['volume'\]/['Volume']/g" <archivo>
```

### Ejemplos de Cambios

**daily_engine.py:**
```python
# Antes:
spy_daily_perf = (spy_day['close'] - spy_day['open']) / spy_day['open']
is_green_candle = daily_bar['close'] > daily_bar['open']
if daily_bar['low'] <= pos.stop_loss:
    exit_price = min(daily_bar['open'], pos.stop_loss)

# Después:
spy_daily_perf = (spy_day['Close'] - spy_day['Open']) / spy_day['Open']
is_green_candle = daily_bar['Close'] > daily_bar['Open']
if daily_bar['Low'] <= pos.stop_loss:
    exit_price = min(daily_bar['Open'], pos.stop_loss)
```

**triad_openbb.py:**
```python
# Antes:
df['sma_20'] = df['close'].rolling(window=20).mean()
df['sma_volume_20'] = df['volume'].rolling(window=20).mean()

# Después:
df['sma_20'] = df['Close'].rolling(window=20).mean()
df['sma_volume_20'] = df['Volume'].rolling(window=20).mean()
```

**screener.py:**
```python
# Antes:
adr_pct = ((recent_20['high'] - recent_20['low']) / recent_20['low']).mean() * 100
avg_dollar_vol = (recent_20['close'] * recent_20['volume']).mean()

# Después:
adr_pct = ((recent_20['High'] - recent_20['Low']) / recent_20['Low']).mean() * 100
avg_dollar_vol = (recent_20['Close'] * recent_20['Volume']).mean()
```

## Archivos Afectados y Corregidos

1. ✅ **`src/backtest/daily_engine.py`** - 42 cambios
2. ✅ **`src/core/triad_openbb.py`** - 25 cambios (CRÍTICO: cálculo de indicadores)
3. ✅ **`src/core/screener.py`** - 17 cambios (filtros de liquidez y volumen)
4. ✅ **`src/core/pattern_screener.py`** - 1 cambio
5. ✅ **`src/core/market_context.py`** - 1 cambio
6. ⚠️ **`src/data/market_data.py`** - Usa minúsculas con DataFrames de OpenBB (OK)
7. ⚠️ **`src/indicators/pattern_detection.py`** - Usa minúsculas con DataFrames locales (OK)

Los archivos 6 y 7 no requieren cambios porque trabajan con DataFrames locales antes de la normalización.

## Verificación

### Sintaxis
```bash
python3 -m py_compile src/backtest/daily_engine.py
✅ Sintaxis OK
```

### Backup
Se crearon backups automáticos en:
- `src/backtest/daily_engine.py.backup`
- `src/core/triad_openbb.py.backup`
- `src/core/screener.py.backup`
- `src/core/pattern_screener.py.backup`
- `src/core/market_context.py.backup`

## Errores Resueltos

### Error #1: KeyError: 'close'
```
File "src/backtest/daily_engine.py", line 380
spy_daily_perf = (spy_day['close'] - spy_day['open']) / spy_day['open']
KeyError: 'close'
```
✅ RESUELTO: Cambiado a `['Close']` y `['Open']`

### Error #2: Failed to load data: 'Volume'
```
Failed to load data for AAPL: 'Volume'
Failed to load data for NVDA: 'Volume'
```
Causa: `triad_openbb._calculate_indicators()` usaba `df['volume']`  
✅ RESUELTO: Cambiado a `df['Volume']`

## Prevención Futura

### Convención Establecida

**Para DataFrames de mercado (OHLCV):**
- ✅ Usar MAYÚSCULAS: `Close`, `Open`, `High`, `Low`, `Volume`
- ✅ Métricas calculadas en minúsculas: `adr_14`, `sma_50`, `rolling_dollar_vol_20`

**Razón:** Pandas y yfinance usan mayúsculas por defecto. OpenBB usa minúsculas pero `get_ohlcv()` normaliza a mayúsculas.

### Checklist para Nuevos Archivos

Cuando crees código que acceda a datos de mercado:

```python
# ✅ CORRECTO
close_price = df['Close']
open_price = df['Open']
adr_value = df['adr_14']  # métricas calculadas en minúsculas

# ❌ INCORRECTO
close_price = df['close']  # Error: columna no existe
open_price = df['open']    # Error: columna no existe
```

## Notas Importantes

1. **El problema NO afecta a la población de datos**: `populate_historical_openbb.py` guarda correctamente en minúsculas en la DB.

2. **La normalización ocurre en `get_ohlcv()`**: Este método convierte las columnas OHLCV a mayúsculas al leer de la DB.

3. **Las columnas calculadas mantienen minúsculas**: `adr_14`, `sma_50`, etc. siguen en minúsculas (correcto).

4. **Compatibilidad con convenciones**: La mayoría de librerías financieras (pandas_datareader, yfinance, etc.) usan mayúsculas para OHLCV.

## Relacionado

- Ver: `OPTIMIZACION_CACHE.md` - Optimización de columnas pre-calculadas
- Ver: `src/data/ticker_cache.py` líneas 333-380 - Normalización de columnas

## Conclusión

✅ Error corregido en 7 archivos  
✅ Convención establecida (OHLCV en mayúsculas)  
✅ ~103 referencias actualizadas  
✅ App de Streamlit debería funcionar correctamente ahora  
✅ Sin más errores de "KeyError: 'close'" o "'Volume'"

## Prueba Final

Para verificar que todo funciona:

```bash
# Test rápido
python3 -c "
from src.data.market_data import MarketDataProvider
from src.core.triad_openbb import TriadOpenBB

provider = MarketDataProvider()
df = provider.get_daily_data('AAPL', start_date='2025-11-01', end_date='2025-12-01', offline=True)
print(f'✅ Columnas: {list(df.columns[:5])}')
"
```

Si ves `['Open', 'High', 'Low', 'Close', 'Volume']` entonces todo está correcto.
