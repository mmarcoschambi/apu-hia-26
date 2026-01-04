# 📊 Población de Datos Históricos con OpenBB

## Script: `populate_historical_openbb.py`

Script completo para poblar la base de datos SQLite con datos históricos usando **OpenBB** (en lugar de yfinance) y calculando **TODAS** las métricas automáticamente.

## ✨ Características

### Datos descargados:
- **OHLCV básico**: Open, High, Low, Close, Volume
- **Fuente**: OpenBB API (más confiable que yfinance para históricos)

### Métricas calculadas automáticamente:

| Métrica | Descripción |
|---------|-------------|
| `dollar_volume` | close * volume |
| `rolling_dollar_vol_20` | Promedio móvil 20 días de dollar_volume |
| `avg_volume_20` | Promedio móvil 20 días de volume |
| `adr_14` | Average Daily Range en $ (14 días) |
| `adr_pct_14` | Average Daily Range en % (14 días) |
| `sma_50` | Simple Moving Average 50 días |
| `sma_200` | Simple Moving Average 200 días |
| `price_above_sma50` | 1 si precio > SMA50, 0 si no |
| `price_above_sma200` | 1 si precio > SMA200, 0 si no |
| `sma50_above_sma200` | 1 si SMA50 > SMA200, 0 si no |
| `trend_aligned` | 1 si todas las condiciones de tendencia son verdaderas |

## 🚀 Uso

### 1. Modo Test (primeros 10 tickers)
```bash
python3 populate_historical_openbb.py --test
```

### 2. Tickers específicos
```bash
python3 populate_historical_openbb.py --tickers AAPL MSFT GOOGL AMZN NVDA
```

### 3. Todos los tickers del universo (completo)
```bash
python3 populate_historical_openbb.py --years 20
```

### 4. Repoblar forzando todos (sin skip)
```bash
python3 populate_historical_openbb.py --tickers AAPL MSFT --no-skip
```

## 📋 Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--years` | Años de histórico a descargar | 20 |
| `--delay` | Segundos entre requests (rate limiting) | 0.3 |
| `--tickers` | Lista específica de tickers | Todos del universo |
| `--test` | Solo primeros 10 tickers | False |
| `--no-skip` | No omitir tickers con datos existentes | False |

## 🔄 Flujo de Trabajo

1. **Verificar datos existentes**: Si un ticker ya tiene datos completos (>75% del periodo), lo omite (a menos que uses `--no-skip`)

2. **Descargar de OpenBB**: Usa la API de OpenBB para obtener datos históricos diarios

3. **Calcular métricas**: Calcula todas las métricas automáticamente:
   - Dollar volume y promedios
   - ADR en $ y %
   - SMAs 50 y 200
   - Flags de tendencia

4. **Insertar en DB**: Guarda en `ticker_cache.db` tabla `ohlcv_cache`

5. **Commit**: Hace commit después de cada ticker

## 📊 Estructura de la Base de Datos

```sql
CREATE TABLE ohlcv_cache (
    ticker TEXT,
    date DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    dollar_volume REAL,
    rolling_dollar_vol_20 REAL,
    market_cap REAL,
    avg_volume_20 REAL,
    adr_14 REAL,
    adr_pct_14 REAL,
    sma_50 REAL,
    sma_200 REAL,
    price_above_sma50 INTEGER,
    price_above_sma200 INTEGER,
    sma50_above_sma200 INTEGER,
    trend_aligned INTEGER,
    PRIMARY KEY (ticker, date)
);
```

## ⚙️ Configuración

El script usa la configuración de `config/settings.py`:

```python
DATA_SOURCE = "openbb"  # Asegúrate de que esté configurado
OPENBB_PROVIDER = "yfinance"  # Provider de OpenBB
```

## 🆚 Comparación con scripts anteriores

| Script | Fuente | Métricas | Estado |
|--------|--------|----------|--------|
| `populate_historical_cache.py` | ❌ yfinance directo | ❌ Solo OHLCV | Obsoleto |
| `scripts/populate_historical_metrics.py` | - | ✅ Calcula métricas post-descarga | Separado |
| `populate_historical_openbb.py` | ✅ OpenBB API | ✅ Todo en uno | **Recomendado** |

## ⚡ Rendimiento

- **Speed**: ~0.3s por ticker (con delay de rate limiting)
- **Tiempo estimado** para 1000 tickers: ~5 minutos
- **Espacio en disco**: ~50-100 MB por 1000 tickers con 20 años de datos

## 🔍 Verificación de Datos

Después de poblar, puedes verificar:

```bash
# Inspeccionar cache
python3 cache_inspector.py

# Ver estadísticas de un ticker
sqlite3 data/ticker_cache.db "SELECT * FROM ohlcv_cache WHERE ticker='AAPL' ORDER BY date DESC LIMIT 10;"
```

## ⚠️ Notas Importantes

1. **Rate Limiting**: El delay de 0.3s previene bloqueos de OpenBB
2. **Datos faltantes**: Si un ticker no tiene datos en OpenBB, se registra como error
3. **NaN handling**: Los valores NaN se convierten en NULL en la base de datos
4. **Rolling windows**: Las primeras filas tendrán menos datos para promedios móviles
5. **Market cap**: Por ahora se guarda como NULL (se puede agregar en el futuro)

## 🐛 Troubleshooting

### Error: "No data available"
- Verificar que OpenBB está instalado: `pip3 install openbb`
- Verificar credenciales de OpenBB (si aplica)
- Probar con un ticker conocido: `--tickers SPY`

### Error: "Connection timeout"
- Aumentar el delay: `--delay 1.0`
- Verificar conexión a internet

### Error: "Table ohlcv_cache not found"
- La tabla se crea automáticamente en `TickerCache`
- Verificar que `data/ticker_cache.db` existe

## 📚 Referencias

- [OpenBB Documentation](https://docs.openbb.co/)
- [Schema de ticker_cache.db](../src/data/ticker_cache.py)
- [Configuración del sistema](../config/settings.py)
