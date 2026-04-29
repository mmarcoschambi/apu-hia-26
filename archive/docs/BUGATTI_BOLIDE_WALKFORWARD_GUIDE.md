# 🏎️⚡📊 BUGATTI BOLIDE WALK-FORWARD - GUÍA RÁPIDA

## 🎯 ¿QUÉ ES?

El **BOLIDE WALK-FORWARD** es la evolución definitiva que combina:

1. **2-Layer Optimization** (Bolide) → 90% más rápido
2. **Walk-Forward IS/VAL/OOS** (Bugatti Optuna) → Anti-overfitting
3. **Memory Optimization** (DIVO) → 60% menos RAM

**Resultado:** El mejor motor para **producción/deployment**.

---

## 📊 METODOLOGÍA: 4 FASES

```
Timeline completo:
┌──────────────────────────────────────────────────────────────┐
│ |------- IN-SAMPLE -------|---- VAL ----|------- OOS -------|│
│   2020-01    2022-12       2023-01 06-30  2023-07  2024-12  │
│                                                               │
│ PHASE 1: Layer 1 (8 critical params) → 100 trials           │
│ PHASE 2: Layer 2 (11 secondary params) → 50 trials          │
│ PHASE 3: VALIDATION test → Degradation %                    │
│ PHASE 4: OUT-OF-SAMPLE test (optional)                      │
└──────────────────────────────────────────────────────────────┘
```

### **PHASE 1: LAYER 1 (IN-SAMPLE)**
- **Qué:** Optimiza 8 parámetros CRÍTICOS
- **Dónde:** 2020-2022 (in-sample)
- **Tickers:** 100 estratificados (30/40/30 top/mid/low)
- **Output:** Best critical params + Sharpe

### **PHASE 2: LAYER 2 (IN-SAMPLE)**
- **Qué:** Optimiza 11 parámetros SECUNDARIOS con Layer 1 FIJO
- **Dónde:** 2020-2022 (mismo período)
- **Tickers:** 50 estratificados DIFERENTES (evita overfit)
- **Output:** Final optimized config

### **PHASE 3: VALIDATION (ROBUSTNESS)**
- **Qué:** Test config en período NUEVO
- **Dónde:** 2023 H1 (nunca visto antes)
- **Objetivo:** Detectar overfitting
- **Métrica:** Degradation %
  - < 20% → ✅ EXCELLENT
  - 20-40% → ⚠️ WARNING
  - > 40% → ❌ CRITICAL OVERFITTING

### **PHASE 4: OUT-OF-SAMPLE (OPTIONAL)**
- **Qué:** Test final con datos NUNCA tocados
- **Dónde:** 2023 H2 - 2024
- **Cuándo:** Solo cuando estés listo para deploy
- **Prompt:** Manual "yes/no" (o `--run-oos`)

---

## 🚀 USO RÁPIDO

### Test Pequeño (5 min):
```bash
python3 bugatti_bolide_walkforward.py \
    --in-start 2022-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-06-30 \
    --oos-start 2023-07-01 --oos-end 2023-12-31 \
    --layer1-trials 20 --layer1-tickers 30 \
    --layer2-trials 10 --layer2-tickers 20
```

### Production Full (30-40 min):
```bash
python3 bugatti_bolide_walkforward.py \
    --in-start 2020-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-06-30 \
    --oos-start 2023-07-01 --oos-end 2024-12-31 \
    --layer1-trials 150 --layer1-tickers 150 \
    --layer2-trials 75 --layer2-tickers 100 \
    --metric sharpe \
    --run-oos  # Auto-run OOS sin prompt
```

---

## 📈 OUTPUT ESPERADO

### Durante la ejecución:
```
================================================================================
🏎️⚡📊 BUGATTI BOLIDE WALK-FORWARD
================================================================================

📊 DATA SPLIT:
  IN-SAMPLE:     2020-01-01 to 2022-12-31  (Optimize)
  VALIDATION:    2023-01-01 to 2023-06-30  (Robustness)
  OUT-OF-SAMPLE: 2023-07-01 to 2024-12-31  (Final Test)

⚙️  OPTIMIZATION:
  Layer 1: 150 trials × 150 tickers (critical)
  Layer 2: 75 trials × 100 tickers (fine-tune)

🎯 METRIC: SHARPE
💰 CAPITAL: $100,000
================================================================================

📈 PHASE 1 & 2: IN-SAMPLE OPTIMIZATION (2-LAYER)
================================================================================
🎯 LAYER 1: CRITICAL PARAMETERS
✅ Stratified universe: 150 tickers
   Top: 45 | Mid: 60 | Low: 45
🏎️💨 Initializing DIVO engine (Layer 1)...
📊 Engine: 150 tickers, 2.3 MB
🚀 Starting Layer 1 optimization (150 trials)...
[Progress bar...]

================================================================================
🏆 LAYER 1 RESULTS (IN-SAMPLE)
================================================================================
SHARPE: 1.234

🔧 LAYER 2: FINE-TUNING
✅ Stratified universe: 100 tickers (different sample)
🚀 Starting Layer 2 optimization (75 trials)...
[Progress bar...]

================================================================================
🏆 LAYER 2 RESULTS (IN-SAMPLE)
================================================================================
SHARPE: 1.456
Improvement over Layer 1: +18.0%

================================================================================
📊 PHASE 3: VALIDATION (ROBUSTNESS TEST)
================================================================================
🧪 Testing optimized params on VALIDATION period...

================================================================================
📊 VALIDATION RESULTS
================================================================================
Sharpe Ratio:  1.234
Total Return:  45.67%
Max Drawdown:  -15.23%
Win Rate:      58.34%
Total Trades:  234
Profit Factor: 1.89

🔍 OVERFITTING CHECK:
  IN-SAMPLE sharpe:  1.456
  VALIDATION sharpe: 1.234
  Degradation:       -15.3%

✅ EXCELLENT! Parameters are robust (< 20% degradation)

================================================================================
🎯 PHASE 4: OUT-OF-SAMPLE TEST
================================================================================
⚠️  Final test - only run when ready to deploy!
================================================================================

Run OUT-OF-SAMPLE test? (yes/no): yes

🚀 Running OUT-OF-SAMPLE test...

================================================================================
🏁 OUT-OF-SAMPLE RESULTS
================================================================================
Sharpe Ratio:  1.189
Total Return:  38.45%
Max Drawdown:  -18.90%
Win Rate:      55.67%
Total Trades:  198
Profit Factor: 1.67

================================================================================
✅ BOLIDE WALK-FORWARD OPTIMIZATION COMPLETE!
================================================================================
📁 Results: outputs/bolide_walkforward

📊 SUMMARY:
  IN-SAMPLE:    1.456
  VALIDATION:   1.234 (-15.3% degradation)
  OUT-OF-SAMPLE: 1.189

  Robustness:   EXCELLENT

⏱️  Time saved vs brute-force: ~90%
💾 RAM saved vs Chiron: ~60%
================================================================================

🏎️⚡📊 BOLIDE WALK-FORWARD OUT! 💨💨💨
```

---

## 📁 ARCHIVOS GENERADOS

```
outputs/bolide_walkforward/
├── layer1_trials_20260109_213045.csv          # Todos los trials Layer 1
├── layer2_trials_20260109_213045.csv          # Todos los trials Layer 2
└── bolide_walkforward_20260109_213045.json    # Report completo
```

### **JSON Report Structure:**
```json
{
  "timestamp": "2026-01-09T21:30:45",
  "method": "Bugatti_BOLIDE_WalkForward",
  "engine": "DIVO (memory-optimized)",
  
  "periods": {
    "in_sample": "2020-01-01 to 2022-12-31",
    "validation": "2023-01-01 to 2023-06-30",
    "out_of_sample": "2023-07-01 to 2024-12-31"
  },
  
  "layer1": {
    "trials": 150,
    "tickers": 150,
    "best_value": 1.234,
    "best_params": { ... }
  },
  
  "layer2": {
    "trials": 75,
    "tickers": 100,
    "best_value": 1.456,
    "improvement_pct": 18.0,
    "best_params": { ... }
  },
  
  "validation": {
    "sharpe": 1.234,
    "degradation_pct": -15.3,
    "robustness": "EXCELLENT",
    "stats": { ... }
  },
  
  "out_of_sample": {
    "run": true,
    "stats": { ... }
  },
  
  "final_params": {
    "risk_dollars": 200,
    "min_rvol": 2.0,
    "signal_type": "breakout",
    ...
  }
}
```

---

## 🎓 INTERPRETACIÓN DE RESULTADOS

### ✅ EXCELLENT (< 20% degradation)
```
IN-SAMPLE:  1.456
VALIDATION: 1.234 (-15.3%)
```
**Significado:** Parámetros son ROBUSTOS, no hay overfitting significativo.
**Acción:** ✅ Deploy en producción

### ⚠️ WARNING (20-40% degradation)
```
IN-SAMPLE:  1.456
VALIDATION: 0.912 (-37.4%)
```
**Significado:** Overfitting moderado, puede funcionar pero con cautela.
**Acción:** ⚠️ Revisar params, probar con más datos, considerar reducir complejidad

### ❌ CRITICAL (> 40% degradation)
```
IN-SAMPLE:  1.456
VALIDATION: 0.634 (-56.5%)
```
**Significado:** OVERFITTING SEVERO, memorización de ruido.
**Acción:** ❌ NO deploy, revisar metodología, usar menos params

---

## 🔬 VENTAJAS vs OTROS MOTORES

| Feature | Bugatti Optuna | BOLIDE | BOLIDE WF |
|---------|----------------|--------|-----------|
| Walk-forward IS/VAL/OOS | ✅ | ❌ | ✅ |
| 2-layer optimization | ❌ | ✅ | ✅ |
| Velocidad | Slow | Fast | Fast |
| Memory optimization | ❌ | ✅ | ✅ |
| Estratificación | ❌ | ✅ | ✅ |
| Anti-overfitting | ✅ | Medio | ✅✅ |
| Degradation % | ✅ | ❌ | ✅ |
| **RECOMENDADO PARA** | Legacy | Research | **Production** |

---

## 💡 TIPS & BEST PRACTICES

### 1. **Períodos Recomendados:**
```python
# BIEN:
--in-start 2020-01-01 --in-end 2022-12-31  # 3 años IS
--val-start 2023-01-01 --val-end 2023-06-30 # 6 meses VAL
--oos-start 2023-07-01 --oos-end 2024-12-31 # 1.5 años OOS

# MAL:
--in-start 2023-01-01 --in-end 2023-06-30  # Muy corto
--val-start 2023-07-01 --val-end 2023-09-30 # Muy corto
```

### 2. **Número de Trials:**
```python
# Quick test (5-10 min):
--layer1-trials 20 --layer2-trials 10

# Development (15-20 min):
--layer1-trials 50 --layer2-trials 25

# Production (30-40 min):
--layer1-trials 150 --layer2-trials 75

# Exhaustive (1-2 hours):
--layer1-trials 300 --layer2-trials 150
```

### 3. **Número de Tickers:**
```python
# Small cap focus (50-100 tickers):
--layer1-tickers 50 --layer2-tickers 30

# Balanced (100-200 tickers):
--layer1-tickers 150 --layer2-tickers 100

# Large universe (200+ tickers):
--layer1-tickers 300 --layer2-tickers 200
```

### 4. **Cuando NO usar walk-forward:**
- ❌ Research rápido / exploratorio
- ❌ Testing de ideas nuevas
- ❌ Tienes < 2 años de datos
- ✅ Usa BOLIDE normal en estos casos

### 5. **Cuando SÍ usar walk-forward:**
- ✅ Deploy en producción con capital real
- ✅ Tienes 3+ años de datos
- ✅ Quieres validación robusta
- ✅ Optimizas > 15 parámetros

---

## 🐛 TROUBLESHOOTING

### "All trials returned -999"
**Problema:** Ninguna combinación genera > 10 trades
**Solución:**
```bash
# 1. Período más largo
--in-start 2018-01-01  # En vez de 2020

# 2. Más tickers
--layer1-tickers 200  # En vez de 100

# 3. Filtros menos restrictivos
# Edita LAYER1_PARAMS en el código
```

### "Degradation > 40% (CRITICAL)"
**Problema:** Overfitting severo
**Solución:**
```python
# 1. Reduce complejidad - menos params
# 2. Más datos en IN-SAMPLE
# 3. Más tickers para diversidad
# 4. Check si mercado cambió entre períodos
```

### "RAM usage keeps growing"
**Problema:** Memory leak en trials largos
**Solución:**
```python
# Ya está implementado: clear_indicator_cache()
# Pero si persiste:
import gc
gc.collect()  # Después de cada phase
```

---

## 📚 REFERENCIAS

- **BOLIDE original:** `bugatti_bolide.py` (sin walk-forward)
- **Bugatti Optuna:** `bugatti_optuna.py` (walk-forward antiguo)
- **Motor DIVO:** `src/backtest/optimization_engine_divo.py`
- **Documentación:** `BUGATTI_GARAGE.md`

---

## 🏁 QUICK START

```bash
# Test rápido (5 min):
python3 bugatti_bolide_walkforward.py \
    --in-start 2022-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-06-30 \
    --layer1-trials 20 --layer1-tickers 30 \
    --layer2-trials 10 --layer2-tickers 20

# Production (30 min):
python3 bugatti_bolide_walkforward.py \
    --in-start 2020-01-01 --in-end 2022-12-31 \
    --val-start 2023-01-01 --val-end 2023-06-30 \
    --oos-start 2023-07-01 --oos-end 2024-12-31 \
    --layer1-trials 150 --layer1-tickers 150 \
    --layer2-trials 75 --layer2-tickers 100 \
    --run-oos
```

---

**Built for production. Optimized for robustness. Ready to race.** 🏎️⚡📊

**Fin.**
