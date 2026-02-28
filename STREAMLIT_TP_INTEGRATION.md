# STREAMLIT TP DISTRIBUTION INTEGRATION

## ✅ Respuesta Corta

**SÍ**, la app de Streamlit ahora carga y configura los porcentajes de TP optimizados cuando presionas el botón **"Load Validated Params"**.

---

## 🔧 Cómo Funciona

### 1. Cuando presionas "📥 Load Validated Params":

La app carga `config/validated_production_params.json` que ahora incluye:
```json
{
  "parameters": {
    "tp1_r": 2.0,
    "tp2_r": 2.5,
    "tp1_pct": 0.30,    ← Nuevo!
    "tp2_pct": 0.40,    ← Nuevo!
    "runner_pct": 0.35  ← Nuevo!
  }
}
```

### 2. Los valores se cargan en la UI:

La app tiene una nueva sección **"Exit Distribution"** con:
- Selector de preset (Balanced, Aggressive, Conservative, etc.)
- 3 number inputs para TP1%, TP2%, Runner%
- Validación que sumen ~100%

### 3. Modos de uso:

#### Modo A: Load Validated Params (Automático)
1. Presionas "📥 Load Validated Params"
2. La app carga los % optimizados de `validated_production_params.json`
3. Los muestra en los controles UI
4. Los pasa al backtest engine

#### Modo B: Preset Manual
1. Seleccionas un preset (ej: "Aggressive (25/30/45)")
2. Los inputs se actualizan automáticamente
3. Están disabled (no editables) hasta que elijas "Custom"

#### Modo C: Custom Manual
1. Seleccionas "Custom" en el preset selector
2. Ajustas manualmente TP1%, TP2%, Runner%
3. La app valida que sumen ~100%

---

## 📋 Cambios en app.py

### Agregados a la UI:

```python
# Nueva sección de Exit Distribution
st.markdown("**Exit Distribution (% of Position)**")
st.caption("⚠️ Vender 50% en TP1 mata el Alpha. Usa 33% o menos.")

# Preset selector
tp_preset = st.selectbox(
    "Preset de Distribución",
    ["Custom", "Balanced (33/33/34)", "Aggressive (25/30/45)", 
     "Conservative (40/35/25)", "Classic (50/30/20)"]
)

# 3 number inputs para los porcentajes
tp1_pct_input = st.number_input("TP1 %", value=33.0, ...)
tp2_pct_input = st.number_input("TP2 %", value=33.0, ...)
runner_pct_input = st.number_input("Runner %", value=34.0, ...)

# Validación de suma
if abs(total_pct - 100) > 5:
    st.warning(f"⚠️ Total: {total_pct:.0f}% (debería sumar ~100%)")
```

### Actualizado en run_cached_backtest:

```python
def run_cached_backtest(
    ...,
    tp1_r=1.75, 
    tp2_r=3.5,
    tp1_pct=0.5,     # Nuevo!
    tp2_pct=0.3,     # Nuevo!
    runner_pct=0.2   # Nuevo!
):
    engine = AdvancedVectorBTEngine(
        ...,
        tp1_pct=tp1_pct,
        tp2_pct=tp2_pct,
        runner_pct=runner_pct
    )
```

### Carga de Validated Params:

```python
# Si hay validated params, los usa como defaults
vp = st.session_state.get('validated_params', {})

def_tp1_pct = vp.get('tp1_pct', 0.5) * 100 if vp else 33.0
def_tp2_pct = vp.get('tp2_pct', 0.3) * 100 if vp else 33.0
def_runner_pct = vp.get('runner_pct', 0.2) * 100 if vp else 34.0
```

---

## 🚀 Flujo Completo

### Workflow típico:

1. **Optimizar parámetros**:
   ```bash
   bash run_dual_validation.sh --tp-preset optimize
   ```
   → Genera `config/validated_production_params.json` con tp1_pct, tp2_pct, runner_pct optimizados

2. **Abrir Streamlit**:
   ```bash
   streamlit run app.py
   ```

3. **Cargar params validados**:
   - Click en "📥 Load Validated Params"
   - Los % optimizados se cargan automáticamente
   - Aparecen en la UI

4. **Ejecutar backtest**:
   - Los % optimizados se pasan al engine
   - Resultados usan la distribución optimizada

---

## 📊 Ejemplo Visual en UI

```
🏆 Validated Parameters
┌─────────────────────────────────────┐
│  📥 Load Validated Params           │  ← Click aquí
└─────────────────────────────────────┘

✅ Loaded: Config_4_Window_14
   Validated: 2026-01-27

🛡️ Institutional Risk Manager
─────────────────────────────────────

Profit Targets (R-Multiples)
┌──────────┬──────────┐
│ TP1 (R)  │ TP2 (R)  │
│  2.0     │  2.5     │  ← Cargados del JSON
└──────────┴──────────┘

Exit Distribution (% of Position)
⚠️ Vender 50% en TP1 mata el Alpha

Preset: [Custom ▼]

┌──────────┬──────────┬──────────┐
│ TP1 %    │ TP2 %    │ Runner % │
│  30      │  40      │  35      │  ← Cargados del JSON
└──────────┴──────────┴──────────┘

✅ Total: 105%  (o mensaje de validación)
```

---

## ✅ Validación

Para verificar que funciona:

### Test 1: Syntax
```bash
python3 -m py_compile app.py
# ✅ Passed
```

### Test 2: Cargar validated params
```bash
streamlit run app.py
# 1. Click "Load Validated Params"
# 2. Verifica que TP1%, TP2%, Runner% se actualicen
# 3. Verifica que sumen ~100%
```

### Test 3: Backtest con params optimizados
```bash
# 1. Load Validated Params
# 2. Ejecuta backtest
# 3. Verifica en logs/trades que use los % correctos
```

---

## 🎯 Presets Disponibles en UI

Cuando seleccionas un preset, los valores se ajustan automáticamente:

| Preset | TP1% | TP2% | Runner% | Total |
|--------|------|------|---------|-------|
| Custom | (manual) | (manual) | (manual) | ? |
| Balanced | 33% | 33% | 34% | 100% |
| Aggressive | 25% | 30% | 45% | 100% |
| Conservative | 40% | 35% | 25% | 100% |
| Classic | 50% | 30% | 20% | 100% |

**Recomendación**: Usa "Custom" solo si cargaste validated params. Sino usa "Aggressive" o "Balanced".

---

## 💡 Recomendaciones de Uso

### Flujo Recomendado:

1. Primero, optimiza:
   ```bash
   bash run_dual_validation.sh --quick --tp-preset optimize
   ```

2. Luego, en Streamlit:
   - Click "📥 Load Validated Params"
   - Verifica los % cargados
   - Ejecuta backtest

3. Experimenta con presets:
   - Prueba "Balanced" vs "Aggressive"
   - Compara Sharpe y returns
   - Ve cuál funciona mejor para TU universo

### Tips:

- ⚠️ **NO uses Classic (50/30/20)** - mata el Alpha
- ✅ Empieza con **Balanced (33/33/34)** si no sabes cuál usar
- ✅ Usa **Aggressive (25/30/45)** para momentum
- ✅ Usa **optimize** en dual_validation para búsqueda científica

---

## 🔬 Troubleshooting

### Problema: "No validated params found"

**Solución**: Ejecuta primero:
```bash
bash run_dual_validation.sh --quick --tp-preset optimize
```

Esto generará `config/validated_production_params.json` con los % optimizados.

### Problema: "Los % no suman 100%"

**Solución**: 
- Si usas preset: está garantizado que suman 100%
- Si usas Custom: ajusta manualmente hasta que la app muestre ✅

### Problema: "Los % no se cargan del JSON"

**Solución**: Verifica que `config/validated_production_params.json` tenga:
```json
{
  "parameters": {
    "tp1_pct": 0.33,
    "tp2_pct": 0.33,
    "runner_pct": 0.34
  }
}
```

Si no tiene estos campos, re-ejecuta dual_validation con la nueva versión.

---

## 📚 Archivos Relacionados

- `app.py` - Streamlit UI (actualizada con TP controls)
- `config/validated_production_params.json` - Params optimizados
- `src/backtest/vectorbt_engine_advanced.py` - Engine que usa los %
- `TP_DISTRIBUTION_GUIDE.md` - Guía completa

---

**✅ Streamlit listo para usar TP percentages optimizados!** 🎯
