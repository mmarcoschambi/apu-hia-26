# 🚀 Cómo Poblar Datos Históricos

## ✅ Script Nuevo: `populate_historical_openbb.py`

Este es el script **RECOMENDADO** para poblar datos históricos. Reemplaza al antiguo `populate_historical_cache.py`.

### ¿Por qué usar este script?

1. ✅ **Usa OpenBB** en lugar de yfinance (datos más confiables)
2. ✅ **Calcula TODAS las métricas automáticamente**:
   - Dollar volume (dollar_volume, rolling_dollar_vol_20)
   - Volume metrics (avg_volume_20)
   - ADR en $ y % (adr_14, adr_pct_14)
   - SMAs (sma_50, sma_200)
   - Trend flags (price_above_sma50, price_above_sma200, sma50_above_sma200, trend_aligned)
3. ✅ **Todo en un solo paso** (no necesitas scripts separados)
4. ✅ **Eficiente**: omite tickers que ya tienen datos completos

---

## 📋 Comandos Rápidos

### 1️⃣ Test con 10 tickers
```bash
python3 populate_historical_openbb.py --test
```

### 2️⃣ Tickers específicos (recomendado para empezar)
```bash
python3 populate_historical_openbb.py --tickers AAPL MSFT GOOGL AMZN NVDA SPY QQQ
```

### 3️⃣ Todos los tickers del universo (completo)
```bash
python3 populate_historical_openbb.py --years 20
```

### 4️⃣ Actualizar solo últimos 2 años
```bash
python3 populate_historical_openbb.py --years 2 --no-skip
```

---

## 📊 Verificar Datos

Después de poblar, verifica que todo está correcto:

```bash
# Ver últimos datos de SPY
sqlite3 data/ticker_cache.db "SELECT ticker, date, close, adr_14, sma_50, trend_aligned FROM ohlcv_cache WHERE ticker='SPY' ORDER BY date DESC LIMIT 5;"

# Contar cuántos tickers tienes
sqlite3 data/ticker_cache.db "SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache;"

# Ver todos los tickers disponibles
sqlite3 data/ticker_cache.db "SELECT DISTINCT ticker FROM ohlcv_cache ORDER BY ticker;"
```

---

## ⚙️ Configuración

Verifica que `config/settings.py` tenga:

```python
DATA_SOURCE = "openbb"  # ✅ Debe estar en "openbb"
OPENBB_PROVIDER = "yfinance"
```

---

## 🆚 Diferencia con Scripts Anteriores

| Script | Fuente | Calcula Métricas | Status |
|--------|--------|------------------|--------|
| `populate_historical_cache.py` | yfinance | ❌ Solo OHLCV | ⚠️ Obsoleto |
| `scripts/populate_historical_metrics.py` | - | ✅ Solo métricas | ⚠️ Separado |
| **`populate_historical_openbb.py`** | **OpenBB** | **✅ Todo junto** | **✅ Usar este** |

---

## 🔄 Flujo Completo

```bash
# 1. Test con un ticker para verificar que funciona
python3 populate_historical_openbb.py --tickers SPY

# 2. Si funciona, poblar tickers principales
python3 populate_historical_openbb.py --tickers AAPL MSFT GOOGL AMZN NVDA META TSLA SPY QQQ --years 10

# 3. Verificar datos
sqlite3 data/ticker_cache.db "SELECT ticker, COUNT(*) as days FROM ohlcv_cache GROUP BY ticker;"

# 4. Si todo está bien, poblar el universo completo
python3 populate_historical_openbb.py --years 20
```

---

## 📈 Columnas en la Base de Datos

Después de ejecutar el script, cada ticker tendrá:

### OHLCV Básico
- `open`, `high`, `low`, `close`, `volume`

### Dollar Volume
- `dollar_volume`: close × volume
- `rolling_dollar_vol_20`: promedio móvil 20 días

### Volume Metrics  
- `avg_volume_20`: promedio móvil de volumen

### ADR (Average Daily Range)
- `adr_14`: ADR en $ (14 días)
- `adr_pct_14`: ADR en % (14 días)

### Moving Averages
- `sma_50`: SMA 50 días
- `sma_200`: SMA 200 días

### Trend Flags
- `price_above_sma50`: 1/0
- `price_above_sma200`: 1/0
- `sma50_above_sma200`: 1/0
- `trend_aligned`: 1/0 (todas las anteriores true)

---

## ⚡ Tips

1. **Empieza con pocos tickers** para verificar que funciona
2. **Usa --test primero** para ver el proceso
3. **El delay de 0.3s** previene rate limiting de OpenBB
4. **Los datos se guardan inmediatamente** (commit por ticker)
5. **Si se interrumpe**, puedes reiniciar y saltará los ya completados

---

## 🐛 Problemas Comunes

### "No data available"
- Verifica que OpenBB esté instalado: `pip3 install openbb`
- Prueba con un ticker conocido: `--tickers SPY`

### "Connection timeout"  
- Aumenta el delay: `--delay 1.0`
- Verifica tu conexión a internet

### Script muy lento
- Normal, OpenBB tiene rate limiting
- Para 1000 tickers son ~5 minutos
