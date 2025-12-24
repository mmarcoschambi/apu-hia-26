# 📚 ÍNDICE DE DOCUMENTACIÓN - LIVE TRADING SYSTEM

## 🚀 **EMPIEZA AQUÍ**

Si es tu primera vez, lee en este orden:

1. **START_HERE_LIVE.md** ← **EMPIEZA AQUÍ**
   - Resumen ejecutivo
   - 196 tickers en el universo
   - Comandos esenciales
   - Quick start

2. **FAQ.md** ← **PREGUNTAS FRECUENTES**
   - Respuestas rápidas
   - Troubleshooting
   - Ejemplos de uso

3. **LIVE_TRADING_COMPLETE_GUIDE.md** ← **GUÍA DETALLADA**
   - Explicación profunda de cada módulo
   - Workflow día a día
   - Opciones avanzadas
   - Integración con Streamlit

---

## 📋 **GUÍAS POR CATEGORÍA**

### **Operación Diaria**
- `START_HERE_LIVE.md` - Inicio rápido
- `FAQ.md` - Preguntas frecuentes
- `morning_scan.sh` - Script automático para cada mañana

### **Técnicas**
- `LIVE_SYSTEM_SUMMARY.md` - Resumen técnico del sistema
- `LIVE_TRADING_COMPLETE_GUIDE.md` - Documentación completa
- `CACHE_MANAGEMENT_GUIDE.md` - Gestión del cache

### **Backtest**
- `DYNAMIC_BACKTEST_GUIDE.md` - Backtest con universo dinámico
- `BACKTESTING.md` - Guía general de backtesting
- `VALIDATION_GUIDE.md` - Validación de resultados

### **Patrones**
- `PATTERN_DETECTION_GUIDE.md` - Detección de patrones
- `BASE_DETECTION_SYSTEM.md` - Sistema de detección de bases
- `TRADE_LIFECYCLE_MASTERCLASS.md` - Ciclo de vida completo

### **Filtros de Mercado**
- `MARKET_FILTERS.md` - Filtros de mercado
- `ENHANCED_MARKET_FILTERS.md` - Filtros avanzados
- `TREND_FILTER_GUIDE.md` - Filtro de tendencia

---

## 🛠️ **SCRIPTS PRINCIPALES**

| Script | Descripción | Comando |
|--------|-------------|---------|
| `live_scanner.py` | Scanner completo de trading | `python3 live_scanner.py --static` |
| `morning_scan.sh` | Workflow automático matutino | `./morning_scan.sh` |
| `cache_inspector.py` | Inspeccionar cache | `python3 cache_inspector.py` |
| `analyze_date_range.py` | Ver fechas disponibles | `python3 analyze_date_range.py` |
| `show_universe.py` | Ver universo de tickers | `python3 show_universe.py` |
| `backtest_dynamic_universe.py` | Backtest dinámico | `python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31` |

---

## 📂 **ARCHIVOS DE DATOS**

| Archivo | Descripción |
|---------|-------------|
| `universe_tickers.txt` | 196 tickers del universo |
| `data/cache/market_cache.db` | Cache persistente (SQLite) |
| `live_trading_focus_list.csv` | Focus list generada diariamente |
| `active_positions.json` | Posiciones activas |

---

## 🔍 **BÚSQUEDA RÁPIDA**

### **¿Necesitas...?**

**Empezar a usar el sistema**
→ Lee: `START_HERE_LIVE.md`
→ Ejecuta: `./morning_scan.sh`

**Resolver un problema**
→ Lee: `FAQ.md`
→ Sección: Troubleshooting

**Entender cómo funciona**
→ Lee: `LIVE_TRADING_COMPLETE_GUIDE.md`
→ Lee: `LIVE_SYSTEM_SUMMARY.md`

**Ver qué datos tienes**
→ Ejecuta: `python3 cache_inspector.py`
→ Ejecuta: `python3 analyze_date_range.py`

**Hacer un backtest histórico**
→ Lee: `DYNAMIC_BACKTEST_GUIDE.md`
→ Ejecuta: `python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31`

**Integrar con Streamlit**
→ Lee: `LIVE_TRADING_COMPLETE_GUIDE.md` (sección "Integración con Streamlit")
→ Lee: `FAQ.md` (preguntas 3 y 10)

**Entender los patrones**
→ Lee: `PATTERN_DETECTION_GUIDE.md`
→ Lee: `BASE_DETECTION_SYSTEM.md`

**Optimizar performance**
→ Lee: `OPTIMIZATION_GUIDE.md`
→ Usa: `--processes 8` en el scanner

---

## 📊 **FLUJO DE TRABAJO RECOMENDADO**

```
┌─────────────────────────────────────────────────────────────────┐
│                      CADA MAÑANA (8:00 AM)                       │
├─────────────────────────────────────────────────────────────────┤
│  ./morning_scan.sh                                               │
│                                                                   │
│  ↓                                                                │
│  1. Market Health Check (SPX, VIX, volatilidad)                 │
│  2. Sector Rotation (top 3 sectores)                            │
│  3. Pattern Scanning (196 tickers)                              │
│  4. Focus List Generation (3-5 setups)                          │
│  5. CSV guardado: live_trading_focus_list.csv                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   PREPARAR PLATAFORMA (8:30 AM)                  │
├─────────────────────────────────────────────────────────────────┤
│  1. Abrir plataforma de trading                                  │
│  2. Agregar tickers de Focus List a watchlist                   │
│  3. Poner alertas en precios Trigger                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    MARKET OPEN (9:30 AM)                         │
├─────────────────────────────────────────────────────────────────┤
│  Esperar señales...                                              │
│                                                                   │
│  Cuando suene alerta:                                            │
│  1. Verificar RVOL > 1.5x                                        │
│  2. Verificar sector fuerte                                      │
│  3. EJECUTAR ENTRADA                                             │
│  4. Colocar stop loss                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 **COMANDOS MÁS USADOS**

```bash
# 1. Workflow completo matutino
./morning_scan.sh

# 2. Ver universo
python3 show_universe.py

# 3. Ver cache
python3 cache_inspector.py

# 4. Scanner manual
python3 live_scanner.py --static

# 5. Scanner rápido (más procesos)
python3 live_scanner.py --static --processes 8

# 6. Backtest 2024
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31

# 7. Ver fechas disponibles
python3 analyze_date_range.py

# 8. Limpiar cache (si es necesario)
python3 -c "from src.data.cache_manager import CacheManager; CacheManager().clear_all()"
```

---

## 📖 **GLOSARIO**

| Término | Significado |
|---------|-------------|
| **Market Health** | Estado del mercado (SPX, VIX, volatilidad) |
| **Sector Rotation** | Análisis de qué sectores están más fuertes |
| **Pattern Detection** | Búsqueda de Cup&Handle, Flat Base, VCP |
| **Focus List** | Lista de 3-5 setups listos para operar |
| **Trigger Price** | Precio donde ejecutar entrada |
| **RVOL** | Relative Volume (volumen relativo) |
| **Cache** | Base de datos local de precios históricos |
| **Universe** | Conjunto de 196 tickers que se escanean |

---

## 🆘 **SOPORTE**

Si tienes problemas:

1. **Lee FAQ.md** - Troubleshooting section
2. **Verifica que instalaste dependencias**: `pip install -r requirements.txt`
3. **Verifica que estás en el directorio correcto**: `cd /home/marcos/trade/momentum-v2`
4. **Revisa los logs** del scanner para errores específicos

---

## ✅ **CHECKLIST DE VERIFICACIÓN**

Antes de usar en vivo, verifica:

- [ ] Dependencias instaladas: `pip install -r requirements.txt`
- [ ] Scripts ejecutables: `chmod +x *.sh *.py`
- [ ] Universo cargado: `python3 show_universe.py` muestra 196 tickers
- [ ] Scanner funciona: `python3 live_scanner.py --static`
- [ ] Cache funciona: `python3 cache_inspector.py`
- [ ] Fechas disponibles: `python3 analyze_date_range.py`

---

**¿Listo para empezar?**

```bash
./morning_scan.sh
```

**¡Buena suerte! 🚀**
