# 🏎️ BUGATTI OPTUNA - PARÁMETROS OPTIMIZADOS V2

## 📋 Resumen de Cambios

Implementado el **2026-01-09** para reducir overfitting y mejorar robustez.

---

## ✅ CAMBIOS IMPLEMENTADOS

### 1. **Signal Type**
```python
# ANTES: ['any', 'vcp', 'breakout', 'ath']
# AHORA: ['vcp', 'breakout', 'ath', 'any']
```
**Cambio**: Incluye ATH (all-time highs) - algunos de los mejores breakouts históricos.

---

### 2. **Momentum Filters** ⭐ CRÍTICO

#### min_adr
```python
# ANTES: [1.5, 2.0, 2.5, 3.0, 3.5]
# AHORA: [1.5, 2.0, 2.5, 3.0]
```
**Razón**: Eliminado 3.5% (demasiado restrictivo). 1.5-3.0% es el sweet spot.

#### min_rvol ⭐⭐⭐
```python
# ANTES: [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
# AHORA: [1.5, 1.75, 2.0, 2.25, 2.5]
```
**Razón**: 3.5-4.0x RVOL elimina 95% de oportunidades. 1.5-2.5x es momentum real sin ser "meme stocks".

---

### 3. **Risk Management** ⭐⭐⭐

#### max_exposure_pct
```python
# ANTES: [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
# AHORA: [0.15, 0.20, 0.25]
```
**Razón**: 40% en una posición es una locura. 15-25% es industry standard profesional.

#### risk_dollars
```python
# ANTES: [100, 150, 200, 250]
# AHORA: [150, 175, 200, 225, 250]
```
**Razón**: Con $100K capital, arriesgar $100 (0.1%) es ridículo. 150-250 (0.15-0.25%) es razonable.

#### max_stop_pct
```python
# ANTES: [0.05, 0.06, 0.07, 0.08, 0.10]
# AHORA: [0.06, 0.07, 0.08]
```
**Razón**: 5% demasiado tight (noise), 10% demasiado amplio. 6-8% es profesional.

---

### 4. **Consolidation Quality**

#### max_consolidation_range ⭐
```python
# ANTES: [5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
# AHORA: [10.0, 12.5, 15.0, 17.5, 20.0]
```
**Razón**: 5-7.5% demasiado tight. 10-20% es VCP real. (25% eliminado - eso no es consolidación).

#### min_consolidation_days
```python
# ANTES: [5, 10, 15, 20]
# AHORA: [5, 10, 15]
```
**Razón**: 20 días es demasiado específico. 5-15 cubre la mayoría de patrones.

---

### 5. **Liquidity** ⭐

```python
# ANTES: min_volume = [100000, 200000, 300000, 500000]
# AHORA: min_volume = [200000, 300000, 500000]

# ANTES: min_dollar_volume = [5e6, 10e6, 15e6, 20e6]
# AHORA: min_dollar_volume = [10e6, 15e6]
```
**Razón**: Simplificado. 100K volumen y $5M son penny stocks. Momentum necesita liquidez.

---

### 6. **RVOL Sizing**

```python
# ANTES: rvol_danger = [2.5, 3.0, 3.5, 4.0]
# AHORA: rvol_danger = [2.5, 3.0, 3.5]

# ANTES: rvol_warning = [1.5, 2.0, 2.5]
# AHORA: rvol_warning = [1.5, 2.0]

# ANTES: rvol_danger_size = [0.20, 0.25, 0.30]
# AHORA: rvol_danger_size = [0.25, 0.30, 0.35]

# ANTES: rvol_warning_size = [0.50, 0.60, 0.70]
# AHORA: rvol_warning_size = [0.55, 0.60, 0.65, 0.70]
```
**Razón**: Ajustes finos para mejor granularidad.

---

### 7. **ADR Sizing**

```python
# ANTES: adr_high = [5.5, 6.0, 6.5, 7.0]
# AHORA: adr_high = [6.0, 6.5, 7.0]

# ANTES: adr_med = [4.0, 4.5, 5.0, 5.5]
# AHORA: adr_med = [4.5, 5.0, 5.5]

# ANTES: adr_med_size = [0.30, 0.33, 0.40]
# AHORA: adr_med_size = [0.30, 0.35, 0.40]
```
**Razón**: Simplificado rangos bajos, mejor granularidad en medium.

---

### 8. **Earnings Filter** ⭐⭐

```python
# ANTES: use_earnings_filter = [True, False]
#        earnings_days = [3, 5, 7]
# AHORA: use_earnings_filter = [False, True]  # False primero
#        earnings_days = [5, 7]
```
**Razón**: Momentum puede APROVECHAR earnings moves. Hacerlo opcional (no forzado).

---

### 9. **Relative Strength** ⭐⭐⭐

#### require_positive_rs
```python
# ANTES: [True, False]
# AHORA: [False, True]  # False primero
```
**Razón**: Combinado con sector_strength es demasiado restrictivo.

#### min_rs
```python
# ANTES: [0.0, 20.0, 40.0, 50.0, 60.0]
# AHORA: [30.0, 40.0, 50.0, 60.0]
```
**Razón**: 0.0 no tiene sentido si require_positive_rs=True. 30-60 es más razonable que 50-70.

#### rs_lookback
```python
# ANTES: ['21d', '63d', 'avg']
# AHORA: ['21d', '63d']
```
**Razón**: 'avg' puede ser confuso. Mantener períodos específicos.

---

### 10. **Market Regime** ⭐⭐⭐

```python
# ANTES: require_bullish_spy = [True, False]
#        max_vix = [25.0, 30.0, 35.0, 50.0, 100.0]

# AHORA: require_bullish_spy = False  # SIEMPRE
#        max_vix = 40.0  # FIXED
```
**Razón**: **NO MARKET TIMING**. Los mejores trades vienen en volatilidad. VIX 40 permite operar en mercados normales/moderados.

---

### 11. **Exits** ⭐⭐

#### use_phases
```python
# ANTES: [True, False]
# AHORA: True  # SIEMPRE
```
**Razón**: Multi-phase exits (TP1/TP2/Runner) funcionan mejor que exits simples.

#### tp1_r
```python
# ANTES: [1.0, 1.5, 2.0]
# AHORA: [1.25, 1.5, 1.75, 2.0]
```
**Razón**: 1.0R es too aggressive. 1.25-2.0R da más "room to breathe".

#### tp2_r
```python
# ANTES: [2.5, 3.0, 3.5, 4.0]
# AHORA: [3.0, 3.5, 4.0]
```
**Razón**: 2.5R demasiado conservador para TP2. 3.0-4.0R mejor.

---

## 📊 IMPACTO ESPERADO

### Reducción de Parámetros
- **ANTES**: 35+ parámetros con rangos amplios
- **AHORA**: 30 parámetros con rangos más tight

### Search Space
- **ANTES**: ~10^40 combinaciones posibles
- **AHORA**: ~10^30 combinaciones (90% reducción)

### Overfitting Risk
- **ANTES**: CRÍTICO (-178% degradation)
- **AHORA**: Esperado < 40% degradation

---

## 🎯 FILOSOFÍA

### Eliminado
- ❌ Market timing (bullish_spy)
- ❌ Rangos extremos (RVOL 4.0, Exposure 40%)
- ❌ Parámetros contradictorios (0.0 RS con require_positive)

### Mantenido
- ✅ Multi-phase exits (TP1/TP2/Runner)
- ✅ Sector rotation (opcional)
- ✅ Dynamic position sizing (RVOL/ADR)

### Agregado
- ✅ ATH signal type
- ✅ Rangos más conservadores
- ✅ Filtros opcionales (earnings, RS)

---

## 🚀 PRÓXIMOS PASOS

### 1. Run Optimization
```bash
python3 bugatti_optuna.py \
  --in-start 2010-01-01 --in-end 2018-12-31 \
  --val-start 2019-01-01 --val-end 2021-12-31 \
  --oos-start 2022-01-01 --oos-end 2024-12-31 \
  --trials 300 \
  --tickers 100 \
  --metric sharpe
```

### 2. Validación Esperada
- **In-Sample Sharpe**: 0.4-0.8 (razonable)
- **Validation Degradation**: < 40% (aceptable)
- **OOS Sharpe**: > 0.0 (positivo)

### 3. Si Falla
- Reducir a 20 parámetros (eliminar sizing dinámico)
- Walk-forward más corto (5 años in-sample)
- Usar solo VCP/Breakout (eliminar ATH/ANY)

---

## ⚠️ WARNINGS

1. **200 trials mínimo** - 400 recomendado
2. **100+ tickers** - más diversificación
3. **NO toques OOS hasta final** - contaminación de datos
4. **Degradation > 60%** = volver a simplificar

---

**Generado**: 2026-01-09  
**Autor**: Bugatti Team  
**Status**: ✅ READY TO TEST
