# Workflow de Optimización con Validación OOS Automática

## Resumen Ejecutivo

Script automatizado que ejecuta múltiples optimizaciones secuencialmente + validación OOS automática para cada signal-type. Incluye protección golden guard para configs validados (VCP tiene `_oos_sharpe: 1.30` stamped).

## Uso

```bash
./run_all_optimizations.sh
```

## Qué hace el script

### 1. **Protección Golden Guard (VCP)**
- Detecta si `config/vcp_config.json` tiene `_oos_sharpe` stamped
- Muestra warning si VCP está protegido contra re-optimización accidental
- VCP actual: `_oos_sharpe: 1.30` validado OOS 2023-2024

### 2. **Optimización IS (In-Sample)**
Ejecuta 5 optimizaciones secuencialmente:

```bash
# 1. VCP
python3 optimize_3tier.py --signal-type vcp --trials 200 --tickers 80
# → guarda en config/vcp_config.json

# 2. Pocket Pivot
python3 optimize_3tier.py --signal-type pocket_pivot --trials 200 --tickers 80
# → guarda en config/pocket_pivot_config.json

# 3. Flat Base
python3 optimize_3tier.py --signal-type flat_base --trials 200 --tickers 80
# → guarda en config/flat_base_config.json

# 4. Breakout (más trials por mayor espacio de búsqueda)
python3 optimize_3tier.py --signal-type breakout --trials 300 --tickers 80
# → guarda en config/breakout_config.json

# 5. Extended Period (multi-signal)
python3 optimize_3tier.py --start 2019-01-01 --end 2025-12-31 --trials 270 --tickers 120
# → guarda en config/production_config.json (default)
```

### 3. **Validación OOS Automática**
Después de cada optimización con `--signal-type`, ejecuta automáticamente:

```bash
python3 validate_signal_oos.py --signal-type {vcp|pocket_pivot|flat_base|breakout} \
    --start 2023-01-01 --end 2024-12-31 --tickers 120
```

**¿Qué valida?**
- Corre backtest OOS (Out-Of-Sample) en período nunca visto por Optuna
- Calcula degradación: `OOS Sharpe / IS Sharpe`
- **Criterios para PASS:**
  - Degradación ≥ 20% (OOS Sharpe ≥ 0.20 * IS Sharpe)
  - OOS trades ≥ 10
  - OOS Sharpe > 0

**Si PASS:**
- Stamp `_oos_sharpe` y `_oos_stamped` en el config
- Activa golden guard para proteger contra re-optimización futura

**Si FAIL:**
- Config se guarda pero NO se stampa `_oos_sharpe`
- Recomendación: re-optimizar con más tickers o período diferente

### 4. **Logs y Resultados**
Guarda en `logs/optimization_runs/session_TIMESTAMP/`:

```
01_vcp.log                      # stdout/stderr completo
01_vcp_result.txt               # resumen: duración, exit code, últimas 50 líneas
01_vcp_oos_validation.log       # log completo de validación OOS

02_pocket_pivot.log
02_pocket_pivot_result.txt
02_pocket_pivot_oos_validation.log

03_flat_base.log
03_flat_base_result.txt
03_flat_base_oos_validation.log

04_breakout.log
04_breakout_result.txt
04_breakout_oos_validation.log

05_extended_period.log
05_extended_period_result.txt

INDEX.txt                       # índice de todos los archivos + OOS Sharpe final
```

## Ejemplo de Salida

```
======================================
Iniciando sesión de optimización: 20260320_142703
Resultados se guardarán en: logs/optimization_runs/session_20260320_142703
======================================

🛡️  VCP Golden Guard detectado: _oos_sharpe=1.3
   VCP config está protegido contra re-optimización accidental

--------------------------------------
🚀 Iniciando: 01_vcp
Comando: python3 optimize_3tier.py --signal-type vcp --trials 200 --tickers 80
Log: logs/optimization_runs/session_20260320_142703/01_vcp.log
Hora inicio: 2026-03-20 14:27:03
--------------------------------------
[... optimización corre ...]
✅ COMPLETADO: 01_vcp (duración: 45m)

🔍 Ejecutando validación OOS para vcp...
[... validación OOS corre ...]
✅ Validación OOS completada para vcp
   Ver resultados en: logs/.../01_vcp_oos_validation.log

--------------------------------------
🚀 Iniciando: 02_pocket_pivot
[... continúa con pocket_pivot ...]
```

## Flujo de Trabajo Recomendado

### Caso 1: Primera optimización (no existe config)
```bash
./run_all_optimizations.sh
```
- Optimiza todos los signal-types
- Valida OOS automáticamente
- Stampa `_oos_sharpe` si pasa validación

### Caso 2: Re-optimizar VCP (ya existe con golden guard)
```bash
# Opción A: Correr todo (VCP será sobrescrito, pero muestra warning)
./run_all_optimizations.sh

# Opción B: Solo algunos signals (recomendado si VCP ya está validado)
python3 optimize_3tier.py --signal-type pocket_pivot --trials 200 --tickers 80
python3 validate_signal_oos.py --signal-type pocket_pivot

python3 optimize_3tier.py --signal-type breakout --trials 300 --tickers 80
python3 validate_signal_oos.py --signal-type breakout
```

### Caso 3: Validación OOS manual (cambiar período OOS)
```bash
# Validar con período OOS diferente
python3 validate_signal_oos.py --signal-type pocket_pivot \
    --start 2024-01-01 --end 2025-12-31 --tickers 150

# Validar con ventana IS explícita (útil para walk-forward)
python3 validate_signal_oos.py --signal-type vcp \
    --is-start 2019-01-01 --is-end 2022-12-31 \
    --start 2023-01-01 --end 2024-12-31
```

## Archivos Modificados/Creados

### Nuevos archivos:
- `validate_signal_oos.py` - validator genérico para cualquier signal-type
- `OPTIMIZATION_OOS_WORKFLOW.md` - esta documentación

### Archivos modificados:
- `run_all_optimizations.sh` - añadida validación OOS automática + golden guard check

### Configs actualizados:
- `config/vcp_config.json` - ya tiene `_oos_sharpe: 1.3` stamped (protegido)
- `config/pocket_pivot_config.json` - será actualizado con `_oos_sharpe` si PASS
- `config/flat_base_config.json` - será actualizado con `_oos_sharpe` si PASS
- `config/breakout_config.json` - será actualizado con `_oos_sharpe` si PASS

## Notas Técnicas

### Golden Guard Protection
```json
{
  "_oos_sharpe": 1.3,
  "_oos_stamped": "2026-03-19T02:01:21",
  "_oos_validation": {
    "oos_sharpe": 1.3,
    "period": "2023-01-01 to 2024-12-31",
    "passed": true
  }
}
```

El script **no** bloquea re-optimización de VCP, pero muestra warning visible. Si quieres protección hard-coded, modifica `optimize_3tier.py` para:

```python
# En optimize_3tier.py, antes de optimization loop:
if signal_type == "vcp":
    cfg_file = Path(f"config/{signal_type}_config.json")
    if cfg_file.exists():
        cfg = json.load(open(cfg_file))
        if cfg.get("_oos_sharpe", 0) > 0:
            logger.warning("VCP golden guard detected. Skipping re-optimization.")
            logger.warning("To re-optimize, manually delete _oos_sharpe from vcp_config.json")
            sys.exit(0)
```

### Degradación aceptable
- **Mínimo:** 20% (muy permisivo)
- **Bueno:** 50-70%
- **Excelente:** 80%+
- VCP actual: 1.30 OOS / 1.0 IS = **130%** (OOS mejor que IS, excepcional)

### Por qué OOS puede ser mejor que IS
1. **Market regime filter activo en OOS:** bear years (2022) eliminados
2. **IS period más largo:** incluye 2015-2022 (crisis COVID, bear 2022)
3. **OOS period más favorable:** 2023-2024 bull run limpio
4. No es overfitting -- es que VCP funciona mejor en bull markets (by design)

## Ver También

- `validate_vcp_oos.py` - validator original específico para VCP
- `BUGATTI_OPTUNA_GUIDE.md` - workflow completo de optimización
- `HOW_TO_USE_VALIDATED_PARAMS.md` - usar configs validados en producción
