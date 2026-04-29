# 🚀 Quick Start - Bugatti Optuna

## Script Principal

**ÚNICO script que necesitas**: `bugatti_optuna.py`

## Comandos Rápidos

### Prueba Rápida (10 min)
```bash
python3 bugatti_optuna.py --trials 50 --tickers 30
```

### Optimización Profesional (1-2 horas)
```bash
python3 bugatti_optuna.py \
  --in-start 2018-01-01 --in-end 2021-12-31 \
  --val-start 2022-01-01 --val-end 2023-12-31 \
  --oos-start 2024-01-01 --oos-end 2024-12-31 \
  --trials 200 --tickers 80
```

### Walk-Forward Completo (Para producción)
```bash
python3 bugatti_optuna.py \
  --in-start 2012-01-01 --in-end 2016-12-31 \
  --val-start 2017-01-01 --val-end 2021-12-31 \
  --oos-start 2022-01-01 --oos-end 2025-12-31 \
  --trials 300 --tickers 100 --metric sharpe
```

## ¿Qué Optimiza?

**29 parámetros en rangos robustos**:

- ✅ Signal Types (VCP, Breakout, ATH)
- ✅ Sector Rotation (Top 30-50%, RS filter)
- ✅ VCP Consolidation (10-25 días)
- ✅ Momentum (ADR, RVol)
- ✅ Position Sizing (RVol-based, ADR-based)
- ✅ Earnings Filter (evita earnings)
- ✅ Relative Strength (sector vs SPY)
- ✅ Multi-Phase Exits (TP1, TP2, Runner)

## Resultados

Archivos generados en: `outputs/walk_forward_v6_pro_optuna/`

- `in_sample_trials.csv` - Todos los trials de Optuna
- `final_report.json` - Mejores parámetros encontrados

## Motor

- **V6_PRO**: Carga datos UNA vez (100× más rápido)
- **Optuna**: Búsqueda bayesiana inteligente
- **Walk-Forward**: Evita overfitting (IN/VAL/OOS)

## Documentación Completa

Lee: `BUGATTI_OPTUNA_GUIDE.md`
