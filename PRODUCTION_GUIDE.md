# Validación Framework - Guía de Producción

## 📁 Archivos Creados

### Nuevos Módulos de Validación
```
src/validation/
├── __init__.py                    # Exports principales
├── research_gate.py               # Three-Phase Research Gate
├── stress_testing.py              # Stress Testing Suite
└── robustness_metrics.py          # Robust Objective Functions
```

### Scripts de Prueba
```
test_validation_framework.py       # Script completo de prueba
MIGRATION_THOR_TO_ADVANCED.md      # Guía de migración detallada
```

### Motor Deprecado
```
src/backtest/optimization_engine_thor.py  # ⚠️ AHORA DEPRECADO
```

---

## 🚀 Cómo Probar el Framework

### Paso 1: Descargar Datos (REQUERIDO)

Si no tienes datos descargados, ejecuta:

```bash
# Opción 1: Descargar universo completo (lento, ~30 min)
python3 manage_universe.py --download --universe universe

# Opción 2: Descargar solo tickers de prueba (rápido, ~5 min)
python3 -c "
from src.data.ticker_cache import TickerCache
from src.data.market_data import MarketDataProvider

provider = MarketDataProvider()
cache = TickerCache()

tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN', 'NFLX', 'AMD', 'CRM']

for ticker in tickers:
    print(f'Descargando {ticker}...')
    try:
        df = provider.download_ohlcv(ticker, '2020-01-01', '2024-12-31')
        if df is not None:
            cache.save_ohlcv(ticker, df)
            print(f'  ✅ {ticker}: {len(df)} días')
        else:
            print(f'  ❌ {ticker}: Sin datos')
    except Exception as e:
        print(f'  ❌ {ticker}: {e}')
"
```

### Paso 2: Ejecutar Pruebas

```bash
# Ejecutar script de prueba completo
python3 test_validation_framework.py
```

Este script ejecutará:
1. **Backtest básico** con AdvancedVectorBTEngine
2. **Three-Phase Research Gate** (Discovery → Validation → Productionization)
3. **Stress Testing Suite** (costs, spreads, liquidity)
4. **Robust Objective Function** (p5/p10 metrics)

---

## 📊 Parámetros Recomendados para Producción

```python
PRODUCTION_PARAMS = {
    # Filtros de liquidez
    'min_rvol': 1.5,              # Mínimo 1.5x volumen relativo
    'min_adr': 2.0,               # Mínimo 2.0% ADR (volatilidad)
    'min_volume': 300000,         # 300k shares diarios
    'min_dollar_volume': 5000000, # $5M volumen diario
    
    # Filtros técnicos
    'max_dist_sma20': 7.0,        # Máximo 7% sobre SMA20
    'min_consolidation_days': 10, # Mínimo 10 días consolidando
    'max_stop_pct': 3.0,          # Stop máximo 3%
    
    # Targets
    'tp1_r': 1.25,                # TP1 a 1.25R
    'tp2_r': 3.0,                 # TP2 a 3.0R
    
    # Riesgo
    'risk_dollars': 150,          # $150 riesgo por trade
    'max_exposure_pct': 0.25,     # 25% exposición máxima
    
    # Modo
    'mode': 'production',         # 'production' o 'convergence'
    
    # Costos (REQUERIDOS en Advanced)
    'fees': 0.001,                # 0.1% comisión
    'slippage': 0.001,            # 0.1% slippage
    
    # Regulación de mercado
    'use_market_regime_filter': True,
    'require_spy_above_sma50': True,
    'max_vix_threshold': 35.0,
    
    # Señal
    'signal_type': 'breakout',    # 'breakout' o 'any'
}
```

---

## 🎯 Three-Phase Research Gate

### Fase 1: Discovery
Valida estructura y parámetros básicos.

### Fase 2: Validation
Métricas estadísticas robustas:
- **PBO** (Probability of Backtest Overfitting) < 50%
- **Bootstrap p5** > 0% (peor caso anual positivo)
- **Bootstrap p10** > 2% (percentil 10 aceptable)
- **Max Drawdown** < 25%
- **Sharpe** > 0.8
- **Mínimo 50 trades**

### Fase 3: Productionization
Stress tests:
- **2x costs** impact > -10%
- **3x costs** impact > -20%
- **Wider spreads** impact > -15%
- **Worst case** impact > -50%

---

## 🔄 Workflow de Producción

```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.validation import ResearchGate, StressTestSuite
from src.validation.robustness_metrics import robust_objective_function

# 1. Definir universo y fechas
universe = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN']
train_dates = ('2022-01-01', '2023-12-31')
test_dates = ('2024-01-01', '2024-12-31')

# 2. Optimizar con objetivo robusto (Optuna)
def objective(trial):
    params = {
        'min_rvol': trial.suggest_float('min_rvol', 1.0, 3.0),
        'min_adr': trial.suggest_float('min_adr', 1.5, 4.0),
        'max_dist_sma20': trial.suggest_float('max_dist_sma20', 5.0, 15.0),
        # ... otros parámetros
    }
    
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=train_dates[0],
        end_date=train_dates[1],
        **params
    )
    engine.load_data()
    result = engine.run_backtest()
    
    return robust_objective_function(result)

# 3. Validar mejor estrategia
gate = ResearchGate()
validation = gate.validate_strategy(
    engine_class=AdvancedVectorBTEngine,
    params=best_params,
    universe=universe,
    train_dates=train_dates,
    test_dates=test_dates
)

# 4. Stress testing
suite = StressTestSuite(AdvancedVectorBTEngine)
stress = suite.run_full_stress_test(
    params=best_params,
    universe=universe,
    test_dates=test_dates
)

# 5. Promover solo si pasa TODO
if validation.promotion_approved and stress.all_passed:
    print("✅ Estrategia lista para producción")
    deploy(best_params)
else:
    print("❌ Rechazada - revisar métricas")
```

---

## 📈 Métricas Clave

### Robustness Metrics
- **Bootstrap p5/p10:** Percentiles de retorno OOS
- **Sortino Ratio:** Sharpe pero solo con downside
- **Calmar Ratio:** Retorno anual / Max Drawdown
- **Omega Ratio:** Ganancias / Pérdidas (asimétrico)
- **Probability of Loss:** Probabilidad de retorno negativo

### Stress Test Metrics
- **Cost Impact:** Sensibilidad a comisiones
- **Spread Impact:** Sensibilidad a spreads amplios
- **Gap Risk:** Riesgo de gaps adversos
- **Capacity:** Límites de tamaño de posición

---

## ⚠️ Errores Comunes

### "No data loaded"
**Solución:** Ejecutar `manage_universe.py --download` primero

### "PBO too high"
**Solución:** La estrategia está sobre-optimizada. Usar:
- Menos parámetros
- Validación walk-forward
- Regularización en Optuna

### "Bootstrap p5 < 0"
**Solución:** El peor caso es negativo. Mejorar:
- Stop losses más ajustados
- Filtros de calidad más estrictos
- Reducir leverage

### "Stress test failed"
**Solución:** Estrategia frágil. Probar:
- Aumentar liquidez mínima
- Reducir frecuencia de trading
- Mejorar timing de entradas

---

## 🆘 Soporte

Si encuentras problemas:

1. **Verificar datos:**
   ```python
   from src.data.ticker_cache import TickerCache
   cache = TickerCache()
   df = cache.get_ohlcv('AAPL', '2023-01-01', '2024-12-31')
   print(f"Datos AAPL: {len(df)} filas" if df is not None else "Sin datos")
   ```

2. **Test simple:**
   ```bash
   python3 -c "from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine; print('✅ OK')"
   ```

3. **Revisar logs:**
   - Los módulos de validación generan logs detallados
   - Busca mensajes de error específicos

---

## 📚 Recursos

- **Migration Guide:** `MIGRATION_THOR_TO_ADVANCED.md`
- **Test Script:** `test_validation_framework.py`
- **Source Code:** `src/validation/`
- **Engine:** `src/backtest/vectorbt_engine_advanced.py`

---

## ✅ Checklist antes de Producción

- [ ] Descargar datos actualizados
- [ ] Ejecutar `test_validation_framework.py`
- [ ] Validar que PBO < 50%
- [ ] Validar que p5 > 0%
- [ ] Validar stress tests
- [ ] Documentar parámetros finales
- [ ] Backtest out-of-sample confirmado
- [ ] Paper trading (opcional pero recomendado)

---

**⚡ NO USAR THOR PARA PRODUCCIÓN - Está deprecado y será eliminado en Q2 2025**
