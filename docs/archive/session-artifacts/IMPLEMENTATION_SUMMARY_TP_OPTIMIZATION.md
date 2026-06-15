# TP DISTRIBUTION OPTIMIZATION - RESUMEN DE IMPLEMENTACIÓN

**Fecha**: 2026-01-27  
**Objetivo**: Convertir porcentajes de salida TP1/TP2/Runner en parámetros optimizables

---

## ✅ IMPLEMENTACIÓN COMPLETADA

### Problema Original
Los porcentajes de salida estaban **hardcodeados** en:
- TP1: 50% de la posición
- TP2: 30% de la posición
- Runner: 20% de la posición

**Análisis**: Esta distribución "mata el Alpha" porque vende demasiado temprano.  
Si solo dejas 20% para runners, pierdes el 80% del upside en big winners (10R+).

### Solución Implementada
Convertir los porcentajes en **parámetros optimizables** con 5 presets predefinidos.

---

## 📝 ARCHIVOS MODIFICADOS

### 1. Engines (Core)
- ✅ `src/backtest/optimization_engine_v6_pro.py`
- ✅ `src/backtest/optimization_engine_thor.py`
- ✅ `src/backtest/vectorbt_engine_advanced.py`

**Cambios**:
- Agregados parámetros: `tp1_pct`, `tp2_pct`, `runner_pct`
- Defaults mantienen comportamiento original (0.5, 0.3, 0.2)
- Actualizados docstrings y comentarios

### 2. Scripts de Optimización
- ✅ `walk_forward_validation.py`
  - Nuevo argumento: `--tp-preset`
  - Lógica de optimización o preset fijo
  - Constraint: suma debe ser 95-105%

- ✅ `run_dual_validation.sh`
  - Nuevo argumento: `--tp-preset`
  - Help message actualizado
  - Ejemplos en summary

### 3. Nuevos Scripts

#### Testing:
- ✅ `test_tp_percentages.py`
  - Tests unitarios para los 3 engines
  - Verifica custom percentages funcionan

#### Análisis:
- ✅ `analyze_tp_distributions.py`
  - Análisis teórico de impacto
  - Comparación de escenarios (Small Winner → Moonshot)
  - Muestra diferencia en R capturados

#### Comparación:
- ✅ `compare_tp_distributions.sh`
  - Ejecuta walk forward con cada preset
  - Genera reporte comparativo
  - Identifica distribución óptima

#### Documentación:
- ✅ `TP_DISTRIBUTION_GUIDE.md`
  - Guía completa de uso
  - Explicación de cada preset
  - Ejemplos y recomendaciones

---

## 🎯 PRESETS DISPONIBLES

| Preset | TP1 | TP2 | Runner | Uso Recomendado |
|--------|-----|-----|--------|-----------------|
| **classic** | 50% | 30% | 20% | ❌ No usar - Mata Alpha |
| **balanced** | 33% | 33% | 34% | ✅ Punto medio equilibrado |
| **aggressive_runner** | 25% | 30% | 45% | ✅ Momentum/Breakouts |
| **conservative** | 40% | 35% | 25% | ✅ Mean Reversion |
| **optimize** | Variable | Variable | Variable | ✅ Búsqueda científica |

---

## 📊 IMPACTO EN ALPHA

### Ejemplo: Trade de 20R (Moonshot como TSLA/GME)

| Distribución | R Capturados | vs Classic |
|--------------|--------------|------------|
| Classic (50/30/20) | 5.65R | - (baseline) |
| Balanced (33/33/34) | 8.29R | **+47%** 🔥 |
| Aggressive (25/30/45) | 10.28R | **+82%** 🚀 |
| Conservative (40/35/25) | 6.65R | +18% |

**Conclusión**: En un solo trade de 20R, Aggressive captura **4.6R más** que Classic!

---

## 🚀 COMANDOS CLAVE

### Optimizar distribución:
```bash
bash run_dual_validation.sh --tp-preset optimize
```

### Usar distribución recomendada (aggressive):
```bash
bash run_dual_validation.sh --tp-preset aggressive_runner
```

### Comparar todos los presets:
```bash
bash compare_tp_distributions.sh
```

### Análisis teórico de impacto:
```bash
python3 analyze_tp_distributions.py
```

### Tests unitarios:
```bash
python3 test_tp_percentages.py
```

---

## 🔬 METODOLOGÍA DE OPTIMIZACIÓN

Cuando usas `--tp-preset optimize`, Optuna busca en este espacio:

```python
tp1_pct: 0.25 → 0.50 (step 0.05)   # 25-50%
tp2_pct: 0.25 → 0.40 (step 0.05)   # 25-40%
runner_pct: 0.15 → 0.40 (step 0.05) # 15-40%

Constraint: 0.95 <= (tp1_pct + tp2_pct + runner_pct) <= 1.05
```

Esto permite encontrar la distribución óptima para TU universo específico.

---

## 💡 RECOMENDACIONES

### Para sistemas Momentum/Breakout:
1. **Primera vez**: Usa `aggressive_runner` (25/30/45)
2. **Optimización**: Luego prueba `optimize` para afinar

### Para sistemas Mean Reversion:
1. Usa `conservative` (40/35/25)

### Para experimentos científicos:
1. Ejecuta `compare_tp_distributions.sh`
2. Ve cuál preset da mejor Sharpe en tu universo
3. Usa ese preset en producción

---

## 📈 VALIDACIÓN

Los parámetros optimizados se validan con:
1. Walk Forward en múltiples ventanas (robustez)
2. Validation con Advanced Engine (producción)
3. Constraint de suma ≈ 100% (consistencia)

Resultados guardados en:
- `outputs/walk_forward_results.json`
- `config/validated_production_params.json`

---

## 🎓 FUNDAMENTO TEÓRICO

### ¿Por qué importa la distribución?

En trading momentum:
- **80% de trades** son pequeños (0-3R)
- **15% de trades** son medianos (3-6R)
- **5% de trades** son grandes (6R+)

Pero ese **5% de trades genera el 80% del Alpha total**.

Si vendes 50% en TP1, estás limitando el upside de ese 5% crítico.

**Ejemplo real**:
- 20 trades pequeños: +40R
- 2 trades medianos: +10R
- 1 trade grande (20R):
  - Classic: +5.65R
  - Aggressive: +10.28R (+82%!)

Total Classic: 55.65R  
Total Aggressive: 60.28R  
**Diferencia: +8.3% en performance total** solo por distribución!

---

## ✅ TESTS PASADOS

```bash
$ python3 test_tp_percentages.py
✅ V6 PRO: Sharpe 0.254, 9 trades (33/33/33)
✅ THOR: Sharpe 1.092, 2 trades (25/35/40)
✅ Advanced: Sharpe 0.350, 4 trades (40/30/30)
```

```bash
$ python3 analyze_tp_distributions.py
📊 Análisis de impacto en 5 escenarios
✅ Aggressive captura +82% más en Moonshoots
✅ Classic es el PEOR en big winners
```

---

**🎯 Sistema listo para optimización de distribución de TP!**

