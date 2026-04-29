# 🏗️ ARQUITECTURA MODULAR - FEATURE IMPLEMENTATION

## 🎯 TU PREGUNTA

**"Tengo que modularizar? Para implementar una nueva feature tengo que hacerla doble (THOR + Advanced)?"**

**RESPUESTA:** ✅ **SÍ, PERO hay una estructura que simplifica todo.**

---

## 📊 ESTADO ACTUAL - 2 Motores

### **1. THOR Engine** (Optimización rápida)
- **Archivo:** `src/backtest/optimization_engine_thor.py`
- **Propósito:** Grid search, optimización Optuna
- **Velocidad:** ⚡ RÁPIDO (NumPy vectorizado)
- **Uso:** Encontrar parámetros óptimos

### **2. Advanced Engine** (VectorBT, simulación realista)
- **Archivo:** `src/backtest/vectorbt_engine_advanced.py`
- **Propósito:** Validación, partial exits, simulación precisa
- **Velocidad:** 🐌 Más lento (más realista)
- **Uso:** Validar parámetros, OOS testing

---

## 🔧 ARQUITECTURA DE FEATURES

### **Patrón Actual:**

```
Feature Nueva → Implementar en 3 lugares:

1. THOR Engine       (optimization_engine_thor.py)
2. Advanced Engine   (vectorbt_engine_advanced.py)  
3. Streamlit UI      (app.py)
```

**Ejemplo:** `require_spy_above_sma50`

---

## 📝 PASO A PASO: IMPLEMENTAR UNA FEATURE

### **Ejemplo:** Nueva feature `use_volume_surge_filter`

#### **PASO 1: THOR Engine** 

```python
# src/backtest/optimization_engine_thor.py

def optimize(self, params: Dict) -> Dict:
    # 1. Extraer parámetro
    use_volume_surge = params.get('use_volume_surge_filter', False)  # ← AQUÍ
    min_volume_surge = params.get('min_volume_surge', 3.0)
    
    # 2. Calcular indicador (si no existe)
    volume_surge = data['volume'] / data['volume'].rolling(20).mean()
    
    # 3. Aplicar filtro
    base_filters = (
        (close > sma20) & 
        (rvol >= min_rvol)
    )
    
    if use_volume_surge:  # ← AQUÍ
        base_filters &= (volume_surge >= min_volume_surge)
    
    # 4. Generar señales
    signals = base_filters
```

**Tiempo:** ~5-10 min

---

#### **PASO 2: Advanced Engine**

```python
# src/backtest/vectorbt_engine_advanced.py

def __init__(self, 
             universe: List[str],
             # ... otros params ...
             use_volume_surge_filter: bool = False,  # ← AQUÍ
             min_volume_surge: float = 3.0):
    
    self.use_volume_surge_filter = use_volume_surge_filter  # ← AQUÍ
    self.min_volume_surge = min_volume_surge

def calculate_entries(self):
    # 1. Calcular indicador
    volume_ma20 = self.volume.rolling(20).mean()
    volume_surge = self.volume / volume_ma20
    
    # 2. Aplicar filtro
    entries = (
        (self.close > self.sma20) &
        (self.rvol >= self.min_rvol)
    )
    
    if self.use_volume_surge_filter:  # ← AQUÍ
        entries &= (volume_surge >= self.min_volume_surge)
    
    return entries
```

**Tiempo:** ~10-15 min

---

#### **PASO 3: Streamlit UI**

```python
# app.py

with st.sidebar:
    st.header("⚙️ Feature Toggles")
    
    # Nueva feature
    use_volume_surge = st.checkbox(
        "Volume Surge Filter",
        value=False,
        help="Require volume > 3x average"
    )
    
    if use_volume_surge:
        min_volume_surge = st.slider(
            "Min Volume Surge",
            min_value=2.0,
            max_value=5.0,
            value=3.0,
            step=0.5
        )

# Pasar a engine
if engine_choice == "THOR":
    engine = OptimizationEngineTHOR(
        tickers=universe,
        # ...
    )
    result = engine.optimize({
        'use_volume_surge_filter': use_volume_surge,
        'min_volume_surge': min_volume_surge if use_volume_surge else 3.0,
    })

elif engine_choice == "Advanced":
    engine = AdvancedVectorBTEngine(
        universe=universe,
        use_volume_surge_filter=use_volume_surge,
        min_volume_surge=min_volume_surge if use_volume_surge else 3.0,
    )
```

**Tiempo:** ~5 min

---

## 🎯 TOTAL TIME: ~20-30 min por feature

---

## 💡 CÓMO SIMPLIFICAR - SHARED CONFIG

### **Solución: Centralizar parámetros**

```python
# config/feature_flags.py

class FeatureConfig:
    """Configuración compartida de features."""
    
    # Feature toggles
    FEATURES = {
        'require_spy_above_sma50': {
            'default': False,
            'description': 'Require SPY > SMA50 for market regime',
            'impact': '+0.35 Sharpe',
            'type': 'boolean'
        },
        'use_volume_surge_filter': {
            'default': False,
            'description': 'Require volume surge > threshold',
            'impact': 'TBD',
            'type': 'boolean',
            'params': {
                'min_volume_surge': {
                    'default': 3.0,
                    'range': (2.0, 5.0),
                    'type': 'float'
                }
            }
        },
        # ... más features
    }
    
    @classmethod
    def get_defaults(cls):
        """Get all default values."""
        return {
            name: config['default'] 
            for name, config in cls.FEATURES.items()
        }
    
    @classmethod
    def get_ui_config(cls, feature_name):
        """Get UI configuration for Streamlit."""
        return cls.FEATURES[feature_name]
```

---

### **Uso en THOR:**

```python
# src/backtest/optimization_engine_thor.py

from config.feature_flags import FeatureConfig

def optimize(self, params: Dict) -> Dict:
    # Auto-load defaults
    feature_defaults = FeatureConfig.get_defaults()
    params = {**feature_defaults, **params}  # Merge
    
    # Use features
    if params['use_volume_surge_filter']:
        # ... lógica
```

---

### **Uso en Advanced:**

```python
# src/backtest/vectorbt_engine_advanced.py

from config.feature_flags import FeatureConfig

def __init__(self, **kwargs):
    # Auto-load defaults
    defaults = FeatureConfig.get_defaults()
    
    for key, default_val in defaults.items():
        setattr(self, key, kwargs.get(key, default_val))
```

---

### **Uso en Streamlit:**

```python
# app.py

from config.feature_flags import FeatureConfig

# Auto-generate UI
st.header("⚙️ Feature Toggles")

for feature_name, config in FeatureConfig.FEATURES.items():
    if config['type'] == 'boolean':
        value = st.checkbox(
            config['description'],
            value=config['default'],
            help=f"Impact: {config['impact']}"
        )
        
        # Store in session_state or dict
        params[feature_name] = value
```

---

## 🚀 WORKFLOW RECOMENDADO

### **Implementar Nueva Feature:**

```bash
# 1. Definir en config (1 archivo)
vim config/feature_flags.py

# 2. Implementar lógica en THOR (1 función)
vim src/backtest/optimization_engine_thor.py

# 3. Implementar lógica en Advanced (1 función)
vim src/backtest/vectorbt_engine_advanced.py

# 4. UI se auto-genera (si usas FeatureConfig)
# app.py ya detecta nuevas features automáticamente

# 5. Test
python3 test_new_feature.py
```

---

## 📋 CHECKLIST PARA NUEVA FEATURE

### **Pre-implementación:**
- [ ] Definir en `config/feature_flags.py`
- [ ] Documentar impacto esperado
- [ ] Definir valores por default

### **Implementación:**
- [ ] THOR: Agregar parámetro en `optimize()`
- [ ] THOR: Implementar lógica de filtro/indicador
- [ ] Advanced: Agregar parámetro en `__init__()`
- [ ] Advanced: Implementar lógica de filtro/indicador
- [ ] App: Agregar checkbox/slider (o auto-generate)

### **Testing:**
- [ ] Test unitario: `test_feature_name.py`
- [ ] Convergence test: `validation_baseline.py --phase 1`
- [ ] Feature impact: `validation_baseline.py --phase 2`
- [ ] Optimization: `validation_baseline.py --phase 4`

### **Validation:**
- [ ] In-sample Sharpe improvement > +0.1
- [ ] Out-of-sample validation
- [ ] Convergence THOR/Advanced < 20% diff

---

## 🛠️ TEMPLATE PARA NUEVA FEATURE

Voy a crear un archivo template...

```python
# templates/new_feature_template.py

"""
TEMPLATE: Implementar nueva feature
====================================

Feature: {FEATURE_NAME}
Description: {DESCRIPTION}
Expected Impact: {EXPECTED_SHARPE_DELTA}
"""

# ===========================================================================
# STEP 1: Config Definition
# ===========================================================================

# config/feature_flags.py
FEATURES = {
    '{feature_name}': {
        'default': False,
        'description': '{description}',
        'impact': 'TBD',
        'type': 'boolean',
        'params': {
            '{param_name}': {
                'default': {default_value},
                'range': ({min}, {max}),
                'type': '{type}'
            }
        }
    }
}

# ===========================================================================
# STEP 2: THOR Implementation
# ===========================================================================

# src/backtest/optimization_engine_thor.py

def optimize(self, params: Dict) -> Dict:
    # Extract params
    use_feature = params.get('{feature_name}', False)
    feature_param = params.get('{param_name}', {default})
    
    # Calculate indicator (if needed)
    # {indicator_calculation}
    
    # Apply filter
    if use_feature:
        base_filters &= ({condition})
    
    # Continue with backtest...

# ===========================================================================
# STEP 3: Advanced Implementation
# ===========================================================================

# src/backtest/vectorbt_engine_advanced.py

def __init__(self, 
             {feature_name}: bool = False,
             {param_name}: float = {default},
             **kwargs):
    
    self.{feature_name} = {feature_name}
    self.{param_name} = {param_name}

def calculate_entries(self):
    # Calculate indicator
    # {indicator_calculation}
    
    # Apply filter
    if self.{feature_name}:
        entries &= ({condition})
    
    return entries

# ===========================================================================
# STEP 4: Streamlit UI
# ===========================================================================

# app.py

with st.sidebar:
    {feature_name} = st.checkbox(
        "{Feature Display Name}",
        value=False,
        help="{Help text}"
    )
    
    if {feature_name}:
        {param_name} = st.slider(
            "{Param Display Name}",
            min_value={min},
            max_value={max},
            value={default}
        )

# ===========================================================================
# STEP 5: Testing
# ===========================================================================

# test_{feature_name}.py

def test_feature_impact():
    # Test THOR
    thor_params = {
        '{feature_name}': True,
        '{param_name}': {test_value}
    }
    thor_result = run_thor(thor_params)
    
    # Test Advanced
    advanced_result = run_advanced(**thor_params)
    
    # Validate convergence
    assert abs(thor_result['sharpe'] - advanced_result['sharpe']) < 0.2

def test_feature_validation():
    # Run feature impact analysis
    results = run_validation_baseline(feature='{feature_name}')
    
    # Check improvement
    assert results['sharpe_delta'] > 0.1  # Expect improvement
"""
```

---

## 🎯 RESUMEN EJECUTIVO

### **¿Hay que implementar doble?**

**SÍ**, en 2-3 lugares:
1. THOR (optimización)
2. Advanced (validación)
3. App UI (opcional, puede auto-generarse)

### **¿Cómo simplificar?**

✅ **Centralizar en `config/feature_flags.py`:**
- Define features una sola vez
- THOR/Advanced importan de ahí
- UI se auto-genera

### **Tiempo por feature:**
- Con template: **20-30 min**
- Sin template: **30-60 min**

---

## 📂 ARCHIVOS A CREAR

### **1. Feature Config (centralizado)**
```
config/
└── feature_flags.py  ← CREAR ESTO
```

### **2. Templates**
```
templates/
├── new_feature_template.py
├── test_feature_template.py
└── README_TEMPLATES.md
```

### **3. Helper Scripts**
```
scripts/
├── generate_feature_scaffold.py  ← Auto-genera código
└── validate_feature_sync.py      ← Verifica que ambos engines tengan la feature
```

---

## 🚀 MEJORA PROPUESTA

Voy a crear estos archivos para simplificar tu workflow...

¿Quieres que cree:
1. `config/feature_flags.py` (centralizado)
2. `templates/new_feature_template.py` (template)
3. `scripts/generate_feature_scaffold.py` (auto-genera código)

Esto reduciría el tiempo de 30 min → **5 min** por feature.

---

**Next:** ¿Crear esta infraestructura modular?
