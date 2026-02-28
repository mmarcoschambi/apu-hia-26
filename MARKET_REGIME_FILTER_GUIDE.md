# Filtro de Contexto de Mercado (Market Regime Filter)

## 🌍 Introducción

El **Market Regime Filter** es una capa profesional que decide **CUÁNDO operar** basándose en el contexto general del mercado. No optimiza parámetros, sino que ajusta la agresividad operativa según las condiciones macro.

### Filosofía Profesional

> "No operar en Stage 3-4 (mercado bajista/distribución)"  
> "El mercado con HIGH VOL es muy difícil los breakouts"  
> "Cuando el mercado es 100% alcista todo el mundo gana dinero"

## 📊 Las 4 Etapas del Mercado (Weinstein Stages)

### STAGE 1: Bull Trend - Aggressive Longs
- **Condiciones**: SPY > SMA200, SMA50 | Momentum +3% | VIX < 20
- **Acción**: Operar agresivo
- **Exposición máxima**: 35% del capital
- **Risk por trade**: 100% ($150)
- **Días en 2022-2024**: 201 días (26.7%)

### STAGE 2: Consolidation - Selective Longs
- **Condiciones**: Mercado lateral o sin tendencia clara
- **Acción**: Operar selectivo
- **Exposición máxima**: 25% del capital
- **Risk por trade**: 75% ($112.50)
- **Días en 2022-2024**: 496 días (66.0%)

### STAGE 3: Distribution - No Longs
- **Condiciones**: SPY < SMA50 | Volatilidad > 2% | VIX > 25
- **Acción**: NO operar largos (o muy defensivo)
- **Exposición máxima**: 10% del capital
- **Risk por trade**: 50% ($75)
- **Días en 2022-2024**: 49 días (6.5%)

### STAGE 4: Bear Trend - Shorts Only
- **Condiciones**: SPY < SMA200, SMA50 | Momentum < -5%
- **Acción**: NO operar largos
- **Exposición máxima**: 0%
- **Risk por trade**: 0%
- **Días en 2022-2024**: 6 días (0.8%)

## 🚀 Cómo Usar

### 1. Configuración Básica (Recomendada)

```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

engine = AdvancedVectorBTEngine(
    universe=['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA'],
    start_date='2022-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=150,
    
    # ✅ ACTIVAR FILTRO DE RÉGIMEN DE MERCADO
    use_market_regime_filter=True,      # Habilitar filtro
    block_trades_in_stage3=True,        # Bloquear longs en distribución
    block_trades_in_stage4=True,        # Bloquear longs en bear market
    adjust_risk_by_regime=True,         # Ajustar tamaño de posición por etapa
)

results = engine.run_backtest()
```

### 2. Configuración Conservadora (Máxima Protección)

```python
engine = AdvancedVectorBTEngine(
    universe=mi_universo,
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=150,
    
    # Filtro de régimen MUY estricto
    use_market_regime_filter=True,
    block_trades_in_stage3=True,        # ✅ Bloquear Stage 3
    block_trades_in_stage4=True,        # ✅ Bloquear Stage 4
    adjust_risk_by_regime=True,         # ✅ Reducir riesgo en Stage 2
)
```

### 3. Configuración Agresiva (Solo Ajuste de Riesgo)

```python
engine = AdvancedVectorBTEngine(
    universe=mi_universo,
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=200,  # Mayor riesgo base
    
    # Régimen activo pero sin bloquear etapas
    use_market_regime_filter=True,
    block_trades_in_stage3=False,       # ❌ NO bloquear (operar siempre)
    block_trades_in_stage4=False,       # ❌ NO bloquear
    adjust_risk_by_regime=True,         # ✅ Solo reducir tamaño en malas etapas
)
```

## 📈 Cómo Funciona Internamente

### Análisis de SPY y VIX

El sistema carga datos de SPY y VIX automáticamente:

1. **Indicadores calculados**:
   - SMA20, SMA50, SMA200 de SPY
   - Momentum 20 días
   - Volatilidad relativa (ATR%)
   - VIX regime (CALM < 15, NORMAL 15-25, HIGH 25-35, EXTREME > 35)

2. **Clasificación diaria**:
   - Cada día del backtest se clasifica en Stage 1, 2, 3 o 4
   - Se ajustan parámetros según la etapa

3. **Filtrado de entradas**:
   - Si `block_trades_in_stage3=True` → Se rechazan entradas en Stage 3
   - Si `block_trades_in_stage4=True` → Se rechazan entradas en Stage 4

4. **Ajuste de riesgo**:
   - Si `adjust_risk_by_regime=True`:
     - Stage 1: 100% del risk_dollars
     - Stage 2: 75% del risk_dollars
     - Stage 3: 50% del risk_dollars
     - Stage 4: 0% (no opera)

## 🎯 Ejemplo de Fechas Reales

### 2022-06-15 (Bear Market)
- **Stage**: STAGE_3 (Distribution)
- **SPY**: $359.81 (debajo SMA200 y SMA50)
- **VIX**: 29.6 (HIGH)
- **Momentum**: -7.1%
- **Acción**: ❌ NO OPERAR LARGOS

### 2024-07-15 (Bull Market)
- **Stage**: STAGE_1 (Bull Trend)
- **SPY**: $551.46 (arriba SMA200 y SMA50)
- **VIX**: 13.1 (CALM)
- **Momentum**: +3.9%
- **Acción**: ✅ OPERAR AGRESIVO (35% exposición, 100% risk)

## 🔍 Verificar el Filtro en Acción

### Durante el Backtest

Cuando ejecutes el backtest, verás en los logs:

```
================================================================================
🌍 MARKET REGIME FILTER ENABLED
================================================================================
   ✅ Market regime classifier initialized
   🚫 Block Stage 3: True
   🚫 Block Stage 4: True
   📊 Adjust risk by regime: True

🌍 Aplicando filtro de régimen de mercado...
   📊 Market Stages Distribution:
      STAGE_1: 150 days (35.0%)
      STAGE_2: 250 days (58.0%)
      STAGE_3: 25 days (5.8%)
      STAGE_4: 5 days (1.2%)
   📊 Entries antes de filtro de régimen: 450
   ❌ Entries bloqueadas por régimen: 75
   ✅ Entries finales: 375
   📊 Risk adjustment by regime: ENABLED
```

### Script de Prueba

Ejecuta el test incluido:

```bash
python3 test_market_regime.py
```

Este script:
- Carga datos de SPY/VIX desde 2022
- Clasifica cada día en Stage 1-4
- Muestra distribución de etapas
- Analiza fechas específicas
- Muestra transiciones de etapas

## 🧪 Comparación: Con vs Sin Filtro

### Experimento Recomendado

```python
# 1. Backtest SIN filtro de régimen
engine_sin_filtro = AdvancedVectorBTEngine(
    universe=mi_universo,
    start_date='2022-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=150,
    use_market_regime_filter=False,  # ❌ Desactivado
)
results_sin = engine_sin_filtro.run_backtest()

# 2. Backtest CON filtro de régimen
engine_con_filtro = AdvancedVectorBTEngine(
    universe=mi_universo,
    start_date='2022-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_dollars=150,
    use_market_regime_filter=True,   # ✅ Activado
    block_trades_in_stage3=True,
    block_trades_in_stage4=True,
    adjust_risk_by_regime=True,
)
results_con = engine_con_filtro.run_backtest()

# 3. Comparar métricas
print(f"SIN filtro - Return: {results_sin['total_return']*100:.2f}%, DD: {results_sin['max_drawdown']*100:.2f}%")
print(f"CON filtro - Return: {results_con['total_return']*100:.2f}%, DD: {results_con['max_drawdown']*100:.2f}%")
```

### Métricas Esperadas

**Con filtro de régimen** se espera:
- ✅ **Menor drawdown** (evita operar en bear markets)
- ✅ **Mayor win rate** (solo opera en condiciones favorables)
- ✅ **Mejor Sharpe ratio** (menos volatilidad)
- ⚠️ **Menos trades totales** (más selectivo)
- ⚠️ **Posible menor retorno absoluto** (si el período tiene muchos rallies en Stage 3)

## 🛠️ Personalización Avanzada

### Ajustar Umbrales de las Etapas

Si quieres modificar las condiciones de clasificación, edita:

```python
# src/utils/market_regime.py

def get_market_stage(self, date: pd.Timestamp) -> str:
    # ... código existente ...
    
    # Ejemplo: Stage 1 más estricto (requiere VIX < 15)
    if (spy_price > row['sma200'] and
        spy_price > row['sma50'] and
        row['mom_20'] > 0.05 and    # Cambiar de 0.03 a 0.05
        vix_value < 15):             # Cambiar de 20 a 15
        return 'STAGE_1'
```

### Crear Tus Propias Etapas

Puedes definir reglas personalizadas:

```python
# Ejemplo: Stage basada en VIX y breadth
if vix_value < 12 and spy_breadth > 0.7:
    return 'STAGE_ULTRA_BULL'
elif vix_value > 35:
    return 'STAGE_CRISIS'
```

## 📚 Integración con Otros Filtros

El Market Regime Filter se combina con:

1. **VolTrig** (RVOL-based sizing): Reduce aún más si RVOL > 3x
2. **ADR Filter**: Reduce si ADR > 6%
3. **Sector Rotation**: Combina con fuerza sectorial
4. **Earnings Filter**: Evita earnings < 5 días

**Orden de aplicación**:
```
1. Market Regime Filter (bloquea días/etapas)
   ↓
2. Entry Signals (genera señales técnicas)
   ↓
3. Liquidity Filters (RVOL, ADR, Volume)
   ↓
4. Sector Filter (fuerza sectorial)
   ↓
5. Position Sizing (VolTrig + Regime multiplier)
```

## ✅ Mejores Prácticas

1. **Siempre activar** `use_market_regime_filter=True`
2. **Bloquear Stage 3 y 4** para swing trading
3. **Ajustar riesgo por régimen** para escalar automáticamente
4. **Probar con diferentes períodos** (incluye 2022 bear market)
5. **Comparar vs baseline** sin filtro para validar mejora

## 🎓 Filosofía Profesional Implementada

Este filtro implementa principios del **Atlas Trading Room**:

- ✅ "No operar en Stage 3-4" → Bloqueo automático
- ✅ "Ajustar agresividad según régimen" → Risk multiplier dinámico
- ✅ "Cerrar en fortaleza, no en debilidad" → Solo opera en Stage 1-2
- ✅ "Análisis profundo de contexto" → SPY, VIX, momentum integrados

---

## 📞 Troubleshooting

### Error: "VIX data not available"
**Solución**: El sistema funciona sin VIX, usa valores por defecto (VIX=20)

### No se bloquean trades en Stage 3
**Verificar**: 
- `block_trades_in_stage3=True`
- `use_market_regime_filter=True`
- Revisar logs para ver clasificación de etapas

### Demasiados trades bloqueados
**Ajustar**:
- `block_trades_in_stage3=False` (solo bloquear Stage 4)
- O usar `adjust_risk_by_regime=True` sin bloquear

---

¡El filtro está listo para usar! 🚀

Para más info, revisar:
- `src/utils/market_regime.py` - Implementación del clasificador
- `test_market_regime.py` - Tests y ejemplos
- `src/backtest/vectorbt_engine_advanced.py` - Integración en el motor
