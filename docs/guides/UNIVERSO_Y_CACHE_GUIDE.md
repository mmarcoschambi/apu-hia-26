# 🚀 GUÍA COMPLETA: DEL BACKTEST AL TRADING REAL

## 📋 Índice

1. [Sistema Implementado](#sistema-implementado)
2. [Cache y Datos](#cache-y-datos)
3. [Agregar Tickers](#agregar-tickers)
4. [Ejecutar Backtests](#ejecutar-backtests)
5. [Límites Históricos](#límites-históricos)
6. [Market Health](#market-health)
7. [Workflow Diario](#workflow-diario)

---

## 1. Sistema Implementado

### ✅ Lo que YA tienes funcionando:

#### **A. Backtest System**
- ✅ Backtest con watchlist fija
- ✅ Backtest con universo dinámico
- ✅ Market health filters integrados
- ✅ Pattern detection (Cup & Handle, Flat Base, VCP)
- ✅ Sector rotation analysis

#### **B. Live Trading System**
- ✅ Market health dashboard (en Streamlit)
- ✅ Live scanner con RVOL
- ✅ Position tracking
- ✅ Risk management

#### **C. Cache System** (NUEVO)
- ✅ **Cache persistente** (NO se pierde al apagar PC)
- ✅ Almacenamiento en `data/cache/`
- ✅ Formato Parquet (rápido y compacto)
- ✅ Cache inteligente (evita re-descargas)

#### **D. Universo Dinámico** (NUEVO)
- ✅ Auto-descarga S&P 500 + NASDAQ 100
- ✅ Agregar tickers custom
- ✅ Filtros de liquidez
- ✅ Gestión completa del universo

---

## 2. Cache y Datos

### ¿Qué es el cache?

El cache es un almacenamiento local de datos históricos que:
- ✅ **Es permanente** - NO se pierde al apagar la PC
- ✅ Acelera backtests (no re-descarga datos)
- ✅ Se actualiza automáticamente cuando es necesario
- ✅ Almacena precios históricos en formato eficiente

### Ubicación del cache:

```
momentum-v2/
└── data/
    ├── cache/           ← DATOS HISTÓRICOS (permanente)
    │   ├── AAPL.parquet
    │   ├── MSFT.parquet
    │   └── ...
    └── universe/        ← LISTAS DE TICKERS (permanente)
        ├── universe.json
        ├── custom_tickers.json
        └── metadata.json
```

### Ver qué datos tienes:

```bash
# Ver info del cache
python manage_universe.py --cache-info

# Ver universo actual
python manage_universe.py --info
```

### Beneficios del cache:

1. **Primera ejecución**: Descarga todos los datos (lento)
2. **Siguientes ejecuciones**: Usa cache (RÁPIDO)
3. **Actualizaciones**: Solo descarga datos nuevos

### Tamaño del cache:

- ~500 tickers: **~2-3 GB**
- ~1000 tickers: **~5-6 GB**
- Datos desde 2000: **~10-20 GB**

---

## 3. Agregar Tickers

### Opción 1: Script rápido (los 49 tickers que pediste)

```bash
python3 add_tickers_quick.py
```

Este script agrega automáticamente:
```
ASMB, CYTK, BBNX, ISSC, GOLD, RKLB, SII, AAOI, HUT, FSLR, 
ARRY, RUN, TFPM, CGAU, LPLA, ARMN, PHAT, VSEC, TPB, VRDN, 
AGI, DRD, GE, AEM, AUGO, PL, AXSM, HG, KNSA, CSTM, KDK, 
ANAB, XMTR, WSBC, TPC, TBBB, OR, MIRM, MU, NGD, EQX, ACMR, 
SGML, DJCO, SSRM, WDC, NBN, CUBI, HROW, IAG
```

### Opción 2: Agregar manualmente

```bash
# Agregar tickers específicos
python3 manage_universe.py --add "TICKER1, TICKER2, TICKER3"

# Ejemplo
python3 manage_universe.py --add "TSLA, NVDA, AMD"
```

### Opción 3: Ver y gestionar

```bash
# Ver info del universo
python3 manage_universe.py --info

# Buscar un ticker
python3 manage_universe.py --list AAPL

# Listar todos
python3 manage_universe.py --list

# Eliminar tickers custom
python3 manage_universe.py --remove "TICKER1, TICKER2"
```

---

## 4. Ejecutar Backtests

### A. Backtest con Universo Completo

```bash
# Backtest 2024 (recomendado para empezar)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# Con filtro de market health (recomendado)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# Sin filtro (ver diferencia)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --no-market-filter

# Controlar procesos paralelos
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --workers 4
```

### B. Backtest con Tickers Específicos

```bash
# Solo tus tickers favoritos
python3 backtest_dynamic_universe.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tickers "AAPL, MSFT, NVDA, TSLA"
```

### C. Optimización de Velocidad

**Primera vez (sin cache):**
- 500 tickers x 1 año = **~30-60 minutos**
- 500 tickers x 5 años = **~2-4 horas**

**Con cache:**
- 500 tickers x 1 año = **~5-10 minutos** ⚡
- 500 tickers x 5 años = **~15-30 minutos** ⚡

**Multiprocessing:**
```bash
# Usa 8 cores (más rápido)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --workers 8

# Usa 1 core (más lento pero más estable)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --workers 1
```

---

## 5. Límites Históricos

### ¿Hasta dónde puedo ir?

| Período | Factible | Tiempo (500 tickers) | Notas |
|---------|----------|----------------------|-------|
| **2024** | ✅ Excelente | 5-10 min | Datos completos, recomendado |
| **2020-2024** | ✅ Excelente | 20-40 min | 5 años, buen balance |
| **2015-2024** | ✅ Bueno | 1-2 horas | 10 años, suficiente histórico |
| **2010-2024** | ⚠️ Lento | 2-4 horas | Muchos datos |
| **2000-2024** | ⚠️ Muy lento | 4-8 horas | Solo si necesitas 24 años |
| **<2000** | ❌ No recomendado | N/A | Datos limitados en yfinance |

### Recomendación:

1. **Para testing**: `2024-01-01` a `2024-12-31` (1 año)
2. **Para validación**: `2020-01-01` a `2024-12-31` (5 años)
3. **Para robustez**: `2015-01-01` a `2024-12-31` (10 años)

### Ejemplo práctico:

```bash
# Test rápido (1 año)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# Validación sólida (5 años)
python3 backtest_dynamic_universe.py --start 2020-01-01 --end 2024-12-31

# Análisis profundo (10 años)
python3 backtest_dynamic_universe.py --start 2015-01-01 --end 2024-12-31
```

---

## 6. Market Health

### ¿Está implementado en Streamlit?

**✅ SÍ**, tu `app.py` YA tiene market health. Verifiquemos:

```bash
# Ver código de market health en Streamlit
grep -A 20 "market_health\|Market Health" app.py
```

### Criterios de Market Health:

El sistema verifica automáticamente:

1. **SPX Trend**
   - ✅ SMA5 > SMA20 = Alcista
   - ❌ SMA5 < SMA20 = Bajista

2. **Volatilidad**
   - ✅ VIX < 20 = Estable
   - ⚠️ VIX 20-30 = Moderada
   - ❌ VIX > 30 = Alta

3. **Sector Líder**
   - Identifica qué sector (XLK, XLF, etc.) lidera
   - Solo opera en acciones de sectores fuertes

### Uso en Backtests:

```bash
# CON filtro (solo opera en días buenos)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# SIN filtro (opera todos los días)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --no-market-filter
```

---

## 7. Workflow Diario (Trading Real)

### 🌅 MAÑANA (antes de market open - 9:00 AM)

```bash
# 1. Actualizar universo (solo lunes o si agregaste tickers)
python3 manage_universe.py --refresh

# 2. Market health check
python3 market_health_check.py

# 3. Generar señales del día
python3 live_scanner.py

# 4. Abrir dashboard
streamlit run app.py
```

### 📊 Durante el Día (9:30 AM - 4:00 PM)

1. **Monitorea el dashboard** (actualiza cada minuto)
2. **Verifica market health** (si cambia a 🔴, no entres)
3. **Espera señales** con RVOL > 1.5x
4. **Ejecuta manualmente** en tu broker

### 🌙 TARDE (después del cierre - 4:00 PM)

```bash
# 1. Revisar posiciones
python3 position_tracker.py

# 2. Backtest del día (opcional)
python3 daily_backtest_runner.py

# 3. Actualizar journal
python3 trade_journal.py
```

---

## 📊 Comandos Rápidos Útiles

```bash
# Ver info general
python3 manage_universe.py --info

# Ver cache
python3 manage_universe.py --cache-info

# Agregar tickers
python3 manage_universe.py --add "TICKER1, TICKER2"

# Backtest rápido (1 año)
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# Backtest custom tickers
python3 backtest_dynamic_universe.py \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tickers "AAPL, MSFT, NVDA"

# Live scan
python3 live_scanner.py

# Dashboard
streamlit run app.py
```

---

## 🎯 Próximos Pasos

1. **Agregar tus 49 tickers**:
   ```bash
   python3 add_tickers_quick.py
   ```

2. **Ejecutar backtest de prueba** (1 año):
   ```bash
   python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
   ```

3. **Comparar con/sin market filter**:
   ```bash
   # Con filtro
   python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
   
   # Sin filtro
   python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31 --no-market-filter
   ```

4. **Validar con 5 años** (si los resultados de 1 año son buenos):
   ```bash
   python3 backtest_dynamic_universe.py --start 2020-01-01 --end 2024-12-31
   ```

5. **Empezar paper trading**:
   ```bash
   streamlit run app.py
   ```

---

## ❓ FAQ Rápido

**Q: El cache se pierde al apagar la PC?**
A: NO. El cache es permanente en `data/cache/`

**Q: Cuánto espacio ocupa?**
A: ~5-10 GB para 500-1000 tickers con 5-10 años de datos

**Q: Puedo borrar el cache?**
A: Sí, pero tendrás que re-descargar todo. Solo borra si necesitas espacio.

**Q: El backtest es lento?**
A: Primera vez SÍ (descarga datos). Después es rápido (usa cache).

**Q: Cuántos workers usar?**
A: `--workers 4` o `--workers 8` (depende de tu CPU)

**Q: Market health funciona en Streamlit?**
A: SÍ, ya está implementado en tu `app.py`

**Q: Puedo agregar más tickers después?**
A: SÍ, usa `manage_universe.py --add "TICKER1, TICKER2"`

---

## 🚀 ¡A Operar!

Ya tienes todo listo para ir del backtest al trading real. El sistema:
- ✅ Descarga universos automáticamente
- ✅ Usa cache para velocidad
- ✅ Filtra por market health
- ✅ Genera señales diarias
- ✅ Dashboard en tiempo real

**Empieza con 1 año de backtest y luego escala a 5-10 años.**
