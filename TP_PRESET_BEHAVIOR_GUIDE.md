# TP PRESET BEHAVIOR - DINÁMICO vs FIJO

## 📋 Tu Pregunta

> "¿Es dinámico o hardcodeado? Si hago pruebas con tp-preset aggressive_runner o conservative, luego veo los resultados de los rangos optimizados en la app?"

---

## ✅ Respuesta Directa

Es **DINÁMICO según el preset** que uses:

| Preset | Comportamiento TP % | Otros params | JSON resultante |
|--------|-------------------|--------------|-----------------|
| `optimize` | ✅ **DINÁMICO** - Optuna busca | ✅ Optimiza | % optimizados encontrados |
| `aggressive_runner` | ❌ **FIJO** - Siempre 25/30/45 | ✅ Optimiza | Siempre 25/30/45 |
| `balanced` | ❌ **FIJO** - Siempre 33/33/34 | ✅ Optimiza | Siempre 33/33/34 |
| `conservative` | ❌ **FIJO** - Siempre 40/35/25 | ✅ Optimiza | Siempre 40/35/25 |
| `classic` | ❌ **FIJO** - Siempre 50/30/20 | ✅ Optimiza | Siempre 50/30/20 |

---

## 🔍 Explicación Detallada

### Con preset FIJO (aggressive_runner, balanced, etc.):

```bash
bash run_dual_validation.sh --tp-preset aggressive_runner
```

**Qué optimiza Optuna**:
- ✅ min_rvol, min_adr, risk_dollars, tp1_r, tp2_r, etc.
- ❌ NO optimiza tp1_pct, tp2_pct, runner_pct (usa valores fijos del preset)

**JSON resultante**:
```json
{
  "parameters": {
    "min_rvol": 1.5,      // ← Optimizado
    "risk_dollars": 500,  // ← Optimizado
    "tp1_pct": 0.25,      // ← FIJO del preset
    "tp2_pct": 0.30,      // ← FIJO del preset
    "runner_pct": 0.45    // ← FIJO del preset
  }
}
```

**En Streamlit**:
- Load Validated Params carga **25/30/45** (siempre igual)
- Son los valores del preset, NO optimizados

---

### Con preset OPTIMIZE (búsqueda óptima):

```bash
bash run_dual_validation.sh --tp-preset optimize
```

**Qué optimiza Optuna**:
- ✅ min_rvol, min_adr, risk_dollars, tp1_r, tp2_r, etc.
- ✅ **SÍ optimiza tp1_pct, tp2_pct, runner_pct** (DINÁMICO)

**Rangos de búsqueda**:
```python
tp1_pct: 0.25 → 0.50 (step 0.05)
tp2_pct: 0.25 → 0.40 (step 0.05)
runner_pct: 0.15 → 0.40 (step 0.05)
Constraint: suma debe ser 0.95-1.05
```

**JSON resultante**:
```json
{
  "parameters": {
    "min_rvol": 2.0,      // ← Optimizado
    "risk_dollars": 750,  // ← Optimizado
    "tp1_pct": 0.35,      // ← OPTIMIZADO (Optuna encontró)
    "tp2_pct": 0.30,      // ← OPTIMIZADO (Optuna encontró)
    "runner_pct": 0.35    // ← OPTIMIZADO (Optuna encontró)
  }
}
```

**En Streamlit**:
- Load Validated Params carga **35/30/35** (ejemplo)
- Son valores ENCONTRADOS por Optuna, NO de ningún preset
- Pueden ser DIFERENTES cada vez que ejecutes optimize

---

## 🎯 Casos de Uso

### Caso 1: Validar un preset específico

**Pregunta**: "¿Funciona bien aggressive_runner (25/30/45) en MI universo?"

**Solución**:
```bash
bash run_dual_validation.sh --quick --tp-preset aggressive_runner
```

**Resultado**:
- JSON tendrá **25/30/45** fijos
- Optuna optimizó OTROS params (min_rvol, etc.) CON esa distribución
- En Streamlit verás **25/30/45** siempre

---

### Caso 2: Buscar distribución óptima

**Pregunta**: "¿Cuál es la MEJOR distribución para MI universo?"

**Solución**:
```bash
bash run_dual_validation.sh --tp-preset optimize
```

**Resultado**:
- JSON tendrá % OPTIMIZADOS (ej: 28/35/37)
- Puede ser diferente a cualquier preset
- En Streamlit verás lo que Optuna ENCONTRÓ

---

### Caso 3: Comparar varios presets

**Pregunta**: "¿Qué preset funciona MEJOR empíricamente?"

**Solución**:
```bash
bash compare_presets_in_streamlit.sh
```

**Resultado**:
- Ejecuta con optimize, aggressive, balanced
- Genera 3 JSONs en config/tp_comparisons/
- Reporte muestra cuál dio mejor Sharpe
- Puedes cargar cada uno en Streamlit para validar

---

## 🔄 Workflow de Comparación

### Método A: Ejecutar cada preset y comparar JSONs

```bash
# 1. Ejecutar con optimize
bash run_dual_validation.sh --quick --tp-preset optimize
cp config/validated_production_params.json config/tp_optimize.json

# 2. Ejecutar con aggressive
bash run_dual_validation.sh --quick --tp-preset aggressive_runner
cp config/validated_production_params.json config/tp_aggressive.json

# 3. Ejecutar con balanced
bash run_dual_validation.sh --quick --tp-preset balanced
cp config/validated_production_params.json config/tp_balanced.json

# 4. Comparar JSONs
python3 -c "
import json
for preset in ['optimize', 'aggressive', 'balanced']:
    with open(f'config/tp_{preset}.json') as f:
        data = json.load(f)
    p = data['parameters']
    print(f'{preset}: {p[\"tp1_pct\"]*100:.0f}/{p[\"tp2_pct\"]*100:.0f}/{p[\"runner_pct\"]*100:.0f} - Sharpe {data[\"performance\"][\"sharpe_ratio\"]:.3f}')
"
```

### Método B: Usar script automático

```bash
bash compare_presets_in_streamlit.sh
```

→ Ejecuta los 3 automáticamente
→ Genera tabla comparativa
→ Guarda backups en config/tp_comparisons/

### Método C: Comparar directamente en Streamlit UI

```bash
streamlit run app.py
```

1. NO hagas "Load Validated Params"
2. Cambia selector "Preset de Distribución":
   - Aggressive (25/30/45)
   - Ejecutar Backtest → Sharpe: ???
3. Cambia a Balanced (33/33/34)
   - Ejecutar Backtest → Sharpe: ???
4. Compara visualmente

**Ventaja**: No necesitas ejecutar dual_validation 3 veces.
**Desventaja**: Los otros params (min_rvol, etc.) no están optimizados para cada distribución.

---

## 💡 Recomendaciones

### Si quieres la MEJOR distribución científicamente:

```bash
# Ejecuta con optimize
bash run_dual_validation.sh --tp-preset optimize

# Carga en Streamlit
streamlit run app.py
→ Load Validated Params
→ Verás los % que Optuna ENCONTRÓ como óptimos
```

### Si quieres COMPARAR presets con params optimizados:

```bash
# Usa el script automático
bash compare_presets_in_streamlit.sh

# Luego en Streamlit prueba cada uno
cp config/tp_comparisons/validated_optimize.json config/validated_production_params.json
streamlit run app.py → Load Params → Backtest → Sharpe: ???

cp config/tp_comparisons/validated_aggressive.json config/validated_production_params.json
streamlit run app.py → Load Params → Backtest → Sharpe: ???
```

### Si solo quieres experimentar rápido:

```bash
streamlit run app.py

# En UI:
→ Cambia preset selector manualmente
→ Ejecuta backtest con cada uno
→ Compara Sharpe
```

**Limitación**: Los otros params (min_rvol, etc.) no estarán optimizados para cada distribución.

---

## 🎯 Respuesta Final a tu Pregunta

**"¿Es dinámico o fijo?"**

Depende del preset:
- `optimize` → **DINÁMICO** (Optuna busca, varía)
- `aggressive/balanced/etc` → **FIJO** (siempre mismo valor)

**"¿Veo los resultados optimizados en la app?"**

SÍ, pero depende de qué ejecutaste:
- Si ejecutaste con `optimize` → Verás % optimizados (ej: 28/35/37)
- Si ejecutaste con `aggressive` → Verás % fijos (25/30/45)
- Si ejecutaste con `balanced` → Verás % fijos (33/33/34)

**"¿Puedo comparar en Streamlit?"**

SÍ, 2 formas:
1. **Ejecutar 3 veces dual_validation** (una por preset) y cargar cada JSON
2. **Cambiar preset selector en UI** y ejecutar backtest con cada uno

---

## 📚 Scripts Disponibles

- `compare_presets_in_streamlit.sh` - Ejecuta 3 presets y genera backups
- `compare_tp_distributions.sh` - Comparación completa de 4 presets
- `test_streamlit_tp_integration.py` - Valida que Streamlit cargue correctamente

---

**✅ Sistema es FLEXIBLE: fijo cuando quieres, dinámico cuando optimizas!** 🎯
