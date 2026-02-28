# CÓMO USAR LOS PARÁMETROS VALIDADOS EN PRODUCCIÓN
====================================================

## 📊 Resultados Logrados

**Walk Forward (2021-2024):**
- Return acumulado OOS: **43.31%** en 3.75 años
- Anualizado: **11.55%** por año
- Total trades: 294
- Sharpe promedio: 0.71
- Ventanas ganadoras: 67%

**Validación con Advanced:**
- Mejor config: Window 10
- Sharpe: 0.52
- Annual Return: 0.15%
- Trades: 19
- Win Rate: 63%

## ✅ Fixes Aplicados

**1. Zero Shares rejections (reducidos de 66% a ~0%):**
   - `max_exposure_pct`: 25% → 35%
   - `rvol_danger_size`: 25% → 40%
   - `rvol_warning_size`: 60% → 70%

**2. Sector Strength:**
   - `require_positive_rs`: True → False (default)
   - Permite operativa en sectores neutrales

**3. Convergencia THOR-Advanced:**
   - Breakout signal agregado en baseline mode
   - ADR period alineado a 20 días
   - Código duplicado eliminado

## 🚀 Implementación en Producción

### Opción 1: Backtest con Params Validados

```bash
# Test rápido (6 meses)
python3 use_validated_params.py --start 2024-01-01 --end 2024-06-30

# Backtest completo (5 años)
python3 use_validated_params.py --start 2020-01-01 --end 2024-12-31

# Con features opcionales
python3 use_validated_params.py --start 2023-01-01 \
    --use-sector-rotation \
    --use-market-regime \
    --capital 200000
```

**Resultado esperado (2024 H1):**
- Trades: 12
- Return: 4.43%
- Sharpe: 1.23
- Win Rate: 75%

### Opción 2: Aplicar a Streamlit Dashboard (app.py)

**Método A - Cargar desde config:**

```python
# En app.py, línea ~50
import json

# Load validated params
with open('config/validated_production_params.json') as f:
    config = json.load(f)
    validated_params = config['parameters']

# Create engine with validated params
engine = AdvancedVectorBTEngine(
    universe=selected_tickers,
    start_date=start_date,
    end_date=end_date,
    signal_type='breakout',  # CRITICAL for convergence
    **validated_params
)
```

**Método B - UI con valores precargados:**

```python
# En sidebar, pre-cargar valores validados
min_rvol = st.sidebar.slider(
    'Min RVOL', 
    min_value=1.0, 
    max_value=3.0, 
    value=validated_params.get('min_rvol', 1.0),  # Valor validado
    step=0.5
)
```

### Opción 3: Live Scanner

```bash
# Modificar live_scanner.py para usar validated params
python3 live_scanner.py --use-validated-params
```

**Implementación:**

```python
# En live_scanner.py
if args.use_validated_params:
    with open('config/validated_production_params.json') as f:
        config = json.load(f)
        params = config['parameters']
else:
    params = default_params
```

## 📋 Params Validados (Config_1_Window_10)

```json
{
  "min_rvol": 1.0,
  "min_adr": 3.0,
  "risk_dollars": 150,
  "max_dist_sma20": 10.0,
  "tp1_r": 1.25,
  "tp2_r": 4.0,
  "require_spy_above_sma50": false,  ← Override para permitir trades
  "min_volume": 300000,
  "min_dollar_volume": 5000000,
  "max_stop_pct": 7.0,
  "min_consolidation_days": 10,
  "rvol_warning": 2.0,
  "rvol_danger": 3.0,
  "rvol_warning_size": 0.70,  ← Relajado (era 0.65)
  "rvol_danger_size": 0.40,   ← Relajado (era 0.30)
  "use_phases": true,
  "signal_type": "breakout"   ← CRÍTICO para convergencia
}
```

## 🔧 Implementación Paso a Paso

### PASO 1: Test Rápido

```bash
# Verificar que params funcionan
python3 use_validated_params.py --start 2024-01-01 --end 2024-06-30
```

**Esperado:** 12 trades, 4.43% return, Sharpe 1.23

### PASO 2: Backtest Largo

```bash
# Validar en 5 años
python3 use_validated_params.py --start 2020-01-01 --end 2024-12-31
```

**Esperado:** 50-100 trades, 15-20% return total

### PASO 3: Integrar en app.py

**Opción Simple - Hardcode params:**

```python
# En app.py, reemplazar params defaults con validated
engine = AdvancedVectorBTEngine(
    universe=tickers,
    start_date=start,
    end_date=end,
    signal_type='breakout',
    min_rvol=1.0,
    min_adr=3.0,
    risk_dollars=150,
    max_dist_sma20=10.0,
    tp1_r=1.25,
    tp2_r=4.0,
    require_spy_above_sma50=False,
    min_consolidation_days=10,
    max_stop_pct=7.0,
    rvol_warning_size=70,
    rvol_danger_size=40,
    use_phases=True
)
```

**Opción Avanzada - Cargar dinámicamente:**

```python
# Función helper en app.py
def load_validated_params():
    config_file = Path('config/validated_production_params.json')
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)['parameters']
    return None

# En main
validated = load_validated_params()
if validated and st.sidebar.checkbox('Use Validated Params', value=True):
    params = validated
else:
    params = {
        'min_rvol': st.sidebar.slider(...),
        # ... custom params
    }
```

### PASO 4: Live Trading

```bash
# Morning scan con validated params
python3 live_scanner.py --use-validated-params --min-score 7.5
```

## 🎯 Mejoras de Performance

**ANTES (sin optimización):**
- Return: 0.9% en 5 años
- Trades: 17 totales
- Conversión: ~3%

**DESPUÉS (con validated params + fixes):**
- Return: 43% en 3.75 años (11.55%/año)
- Trades: 294 totales (~80/año)
- Conversión: ~30% (era 3.7%, fixes lo mejoraron)
- Zero_shares rechazos: 0 (era 66%)

## ⚠️ Notas Importantes

**1. signal_type='breakout' es CRÍTICO:**
   - Sin esto, Advanced usa lógica trend (close > SMA20)
   - Con validated params de V6_PRO no funcionará
   - SIEMPRE pasar `signal_type='breakout'`

**2. require_spy_above_sma50 override:**
   - Validated params tiene `true`
   - Pero bloquea trades en mercados laterales
   - Script override a `false` automáticamente
   - Re-habilita si usas `--use-market-regime`

**3. Capital y Exposure:**
   - max_exposure aumentado a 35%
   - Si usas capital > $100k, ajusta proporcionalmente
   - Ej: $200k → max_exposure puede ser 40-50%

## 📈 Performance Esperada

**Período 2024 (H1):**
- Trades: 12
- Return: 4.43%
- Sharpe: 1.23
- Win Rate: 75%

**Período 2020-2024 (full):**
- Trades: 50-80
- Return: 15-20%
- Sharpe: 0.8-1.2
- Win Rate: 60-70%

## 🔄 Re-optimización

Si performance degrada en futuro:

```bash
# Re-run dual validation
bash run_dual_validation.sh

# Esto actualiza config/validated_production_params.json
# Luego re-aplicar a producción
```

Frecuencia recomendada: Cada 6-12 meses o cuando Sharpe < 0.5
