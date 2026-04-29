# TP DISTRIBUTION OPTIMIZATION - QUICK START

## ⚡ Respuesta Rápida

**Pregunta**: ¿Los % de TP1/TP2/Runner se optimizan o están hardcodeados?

**Respuesta**: 
- ❌ ANTES: Hardcodeado (50/30/20)
- ✅ AHORA: **Optimizable** con 5 presets

---

## 🎯 Uso Inmediato

### Opción 1: Optimizar (Mejor)
```bash
bash run_dual_validation.sh --tp-preset optimize
```

### Opción 2: Usar Aggressive (Recomendado para momentum)
```bash
bash run_dual_validation.sh --tp-preset aggressive_runner
```

### Opción 3: Comparar todos
```bash
bash compare_tp_distributions.sh
```

---

## 📊 ¿Qué preset usar?

| Tu Sistema | Preset Recomendado | Distribución |
|------------|-------------------|--------------|
| Momentum/Breakout | `aggressive_runner` | 25% / 30% / 45% |
| Mean Reversion | `conservative` | 40% / 35% / 25% |
| No sé | `balanced` | 33% / 33% / 34% |
| Científico | `optimize` | Optuna busca |

---

## 💡 ¿Por qué importa?

**Trade de 20R** (moonshot como TSLA/GME):

- Classic (50/30/20): Capturas solo **5.65R** ❌
- Aggressive (25/30/45): Capturas **10.28R** ✅ (+82%!)

**Diferencia: 4.6R más por trade grande!**

En 5 moonshots → **+23R total = +7% performance**

---

## 🚀 Comandos Útiles

```bash
# Ver análisis teórico
python3 analyze_tp_distributions.py

# Test rápido
python3 test_tp_percentages.py

# Optimización rápida (15 min)
bash run_dual_validation.sh --quick --tp-preset optimize

# Optimización completa (1-2 horas)
bash run_dual_validation.sh --tp-preset optimize

# Comparar presets (1-2 horas)
bash compare_tp_distributions.sh
```

---

## 📖 Documentación Completa

- `TP_DISTRIBUTION_GUIDE.md` - Guía detallada
- `IMPLEMENTATION_SUMMARY_TP_OPTIMIZATION.md` - Resumen técnico
- `CHANGELOG_TP_OPTIMIZATION.md` - Changelog

---

**✅ Listo para maximizar tu Alpha!** 🚀
