# 🚨 BUG CRÍTICO: Todos los TP Presets Dan Mismo Resultado

## Síntoma

```
balanced:          Sharpe 1.249, 61 trades
classic:           Sharpe 1.249, 61 trades (IDÉNTICO)
conservative:      Sharpe 1.249, 61 trades (IDÉNTICO)
aggressive_runner: Sharpe 1.249, 61 trades (IDÉNTICO)
```

**TODOS los presets dan exactamente el mismo resultado.**

Esto es IMPOSIBLE ya que usan diferentes TP distributions:
- balanced: 33% / 33% / 34%
- classic: 50% / 30% / 20%
- conservative: 40% / 35% / 25%
- aggressive_runner: 25% / 30% / 45%

---

## Causa Raíz

El bug está en `walk_forward_validation.py` líneas 259-262:

```python
# Add TP percentages if using preset (not in best_params from Optuna)
tp_config = self.tp_presets.get(self.tp_preset)
if tp_config is not None:
    full_params.update(tp_config)
```

**Posibles causas:**
1. `self.tp_preset` no se está actualizando correctamente
2. `self.tp_presets` no contiene el preset correcto
3. Los TP% se están aplicando DESPUÉS de validation (tarde)
4. Cache corrupto que devuelve siempre mismos resultados

---

## Diagnóstico Agregado

Agregué logging en línea 261:

```python
logger.info(f"🔍 DEBUG TP CONFIG:")
logger.info(f"   tp_preset: {self.tp_preset}")
logger.info(f"   tp_config: {tp_config}")
logger.info(f"   Before update: tp1={full_params.get('tp1_pct')}")
if tp_config is not None:
    full_params.update(tp_config)
    logger.info(f"   After update: tp1={full_params.get('tp1_pct')}")
```

---

## Reproducción

```bash
bash test_tp_bug.sh
```

Esto corre 4 presets diferentes y verifica si:
1. El TP config se carga correctamente
2. Se aplica al full_params
3. Se guarda en validated_production_params.json

---

## Solución Temporal

Mientras debuggeo esto, puedes:

**Opción A: Editar manualmente validated_production_params.json**
```bash
# Después de correr cada preset, editar el JSON:
vim config/validated_production_params.json
# Cambiar tp1_pct/tp2_pct/runner_pct manualmente
```

**Opción B: Usar backtest_dynamic_universe.py directo**
```bash
# Especificar TP% como argumentos
python3 backtest_dynamic_universe.py \
  --tp1-pct 0.33 \
  --tp2-pct 0.33 \
  --runner-pct 0.34 \
  # ... otros params
```

**Opción C: Esperar fix**
Estoy investigando la causa raíz ahora.

---

## Status

✅ **RESUELTO**

---

## Causa Real: Race Condition (Ejecución Paralela)

El usuario corrió los 4 presets **EN PARALELO**:

```bash
bash run_dual_validation.sh --tp-preset balanced &
bash run_dual_validation.sh --tp-preset classic &
bash run_dual_validation.sh --tp-preset conservative &
bash run_dual_validation.sh --tp-preset aggressive_runner &
wait
```

**Problema:**
- Los 4 procesos escriben al mismo archivo: `outputs/walk_forward_results.json`
- Race condition: El último en terminar sobreescribe el resultado
- Todos leen el mismo resultado final (por eso son idénticos)

---

## Solución

### Opción A: Secuencial (Recomendado)

Usa el nuevo script que automatiza todo:

```bash
bash run_all_tp_presets.sh
```

Esto corre los 4 presets **secuencialmente** y:
- Guarda cada resultado en archivo único
- Genera reporte de comparación
- Selecciona automáticamente el ganador
- Copia el mejor a `config/validated_production_params.json`

**Tiempo: ~40-60 minutos** (pero resultados correctos ✅)

### Opción B: Manual Secuencial

```bash
# Uno por uno (espera a que termine cada uno)
bash run_dual_validation.sh --tp-preset balanced
bash run_dual_validation.sh --tp-preset classic
bash run_dual_validation.sh --tp-preset conservative
bash run_dual_validation.sh --tp-preset aggressive_runner
```

### Opción C: Paralelo con Aislamiento (Avanzado)

Requiere modificar `walk_forward_validation.py` para aceptar `--output-suffix`:

```bash
# Not implemented yet
```

---

## Próximos Pasos

1. ✅ Corre: `bash run_all_tp_presets.sh`
2. ⏳ Espera ~45 minutos
3. ✅ Revisa el reporte de comparación
4. ✅ El ganador se copia automáticamente
5. ✅ Prueba en Streamlit: `streamlit run app.py`
