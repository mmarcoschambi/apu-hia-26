# 🐛 ANÁLISIS DE BUGS: Resultados No Determinísticos

## 🎯 Problema Identificado

### Bug #1: Resultados Diferentes en Cada Ejecución

**Síntomas:**
- Mismos parámetros → Resultados diferentes
- Ejecución 1: $104K (+4.5%)
- Ejecución 2: $135K (+36%)
- Ejecución 3: $143K (+43%)
- Ejecución 4: $105K (+5.9%)

**Causa Raíz: NON-DETERMINISTIC UNIVERSE SELECTION**

### 🔍 Investigación

El problema está en cómo se selecciona el universo de tickers:

```python
# En app.py, línea ~250-265
conn = sqlite3.connect("./data/ticker_cache.db")
cursor = conn.cursor()

if top_n_liquid == 0:  # All tickers
    query = "SELECT ticker FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY ticker"
else:  # Top N by liquidity
    query = "SELECT ticker, AVG(dollar_volume) as avg_dv FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY avg_dv DESC LIMIT ?"
```

**Problemas:**

1. **Sin ORDER BY determinístico completo**
   - `ORDER BY ticker` puede dar diferentes resultados si hay empates
   - `ORDER BY avg_dv DESC` puede variar si hay nuevos datos en cache
   - SQLite no garantiza orden consistente sin EXPLICIT ordering

2. **Cache database puede cambiar**
   - Si hay nuevos datos descargados entre ejecuciones
   - Si hay actualizaciones de precio
   - Si hay cambios en `dollar_volume`

3. **TTL del cache de Streamlit (3600s)**
   - Cache expira después de 1 hora
   - Cada nueva consulta puede obtener diferentes tickers

4. **Point-in-Time Universe no consistente**
   - Aunque uses `use_pit_universe=True`, el query no es determinístico
   - Debería usar snapshot de fechas específicas

### Bug #2: PDF Return Quantiles - Gráfico de Distribución Bugueado

**Síntomas:**
- Última página del PDF muestra gráfico distorsionado
- Box plot o violin plot con valores extraños
- Daily/Weekly quantiles fuera de rango

**Causa:** QuantStats `distribution` plot con datos escasos o irregulares

---

## ✅ SOLUCIONES

### Solución Bug #1: Universe Determinístico

#### Fix Inmediato (Línea ~250 en app.py):

```python
# ANTES (Non-deterministic):
if top_n_liquid == 0:
    query = "SELECT ticker FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY ticker"
else:
    query = "SELECT ticker, AVG(dollar_volume) as avg_dv FROM ohlcv_cache WHERE date BETWEEN ? AND ? GROUP BY ticker HAVING COUNT(*) >= ? ORDER BY avg_dv DESC LIMIT ?"

# DESPUÉS (Deterministic):
if top_n_liquid == 0:
    query = """
        SELECT ticker 
        FROM ohlcv_cache 
        WHERE date BETWEEN ? AND ? 
        GROUP BY ticker 
        HAVING COUNT(*) >= ? 
        ORDER BY ticker ASC, MIN(date) ASC
    """
else:
    query = """
        SELECT ticker
        FROM (
            SELECT ticker, AVG(dollar_volume) as avg_dv, MIN(date) as first_date
            FROM ohlcv_cache 
            WHERE date BETWEEN ? AND ? 
            GROUP BY ticker 
            HAVING COUNT(*) >= ?
        )
        ORDER BY avg_dv DESC, first_date ASC, ticker ASC
        LIMIT ?
    """
```

#### Fix Adicional: Logging del Universo

```python
# Después de obtener el universe, agregar:
universe_hash = hash(tuple(sorted(universe)))
logger.info(f"🎯 Universe deterministic hash: {universe_hash}")
logger.info(f"📊 Universe size: {len(universe)} tickers")
logger.info(f"📝 First 10: {universe[:10]}")

# Esto te permitirá verificar si el universo es consistente
```

### Solución Bug #2: PDF Distribution Plot Fix

Ya aplicado en el código anterior con try-except, pero puedes mejorar:

```python
# En generate_pdf_report, reemplazar:
try:
    fig = qs.plots.distribution(self.daily_returns, show=False)
    pdf.savefig(fig)
    plt.close(fig)
except Exception as e:
    logger.warning(f"⚠️  Skipped Distribution plot: {e}")
    # Crear plot alternativo más simple
    fig, ax = plt.subplots(figsize=(10, 6))
    self.daily_returns.hist(bins=50, ax=ax, color='steelblue', edgecolor='black')
    ax.set_title('Daily Returns Distribution')
    ax.set_xlabel('Return')
    ax.set_ylabel('Frequency')
    pdf.savefig(fig)
    plt.close(fig)
```

---

## 🔧 Fix Completo Paso a Paso

### Paso 1: Deshabilitar Cache Temporalmente (Testing)

```python
# En app.py, línea 87, comentar cache:
# @st.cache_data(ttl=3600, show_spinner=False)  # DESHABILITADO PARA TESTING
def run_cached_backtest(
    ...
```

**Ejecuta 3 veces** y verifica si los resultados son IDÉNTICOS.

- ✅ Si son idénticos → El problema era el cache
- ❌ Si siguen diferentes → Hay otro problema (randomness interno)

### Paso 2: Hacer Cache Determinístico

Si el problema era el cache, necesitas:

1. **Agregar universe_hash al cache key:**

```python
@st.cache_data(ttl=3600, show_spinner=False, hash_funcs={list: lambda x: hash(tuple(sorted(x)))})
def run_cached_backtest(
    universe,  # Este debe ser ORDENADO
    ...
```

2. **Ordenar universe antes de pasar:**

```python
# Línea ~268, ANTES de llamar run_cached_backtest:
universe = sorted(universe)  # ← AGREGAR ESTA LÍNEA
results, rejection_stats = run_cached_backtest(
    universe,
    ...
```

### Paso 3: Verificar Randomness Interno

Si aún hay diferencias, buscar:

```bash
# Buscar uso de random sin seed
grep -r "random\." src/ --include="*.py" | grep -v "random.seed"

# Buscar uso de numpy random sin seed
grep -r "np.random" src/ --include="*.py" | grep -v "np.random.seed"

# Buscar uso de shuffle
grep -r "shuffle" src/ --include="*.py"

# Buscar uso de sample
grep -r "\.sample(" src/ --include="*.py"
```

---

## 🧪 Script de Testing

Créa este script para verificar determinismo:

```python
#!/usr/bin/env python3
"""test_determinism.py - Verify backtest is deterministic"""

import sys
sys.path.insert(0, '.')

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
import pandas as pd

# Fixed parameters
params = {
    'universe': sorted(['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']),  # SORTED
    'start_date': '2023-01-01',
    'end_date': '2023-12-31',
    'initial_capital': 100000,
    'risk_pct': 0.01,
    'risk_dollars': 1000,
    'max_exposure_pct': 0.3,
    'max_dist_sma20': 7.0,
    'min_rvol': 1.8,
    'min_adr': 2.5,
    'min_volume': 500000,
    'min_dollar_volume': 5000000,
    'rvol_danger': 4.0,
    'rvol_warning': 2.5,
    'rvol_danger_size': 0.5,
    'rvol_warning_size': 0.75,
    'adr_high': 5.0,
    'adr_med': 3.5,
    'max_stop_pct': 0.08,
    'min_consolidation_days': 5,
    'earnings_days': 3,
    'earnings_cushion': 2,
    'use_earnings_calendar': False,
    'offline_mode': True,
    'use_adaptive_filtering': False,
    'tp1_r': 2.0,
    'tp2_r': 4.75,
    'require_spy_above_sma50': True,
    'tp1_pct': 0.5,
    'tp2_pct': 0.3,
    'runner_pct': 0.2,
    'use_pit_universe': False,
}

print("=" * 80)
print("DETERMINISM TEST - Running backtest 3 times with IDENTICAL parameters")
print("=" * 80)

results_list = []

for i in range(3):
    print(f"\n🔄 Run {i+1}/3...")
    engine = AdvancedVectorBTEngine(**params)
    results = engine.run_backtest()
    engine.cleanup()
    
    if results:
        final_equity = results['final_equity']
        total_trades = results['total_trades']
        net_profit = results['net_profit']
        
        print(f"   Final Equity: ${final_equity:,.2f}")
        print(f"   Total Trades: {total_trades}")
        print(f"   Net Profit: ${net_profit:,.2f}")
        
        results_list.append({
            'equity': final_equity,
            'trades': total_trades,
            'profit': net_profit
        })
    else:
        print("   ❌ No results")

print("\n" + "=" * 80)
print("RESULTS COMPARISON")
print("=" * 80)

if len(results_list) == 3:
    equity_match = (results_list[0]['equity'] == results_list[1]['equity'] == results_list[2]['equity'])
    trades_match = (results_list[0]['trades'] == results_list[1]['trades'] == results_list[2]['trades'])
    
    print(f"Run 1: ${results_list[0]['equity']:,.2f} | {results_list[0]['trades']} trades")
    print(f"Run 2: ${results_list[1]['equity']:,.2f} | {results_list[1]['trades']} trades")
    print(f"Run 3: ${results_list[2]['equity']:,.2f} | {results_list[2]['trades']} trades")
    
    if equity_match and trades_match:
        print("\n✅ DETERMINISTIC: All runs produced identical results!")
    else:
        print("\n❌ NON-DETERMINISTIC: Results vary between runs!")
        print(f"   Equity variance: ${max([r['equity'] for r in results_list]) - min([r['equity'] for r in results_list]):,.2f}")
        print(f"   Trades variance: {max([r['trades'] for r in results_list]) - min([r['trades'] for r in results_list])}")
        print("\n🔍 Possible causes:")
        print("   1. Random number generation without fixed seed")
        print("   2. Universe selection varies")
        print("   3. Date/time dependent logic")
        print("   4. Dictionary/set iteration order")
else:
    print("❌ Could not complete all 3 runs")
```

---

## 💡 Recomendaciones

### Inmediato:
1. **Deshabilita cache temporalmente** y verifica si los resultados son consistentes
2. **Ordena el universe** antes de pasarlo al backtest
3. **Usa logging** para ver qué tickers se están usando

### Mediano Plazo:
1. **Agrega seed fijo** para cualquier random en el código
2. **Usa ORDER BY completo** en queries SQL
3. **Implementa hash de universe** para tracking

### Largo Plazo:
1. **Point-in-Time Universe** con snapshot fijo por fecha
2. **Audit trail** que guarde universe usado en cada backtest
3. **Validation mode** que verifique determinismo automáticamente

---

## 📊 Verificación Rápida

Para verificar si el problema es el cache:

```python
# En la terminal Python:
from app import run_cached_backtest
import streamlit as st

# Clear cache
st.cache_data.clear()

# Run twice with same params
# Si da diferentes resultados → Bug en engine/data
# Si da iguales → Bug era el cache
```

---

## 🎯 Fix Prioritario

**Para el cache:**
```python
# app.py, línea ~268, AGREGAR:
universe = sorted(list(set(universe)))  # Deterministic + no duplicates
universe_str = ','.join(universe[:10]) + f"...({len(universe)} total)"
st.write(f"🎯 Universe: {universe_str}")  # Visual verification

results, rejection_stats = run_cached_backtest(
    universe,
    ...
```

**Para el PDF:**
Ya está fixeado con try-except. Si sigue con problemas, usar:
```python
analyzer.generate_pdf_report(skip_snapshot=True)
```

---

## ✅ Checklist de Verificación

- [ ] Ordenar universe antes de backtest
- [ ] Agregar logging de universe usado
- [ ] Verificar queries SQL tienen ORDER BY completo
- [ ] Buscar uso de random sin seed
- [ ] Probar con cache deshabilitado
- [ ] Comparar 3 ejecuciones consecutivas

---

**Status:** Análisis completo - Fixes listos para aplicar
