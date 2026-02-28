# Optimization Scripts Suite

Scripts para optimizar los parámetros del sistema de trading y encontrar rangos óptimos.

## 📁 Scripts Disponibles

### 1. `range_finder.py`
Encuentra rangos óptimos para cada parámetro analizando el rendimiento histórico.

**Uso:**
```bash
# Auto-detect último trade_log
python3 scripts/optimization/range_finder.py

# Archivo específico
python3 scripts/optimization/range_finder.py --file outputs/backtests/trade_log.csv
```

**Analiza:**
- `dist_sma20_pct`: Distancia a SMA20 (extensión)
- `context_rvol`: Volumen relativo  
- `context_adr`: Rango promedio diario (volatilidad)
- `consolidation_days`: Días de consolidación

**Output:**
- Tabla de rendimiento por rango
- Mejor rango para cada parámetro
- CSV con resultados en `outputs/optimization/ranges_*.csv`

---

### 2. `optimize_parameters.py`
Suite completa de optimización con 3 métodos diferentes.

**Uso:**
```bash
# Ejecutar todos los métodos
python3 scripts/optimization/optimize_parameters.py --method all

# Solo correlaciones
python3 scripts/optimization/optimize_parameters.py --method correlations

# Solo grid search
python3 scripts/optimization/optimize_parameters.py --method grid

# Solo walk-forward
python3 scripts/optimization/optimize_parameters.py --method walkforward
```

**Métodos:**

#### A. Correlation Analysis
- Encuentra qué parámetros correlacionan más con rentabilidad
- Compara promedios de Winners vs Losers
- Identifica qué "perillas" tocar

#### B. Grid Search
- Prueba TODAS las combinaciones de parámetros
- Encuentra la combinación óptima
- Rankea por score combinado (Win Rate + Avg R + Profit Factor)
- **Advertencia:** Puede ser lento con muchos parámetros

#### C. Walk-Forward Optimization
- Previene overfitting
- Entrena en período histórico, valida en período futuro
- Identifica parámetros estables a través del tiempo
- Método más robusto para producción

---

### 3. `quick_diagnostics.py`
Diagnóstico rápido de qué parámetros tienen más impacto.

**Uso:**
```bash
python3 scripts/optimization/quick_diagnostics.py
```

**Analiza:**
- RVOL promedio en Winners vs Losers
- Distancia SMA20 promedio
- Consolidación promedio

---

## 📊 Interpretación de Resultados

### Win Rate
- **Real (Trades Completos):** 36.3%
- **Inflado (Eventos Parciales):** 45.7%
- ⚠️ El dashboard anterior contaba TP1, TP2, RUNNER como trades separados

### R-Multiple
- **Avg R = -0.02R:** Barely breaking even por trade
- **Target:** Buscar combinaciones con Avg R > 1.0R
- **Profit Factor:** Actual 0.98 (perdiendo ligeramente)

### Parámetros Prometedores (según análisis actual)
```
dist_sma20_pct: 0-3%       (R=+0.19, WR=39.1%)
context_rvol:   2-2.5x     (R=+0.30, WR=40.6%)
context_adr:    3-4%       (R=+0.21, WR=47.6%)
```

---

## 🎯 Workflow Recomendado

### Paso 1: Ejecutar Backtest
```bash
# En Streamlit o por línea de comando
python3 backtest_vectorbt_advanced.py
```

### Paso 2: Análisis Rápido
```bash
# Ver qué parámetros funcionan mejor
python3 scripts/optimization/range_finder.py
```

### Paso 3: Correlaciones
```bash
# Entender relaciones
python3 scripts/optimization/optimize_parameters.py --method correlations
```

### Paso 4: Grid Search (opcional)
```bash
# Solo si quieres probar combinaciones específicas
python3 scripts/optimization/optimize_parameters.py --method grid
```

### Paso 5: Walk-Forward (robusto)
```bash
# Validación rigurosa
python3 scripts/optimization/optimize_parameters.py --method walkforward
```

### Paso 6: Aplicar Cambios
Edita filtros en `config/backtest_config.yaml` o ajusta en UI de Streamlit.

---

## 📈 QuantStats Integration

Los scripts usan **TradeGrouper** para agrupar salidas parciales correctamente:

```python
from src.analytics.quantstats_analyzer import QuantStatsAnalyzer

trade_log = pd.read_csv('outputs/backtests/trade_log.csv')
analyzer = QuantStatsAnalyzer(trade_log, initial_capital=100000)

# Métricas corregidas
metrics = analyzer.get_trade_metrics()
print(f"Win Rate Real: {metrics['win_rate_pct']:.1f}%")
print(f"Total Trades: {metrics['total_trades']}")

# Métricas QuantStats (Sharpe, Sortino, etc.)
qs_metrics = analyzer.get_quantstats_metrics()
print(f"Sharpe: {qs_metrics['sharpe_ratio']:.2f}")
```

---

## 🔧 Configuración de Parámetros

Los scripts prueban estos rangos por defecto:

```python
param_grid = {
    'max_dist_sma20': [5.0, 7.0, 10.0, 12.0, 15.0],
    'consolidation_min': [10, 15, 20, 25],
    'rvol_min': [1.2, 1.5, 2.0],
}
```

Puedes modificarlos editando los archivos directamente.

---

## ⚠️ Consideraciones Importantes

### Trades Parciales
El motor VectorBT genera salidas parciales (TP1, TP2, RUNNER). Los scripts automáticamente agrupan estos eventos en trades completos para métricas correctas.

### Overfitting
- Grid Search puede encontrar parámetros "perfectos" para datos históricos
- **Siempre** valida con Walk-Forward o out-of-sample
- Si Avg R es demasiado bueno (>2R), probablemente hay overfitting

### Tamaño de Muestra
- Mínimo 20 trades para considerar resultados válidos
- Mínimo 100 trades para alta confianza
- Los scripts filtran automáticamente muestras pequeñas

### Contexto de Mercado
- Estos resultados son para el período probado
- Mercado alcista vs bajista puede cambiar parámetros óptimos
- Considera usar `vix_regime` y `spy_above_ema20` como filtros adicionales

---

## 📝 Output Files

Todos los archivos se guardan en `outputs/optimization/`:

```
outputs/optimization/
├── ranges_20260107_164524.csv          # Range finder results
├── grid_search_20260107_165030.csv     # Grid search rankings
└── walkforward_20260107_170245.csv     # Walk-forward validation
```

---

## 🚀 Próximos Pasos

Después de optimizar:

1. **Aplicar mejores parámetros** en config o UI
2. **Re-ejecutar backtest** con parámetros optimizados
3. **Verificar métricas** en tab QuantStats de Streamlit
4. **Paper trading** antes de live

**Target Metrics:**
- Win Rate: 45-55%
- Avg R: 1.0-1.5R
- Profit Factor: >1.5
- Sharpe Ratio: >1.0

---

## 💡 Tips

1. **No optimices cada parámetro individualmente** - Usa combinaciones
2. **Prioriza robustez sobre perfección** - Walk-forward > Grid search
3. **Menos es más** - Pocos filtros restrictivos mejor que muchos complejos
4. **Contexto importa** - RVOL alto + Sector fuerte > Solo RVOL alto
5. **Documenta cambios** - Guarda los CSV de resultados

---

## 🐛 Troubleshooting

**Error: "Column(s) ['ticker'] do not exist"**
- Fixed en última versión - usa `reset_index()` en groupby

**Error: "avg_drawdown no existe"**
- Fixed - implementado custom en QuantStatsAnalyzer

**Sin trades después de filtrar**
- Parámetros muy restrictivos
- Revisa con range_finder qué rangos tienen más datos

**Métricas muy diferentes entre dashboard y QuantStats**
- Normal - Dashboard cuenta salidas parciales por separado
- QuantStats agrupa correctamente

---

## 📚 Recursos

- [QuantStats Docs](https://github.com/ranaroussi/quantstats)
- [VectorBT Docs](https://vectorbt.dev/)
- `GUIA_EXPERIMENTACION_FILTROS.md` - Guía de filtros
- `FILTROS_OPTIMIZADOS.md` - Resultados anteriores
