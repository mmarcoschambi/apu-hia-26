# 🏎️ BUGATTI EVO - Walk-Forward Configuration Guide

## 📊 TU SITUACIÓN ACTUAL

**Data Disponible:**
- **123 tickers** con data completa
- **IN-SAMPLE**: 2020-01-01 → 2022-12-31 (3 años, 756 días)
- **VALIDATION**: 2023-01-01 → 2023-06-30 (6 meses, 124 días)
- **OOS**: 2023-07-01 → 2024-12-31 (18 meses, 378 días)

**Problema detectado:** Error "No data loaded" porque el universo aleatorio no encontró tickers válidos.

---

## 🎯 OPCIONES DE CONFIGURACIÓN

### **OPCIÓN 1: AUMENTAR TICKERS POR FOLD** ⭐ (RECOMENDADO)
**Pros:**
- Más robusto (más data = más señales estadísticas)
- Reduce overfitting (diversificación)
- Aprovecha tus 123 tickers disponibles

**Cons:**
- Más lento (más tickers = más cálculos)

**Configuración sugerida:**
```bash
python3 bugatti_evo.py \
  --k-folds 3 \
  --fold-size 100 \           # ← DE 50 a 100
  --l1-trials 50 \
  --l2-trials 30 \
  --in-start 2020-01-01 \
  --in-end 2022-12-31 \
  --val-start 2023-01-01 \
  --val-end 2023-06-30 \
  --oos-start 2023-07-01 \
  --oos-end 2024-12-31 \
  --run-oos
```

**Por qué funciona:**
- Con 100 tickers por fold y stratified sampling (30% High / 40% Mid / 30% Low), aseguras que SIEMPRE habrá tickers en todos los períodos
- K=3 folds da 3 muestras independientes para votación democrática

---

### **OPCIÓN 2: MÁS FOLDS (Mayor Diversidad)**
**Pros:**
- Mayor confianza estadística (más votos)
- Mejor detección de overfitting

**Cons:**
- MUY lento (3x-5x tiempo de ejecución)
- Puede no mejorar mucho si los folds son similares

**Configuración sugerida:**
```bash
python3 bugatti_evo.py \
  --k-folds 5 \              # ← DE 3 a 5
  --fold-size 80 \
  --l1-trials 40 \           # ← Reducir trials por fold para compensar
  --l2-trials 25 \
  --in-start 2020-01-01 \
  --in-end 2022-12-31 \
  --val-start 2023-01-01 \
  --val-end 2023-06-30 \
  --oos-start 2023-07-01 \
  --oos-end 2024-12-31 \
  --run-oos
```

**Cuándo usar:** Si después de la Opción 1 sigues viendo mucha varianza entre folds (Stability Score < 60%)

---

### **OPCIÓN 3: EXTENDER PERÍODOS** (NO RECOMENDADO)
**Cambiar fechas a:**
```
IN-SAMPLE: 2019-01-01 → 2022-12-31 (4 años)
VALIDATION: 2023-01-01 → 2023-12-31 (1 año)
OOS: 2024-01-01 → 2024-12-31 (1 año)
```

**Pros:**
- Más data = más trades = más confianza

**Cons:**
- ⚠️ **RIESGO DE LOOK-AHEAD BIAS**: Si extiendes VALIDATION/OOS hacia el pasado, estás "mirando el futuro" desde la perspectiva de IN-SAMPLE
- Rompes la filosofía Walk-Forward (debe ser temporal: pasado → futuro)
- Solo útil si tienes MÁS data histórica (ej: 2015-2019)

**Cuándo usar:** SOLO si tienes más data histórica antes de 2020

---

### **OPCIÓN 4: NINGUNA (Usar menos tickers)**
**Si el problema es que 150 tickers no están en tu DB:**
- Ya verificamos que tienes 123 tickers completos
- Puedes usar 100-120 por fold sin problema

**NO es necesario** cambiar nada de períodos.

---

## 🏆 **RECOMENDACIÓN FINAL**

### **Para máxima robustez (producción):**
```bash
python3 bugatti_evo.py \
  --k-folds 3 \
  --fold-size 100 \
  --l1-trials 50 \
  --l2-trials 30 \
  --equity 100000 \
  --seed 42 \
  --in-start 2020-01-01 \
  --in-end 2022-12-31 \
  --val-start 2023-01-01 \
  --val-end 2023-06-30 \
  --oos-start 2023-07-01 \
  --oos-end 2024-12-31 \
  --run-oos
```

**Tiempo estimado:** 15-25 minutos
**Resultado esperado:** Sharpe ~0.5-0.8 en CV, degradación < 30% en validation

### **Para testing rápido:**
```bash
python3 bugatti_evo.py \
  --k-folds 3 \
  --fold-size 80 \
  --l1-trials 30 \
  --l2-trials 20 \
  --in-start 2021-01-01 \    # ← Solo 2 años
  --in-end 2022-12-31 \
  --val-start 2023-01-01 \
  --val-end 2023-06-30
```

**Tiempo estimado:** 5-8 minutos

---

## 🔍 **INTERPRETACIÓN DE RESULTADOS**

### **Stability Score:**
- **> 80%**: Excelente (params muy estables)
- **60-80%**: Bueno (ligera varianza)
- **40-60%**: Aceptable (hay overfitting moderado)
- **< 40%**: Crítico (revisar params o agregar más folds)

### **Degradation (Validation vs CV):**
- **< 20%**: Excelente robustez
- **20-40%**: Aceptable (ligero overfitting)
- **> 40%**: Overfitting severo (reducir complejidad)

### **Votación Democrática:**
```
🗳️  Voting with 3/3 qualified folds (Sharpe > 0.5)  ← IDEAL
🗳️  Voting with 2/3 qualified folds (Sharpe > 0.5)  ← Aceptable
⚠️  WARNING: Only 1/3 folds passed                    ← Revisar params
❌ CRITICAL: All folds returned -999                  ← Data o params rotos
```

---

## 🛠️ **TROUBLESHOOTING**

### **Error "No data loaded":**
- **Causa:** Stratified sampling no encontró suficientes tickers en ese período
- **Fix:** Aumentar `--fold-size` a 100-120 (tienes 123 disponibles)

### **Todos los folds devuelven -999:**
- **Causa 1:** `require_positive_rs=True` demasiado restrictivo
- **Causa 2:** Parámetros de filtro muy estrictos
- **Fix:** Verificar que RS funciona (ya fixed ✅)

### **Sharpe negativo en OOS:**
- **Causa:** Overfitting en IN-SAMPLE
- **Fix:** Aumentar K-folds, reducir trials, o usar período IN-SAMPLE más largo

---

## 📈 **PRÓXIMOS PASOS**

1. **Ejecutar con config recomendada** (fold-size=100)
2. **Revisar report JSON:** `outputs/bugatti_evo/bugatti_evo_report_*.json`
3. **Si Stability < 60%:** Aumentar a 5 folds
4. **Si Degradation > 40%:** Reducir L2 trials o simplificar LAYER2_PARAMS
5. **Si OOS Sharpe < 0:** Tu estrategia necesita más trabajo

---

**"La robustez no es coincidencia, es estadística."** 🏎️💨
