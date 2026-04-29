# 🏎️ Bugatti Optuna - Walk-Forward Optimization

## ¿Qué hace este script?

Encuentra **rangos robustos** de parámetros usando **Optuna** para evitar overfitting.

### ❌ MAL (Números Mágicos):
```python
min_rvol = 2.5  # ← Este número "perfecto" solo funciona en 2012-2016
```

### ✅ BIEN (Rangos Robustos):
```python
min_rvol = trial.suggest_categorical([0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
# ← Optuna busca QUÉ rango funciona mejor en diferentes mercados
```

---

## 🎯 Parámetros que Optimiza

### 1. **SIGNAL TYPES** (¿Cuál setup funciona mejor?)
```python
signal_type = ['any', 'vcp', 'breakout', 'ath']
```
- **VCP**: Volatility Contraction Pattern (15+ días consolidación)
- **BREAKOUT**: Ruptura de consolidación (<15% rango)
- **ATH**: All-Time High
- **ANY**: Cualquier setup válido

**¿Qué aprende?** Si VCP funciona mejor que breakouts en bull markets, etc.

---

### 2. **SECTOR ROTATION** (Top X% Methodology)
```python
require_sector_strength = [True, False]
sector_top_percentile = [0.30, 0.35, 0.40, 0.45, 0.50]
```
- **Top 40%**: Solo operar sectores fuertes (top 40% de performance)
- **Top 30%**: Más restrictivo, solo los mejores sectores

**¿Qué aprende?** ¿Funciona mejor filtrar por sector? ¿Top 30% o 40%?

---

### 3. **VCP CONSOLIDATION QUALITY** (¿Cuántos días?)
```python
min_consolidation_days = [0, 5, 10, 15, 20, 25]
max_consolidation_range = [5.0, 7.5, 10.0, 12.5, 15.0, 20.0]
```
- **15+ días**: VCP clásico de Mark Minervini
- **10 días**: Consolidación más corta
- **0 días**: Sin filtro de consolidación

**¿Qué aprende?** ¿Necesitas 15 días o funcionan bien 10? ¿Rango <10% o <15%?

---

### 4. **MOMENTUM FILTERS** (¿Cuánta fuerza necesitas?)
```python
min_adr = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]  # Average Daily Range
min_rvol = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]  # Relative Volume
```
- **ADR 4%**: Solo stocks muy volátiles
- **ADR 2%**: Más moderado
- **RVol 2.5×**: Volumen muy alto (momentum fuerte)
- **RVol 1.0×**: Volumen normal

**¿Qué aprende?** ¿Mejor operar solo momentum extremo (RVol 2.5×) o también moderado?

---

### 5. **RISK MANAGEMENT** (¿Cuánto riesgo?)
```python
max_exposure_pct = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
risk_dollars = [100, 150, 200, 250]
max_stop_pct = [0.05, 0.06, 0.07, 0.08, 0.10]
```
- **25% exposure**: Máximo 25% del capital en trades simultáneos
- **$150 risk**: Arriesgar $150 por trade (stop loss)
- **7% stop**: Stop loss al 7% bajo entrada

**¿Qué aprende?** ¿Funciona mejor 25% o 35% exposure? ¿$150 o $200 risk?

---

### 6. **RVOL-BASED POSITION SIZING** (Reducir tamaño en stocks "calientes")
```python
rvol_danger = [2.5, 3.0, 3.5, 4.0]       # RVol "peligroso"
rvol_warning = [1.5, 2.0, 2.5]           # RVol "advertencia"
rvol_danger_size = [0.20, 0.25, 0.30]    # Reducir a 25% del tamaño
rvol_warning_size = [0.50, 0.60, 0.70]   # Reducir a 60% del tamaño
```

**Lógica**: Si un stock tiene RVol 3.5× (mucho hype), reduce tamaño de posición.

**¿Qué aprende?** ¿Funciona mejor reducir a 25% o 30%? ¿Cuándo considerar "peligro"?

---

### 7. **MULTI-PHASE EXITS** (TP1, TP2, Runner)
```python
use_phases = [True, False]
tp1_r = [1.0, 1.5, 2.0]     # Take Profit 1 en 1.5R
tp2_r = [2.5, 3.0, 3.5, 4.0] # Take Profit 2 en 3R
```

**Sistema de 3 fases**:
- **TP1**: Vende 50% en 1.5R → Stop a breakeven
- **TP2**: Vende 30% en 3R
- **Runner**: 20% corre con trailing stop (EMA8 < EMA21)

**¿Qué aprende?** ¿Funciona mejor salir en fases o hold completo?

---

## 📋 Como Usar

### Prueba Rápida (10 minutos)
```bash
python3 bugatti_optuna.py --trials 50 --tickers 30
```

### Optimización Media (20 minutos)
```bash
python3 bugatti_optuna.py --trials 100 --tickers 50 --metric sharpe
```

### Optimización Completa (1-2 horas)
```bash
python3 bugatti_optuna.py \
  --in-start 2018-01-01 --in-end 2021-12-31 \
  --val-start 2022-01-01 --val-end 2023-12-31 \
  --oos-start 2024-01-01 --oos-end 2024-12-31 \
  --trials 300 --tickers 100 --metric sharpe
```

### Walk-Forward Completo (Para evitar overfitting)
```bash
python3 bugatti_optuna.py \
  --in-start 2012-01-01 --in-end 2016-12-31 \
  --val-start 2017-01-01 --val-end 2021-12-31 \
  --oos-start 2022-01-01 --oos-end 2025-12-31 \
  --trials 200 --tickers 80
```

---

## 📊 Resultados

### Archivos generados:
- `outputs/walk_forward_v6_pro_optuna/in_sample_trials.csv` - Todos los trials
- `outputs/walk_forward_v6_pro_optuna/final_report.json` - Mejores parámetros

### Top 5 Configuraciones:
```
value  signal_type  min_adr  max_exposure  sector_top_percentile  min_consolidation_days
2.45   vcp         2.5      0.25          0.40                   15
2.38   breakout    3.0      0.30          0.35                   10
2.31   any         2.0      0.25          0.40                   5
```

---

## 🎓 ¿Qué Aprendes?

Optuna encuentra:

1. **¿VCP o Breakout?** → Cuál setup funciona mejor
2. **¿Sector Filter ON/OFF?** → Si vale la pena filtrar por sector
3. **¿Top 30% o 40%?** → Qué percentil de sector es óptimo
4. **¿15 días o 10?** → Cuántos días de consolidación necesitas
5. **¿RVol 2× o 2.5×?** → Cuánto momentum es suficiente
6. **¿Exposure 25% o 35%?** → Cuánto capital arriesgar simultáneamente

**Todo con RANGOS robustos**, no números mágicos que solo funcionan en un período.

---

## ⚠️ Anti-Overfitting

El script usa **Walk-Forward** en 3 fases:

1. **IN-SAMPLE** (2018-2021): Optuna optimiza aquí
2. **VALIDATION** (2022-2023): Prueba los parámetros (si degrada >40% = overfitting)
3. **OUT-OF-SAMPLE** (2024-2025): Test final (NUNCA se usa en optimización)

Si degradación < 20% → ✅ Parámetros robustos
Si degradación > 40% → ❌ Overfitting detectado

---

## 🏎️ Performance

- Motor V6_PRO carga datos UNA VEZ
- 100 trials × 50 tickers = ~10 minutos
- 100× más rápido que el motor clásico
