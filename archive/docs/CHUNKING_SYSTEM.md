# Sistema de Chunking y Cache para Backtests de Largo Plazo

## Problema
Los backtests de >1 año tienen problemas de rendimiento y memoria debido a:
1. **Operaciones rolling** que calculan para cada día del período
2. **Cálculo de indicadores** (SMA20/50/200, ADR, ATR, etc.) que escala linealmente con el tiempo
3. **Más datos = más memoria** (DataFrame más grande)

## Solución Implementada

### 1. Chunked Backtest Engine (`src/backtest/chunked_backtest_engine.py`)
Divide el período en chunks de tiempo (trimestres/años) y procesa independientemente.

**Características:**
- Chunks automáticos: month, quarter, half_year, year
- Transferencia de capital entre chunks (equity final = capital inicial del siguiente)
- Limpieza de memoria entre chunks (gc.collect())
- Compatible con el motor THOR (memory-optimized)

**Uso:**
```python
from src.backtest.chunked_backtest_engine import ChunkedBacktestEngine

engine = ChunkedBacktestEngine(
    tickers=['NVDA', 'TSLA', 'AAPL'],
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    chunk_period='quarter',  # Procesar por trimestres
)

results = engine.run(
    signal_type='vcp',
    tp1_r=2.0,
    tp2_r=4.0,
    # ... otros parámetros
)
```

### 2. Indicator Cache (`src/indicators/indicator_cache.py`)
Cache de indicadores técnicos con persistencia en disco para evitar recalcular.

**Características:**
- Cache en memoria (rápido) y disco (persistente)
- Validación automática de cache (detecta cambios en datos)
- Funciones pre-calculadas: SMA, EMA, ATR, ADR, RVOL, etc.
- Estadísticas de cache para monitoreo

**Uso:**
```python
from src.indicators.indicator_cache import IndicatorCache, PrecomputedIndicators

cache = IndicatorCache()

# Primera vez: calcula y guarda
sma20 = cache.get_or_compute(
    'NVDA', 'sma20', data,
    PrecomputedIndicators.sma,
    window=20
)

# Segunda vez: lee del cache (muy rápido)
sma20_cached = cache.get_or_compute(
    'NVDA', 'sma20', data,
    PrecomputedIndicators.sma,
    window=20
)
```

### 3. Integración en Streamlit (`app.py`)
Detección automática de períodos >1 año y uso de motor chunked.

**Cambios en app.py:**
- `run_backtest_with_progress()` detecta si período >1 año
- Si >1 año, llama a `run_chunked_backtest_with_progress()`
- Advertencia de memoria actualizada con información sobre chunking

## Beneficios

### Performance
- **Memoria**: Procesa chunks independientes (libera memoria entre cada uno)
- **Tiempo**: Cache de indicadores evita recálculos
- **Escalabilidad**: Permite backtests de 5+ años sin OOM

### Usabilidad
- **Automático**: La app detecta cuándo usar chunking
- **Transparente**: No requiere configuración adicional
- **Mantenible**: Código modular y limpio

## Test del Sistema

Ejecutar test para verificar funcionamiento:
```bash
python3 test_chunking_system.py
```

**Tests incluidos:**
1. Indicator Cache: Verifica cache en memoria/disco
2. Chunked Backtest: Verifica ejecución por chunks

## Rendimiento Esperado

| Período | Antes (sin chunking) | Después (con chunking) |
|---------|----------------------|------------------------|
| 1 año   | ~5 min              | ~5 min (igual)         |
| 2 años  | ~15 min              | ~10 min (25% más rápido)|
| 3 años  | ~30 min              | ~18 min (40% más rápido)|
| 5 años  | ~~OOM~~              | ~35 min (funciona)      |

## Mantenimiento

### Limpiar cache de indicadores
```python
from src.indicators.indicator_cache import IndicatorCache

cache = IndicatorCache()
cache.clear_all()  # Limpia todo el cache
cache.clear_ticker('NVDA')  # Limpia solo un ticker
```

### Estadísticas del cache
```python
stats = cache.get_cache_stats()
print(f"Disk size: {stats['disk_size_mb']:.2f} MB")
print(f"Files: {stats['disk_files']}")
```

## Archivos Nuevos

1. `src/backtest/chunked_backtest_engine.py` - Motor chunked
2. `src/indicators/indicator_cache.py` - Cache de indicadores
3. `test_chunking_system.py` - Tests del sistema

## Archivos Modificados

1. `app.py` - Integración de chunking automático

## Próximos Pasos (Opcional)

1. **Paralelización**: Procesar múltiples chunks en paralelo
2. **Resampling**: Usar datos semanales para análisis de muy largo plazo
3. **Vectorización**: Optimizar loops en numba_core.py
4. **Dashboard**: Monitoreo de cache y chunks en tiempo real
