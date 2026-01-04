# 📚 Inventario de Scripts del Sistema

## 🎯 Scripts de Producción (USAR ESTOS)

### 🚀 Trading en Vivo
- **`live_scanner.py`** (698 líneas) - Sistema completo de trading diario con escaneo pre-market, análisis intraday, y generación de alertas. Incluye risk management y tracking de posiciones. **USAR ESTE** para tu flujo diario completo.

- **`live_trading_scanner.py`** (245 líneas) - Scanner más simple enfocado en pre-market y detección de setups. Usa OpenBB. **Alternativa ligera** si solo quieres el escaneo rápido.

- **`live_scanner_avwap.py`** (503 líneas) - Scanner especializado en AVWAP, genera Focus List al cierre del mercado. Usa yfinance. **Para generación de watchlist EOD**.

- **`position_tracker.py`** (341 líneas) - Tracking de posiciones abiertas con P&L en tiempo real. **Esencial** para gestión de trades activos.

### 📊 Backtesting  
- **`backtest_dynamic_universe.py`** (692 líneas) - Backtest avanzado que simula trading real escaneando el universo completo cada día. **Motor principal de backtesting** realista.

- **`backtest_runner.py`** (pequeño) - Interface simple para backtesting. Wrapper conveniente para análisis históricos rápidos.

- **`backtest_headless.py`** - Versión sin UI para integración con dashboard. Usa OpenBB.

- **`analyze_backtest_sectors.py`** (510 líneas) - Análisis de correlación entre trades y salud de mercado/sectores. Para optimización post-backtest.

### 🗄️ Gestión de Datos
- **`populate_historical_openbb.py`** (322 líneas) ✅ **NUEVO - USAR ESTE** - Pobla datos históricos con OpenBB y calcula TODAS las métricas (ADR, SMAs, trends, etc.) en un paso.

- **`manage_universe.py`** (271 líneas) - CLI para gestión del universo de tickers (agregar/ver/actualizar). **Herramienta principal** para administrar tickers.

- **`cache_inspector.py`** - Inspección del cache, verifica datos disponibles.

- **`inspect_cache.py`** (326 líneas) - Similar al anterior, más detallado. Verifica datos y gaps.

### 🔄 Workflows Automatizados
- **`daily_workflow.py`** - Workflow completo pre-market a post-market. **Para automatizar** tu rutina diaria completa.

- **`morning_workflow.py`** (276 líneas) - Rutina matinal pre-market (market health, scan, focus list). **Para automatizar** pre-market.

- **`market_health_check.py`** (246 líneas) - Verificación de condiciones de mercado antes de buscar setups. Analiza SPY/QQQ/sectores.

### 📈 Análisis y Utilidades
- **`app.py`** (2074 líneas) - Dashboard Streamlit completo con visualizaciones, backtesting, análisis. **UI principal** del sistema.

- **`trade_journal.py`** (272 líneas) - Sistema de journaling automático con analytics de performance.

- **`quick_analysis.py`** - Análisis rápido de un símbolo individual.

---

## ⚠️ Scripts Obsoletos/Deprecados (CONSIDERAR ELIMINAR)

### 🗑️ Data Population Antiguos
- **`populate_historical_cache.py`** (182 líneas) - ❌ **OBSOLETO** - Usa yfinance directo, no calcula métricas. Reemplazado por `populate_historical_openbb.py`.

- **`quick_populate_cache.py`** - ❌ **OBSOLETO** - Similar al anterior. Usar el nuevo script de OpenBB.

- **`populate_historical_fundamentals.py`** (298 líneas) - Puebla market cap y avg volume. **Parcialmente obsoleto**, las métricas ahora se calculan en `populate_historical_openbb.py`.

- **`scripts/populate_historical_metrics.py`** - ❌ **OBSOLETO** - Calcula métricas post-descarga. Ya no necesario con el nuevo script.

- **`scripts/add_historical_metrics.py`** - ❌ **OBSOLETO** - Similar al anterior.

### 🧪 Scripts de Testing
- **`scripts/test_cache_switch.py`** - Test para cambio de cache. **Eliminar** si ya migraste a OpenBB.

- **`scripts/test_fast_filters.py`** - Test de filtros. **Mantener solo** si estás optimizando filtros.

- **`ejecutar_backtest_nuevo.py`** - Test de backtest. **Eliminar** si `backtest_runner.py` funciona bien.

- **`run_backtest_with_trend_filter.py`** - Test de filtro de tendencia. **Eliminar** si ya está integrado.

### 🔧 Migraciones/Mantenimiento
- **`migrate_add_liquidity_columns.py`** (266 líneas) - ❌ **Una vez ejecutado, eliminar** - Migración para agregar columnas de liquidez.

- **`optimize_sqlite_indexes.py`** (250 líneas) - ❌ **Una vez ejecutado, eliminar** - Crea índices en SQLite.

- **`clear_corrupted_cache.py`** - Limpia cache corrupto. **Mantener** por si hay problemas con cache.

### 📝 Gestión de Tickers (Redundantes)
- **`add_and_check_tickers.py`** - Agregar tickers y verificar liquidez. **Redundante** con `manage_universe.py`.

- **`add_major_indices.py`** - Agregar S&P500/NASDAQ. **Redundante** con `manage_universe.py`.

- **`add_tickers_quick.py`** - Atajo para agregar tickers. **Redundante** con `manage_universe.py`.

- **`show_universe.py`** - Muestra info del universo. **Redundante** con `manage_universe.py`.

### 🔍 Utilidades Duplicadas
- **`get_top_liquidity_tickers.py`** - Obtiene tickers más líquidos. **Funcionalidad ya en** `manage_universe.py` o queries SQL.

- **`get_top_historical.py`** - Similar al anterior.

- **`analyze_date_range.py`** - Analiza rango de fechas en cache. **Funcionalidad en** `cache_inspector.py`.

### 🎛️ Optimización (Situacional)
- **`optimize_filters.py`** (334 líneas) - Optimiza parámetros ADR y exposure. **Mantener solo** si estás activamente optimizando.

- **`run_custom_optimization.py`** - Optimización con lista custom. **Eliminar** si no lo usas.

- **`daily_backtest_runner.py`** (256 líneas) - Runner institucional. **Redundante** con `backtest_runner.py` o `backtest_dynamic_universe.py`.

### 📦 Varios
- **`cache_intraday_data.py`** (346 líneas) - Cachea datos intraday 5m. **Mantener** si usas datos intraday activamente, sino eliminar.

- **`transform_results.py`** - Transforma resultados para dashboard. **Mantener** si el dashboard lo necesita.

---

## 🎯 Recomendaciones de Limpieza

### ✅ FASE 1: Eliminar Obsoletos Obvios (10 archivos)
```bash
# Scripts que usan yfinance antiguo y fueron reemplazados
rm populate_historical_cache.py
rm quick_populate_cache.py
rm scripts/populate_historical_metrics.py
rm scripts/add_historical_metrics.py

# Migraciones ya ejecutadas
rm migrate_add_liquidity_columns.py
rm optimize_sqlite_indexes.py

# Tests obsoletos
rm ejecutar_backtest_nuevo.py
rm run_backtest_with_trend_filter.py
rm scripts/test_cache_switch.py
rm scripts/test_fast_filters.py
```

### ✅ FASE 2: Consolidar Gestión de Tickers (6 archivos)
```bash
# Todos reemplazados por manage_universe.py
rm add_and_check_tickers.py
rm add_major_indices.py
rm add_tickers_quick.py
rm show_universe.py
rm get_top_liquidity_tickers.py
rm get_top_historical.py
```

### ✅ FASE 3: Eliminar Utilidades Duplicadas (3 archivos)
```bash
rm analyze_date_range.py  # Ya en cache_inspector.py
rm run_custom_optimization.py  # Si no lo usas
rm daily_backtest_runner.py  # Redundante con backtest_runner.py
```

### ⚠️ FASE 4: Revisar Según Uso (4 archivos)
```bash
# Eliminar solo si NO los usas activamente
rm cache_intraday_data.py  # ¿Usas datos intraday?
rm optimize_filters.py  # ¿Estás optimizando parámetros?
rm populate_historical_fundamentals.py  # Parcialmente obsoleto
rm transform_results.py  # ¿El dashboard lo necesita?
```

---

## 📋 Scripts Finales Recomendados (17 archivos core)

### Production Ready:
1. `app.py` - Dashboard principal
2. `live_scanner.py` - Trading diario completo
3. `live_trading_scanner.py` - Scanner ligero
4. `position_tracker.py` - Tracking de posiciones
5. `backtest_dynamic_universe.py` - Backtest principal
6. `backtest_runner.py` - Backtest simple
7. `backtest_headless.py` - Backtest para dashboard
8. `populate_historical_openbb.py` ✅ - Población de datos
9. `manage_universe.py` - Gestión de tickers
10. `cache_inspector.py` - Inspección de cache
11. `market_health_check.py` - Health check
12. `daily_workflow.py` - Workflow completo
13. `morning_workflow.py` - Workflow pre-market
14. `trade_journal.py` - Journaling
15. `analyze_backtest_sectors.py` - Análisis post-backtest
16. `quick_analysis.py` - Análisis rápido
17. `clear_corrupted_cache.py` - Mantenimiento cache

### Opcionales (mantener si usas):
- `live_scanner_avwap.py` - Si usas AVWAP
- `cache_intraday_data.py` - Si usas intraday
- `inspect_cache.py` - Alternativa a cache_inspector
- `optimize_filters.py` - Si optimizas activamente

---

## 📊 Resumen de Limpieza

| Categoría | Scripts | Acción |
|-----------|---------|--------|
| ✅ Core Production | 17 | **MANTENER** |
| 🗑️ Obsoletos | 10 | **ELIMINAR FASE 1** |
| 🔄 Redundantes | 9 | **ELIMINAR FASE 2-3** |
| ⚠️ Revisar | 4 | **ELIMINAR si no usas** |
| **Total Eliminables** | **23** | De 37 scripts a ~17 core |

**Resultado**: Sistema más limpio, mantenible y enfocado en scripts que realmente usas.
