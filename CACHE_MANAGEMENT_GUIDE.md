# 📦 CACHE MANAGEMENT GUIDE

Guía completa para gestionar y verificar tus datos en cache.

---

## 🔍 ¿QUÉ ES EL CACHE?

El sistema guarda los datos históricos descargados en:

```
/home/marcos/trade/momentum-v2/data/cache/
```

Esto evita descargar los mismos datos una y otra vez, **ahorrando tiempo y ancho de banda**.

---

## 📊 VERIFICAR EL CACHE

### 1️⃣ Resumen General

Ver estadísticas generales del cache:

```bash
python3 inspect_cache.py
```

**Output:**
```
📦 CACHE SUMMARY
════════════════════════════════════════════
📁 Cache directory: /home/marcos/trade/momentum-v2/data/cache
📊 Total files: 154
💾 Total size: 2.74 MB
📈 Tickers cached: 44

🎯 Sample tickers:
   AAPL, AGI, ALAB, APGE, APP, ASTS, AXSM...
```

**Información que ves:**
- Total de archivos en cache
- Espacio ocupado
- Número de tickers almacenados
- Lista de tickers disponibles

---

### 2️⃣ Inspeccionar Ticker Específico

Ver datos detallados de un ticker:

```bash
python3 inspect_cache.py --ticker AAPL
```

**Output:**
```
📊 INSPECTING: AAPL
════════════════════════════════════════════

✅ DAILY DATA:
   File: AAPL_daily.pkl
   Range: 2020-12-22 → 2025-12-19
   Total bars: 1255
   Missing days: 49 (3.8%)
   Completeness: 96.2%
   Size: 0.07 MB
   Last updated: 1 days ago
   Columns: Open, High, Low, Close, Volume, dividend

   Last 5 bars:
                  Open        High         Low       Close     Volume
   2025-12-15  280.15      280.15      272.84      274.11   50409100
   2025-12-16  272.82      275.50      271.79      274.61   37648600
   ...
```

**Información detallada:**
- ✅ **Range**: Fechas disponibles (desde → hasta)
- ✅ **Total bars**: Número de barras diarias
- ✅ **Missing days**: Días faltantes (weekends/holidays no cuentan)
- ✅ **Completeness**: % de datos completos
- ✅ **Last updated**: Antigüedad del cache
- ✅ **Preview**: Últimas 5 barras

---

### 3️⃣ Verificar Preparación para Backtest

Antes de correr un backtest largo, verifica que tienes todos los datos:

```bash
# Ejemplo: verificar si tienes datos para backtest 2020-2024
python3 inspect_cache.py --check-backtest 2020-01-01 2024-12-31 "AAPL,MSFT,GOOGL,TSLA"
```

**Output:**
```
🔍 BACKTEST READINESS CHECK
════════════════════════════════════════════
Period: 2020-01-01 → 2024-12-31
Tickers to check: 4
════════════════════════════════════════════

✅ READY: 3/4 (75.0%)
⚠️  INCOMPLETE: 1
❌ MISSING: 0

⚠️  INCOMPLETE TICKERS:
   TSLA: Has 2021-06-15 → 2024-12-20, needs 2020-01-01 → 2024-12-31
```

**Interpretación:**
- ✅ **READY**: Ticker tiene todos los datos necesarios
- ⚠️ **INCOMPLETE**: Ticker tiene datos, pero no cubre todo el rango
- ❌ **MISSING**: Ticker no está en cache

---

## 📥 DESCARGAR DATOS FALTANTES

### Descargar datos de un ticker:

```bash
# Download desde 2020 hasta hoy
python3 inspect_cache.py --download AAPL

# Download rango específico
python3 inspect_cache.py --download AAPL --start 2020-01-01 --end 2024-12-31
```

**Output:**
```
📥 Downloading AAPL...
   ✅ Downloaded 1255 bars
   Range: 2020-01-01 → 2024-12-31
```

---

## 🕐 DURACIÓN DEL CACHE

### ¿Cuánto dura el cache?

El cache **NO expira automáticamente**. Los archivos permanecen hasta que:

1. ✅ **Los borras manualmente**
2. ✅ **Los actualizas descargando de nuevo**
3. ✅ **Reinicias tu PC** (NO, el cache persiste)

### ¿Cuándo actualizar?

- **Diariamente**: Si operas en vivo, actualiza cada día
- **Semanalmente**: Para backtesting histórico
- **Bajo demanda**: Solo cuando necesites datos nuevos

---

## 🗑️ LIMPIAR CACHE

### Borrar cache completo:

```bash
rm -rf data/cache/*.pkl
```

### Borrar ticker específico:

```bash
rm data/cache/AAPL_*.pkl
```

### Borrar datos antiguos (>30 días):

```bash
find data/cache -name "*.pkl" -mtime +30 -delete
```

---

## 💡 TIPS Y BEST PRACTICES

### 1️⃣ **Cache Selectivo**

No necesitas tener TODO el mercado en cache. Solo descarga lo que vas a usar:

```bash
# Descargar solo tu watchlist
for ticker in AAPL MSFT GOOGL TSLA NVDA; do
    python3 inspect_cache.py --download $ticker
done
```

### 2️⃣ **Verificar Antes de Backtests Largos**

Antes de correr un backtest de años, verifica el cache:

```bash
python3 inspect_cache.py --ticker AAPL
```

Si ves "Last updated: 30 days ago" → considera actualizar.

### 3️⃣ **Cache vs Network**

| Operación | Sin Cache | Con Cache |
|-----------|-----------|-----------|
| Backtest 1 año | ~10 min | ~30 seg |
| Backtest 5 años | ~45 min | ~2 min |
| Scan diario | ~5 min | ~10 seg |

**El cache es CRÍTICO para backtests largos.**

### 4️⃣ **Datos Faltantes (Gaps)**

Si ves "Missing days: 50 (4%)" → **es NORMAL**.

Causas comunes:
- Weekends (no trading)
- Holidays (mercado cerrado)
- Suspensiones de trading
- IPO reciente

**<5% de gaps = OK**
**>10% de gaps = Revisar**

---

## 🔧 COMANDOS RÁPIDOS

```bash
# Ver resumen
python3 inspect_cache.py

# Inspeccionar AAPL
python3 inspect_cache.py --ticker AAPL

# Descargar TSLA
python3 inspect_cache.py --download TSLA

# Verificar readiness para backtest
python3 inspect_cache.py --check-backtest 2024-01-01 2024-12-31 "AAPL,MSFT"

# Borrar todo
rm -rf data/cache/*.pkl

# Ver tamaño del cache
du -sh data/cache/
```

---

## ❓ FAQ

### ¿El cache consume mucho espacio?

**NO.** Típicamente:
- 1 ticker = ~50-100 KB
- 100 tickers = ~5-10 MB
- 500 tickers = ~25-50 MB

**Muy liviano.**

### ¿El cache se sincroniza entre sesiones?

**SÍ.** El cache persiste en disco. Si cierras la terminal y vuelves mañana, los datos siguen ahí.

### ¿Puedo usar el cache en múltiples scripts?

**SÍ.** Todos los scripts del proyecto comparten el mismo cache:
- `backtest_dynamic_universe.py`
- `live_trading_scanner.py`
- `app.py` (Streamlit)

### ¿Qué pasa si descargo datos duplicados?

Se **sobrescriben** los archivos existentes. No hay duplicados.

### ¿Puedo tener múltiples caches?

Sí, pero NO es recomendado. El cache está definido en `src/data/market_data.py`:

```python
self.cache_dir = cache_dir or Path("./data/cache")
```

---

## 🚀 WORKFLOW RECOMENDADO

### Para Backtesting:

1. **Verificar cache**:
   ```bash
   python3 inspect_cache.py
   ```

2. **Inspeccionar tickers clave**:
   ```bash
   python3 inspect_cache.py --ticker AAPL
   ```

3. **Descargar faltantes** (si es necesario):
   ```bash
   python3 inspect_cache.py --download AAPL
   ```

4. **Correr backtest**:
   ```bash
   python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
   ```

### Para Live Trading:

1. **Actualizar cache diariamente**:
   ```bash
   # Poner en cron job o script matutino
   for ticker in $(cat watchlist.txt); do
       python3 inspect_cache.py --download $ticker
   done
   ```

2. **Verificar antes de trading**:
   ```bash
   python3 inspect_cache.py --ticker AAPL
   # Debe mostrar: Last updated: 0 days ago
   ```

---

## 📈 RESUMEN

| Comando | Uso |
|---------|-----|
| `python3 inspect_cache.py` | Ver resumen general |
| `--ticker AAPL` | Inspeccionar ticker |
| `--download AAPL` | Descargar datos |
| `--check-backtest START END TICKERS` | Verificar readiness |
| `rm -rf data/cache/*.pkl` | Limpiar todo |

**El cache es tu aliado para backtests rápidos. ¡Úsalo sabiamente!** 🚀

---

