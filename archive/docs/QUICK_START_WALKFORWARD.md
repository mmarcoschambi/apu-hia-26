# 🚀 QUICK START - WALK FORWARD

## 📋 Contexto Rápido

**¿Qué se descubrió?**
- ✅ THOR contaba todos los exits (TP1+TP2+Runner) → FIXED
- ✅ Parámetros óptimos encontrados (Trial #29, Sharpe 1.14)
- ✅ Out-of-sample validado (2024: Sharpe 3.78)
- ✅ `require_spy_above_sma50` mejora +35% Sharpe

**¿Los resultados son buenos?**
- ✅ **SÍ, EXCELENTES**
- Convergencia: Sharpe diff 0.01
- Optimización: +93% mejora
- OOS: +232% mejor que in-sample

---

## ⚡ EJECUTAR AHORA (3 opciones)

### **Opción 1: Pipeline Completo (RECOMENDADO)**

```bash
bash run_complete_pipeline.sh
```

**Qué hace:**
1. Aplica parámetros óptimos ✅
2. Valida convergencia ✅
3. Pregunta quick/full mode
4. Ejecuta Walk Forward
5. Analiza rangos robustos
6. Genera config de producción

**Tiempo:** 10-60 min

---

### **Opción 2: Solo Walk Forward**

```bash
# Quick (10 min, 5 ventanas)
bash run_walk_forward.sh --quick

# Full (60 min, 7-10 ventanas)
bash run_walk_forward.sh
```

Luego:
```bash
python3 analyze_robust_ranges.py
```

---

### **Opción 3: Manual Step-by-Step**

```bash
# 1. Validar que fixes funcionan
python3 test_convergence_quick.py

# 2. Validation completa
python3 validation_baseline.py --all

# 3. Walk Forward
bash run_walk_forward.sh --quick

# 4. Rangos robustos
python3 analyze_robust_ranges.py

# 5. Aplicar a producción
python3 update_production_params.py
```

---

## 📊 ¿Qué esperar del Walk Forward?

### **Métricas objetivo:**

| Métrica | Target | Interpretación |
|---------|--------|----------------|
| Mean Sharpe | > 0.8 | Performance promedio |
| Sharpe StdDev | < 0.4 | Consistencia |
| Robustness Score | > 1.5 | Mean/StdDev |
| Win Rate | > 70% | Porcentaje de exits positivos |

### **Ejemplo de output esperado:**

```
📊 WALK FORWARD AGGREGATE RESULTS
Metric               | Mean   | Median | Std    | Min    | Max   
--------------------------------------------------------------------
Sharpe Ratio         | 1.05   | 1.12   | 0.35   | 0.61   | 1.48
Return %             | 2.15   | 2.03   | 0.89   | 0.87   | 3.44
Win Rate %           | 74.3   | 75.0   | 6.2    | 66.7   | 85.7

🎯 ROBUSTNESS SCORE: 2.14
   ✅ EXCELLENT: Very stable across windows
```

---

## 🎯 Rangos Robustos Esperados

```python
{
    'min_rvol': (1.5, 2.0),        # Centro: 1.75
    'min_adr': (2.0, 2.5),         # Centro: 2.25
    'risk_dollars': (100, 150),    # Centro: 125
    'max_dist_sma20': (8.0, 12.0), # Centro: 10.0
    'tp1_r': (1.25, 1.5),          # Centro: 1.375
    'tp2_r': (2.5, 3.5)            # Centro: 3.0
}
```

**Usar el CENTRO como parámetros de producción.**

---

## ⚠️ Si Walk Forward falla

### **Problema: Muy pocos trades**
```bash
# Aumentar universo de tickers
--tickers AAPL MSFT GOOGL NVDA TSLA META AMZN NFLX

# O relajar filtros
--trials 50  # Más búsqueda
```

### **Problema: Takes too long**
```bash
# Usar quick mode
bash run_walk_forward.sh --quick

# O reducir trials
bash run_walk_forward.sh --trials 20
```

---

## 📈 Después del Walk Forward

1. **Revisar** `outputs/walk_forward_results.json`
2. **Ejecutar** `python3 analyze_robust_ranges.py`
3. **Implementar** parámetros del centro de rangos robustos
4. **Backtest final** con params validados
5. **Deploy** a producción

---

## 🏁 EJECUTA AHORA

```bash
bash run_complete_pipeline.sh
```

**Duración:** 10-60 min

**Output:** Parámetros validados y listos para producción

---

**¿Listo?** → `bash run_complete_pipeline.sh` 🚀
