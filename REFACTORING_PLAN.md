# 🔧 Plan de Refactorización: Consolidación de Motores

## 🎯 Problema Identificado

### Divergencia en Conteo de Trades
- **THOR**: Reporta `total_trades = unique_entries = len(all_trades) // 3`
  - 3 entradas → 9 salidas → **Reporta 3 trades**
- **Advanced**: Reporta `total_trades = len(all_trades)`
  - 3 entradas → 9 salidas → **Reporta 9 trades**

### Win Rate también diverge
- **THOR (L763)**: `win_rate = winners / all_trades_count` pero reporta `unique_entries`
- **Advanced (L1550)**: `win_rate = winners / total_trades` (todas las salidas)
- **Resultado**: Win rate 85.71% vs 66.67% (19% diferencia)

---

## 📋 Arquitectura Propuesta

### 1. Módulos Compartidos

```
src/utils/
├── metrics.py           ← Cálculos comunes (RVOL, ADR, Sharpe, etc)
├── trade_counter.py     ← Lógica de conteo unificada
└── validators.py        ← Validación de convergencia
```

### 2. Módulo: `src/utils/metrics.py`

**Funciones a extraer:**

```python
def calculate_rvol(volume: float, avg_volume: float) -> float:
    """Calcula Relative Volume de manera estándar"""
    return volume / avg_volume if avg_volume > 0 else 0.0

def calculate_adr(high: pd.Series, low: pd.Series, close: pd.Series, periods: int = 20) -> pd.Series:
    """Calcula Average Daily Range"""
    daily_range = (high - low) / close * 100
    return daily_range.rolling(periods).mean()

def calculate_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    """Calcula Sharpe Ratio anualizado"""
    if returns.std() == 0 or len(returns) == 0:
        return 0.0
    return returns.mean() / returns.std() * np.sqrt(periods_per_year)

def calculate_max_drawdown(equity: pd.Series) -> float:
    """Calcula Max Drawdown en porcentaje"""
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    return abs(drawdown.min())
```

### 3. Módulo: `src/utils/trade_counter.py`

**Funciones para estandarizar conteo:**

```python
from enum import Enum
from typing import Dict, Tuple
import pandas as pd

class CountingMethod(Enum):
    COMPLETE_POSITIONS = "complete"  # 1 entrada = 1 trade
    ALL_EXITS = "all"                # Cada exit = 1 trade
    DUAL = "dual"                    # Reporta ambos

def count_trades(
    trades_df: pd.DataFrame,
    method: CountingMethod = CountingMethod.COMPLETE_POSITIONS
) -> Dict:
    """
    Cuenta trades de manera estandarizada.
    
    Args:
        trades_df: DataFrame con todas las salidas (TP1, TP2, Runner)
        method: Método de conteo
        
    Returns:
        Dict con métricas según el método
    """
    total_exits = len(trades_df)
    
    if method == CountingMethod.COMPLETE_POSITIONS:
        # Asume 3 salidas por entrada
        unique_positions = total_exits // 3
        return {
            'total_trades': unique_positions,
            'total_exits': total_exits,
            'counting_method': 'complete_positions',
            'breakdown': {
                'tp1': total_exits // 3,
                'tp2': total_exits // 3,
                'runner': total_exits // 3
            }
        }
    
    elif method == CountingMethod.ALL_EXITS:
        return {
            'total_trades': total_exits,
            'total_exits': total_exits,
            'counting_method': 'all_exits'
        }
    
    elif method == CountingMethod.DUAL:
        return {
            'complete_positions': total_exits // 3,
            'total_exits': total_exits,
            'counting_method': 'dual'
        }

def calculate_win_rate(
    trades_df: pd.DataFrame,
    method: CountingMethod = CountingMethod.COMPLETE_POSITIONS
) -> float:
    """
    Calcula win rate según método de conteo.
    
    COMPLETE_POSITIONS: Una posición es ganadora si PnL neto > 0
    ALL_EXITS: Cada exit se evalúa independientemente
    """
    if len(trades_df) == 0:
        return 0.0
    
    if method == CountingMethod.COMPLETE_POSITIONS:
        # Agrupar por entrada (cada 3 exits)
        n_positions = len(trades_df) // 3
        wins = 0
        
        for i in range(n_positions):
            position_trades = trades_df.iloc[i*3:(i+1)*3]
            net_pnl = position_trades['PnL'].sum()
            if net_pnl > 0:
                wins += 1
        
        return wins / n_positions if n_positions > 0 else 0.0
    
    else:  # ALL_EXITS
        winners = len(trades_df[trades_df['PnL'] > 0])
        return winners / len(trades_df)
```

### 4. Modificaciones a los Motores

**THOR (`optimization_engine_thor.py`):**
```python
from src.utils.trade_counter import count_trades, calculate_win_rate, CountingMethod
from src.utils.metrics import calculate_sharpe, calculate_max_drawdown

# Línea ~750-790:
trade_stats = count_trades(all_trades, method=CountingMethod.COMPLETE_POSITIONS)
win_rate_pct = calculate_win_rate(all_trades, method=CountingMethod.COMPLETE_POSITIONS) * 100
sharpe_ratio = calculate_sharpe(returns)
max_drawdown_pct = calculate_max_drawdown(total_equity) * 100

result = {
    'total_trades': trade_stats['total_trades'],       # 3
    'total_exits': trade_stats['total_exits'],         # 9
    'win_rate_pct': win_rate_pct,
    'sharpe_ratio': sharpe_ratio,
    # ...
}
```

**Advanced (`vectorbt_engine_advanced.py`):**
```python
from src.utils.trade_counter import count_trades, calculate_win_rate, CountingMethod
from src.utils.metrics import calculate_sharpe, calculate_max_drawdown

# Línea ~1540-1575:
# OPCIÓN: Usar mismo método que THOR para convergencia
trade_stats = count_trades(all_trades, method=CountingMethod.COMPLETE_POSITIONS)
win_rate = calculate_win_rate(all_trades, method=CountingMethod.COMPLETE_POSITIONS)
sharpe = calculate_sharpe(returns)
max_dd = calculate_max_drawdown(total_equity)

return {
    'total_trades': trade_stats['total_trades'],       # Consistente con THOR
    'total_exits': trade_stats['total_exits'],
    'win_rate': win_rate,
    'sharpe_ratio': sharpe,
    # ...
}
```

---

## 🧪 Tests de Convergencia Mejorados

### `validation_baseline.py` actualizado:
```python
# Comparar usando COMPLETE_POSITIONS para ambos
thor_trades = thor_results['total_trades']  # Ya usa unique_entries
adv_trades = adv_results['total_trades']    # Ahora también usa unique_entries

# También validar exits
thor_exits = thor_results.get('total_exits', thor_trades * 3)
adv_exits = adv_results.get('total_exits', adv_trades * 3)

# Verificar invariante
assert thor_exits == thor_trades * 3, "THOR: exits != trades * 3"
assert adv_exits == adv_trades * 3, "Advanced: exits != trades * 3"
```

---

## 🎨 UI Streamlit

**Mostrar ambas métricas:**
```python
col1, col2 = st.columns(2)
with col1:
    st.metric("Complete Positions", results['total_trades'])
with col2:
    st.metric("Total Exits", results['total_exits'])
    
st.caption("ℹ️ Each position has 3 exits: TP1 (33%), TP2 (33%), Runner (34%)")
```

---

## 🚀 Plan de Implementación

### Fase 1: Crear Módulos Compartidos ✅
1. Crear `src/utils/metrics.py`
2. Crear `src/utils/trade_counter.py`
3. Unit tests para cada función

### Fase 2: Refactorizar THOR 
1. Importar módulos compartidos
2. Usar CountingMethod.DUAL
3. Tests de regresión

### Fase 3: Refactorizar Advanced
1. Importar módulos compartidos
2. Alinear con THOR (COMPLETE_POSITIONS)
3. Tests de convergencia

### Fase 4: Actualizar Tests
1. `validation_baseline.py` - Usar métricas normalizadas
2. `walk_forward_analysis.py` - Mismo método de conteo
3. Nuevos tests de equivalencia

### Fase 5: Actualizar UI
1. Streamlit: mostrar dual metrics
2. Logs: clarificar método de conteo
3. Documentación

---

## 🎯 Criterios de Evaluación

### ¿Cuándo dos implementaciones son equivalentes?

**A. Mismo cálculo, mismo código:**
- ✅ Fácil: Extraer a función compartida
- Ejemplo: `calculate_sharpe()` - fórmula idéntica

**B. Mismo cálculo, diferente código:**
- ⚠️ Requiere validación
- Método: Property-based testing
- Ejemplo: RVOL calculado en pandas vs numpy

**C. Diferente cálculo, mismo propósito:**
- ⚠️ Decidir cuál es "correcto"
- Método: Backtest con datos conocidos
- Ejemplo: ATR con diferentes períodos

**D. Diferente cálculo, diferentes resultados (ambos válidos):**
- ℹ️ Mantener ambos, documentar diferencias
- Método: Exposición como parámetro
- Ejemplo: Position sizing con RVOL vs Fixed Dollar

### Framework de Decisión:

```python
def should_consolidate(func1, func2):
    """Decide si dos funciones deben consolidarse"""
    
    # 1. Test con datos sintéticos
    test_data = generate_test_cases(1000)
    results1 = [func1(d) for d in test_data]
    results2 = [func2(d) for d in test_data]
    
    # 2. Verificar equivalencia numérica
    if np.allclose(results1, results2, rtol=1e-5):
        return "CONSOLIDAR", "Resultados idénticos"
    
    # 3. Verificar correlación
    corr = np.corrcoef(results1, results2)[0,1]
    if corr > 0.99:
        return "REVISAR", "Alta correlación, posible diferencia de precisión"
    
    # 4. Verificar si uno es subset del otro
    if all(r1 == r2 for r1, r2 in zip(results1, results2) if r2 != 0):
        return "PARAMETRIZAR", "Uno es caso especial del otro"
    
    return "MANTENER_SEPARADO", "Lógicas fundamentalmente diferentes"
```

---

## 📊 Código Repetido vs Código Similar

### REPETIDO (consolidar siempre):
```python
# ANTES: En 3 archivos diferentes
sharpe = returns.mean() / returns.std() * np.sqrt(252)

# DESPUÉS: En src/utils/metrics.py
from src.utils.metrics import calculate_sharpe
sharpe = calculate_sharpe(returns)
```

### SIMILAR pero diferente (evaluar):
```python
# THOR:
rvol = volume / sma_volume_20

# Advanced:
rvol = volume / ema_volume_10

# SOLUCIÓN: Parametrizar
from src.utils.metrics import calculate_rvol
rvol = calculate_rvol(volume, avg_volume, method='sma', periods=20)
```

---

## 🔍 Cómo Evaluar Diferencias

### Ejemplo: RVOL con SMA vs EMA

```python
# Test de equivalencia
import pandas as pd
import numpy as np

def test_rvol_methods():
    # Datos sintéticos
    volume = pd.Series([1000, 1200, 800, 1500, 900] * 100)
    
    # Método 1: SMA
    rvol_sma = volume / volume.rolling(20).mean()
    
    # Método 2: EMA
    rvol_ema = volume / volume.ewm(span=10).mean()
    
    # Comparar
    corr = np.corrcoef(rvol_sma[20:], rvol_ema[20:])[0,1]
    print(f"Correlación: {corr:.4f}")
    
    # Evaluar impact en trading
    entries_sma = (rvol_sma > 2.0).sum()
    entries_ema = (rvol_ema > 2.0).sum()
    print(f"Entries SMA: {entries_sma}, EMA: {entries_ema}")
    
    # Decisión:
    if corr > 0.95 and abs(entries_sma - entries_ema) < 5:
        return "SIMILAR - Usar SMA por tradición"
    else:
        return "DIFERENTE - Parametrizar ambos"
```

---

## 🛠️ Pasos de Implementación

### PASO 1: Commit y Branch ✅
```bash
git add -A
git commit -m "Pre-refactoring baseline"
git checkout -b refactor/consolidate-engines
```

### PASO 2: Crear Módulos Base
```bash
# Crear con tests unitarios desde el inicio
touch src/utils/metrics.py
touch src/utils/trade_counter.py
touch tests/test_metrics.py
touch tests/test_trade_counter.py
```

### PASO 3: Extraer Funciones (orden específico)
1. **Métricas simples** (RVOL, ADR) → Menos riesgo
2. **Métricas complejas** (Sharpe, Drawdown) → Validar bien
3. **Conteo de trades** → CRÍTICO para convergencia
4. **Win rate** → Depende del conteo

### PASO 4: Refactorizar Motor por Motor
1. **THOR primero** (más simple)
   - Tests de regresión
   - Validar resultados idénticos
2. **Advanced segundo**
   - Alinear con THOR
   - Tests de convergencia
3. **Daily Engine** (si aplica)

### PASO 5: Actualizar Tests
1. `validation_baseline.py`
2. `walk_forward_analysis.py`
3. `analyze_robust_ranges.py`

### PASO 6: UI Streamlit
1. Importar métricas compartidas
2. Mostrar dual reporting
3. Tooltips explicativos

---

## ⚠️ Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Romper THOR | Media | Alto | Tests de regresión antes/después |
| Romper Advanced | Media | Alto | Tests de convergencia |
| Cambiar resultados históricos | Alta | Crítico | Guardar baseline, comparar |
| Introducir bugs | Media | Alto | Unit tests exhaustivos |

---

## ✅ Criterios de Éxito

### Convergencia Perfecta:
- ✅ THOR trades == Advanced trades (usando mismo método)
- ✅ Win rate diff < 1%
- ✅ Sharpe diff < 0.01
- ✅ Return diff < 0.1%

### Código Limpio:
- ✅ 0 duplicación en cálculos core
- ✅ Tests unitarios > 90% coverage
- ✅ Documentación clara de diferencias intencionales

### Performance:
- ✅ Tiempo ejecución ≤ baseline
- ✅ Memoria ≤ baseline

---

## 📝 Próximos Pasos Inmediatos

1. ✅ **HECHO**: Commit y crear branch
2. **AHORA**: Crear `src/utils/metrics.py` con tests
3. **LUEGO**: Crear `src/utils/trade_counter.py` con tests
4. **DESPUÉS**: Refactorizar THOR para usar módulos
5. **FINALMENTE**: Alinear Advanced y validar convergencia

---

## 💬 Respuestas a tus Preguntas

### ¿Cómo evaluar código no repetido pero con mismo/diferente resultado?

**Framework de 4 pasos:**

1. **Test de Equivalencia Numérica**
   ```python
   assert np.allclose(result1, result2, rtol=1e-6)
   ```

2. **Test de Correlación**
   ```python
   if correlation > 0.99: "Casi idéntico"
   elif correlation > 0.90: "Similar, verificar"
   else: "Diferente"
   ```

3. **Test de Impact en Trading**
   ```python
   # Correr backtest con ambos métodos
   sharpe_diff = abs(sharpe1 - sharpe2)
   if sharpe_diff < 0.05: "Impacto insignificante"
   ```

4. **Análisis de Edge Cases**
   ```python
   # Probar con datos extremos
   test_zero_volume()
   test_negative_values()
   test_missing_data()
   ```

### ¿Qué hacer si dan resultados diferentes?

**Decisión Tree:**
```
¿Dan resultados diferentes?
├─ ¿Cuál es "correcto"?
│  ├─ Hay estándar industria → Usar estándar
│  ├─ Uno tiene bugs → Fixear
│  └─ Ambos válidos → Parametrizar
│
├─ ¿El delta importa?
│  ├─ Sharpe diff < 0.05 → Elegir más simple
│  └─ Sharpe diff > 0.05 → Investigar a fondo
│
└─ ¿Son compatibles?
   ├─ Sí → Ofrecer como opción (parámetro)
   └─ No → Mantener separado, documentar
```

---

## 🎯 Ejemplo Concreto: RVOL

Supongamos encuentras:

```python
# THOR usa:
rvol = volume / volume.rolling(20).mean()  # SMA 20

# Advanced usa:
rvol = volume / volume.ewm(span=10).mean()  # EMA 10
```

**Evaluación:**
1. Correr backtest con ambos en 2020-2024
2. Si Sharpe diff < 0.05 → Consolidar al método más común (SMA 20)
3. Si Sharpe diff > 0.05 → Parametrizar:
   ```python
   def calculate_rvol(volume, method='sma', periods=20):
       if method == 'sma':
           return volume / volume.rolling(periods).mean()
       elif method == 'ema':
           return volume / volume.ewm(span=periods).mean()
   ```

---

**¿Listo para empezar? Te sugiero:**
1. Primero crear `metrics.py` y `trade_counter.py` con tests
2. Luego fix el conteo en ambos motores
3. Re-correr validation y ver convergencia perfecta
