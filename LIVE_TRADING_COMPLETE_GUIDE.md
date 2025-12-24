# LIVE TRADING SYSTEM - Guía Completa
=============================================

## 📚 **OVERVIEW**

Este sistema te permite pasar del backtest al trading en vivo con un flujo completo diario:

1. **Market Health Check** - Verifica condiciones del mercado
2. **Sector Rotation** - Identifica sectores fuertes
3. **Dynamic Scanning** - Busca oportunidades en todo el universo
4. **Pattern Detection** - Detecta Cup&Handle, Flat Base, VCP
5. **Focus List** - Genera lista de 3-5 setups con precios trigger

## 🎯 **CARACTERÍSTICAS CLAVE**

### ✅ **Cache Persistente**
- Los datos se guardan en SQLite (`data/cache/market_cache.db`)
- **Sobrevive entre sesiones** - No pierdes datos al apagar la PC
- Segunda ejecución es **mucho más rápida**
- Se puede hacer backtest desde años atrás (hasta donde tengas datos)

### ✅ **Multiprocessing**
- Usa múltiples núcleos de CPU
- Escanea 600+ tickers en minutos (no horas)
- Configurable: `--processes N`

### ✅ **Market Filters Integrados**
Antes de escanear, verifica:
- **SPX Tendencia**: SMA5 > SMA20 ✅
- **VIX**: < 20 y bajando/estable ✅
- **Volatilidad**: Baja/moderada ✅

Si el mercado no cumple → **NO genera señales** (te ahorra dinero)

### ✅ **Universo Dinámico**
- S&P 500: ~500 tickers
- NASDAQ 100: ~100 tickers
- Total: ~600 tickers únicos
- Se descarga automáticamente (no necesitas actualizar listas)

---

## 🚀 **INSTALACIÓN**

```bash
# 1. Instalar dependencias (si aún no lo hiciste)
pip install -r requirements.txt

# 2. Verificar que los scripts sean ejecutables
chmod +x live_scanner.py cache_inspector.py analyze_date_range.py
```

---

## 📖 **USO DIARIO**

### **WORKFLOW COMPLETO DEL DÍA**

#### **1. Pre-Market (8:00 AM - 9:30 AM)**

```bash
# Ejecutar el scanner en vivo
python live_scanner.py
```

Esto hace:
1. ✅ Market Health Check (SPX, VIX, volatilidad)
2. ✅ Sector Rotation (identifica los 3 sectores más fuertes)
3. ✅ Escanea ~600 tickers buscando patrones
4. ✅ Genera Focus List con precios trigger
5. ✅ Guarda CSV: `live_trading_focus_list.csv`

**Output esperado:**
```
🟢 GREEN LIGHT
Max Positions: 4

Top 3 Sectors:
  1. Technology (XLK)
  2. Communication Services (XLC)
  3. Consumer Discretionary (XLY)

Focus List: 4 setups ready

Ticker   Pattern         Current    Trigger    Stop
AAPL     Cup & Handle    $185.50    $187.60    $173.39
MSFT     Flat Base       $375.20    $378.30    $349.84
NVDA     VCP             $495.80    $501.00    $463.42
META     Cup & Handle    $355.40    $358.50    $331.35
```

#### **2. Market Open (9:30 AM)**

1. Abre tu plataforma de trading
2. Agrega los tickers de la Focus List a tu watchlist
3. Pon **alertas de precio** en los Trigger Prices

#### **3. Durante el Día**

Cuando suene una alerta:

1. **Verifica RVOL > 1.5x** (volumen relativo)
2. **Verifica que el sector esté fuerte** (mira SPY/QQQ)
3. **Si todo se alinea → EJECUTAR ENTRADA**
4. **Colocar stop loss inmediatamente**

#### **4. Final del Día**

```bash
# Actualizar posiciones activas (si las tienes)
python position_tracker.py
```

---

## 🗄️ **GESTIÓN DEL CACHE**

### **Ver qué datos tienes**

```bash
# Inspector de cache
python cache_inspector.py
```

Output:
```
📊 CACHE INSPECTOR
==================
Total Tickers en Cache: 587
Total Registros: 234,567
Rango de Fechas: 2023-01-03 → 2024-12-20
Tamaño de DB: 45.67 MB

Ticker   First Date   Last Date    Records  Last Updated
AAPL     2023-01-03   2024-12-20     1,250  2024-12-20 14:30:00
MSFT     2023-01-03   2024-12-20     1,250  2024-12-20 14:31:00
...
```

### **Analizar rango de fechas disponible**

```bash
python analyze_date_range.py
```

Output:
```
📅 DATE RANGE ANALYZER
======================
Fecha más temprana: 2023-01-03
Fecha más reciente:  2024-12-20
Total días cubiertos: 717

RECOMENDACIÓN PARA BACKTEST:
Puedes hacer backtest desde: 2023-01-03 hasta 2024-12-20
```

### **Limpiar cache (si es necesario)**

```bash
# Limpiar un ticker específico
python -c "from src.data.cache_manager import CacheManager; CacheManager().clear_ticker('AAPL')"

# Limpiar TODO el cache
python -c "from src.data.cache_manager import CacheManager; CacheManager().clear_all()"

# Optimizar DB (libera espacio)
python -c "from src.data.cache_manager import CacheManager; CacheManager().vacuum()"
```

---

## 🔄 **BACKTEST CON UNIVERSO DINÁMICO**

El cache te permite hacer backtests históricos rápidos:

```bash
# Backtest de 1 año
python backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# Backtest de 5 años (si tienes los datos)
python backtest_dynamic_universe.py --start 2020-01-01 --end 2024-12-31

# Backtest con más procesos (más rápido)
python backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --processes 8
```

**Primera ejecución:**
- Descarga datos de ~600 tickers
- Puede tardar 30-60 minutos
- Datos quedan en cache

**Segunda ejecución:**
- Lee desde cache
- **5-10 minutos** ⚡

---

## ⚙️ **OPCIONES AVANZADAS**

### **Scanner con opciones**

```bash
# Solo S&P 500
python live_scanner.py --sp500 --no-nasdaq

# Solo NASDAQ 100
python live_scanner.py --no-sp500 --nasdaq

# Usar más procesos (más rápido)
python live_scanner.py --processes 12

# Más setups en Focus List
python live_scanner.py --max-setups 10
```

### **Fechas límite para backtest**

**¿Hasta dónde puedes ir para atrás?**

Depende de tu cache. Usa:
```bash
python analyze_date_range.py
```

Para ver tu rango disponible.

**Límite teórico:**
- Yahoo Finance: ~20-25 años
- Pero calidad de datos < 2010 es dudosa
- **Recomendado: 2015 en adelante**

---

## 📊 **INTEGRACIÓN CON STREAMLIT**

### **Actualizar filtros de fecha dinámicamente**

El sistema puede actualizar automáticamente los filtros de fecha en Streamlit basándose en los datos reales disponibles:

```python
# En app.py
from src.data.cache_manager import CacheManager

cache = CacheManager()
info = cache.get_cache_info()

if len(info) > 0:
    info['first_date'] = pd.to_datetime(info['first_date'])
    info['last_date'] = pd.to_datetime(info['last_date'])
    
    min_date = info['first_date'].min()
    max_date = info['last_date'].max()
    
    # Usar en Streamlit
    start_date = st.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )
```

### **Verificar Market Health en Dashboard**

```python
from live_scanner import MarketHealthMonitor

monitor = MarketHealthMonitor(cache)
health = monitor.check_market_health()

if health['can_trade']:
    st.success(f"{health['status']} - Can trade up to {health['max_positions']} positions")
else:
    st.error(f"{health['status']} - Do not trade today")
```

---

## 🎓 **PREGUNTAS FRECUENTES**

### **1. ¿El cache sobrevive si apago la PC?**

**SÍ.** El cache se guarda en SQLite (`data/cache/market_cache.db`). Puedes apagar la PC, reiniciar, y los datos siguen ahí.

### **2. ¿Multiprocessing o Cache es mejor para performance?**

**AMBOS.**
- **Primera ejecución**: Multiprocessing reduce de 2 horas → 30 min
- **Siguientes ejecuciones**: Cache reduce de 30 min → 5 min

### **3. ¿Hasta dónde puedo ir para atrás con backtest?**

Depende de cuánto datos descargues. Yahoo Finance tiene hasta ~25 años, pero:
- **2015-2024**: Excelente calidad ✅
- **2010-2015**: Buena calidad ⚠️
- **< 2010**: Calidad dudosa, algunos tickers no existían ❌

### **4. ¿Cuántos tickers tengo en mi universo?**

```bash
python -c "from live_scanner import get_universe; u = get_universe(); print(f'Total: {len(u)} tickers')"
```

Típicamente:
- S&P 500: ~500
- NASDAQ 100: ~100
- Overlap: ~50
- **Total único: ~550-600 tickers**

### **5. ¿Cómo sé qué datos tengo y qué no?**

```bash
python cache_inspector.py
```

Te muestra ticker por ticker qué fechas tienes.

### **6. ¿El sistema está implementado en Streamlit?**

Parcialmente. Los market filters (SPX, VIX, sectores) están en el código pero **necesitas integrarlos**.

Para hacerlo, agrega en `app.py`:

```python
# Importar
from live_scanner import MarketHealthMonitor, SectorRotationAnalyzer
from src.data.cache_manager import CacheManager

# En sidebar o main
cache = CacheManager()
monitor = MarketHealthMonitor(cache)
health = monitor.check_market_health()

# Mostrar en UI
st.sidebar.subheader("Market Health")
st.sidebar.metric("Status", health['status'])
st.sidebar.metric("Max Positions", health['max_positions'])
```

---

## 📝 **RESUMEN RÁPIDO**

| Task | Command |
|------|---------|
| **Scanner diario** | `python live_scanner.py` |
| **Ver cache** | `python cache_inspector.py` |
| **Analizar fechas** | `python analyze_date_range.py` |
| **Backtest 2024** | `python backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31` |
| **Limpiar cache** | `python -c "from src.data.cache_manager import CacheManager; CacheManager().clear_all()"` |
| **Ver universo** | `python -c "from live_scanner import get_universe; print(len(get_universe()))"` |

---

## 🎯 **PRÓXIMOS PASOS**

1. **Ejecuta el scanner por primera vez** → `python live_scanner.py`
2. **Revisa el cache** → `python cache_inspector.py`
3. **Analiza fechas disponibles** → `python analyze_date_range.py`
4. **Haz un backtest histórico** → `python backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31`
5. **Integra market health en Streamlit** → Edita `app.py`

---

**¡Listo para operar en el mundo real!** 🚀
