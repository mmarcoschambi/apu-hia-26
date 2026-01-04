# ❓ FAQ - RESPUESTAS RÁPIDAS

## 🎯 **PREGUNTAS PRINCIPALES**

### **1. ¿Cómo empiezo a usar esto para el día a día?**
```bash
./morning_scan.sh
```
O manualmente:
```bash
python3 live_scanner.py --static
```

---

### **2. ¿El mercado se verifica automáticamente (SPX, VIX, sectores)?**
✅ **SÍ, automáticamente.**

El scanner verifica:
- SPX en tendencia alcista (SMA5 > SMA20)
- VIX < 20 y estable/bajando
- Volatilidad realizada baja
- **Si el mercado no cumple → NO genera señales**

---

### **3. ¿Esto está en la app de Streamlit?**
⚠️ **No todavía, pero es fácil agregarlo.**

Agrega en `app.py`:
```python
from live_scanner import MarketHealthMonitor
from src.data.cache_manager import CacheManager

cache = CacheManager()
monitor = MarketHealthMonitor(cache)
health = monitor.check_market_health()

# En sidebar
st.sidebar.subheader("🚦 Market Health")
st.sidebar.metric("Status", health['status'])
st.sidebar.metric("Max Positions", health['max_positions'])
```

---

### **4. ¿El backtest busca oportunidades como en el mundo real?**
✅ **SÍ, exactamente.**

El backtest dinámico:
- Cada día busca oportunidades en todo el universo
- Usa precios reales de ese día
- Simula cómo operarías en vivo
- **No usa watchlist fija** (más realista)

```bash
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
```

---

### **5. ¿Multiprocessing o cache es mejor?**
✅ **AMBOS. Se complementan.**

| Tecnología | Beneficio | Cuándo se usa |
|------------|-----------|---------------|
| **Multiprocessing** | Escanea 196 tickers en paralelo | Siempre (automático) |
| **Cache** | Evita re-descargar datos | Segunda ejecución en adelante |

**Resultado:**
- Primera vez: 20-40 minutos
- Segunda vez: 2-5 minutos (10x más rápido)

---

### **6. ¿Hasta dónde puedo hacer backtest?**
✅ **Hasta donde tengas datos.**

Verifica tu rango:
```bash
python3 analyze_date_range.py
```

**Límites:**
- Yahoo Finance: hasta ~25 años
- Calidad recomendada: **2015-2024**
- Antes de 2010: datos pueden ser incompletos

---

### **7. ¿El cache sobrevive si apago la PC?**
✅ **SÍ.**

Se guarda en: `data/cache/market_cache.db` (SQLite)
- Sobrevive reinicios
- Sobrevive apagados
- Sobrevive crashes
- **Permanente hasta que lo borres manualmente**

---

### **8. ¿Cómo sé qué datos tengo y cuáles no?**
```bash
python3 cache_inspector.py
```

Output muestra:
- Qué tickers están en cache
- Rango de fechas por ticker
- Última actualización
- Tamaño de DB

---

### **9. ¿Cuántos tickers tengo en mi universo?**
```bash
python3 show_universe.py
```

**Respuesta: 196 tickers**

Incluye:
- FAANG (AAPL, MSFT, GOOGL, AMZN, META)
- Tech giants (NVDA, TSLA, ORCL, etc.)
- Blue chips (BRK.B, JPM, V, MA, etc.)
- Todos los sectores principales

---

### **10. ¿Los filtros de fecha en Streamlit se actualizan solos?**
⚠️ **No automáticamente, pero puedes implementarlo.**

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
    
    # Usar en date_input
    start_date = st.date_input(
        "Start Date",
        value=min_date,
        min_value=min_date,
        max_value=max_date
    )
```

---

## 🔧 **COMANDOS ÚTILES**

| Necesito... | Comando |
|-------------|---------|
| **Escanear hoy** | `./morning_scan.sh` |
| **Ver universo** | `python3 show_universe.py` |
| **Ver cache** | `python3 cache_inspector.py` |
| **Ver fechas** | `python3 analyze_date_range.py` |
| **Backtest 2024** | `python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31` |
| **Limpiar cache** | `python3 -c "from src.data.cache_manager import CacheManager; CacheManager().clear_all()"` |
| **Más rápido** | `python3 live_scanner.py --static --processes 8` |

---

## 📊 **EJEMPLO DE OUTPUT DEL SCANNER**

```
🚦 STEP 1: MARKET HEALTH CHECK
Status: 🟢 GREEN LIGHT
Score: 6/7
  ✅ SPX en tendencia ALCISTA
  ✅ VIX BAJO (15.2)
  ✅ VIX ESTABLE/BAJANDO
  ✅ Volatilidad BAJA (12.3%)

Can Trade: YES
Max Positions: 4

🔄 STEP 2: SECTOR ROTATION ANALYSIS
Sector                          5d %    20d %    60d %   Score
Technology                      2.50%    8.30%   15.20%   4/4 🔥
Communication Services          1.80%    6.10%   12.40%   4/4 🔥
Consumer Discretionary          1.20%    4.50%    9.80%   4/4 🔥

🎯 Top 3 Sectors:
  1. Technology (XLK)
  2. Communication Services (XLC)
  3. Consumer Discretionary (XLY)

🔍 STEP 4: PATTERN SCANNING
Scanning 196 tickers...
✅ Found 45 candidates

🎯 STEP 5: FOCUS LIST GENERATION
✅ 4 setups ready for today:

Ticker   Pattern         Current    Trigger    Stop
AAPL     Cup & Handle    $185.50    $187.60    $173.39
MSFT     Flat Base       $375.20    $378.30    $349.84
NVDA     VCP             $495.80    $501.00    $463.42
META     Cup & Handle    $355.40    $358.50    $331.35

💾 Focus list saved to: live_trading_focus_list.csv
```

---

## 🚨 **TROUBLESHOOTING**

### **"ModuleNotFoundError"**
```bash
pip install -r requirements.txt
```

### **"No module named 'src'"**
```bash
cd /home/marcos/trade/momentum-v2
python3 live_scanner.py --static
```

### **Scanner toma mucho tiempo**
```bash
# Usa más procesos
python3 live_scanner.py --static --processes 8
```

### **Universo vacío o muy pequeño**
Verifica que `universe_tickers.txt` existe:
```bash
ls -la universe_tickers.txt
cat universe_tickers.txt | head -20
```

### **Cache vacío**
Normal en la primera ejecución. El scanner lo llenará automáticamente.

---

## 📚 **DOCUMENTOS CLAVE**

| Documento | Para qué sirve |
|-----------|----------------|
| `START_HERE_LIVE.md` | **EMPIEZA AQUÍ** - Guía rápida |
| `LIVE_TRADING_COMPLETE_GUIDE.md` | Guía detallada completa |
| `LIVE_SYSTEM_SUMMARY.md` | Resumen técnico |
| `FAQ.md` | Este documento - respuestas rápidas |

---

## 🎓 **PRÓXIMOS PASOS**

### **Ahora mismo:**
```bash
./morning_scan.sh
```

### **Mañana:**
```bash
./morning_scan.sh
```
(Será 10x más rápido por el cache)

### **Para producción:**
Programa ejecución automática:
```bash
# Linux/Mac - Crontab
0 8 * * 1-5 cd /home/marcos/trade/momentum-v2 && ./morning_scan.sh
```

### **Para Streamlit:**
1. Abre `app.py`
2. Copia el código de Market Health (ver pregunta 3)
3. Guarda y ejecuta: `streamlit run app.py`

---

## 💡 **TIP FINAL**

**El flujo diario más simple:**

1. **8:00 AM** → `./morning_scan.sh`
2. **8:05 AM** → Revisar `live_trading_focus_list.csv`
3. **8:10 AM** → Agregar tickers a tu plataforma
4. **9:30 AM** → Market open, esperar señales

**¡Eso es todo!** 🚀

---

**Última actualización:** 2024-12-23
