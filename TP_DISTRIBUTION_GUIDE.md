# TP DISTRIBUTION OPTIMIZATION - GUÍA

## 📋 RESUMEN

Los porcentajes de salida en TP1, TP2 y Runner ahora son **PARAMETROS OPTIMIZABLES** en lugar de estar hardcodeados.

### ¿Qué cambió?

**ANTES (Hardcodeado):**
- TP1: 50% de la posición
- TP2: 30% de la posición  
- Runner: 20% de la posición

**AHORA (Configurable y Optimizable):**
- Los 3 engines aceptan `tp1_pct`, `tp2_pct`, `runner_pct` como parámetros
- `run_dual_validation.sh` puede optimizar o usar presets
- Se valida que la suma sea ≈ 100%

---

## 🎯 PRESETS DISPONIBLES

### 1. `optimize` (Default)
Busca la distribución óptima usando Optuna:
- tp1_pct: 25-50%
- tp2_pct: 25-40%
- runner_pct: 15-40%
- **Constraint**: Suma debe estar entre 95-105%

### 2. `classic` (Tradicional - ⚠️ Mata Alpha)
- TP1: 50%
- TP2: 30%
- Runner: 20%
- ❌ **PROBLEMA**: Vende demasiado temprano, limita upside

### 3. `balanced` (Equilibrado)
- TP1: 33%
- TP2: 33%
- Runner: 34%
- ✅ Distribución equitativa de riesgo/reward

### 4. `aggressive_runner` (Busca Home Runs)
- TP1: 25%
- TP2: 30%
- Runner: 45%
- ✅ **RECOMENDADO** para capturar Alpha
- Deja correr más posición para grandes movimientos

### 5. `conservative` (Asegura ganancias)
- TP1: 40%
- TP2: 35%
- Runner: 25%
- Prioriza asegurar ganancias sobre maximizar upside

---

## 🚀 USAGE

### Walk Forward con preset específico:
```bash
python3 walk_forward_validation.py \
    --tp-preset balanced \
    --start 2023-01-01 \
    --end 2024-12-31
```

### Dual Validation con preset:
```bash
bash run_dual_validation.sh --tp-preset aggressive_runner
```

### Optimizar distribución:
```bash
bash run_dual_validation.sh --tp-preset optimize
```

### Comparar todos los presets:
```bash
bash compare_tp_distributions.sh
```

---

## 📊 ARCHIVOS MODIFICADOS

### Engines actualizados:
1. ✅ `src/backtest/optimization_engine_v6_pro.py`
   - Acepta `tp1_pct`, `tp2_pct`, `runner_pct` en params
   - Defaults: 0.5, 0.3, 0.2

2. ✅ `src/backtest/optimization_engine_thor.py`
   - Acepta `tp1_pct`, `tp2_pct`, `runner_pct` en params
   - Defaults: 0.5, 0.3, 0.2

3. ✅ `src/backtest/vectorbt_engine_advanced.py`
   - Acepta `tp1_pct`, `tp2_pct`, `runner_pct` en constructor kwargs
   - Defaults: 0.5, 0.3, 0.2

### Scripts de optimización:
4. ✅ `walk_forward_validation.py`
   - Nuevo argumento: `--tp-preset`
   - Optimiza TP percentages si preset='optimize'
   - Usa valores fijos si preset != 'optimize'

5. ✅ `run_dual_validation.sh`
   - Nuevo argumento: `--tp-preset`
   - Propaga preset a walk_forward_validation.py

### Nuevos scripts:
6. ✅ `test_tp_percentages.py`
   - Tests unitarios para TP percentages
   - Verifica los 3 engines

7. ✅ `compare_tp_distributions.sh`
   - Compara los 4 presets principales
   - Genera reporte comparativo

---

## 💡 RECOMENDACIONES

### Para maximizar Alpha:
```bash
# Opción 1: Deja que Optuna optimice
bash run_dual_validation.sh --tp-preset optimize

# Opción 2: Usa aggressive_runner
bash run_dual_validation.sh --tp-preset aggressive_runner
```

### Para testing conservador:
```bash
bash run_dual_validation.sh --tp-preset conservative
```

### Para experimentar:
```bash
# Compara todos y ve cuál da mejor Sharpe
bash compare_tp_distributions.sh
```

---

## 🔧 INTEGRACIÓN CON OTROS SCRIPTS

Los parámetros optimizados se guardan en:
- `outputs/walk_forward_results.json` (incluye tp1_pct, tp2_pct, runner_pct)
- `config/validated_production_params.json` (parámetros validados)

Estos pueden usarse directamente en:
- `simplified_backtest.py`
- `app.py` (Streamlit dashboard)
- `live_scanner.py`
- `bugatti_*.py` (optimization scripts)

---

## 📈 ANÁLISIS TEÓRICO

### Por qué 50/30/20 mata el Alpha:

Si tienes un trade ganador que hace 10R:
- **Classic (50/30/20)**: 
  - 50% sale en 1.5R = 0.75R
  - 30% sale en 3R = 0.9R
  - 20% sale en 10R = 2.0R
  - **Total: 3.65R**

- **Aggressive Runner (25/30/45)**:
  - 25% sale en 1.5R = 0.375R
  - 30% sale en 3R = 0.9R
  - 45% sale en 10R = 4.5R
  - **Total: 5.775R** ← 58% más Alpha! 🚀

### Por qué importa:

En sistemas de breakout momentum:
- La mayoría de trades son pequeños (1-2R)
- Unos POCOS trades hacen 5-15R
- Esos pocos trades generan TODO el Alpha

**Conclusión**: Dejar correr más % en runners captura mejor el Alpha de los big movers.

---

## 🧪 TESTING

Ejecuta el test para verificar que todo funciona:
```bash
python3 test_tp_percentages.py
```

Debería mostrar resultados para los 3 engines con distribuciones custom.

---

## 📚 REFERENCIAS

- Análisis original: "Vende solo 1/3 en TP1 y deja 2/3 para buscar ese TP2 o Runner"
- Implementación: 2026-01-27
- Engines afectados: V6_PRO, THOR, Advanced
- Scripts actualizados: walk_forward, dual_validation

---

**¡Ahora puedes optimizar científicamente cuánto vender en cada nivel!** 🎯
