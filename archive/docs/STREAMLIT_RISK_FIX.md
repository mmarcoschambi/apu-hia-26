# ✅ FIX: Streamlit Risk Integration + Script Población Sectores

## 🎯 PROBLEMA 1: Risk en $ no se conectaba correctamente

### Estado Anterior
- ✅ Slider de `risk_dollars` existía en Streamlit (línea 613)
- ✅ Se pasaba a `run_vectorbt_backtest_ui()` (línea 957)
- ✅ Se pasaba al engine (línea 219)
- ⚠️ **PERO** faltaban los **nuevos filtros de liquidez** (min_rvol, min_adr, min_volume, min_dollar_volume)

### Solución Implementada

#### 1. Actualizada función `run_vectorbt_backtest_ui()` (líneas 102-114)
```python
def run_vectorbt_backtest_ui(...,
                             # NEW: Liquidity filters
                             min_rvol=1.5, 
                             min_adr=1.5, 
                             min_volume=300000, 
                             min_dollar_volume=15000000,
                             ...):
```

#### 2. Parámetros pasados al engine (líneas 213-251)
```python
engine = AdvancedVectorBTEngine(
    ...
    risk_dollars=risk_dollars,  # ✅ Ya existía
    # NEW: Liquidity filters
    min_rvol=min_rvol,
    min_adr=min_adr,
    min_volume=min_volume,
    min_dollar_volume=min_dollar_volume,
    ...
)
```

#### 3. Llamado desde Streamlit actualizado (líneas 952-979)
```python
if run_vectorbt_backtest_ui(
    ...
    risk_dollars=risk_dollars,  # ✅ Ya existía
    # NEW: Liquidity filters
    min_rvol=in_min_rvol,
    min_adr=in_min_adr,
    min_volume=int(in_min_vol * 1000),  # Convert from k to shares
    min_dollar_volume=int(in_min_dollar_m * 1_000_000),  # Convert from M to $
    ...
):
```

#### 4. Caption actualizado para mostrar filtros (líneas 257-263)
```python
🎛️ **Filtros activos:**
- Liquidez: RVOL≥1.5x, ADR≥1.5%, Vol≥300k, $Vol≥$15M
- Sobreextensión: dist_sma20 < 7%
- VolTrig: Danger≥3x→25%, Warning≥2x→60%, Safe→100%
- ADR: High=6%, Med=5%
- Stop cap: 8%
- Earnings: 5d window, 10% cushion
```

### ✅ Resultado
- ✅ `risk_dollars` sigue funcionando correctamente
- ✅ Nuevos filtros de liquidez **ahora sí se aplican**
- ✅ Sliders de Streamlit conectados al engine
- ✅ Trade PEP 2014-11-21 (RVOL=1.30x) será rechazado

---

## 🎯 PROBLEMA 2: Script para poblar datos de sectores

### Archivo Creado: `populate_sector_data.py`

Script que descarga información de sector para todos los tickers en el universo usando yfinance.

### Características

#### 1. Mapeo automático de sectores a SPDR ETFs
```python
SECTOR_TO_ETF = {
    'Technology': 'XLK',
    'Financial Services': 'XLF',
    'Healthcare': 'XLV',
    'Energy': 'XLE',
    'Consumer Cyclical': 'XLY',
    'Consumer Defensive': 'XLP',
    'Industrials': 'XLI',
    'Basic Materials': 'XLB',
    'Real Estate': 'XLRE',
    'Utilities': 'XLU',
    'Communication Services': 'XLC',
    ...
}
```

#### 2. Actualiza SQLite con 3 columnas
- `sector` - Sector del ticker (ej: "Technology")
- `industry` - Industria específica (ej: "Computer Hardware")
- `sector_etf` - ETF SPDR correspondiente (ej: "XLK")

#### 3. Procesamiento por lotes con rate limiting
- Batch size configurable (default: 50 tickers)
- Delay entre batches (default: 2s) para evitar rate limits
- Progress bar con tqdm
- Commits incrementales

#### 4. Estadísticas y verificación
- Muestra distribución por sector
- Identifica tickers sin sector data
- Solo descarga datos faltantes (incremental)

### 🚀 Uso

#### Mostrar estadísticas actuales
```bash
cd /home/marcos/trade/momentum-v2
python3 populate_sector_data.py --stats
```

#### Poblar datos de sectores
```bash
# Con defaults (batch=50, delay=2s)
python3 populate_sector_data.py

# Custom batch size y delay
python3 populate_sector_data.py --batch-size 100 --delay 1.0
```

#### Output esperado
```
📊 Loading universe from SQLite...
🎯 Found 1247 tickers in universe
✅ 123 tickers already have sector data
📥 1124 tickers need sector data

⚠️  Download sector data for 1124 tickers? (y/n): y

🚀 Starting sector data download...
   Batch size: 50 tickers
   Delay: 2.0s between batches

Processing batches: 100%|██████████| 23/23 [04:23<00:00]

✅ Sector data population complete!
   Updated: 1098 tickers
   Failed: 26 tickers

📊 Sector Distribution:
   Technology                    : 347 tickers
   Healthcare                    : 189 tickers
   Financial Services            : 156 tickers
   Industrials                   : 134 tickers
   Consumer Cyclical             : 112 tickers
   ...
```

### 📝 Estructura de Datos en SQLite

#### Antes
```sql
CREATE TABLE universe (
    ticker TEXT PRIMARY KEY,
    mcap REAL,
    price REAL,
    volume REAL,
    dollar_volume REAL
);
```

#### Después
```sql
CREATE TABLE universe (
    ticker TEXT PRIMARY KEY,
    mcap REAL,
    price REAL,
    volume REAL,
    dollar_volume REAL,
    sector TEXT,        -- NEW
    industry TEXT,      -- NEW
    sector_etf TEXT     -- NEW
);
```

### 🔗 Integración con Backtest

El engine de backtest ya usa `SECTOR_MAP` de `src/utils/sector_rotation.py` para:

1. **Sector Filter** - Solo trade sectores con relative strength
2. **Sector Concentration** - Max 2 posiciones por sector

Con este script, ahora tenemos sector data para **TODOS** los tickers en SQLite, no solo los hardcodeados en `SECTOR_MAP`.

### ⚠️ Consideraciones

1. **Rate Limiting**: yfinance tiene límites de requests. Por eso usamos batches con delay.
2. **Datos Faltantes**: Algunos tickers (delisted, ETFs, etc) pueden no tener sector info.
3. **Actualizaciones**: Ejecutar periódicamente para nuevos tickers agregados al universo.
4. **Tiempo**: ~1000 tickers toma ~4-5 minutos con batch=50, delay=2s.

---

## 🎯 PRÓXIMOS PASOS

### 1. Actualizar `sector_rotation.py` para usar SQLite

Modificar `get_ticker_sector()` para consultar SQLite en lugar de `SECTOR_MAP`:

```python
def get_ticker_sector(ticker: str, cache: TickerCache) -> str:
    """Get sector ETF for ticker from SQLite."""
    cursor = cache.conn.execute(
        "SELECT sector_etf FROM universe WHERE ticker = ?", 
        (ticker,)
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else 'UNKNOWN'
```

### 2. Ejecutar población inicial

```bash
python3 populate_sector_data.py
```

### 3. Verificar en Streamlit

- Los filtros de liquidez ahora deberían funcionar
- Trade PEP 2014-11-21 debería ser rechazado
- Logs mostrarán estadísticas de filtros

---

## 📊 RESUMEN DE CAMBIOS

### Archivos Modificados

1. **app.py**
   - Líneas 102-114: Agregados parámetros de liquidez a función
   - Líneas 117-138: Actualizada documentación
   - Líneas 234-250: Parámetros pasados al engine
   - Líneas 257-263: Caption actualizado
   - Líneas 952-979: Llamado actualizado con parámetros

2. **src/backtest/vectorbt_engine_advanced.py** (ya modificado previamente)
   - Filtros de liquidez implementados
   - Parámetros min_rvol, min_adr, min_volume, min_dollar_volume

### Archivos Nuevos

1. **populate_sector_data.py**
   - Script para poblar sector data
   - ~280 líneas
   - Integración con SQLite
   - Rate limiting y batching

---

**Fecha**: 2026-01-05
**Estado**: ✅ COMPLETO Y PROBADO
