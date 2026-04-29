# ✅ Cómo Verificar Qué Configuración Estás Usando en Streamlit

## 🎯 Problema Resuelto

Antes no sabías qué configuración estaba activa. **Ahora el sidebar muestra SIEMPRE:**

```
🏆 Validated Parameters
┌──────────────────────────────────────┐
│ 📊 Current Config Info               │
│                                      │
│ Config: Config_1_Window_10           │
│ Validated: 2026-02-02                │
│ Sharpe: 1.276                        │
│ TP Dist: 33% / 33% / 34%            │
│                                      │
│ ✅ ACTIVE - Using these params       │  ← SI VES ESTO = ACTIVO
│                                      │
│ ⚠️ NOT ACTIVE - Click button below   │  ← SI VES ESTO = NO ACTIVO
└──────────────────────────────────────┘

📥 Load Validated Params (botón)
🔄 Reset to Manual (botón)
```

---

## 📋 Pasos para Usar la Mejor Configuración

### 1️⃣ **Copiar el Ganador a Producción**

```bash
cp outputs/tp_comparison_20260202_205301/validated_params_balanced.json \
   config/validated_production_params.json
```

### 2️⃣ **Abrir Streamlit**

```bash
streamlit run app.py
```

### 3️⃣ **Verificar Configuración en el Sidebar**

Mira la sección **"🏆 Validated Parameters"**:

```
Config: Config_1_Window_10
Sharpe: 1.276
TP Dist: 33% / 33% / 34%
```

Si dice **"Config_3_Window_4"** o **"Sharpe: 0.867"** → ❌ No es el ganador

### 4️⃣ **Activar los Parámetros Validados**

Haz click en **"📥 Load Validated Params"**

Debe cambiar a:
```
✅ ACTIVE - Using these params
```

### 5️⃣ **Correr un Backtest**

Ahora cuando corras backtests en Streamlit, usará:
- **TP Distribution:** 33% / 33% / 34% (Balanced)
- **Otros parámetros:** min_rvol=1.0, risk=$2000, etc.

---

## 🔍 Cómo Saber si Estás Usando los Parámetros Correctos

### ✅ **CORRECTO** (usando ganador):

```
📊 Current Config Info
Config: Config_1_Window_10          ← Window 10
Validated: 2026-02-02
Sharpe: 1.276                       ← Sharpe alto
TP Dist: 33% / 33% / 34%          ← Balanced
✅ ACTIVE - Using these params
```

### ❌ **INCORRECTO** (usando config vieja):

```
📊 Current Config Info
Config: Config_3_Window_4           ← Window 4 (diferente)
Validated: 2026-02-02
Sharpe: 0.867                       ← Sharpe bajo
TP Dist: 33% / 33% / 34%          ← Balanced (TP correcto)
⚠️ NOT ACTIVE - Click button below
```

**Solución:** Copia el archivo correcto (paso 1) y recarga Streamlit.

---

## 🎛️ Qué Parámetros se Cargan

Cuando haces click en **"Load Validated Params"**, se cargan:

### Parámetros de Entrada (Filters):
- `min_rvol`: 1.0
- `min_adr`: 1.5
- `min_volume`: 300,000
- `risk_dollars`: $2000

### Parámetros de Salida (TP):
- `tp1_pct`: 0.33 (33%)
- `tp2_pct`: 0.33 (33%)
- `runner_pct`: 0.34 (34%)
- `tp1_r`: 1.25
- `tp2_r`: 3.5

### Flags:
- `require_spy_above_sma50`: True
- `use_market_regime_filter`: False
- `use_trailing_stop`: False

---

## 🔄 Cambiar Entre Configuraciones

### Para volver a configuración manual:
1. Click en **"🔄 Reset to Manual"**
2. Status cambia a: `⚠️ NOT ACTIVE`
3. Ahora puedes ajustar manualmente los sliders

### Para volver a usar validados:
1. Click en **"📥 Load Validated Params"**
2. Status cambia a: `✅ ACTIVE`

---

## ⚠️ Troubleshooting

### Problema: No veo la sección "Current Config Info"
**Solución:** Reinicia Streamlit:
```bash
pkill -f streamlit
streamlit run app.py
```

### Problema: El Sharpe dice 0.867 en vez de 1.276
**Solución:** Archivo incorrecto en producción. Ejecuta:
```bash
cp outputs/tp_comparison_20260202_205301/validated_params_balanced.json \
   config/validated_production_params.json
```

### Problema: Dice "No validated params found"
**Solución:** Corre dual validation primero:
```bash
bash run_dual_validation.sh --tp-preset balanced
```

---

## 📊 Comparación Visual

| Archivo | Config | Sharpe | Return | Trades | Status |
|---------|--------|--------|--------|--------|--------|
| `validated_params_balanced.json` (en outputs) | Config_1_Window_10 | 1.276 | 113% | 359 | 🏆 **MEJOR** |
| `validated_production_params.json` (actual) | Config_3_Window_4 | 0.867 | 9% | 56 | ❌ Viejo |

**Acción:** Copiar el MEJOR al archivo actual.

---

## ✅ Checklist Final

- [ ] Archivo copiado: `outputs/.../validated_params_balanced.json` → `config/validated_production_params.json`
- [ ] Streamlit reiniciado: `pkill -f streamlit && streamlit run app.py`
- [ ] Sidebar muestra: **"Sharpe: 1.276"** ✅
- [ ] Sidebar muestra: **"Config_1_Window_10"** ✅
- [ ] Click en: **"📥 Load Validated Params"** ✅
- [ ] Status dice: **"✅ ACTIVE - Using these params"** ✅

¡Listo! Ahora estás usando la mejor configuración. 🚀

