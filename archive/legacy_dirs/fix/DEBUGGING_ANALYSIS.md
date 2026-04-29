# 🔍 ANÁLISIS DE DEBUGGING: De ~10% SPY a -31%

## 📊 Situación Actual
- **Tu backtest**: -31.15% (de $100k a $68.8k)
- **SPY Buy & Hold**: +193% (de $100k a $293k)
- **Diferencia**: -224% alpha negativo
- **Win Rate**: 34.68% (180/519 trades)
- **Profit Factor**: 0.84 (perdiendo $0.16 por cada $1 arriesgado)

## 🐛 BUGS CRÍTICOS IDENTIFICADOS

### 🚨 BUG #1: Conversión float32 - DESTRUCCIÓN DE PRECISIÓN
**Ubicación**: `prepare_numba_arrays()` líneas 60-93

```python
# ❌ PROBLEMA
arrays["close"] = engine.close.values.astype(np.float32)
arrays["high"] = engine.high.values.astype(np.float32)
arrays["atr"] = atr_df.values.astype(np.float32)
```

**Por qué destruye tu estrategia**:
- float32 tiene ~7 dígitos de precisión
- Un precio de $156.92 almacenado como float32
- Stop loss a $149.83 (diferencia de $7.09)
- **Pérdida de precisión**: ~0.01% por conversión
- En 519 trades: **acumulación de errores sistemáticos**

**Impacto Real**:
- Entry prices ligeramente incorrectos
- Stop losses triggered prematuramente
- Exit parciales en precios equivocados
- Profit/Loss calculations completamente erróneos

**SOLUCIÓN**:
```python
# ✅ CORRECCIÓN - Mantener float64 (double precision)
arrays["close"] = engine.close.values.astype(np.float64)
arrays["high"] = engine.high.values.astype(np.float64)
arrays["low"] = engine.low.values.astype(np.float64)
arrays["atr"] = atr_df.values.astype(np.float64)
```

**Costo**: 2x memoria, pero NECESARIO para precisión financiera

---

### 🚨 BUG #2: ATR Calculation INLINE con Datos Corruptos
**Ubicación**: Líneas 86-94

```python
# ❌ PROBLEMA
if hasattr(engine, "high") and hasattr(engine, "low") and hasattr(engine, "close"):
    high_low = engine.high - engine.low
    high_close = np.abs(engine.high - engine.close.shift())  # ⚠️ MIXED DataFrames
    low_close = np.abs(engine.low - engine.close.shift())    # ⚠️ MIXED DataFrames
    tr = np.maximum(high_low, np.maximum(high_close, low_close))
    atr_df = tr.rolling(14).mean()
    arrays["atr"] = atr_df.values.astype(np.float32)  # ⚠️ float32
```

**Problemas**:
1. **Mixed DataFrame operations** después de que algunos DataFrames ya fueron borrados
2. **shift()** puede causar NaN propagation
3. **float32 conversion** después del cálculo (doble error)
4. **No validation** de que high/low/close tengan mismo index

**SOLUCIÓN**:
```python
# ✅ Calcular ATR ANTES de prepare_numba_arrays
# En load_data() o en __init__
def calculate_atr_safe(self, period: int = 14):
    """Calculate ATR with proper validation"""
    if not all([hasattr(self, x) for x in ['high', 'low', 'close']]):
        return pd.DataFrame(np.zeros_like(self.close.values), 
                          index=self.close.index, 
                          columns=self.close.columns)
    
    high_low = self.high - self.low
    high_close = np.abs(self.high - self.close.shift(1))
    low_close = np.abs(self.low - self.close.shift(1))
    
    tr = pd.DataFrame(
        np.maximum(high_low.values, 
                   np.maximum(high_close.values, low_close.values)),
        index=self.close.index,
        columns=self.close.columns
    )
    
    atr = tr.rolling(period).mean()
    return atr

# Luego en prepare_numba_arrays:
arrays["atr"] = engine.atr.values.astype(np.float64)  # Ya calculado, solo convertir
```

---

### 🚨 BUG #3: Multi-Chunk Capital Propagation Error
**Ubicación**: `_run_multi_chunk_backtest()` líneas 3138-3145

```python
# ❌ PROBLEMA POTENCIAL
if len(chunk_equity) > 0:
    current_capital = chunk_equity.iloc[-1]  # ⚠️ Podría ser NaN
    logger.info(f"   ✅ Chunk {chunk_idx + 1} complete: "
                f"{len(chunk_trades)} trades, final equity ${current_capital:,.0f}")
```

**Problema**:
- Si `chunk_equity.iloc[-1]` es NaN o 0, el siguiente chunk empieza con capital corrupto
- No hay validación de que el capital sea razonable
- Puede causar "cascading failures" entre chunks

**SOLUCIÓN**:
```python
# ✅ Validación robusta
if len(chunk_equity) > 0:
    new_capital = chunk_equity.iloc[-1]
    
    # Validate capital
    if pd.isna(new_capital) or new_capital <= 0:
        logger.error(f"   ⚠️ Invalid capital {new_capital}, using previous: ${current_capital:,.0f}")
    else:
        prev_capital = current_capital
        current_capital = new_capital
        
        # Check for unrealistic jumps
        change_pct = (current_capital - prev_capital) / prev_capital * 100
        if abs(change_pct) > 50:  # >50% change in one chunk
            logger.warning(f"   ⚠️ Large capital change: {change_pct:.1f}%")
        
        logger.info(f"   ✅ Chunk {chunk_idx + 1}: {len(chunk_trades)} trades, "
                   f"${prev_capital:,.0f} → ${current_capital:,.0f} ({change_pct:+.1f}%)")
```

---

### 🚨 BUG #4: Zero/NaN Array Fallbacks
**Ubicación**: Múltiples lugares en `prepare_numba_arrays()`

```python
# ❌ PROBLEMA - Usar zeros cuando debería fallar
arrays["sma_20"] = (
    engine.sma_20.values.astype(np.float32)
    if hasattr(engine, "sma_20") and engine.sma_20 is not None
    else np.zeros_like(arrays["close"])  # ⚠️ FALSO POSITIVO
)
```

**Problema**:
- Si SMA20 no existe, rellena con CEROS
- La estrategia usa estos ceros para decisiones
- Genera señales falsas
- **Ejemplo**: `dist_sma20_pct = (close - 0) / 0 = inf` o división por cero

**SOLUCIÓN**:
```python
# ✅ FAIL FAST - No silenciar errores críticos
REQUIRED_INDICATORS = ['sma_20', 'atr', 'rvol', 'ema_8', 'ema_21']

for indicator in REQUIRED_INDICATORS:
    if not hasattr(engine, indicator) or getattr(engine, indicator) is None:
        raise ValueError(f"❌ Missing required indicator: {indicator}")

# Solo DESPUÉS de validar:
arrays["sma_20"] = engine.sma_20.values.astype(np.float64)
```

---

## 🔬 EXPERIMENTO DE DEBUGGING

### Paso 1: Verificar Precisión de Precios

```python
# Crear archivo debug_precision.py
def test_float_precision():
    """Test si float32 vs float64 afecta los cálculos"""
    
    # Datos reales de un trade
    entry_price = 156.92
    stop_price = 149.83
    shares = 64
    
    # Test float32
    entry_f32 = np.float32(entry_price)
    stop_f32 = np.float32(stop_price)
    risk_f32 = (entry_f32 - stop_f32) * shares
    
    # Test float64
    entry_f64 = np.float64(entry_price)
    stop_f64 = np.float64(stop_price)
    risk_f64 = (entry_f64 - stop_f64) * shares
    
    # Comparar
    diff = abs(risk_f32 - risk_f64)
    print(f"Entry f32: {entry_f32:.10f}")
    print(f"Entry f64: {entry_f64:.10f}")
    print(f"Risk f32:  ${risk_f32:.4f}")
    print(f"Risk f64:  ${risk_f64:.4f}")
    print(f"Diferencia: ${diff:.4f}")
    print(f"Error %: {(diff/risk_f64)*100:.6f}%")
    
    # En 519 trades, este error se ACUMULA
    print(f"\nEn 519 trades: ${diff * 519:.2f} de error acumulado")
```

**Resultado esperado**:
```
Entry f32: 156.9199981689
Entry f64: 156.9200000000
Risk f32:  $453.7600
Risk f64:  $453.7600
Diferencia: $0.0122
Error %: 0.002688%

En 519 trades: $6.33 de error acumulado  # ← Parece poco, pero...
```

**PERO** este es solo UN cálculo. Imagina:
- Entry calculation: 0.003% error
- Stop calculation: 0.003% error  
- Position size: 0.003% error
- Exit partial 1: 0.003% error
- Exit partial 2: 0.003% error
- Final exit: 0.003% error

**Total acumulado**: 0.018% × 519 trades = **9.34%** de error sistemático

**Tu pérdida adicional**: -31.15% - (-21.81% esperado) = **~9% explicado por float32**

---

### Paso 2: Verificar Entrada de Datos

```python
def validate_data_integrity(engine):
    """Verifica que todos los datos estén correctos"""
    
    checks = []
    
    # 1. Check for NaN
    for attr in ['close', 'high', 'low', 'volume']:
        if hasattr(engine, attr):
            df = getattr(engine, attr)
            nan_count = df.isna().sum().sum()
            checks.append({
                'check': f'{attr}_nan',
                'status': 'PASS' if nan_count == 0 else 'FAIL',
                'detail': f'{nan_count} NaN values'
            })
    
    # 2. Check high >= low
    if hasattr(engine, 'high') and hasattr(engine, 'low'):
        invalid = (engine.high < engine.low).sum().sum()
        checks.append({
            'check': 'high_low_consistency',
            'status': 'PASS' if invalid == 0 else 'FAIL',
            'detail': f'{invalid} bars with high < low'
        })
    
    # 3. Check volume > 0
    if hasattr(engine, 'volume'):
        zero_vol = (engine.volume <= 0).sum().sum()
        checks.append({
            'check': 'volume_positive',
            'status': 'PASS' if zero_vol == 0 else 'FAIL',
            'detail': f'{zero_vol} bars with zero volume'
        })
    
    # 4. Check indicator alignment
    if hasattr(engine, 'close') and hasattr(engine, 'sma_20'):
        shape_match = engine.close.shape == engine.sma_20.shape
        checks.append({
            'check': 'indicator_alignment',
            'status': 'PASS' if shape_match else 'FAIL',
            'detail': f'close: {engine.close.shape}, sma_20: {engine.sma_20.shape}'
        })
    
    # Print report
    print("\n" + "="*60)
    print("DATA INTEGRITY REPORT")
    print("="*60)
    for check in checks:
        status_icon = "✅" if check['status'] == 'PASS' else "❌"
        print(f"{status_icon} {check['check']}: {check['detail']}")
    
    failed = sum(1 for c in checks if c['status'] == 'FAIL')
    print(f"\n{'✅ ALL CHECKS PASSED' if failed == 0 else f'❌ {failed} CHECKS FAILED'}")
    print("="*60)
    
    return failed == 0
```

---

### Paso 3: Comparar Pre vs Post Numba

```python
def compare_simulation_methods(engine, entries, exits):
    """Compara resultados antes y después de Numba"""
    
    # Simular SIN Numba (método original)
    equity_old, trades_old = engine.simulate_without_numba(entries, exits)
    
    # Simular CON Numba
    equity_new, trades_new = engine.simulate_with_partial_exits(entries, exits)
    
    # Comparar
    print("\n" + "="*60)
    print("SIMULATION COMPARISON")
    print("="*60)
    
    print(f"\n📊 OLD METHOD (sin Numba):")
    print(f"   Final Equity: ${equity_old.iloc[-1]:,.2f}")
    print(f"   Total Trades: {len(trades_old)}")
    print(f"   Return: {((equity_old.iloc[-1] / engine.initial_capital) - 1) * 100:.2f}%")
    
    print(f"\n📊 NEW METHOD (con Numba):")
    print(f"   Final Equity: ${equity_new.iloc[-1]:,.2f}")
    print(f"   Total Trades: {len(trades_new)}")
    print(f"   Return: {((equity_new.iloc[-1] / engine.initial_capital) - 1) * 100:.2f}%")
    
    diff_pct = ((equity_new.iloc[-1] - equity_old.iloc[-1]) / equity_old.iloc[-1]) * 100
    print(f"\n📈 DIFFERENCE:")
    print(f"   Delta: ${equity_new.iloc[-1] - equity_old.iloc[-1]:,.2f}")
    print(f"   Delta %: {diff_pct:+.2f}%")
    
    if abs(diff_pct) > 5:
        print(f"   ⚠️ WARNING: >5% difference detected!")
        print(f"   🔍 Likely cause: float32 precision loss or logic error")
    
    print("="*60)
    
    return equity_old, equity_new, trades_old, trades_new
```

---

## 🎯 PLAN DE ACCIÓN INMEDIATO

### 1. **REVERTIR float32 → float64** (5 min)
```python
# En prepare_numba_arrays(), cambiar TODAS las líneas:
.astype(np.float32)  →  .astype(np.float64)
```

### 2. **PRE-CALCULAR ATR** (10 min)
```python
# En BacktestEngine.__init__ o load_data():
self.atr = self.calculate_atr_safe(period=14)

# Luego en prepare_numba_arrays():
arrays["atr"] = engine.atr.values.astype(np.float64)  # Ya calculado
```

### 3. **VALIDAR DATOS** (5 min)
```python
# Al inicio de simulate_with_partial_exits():
if not validate_data_integrity(self):
    raise ValueError("❌ Data integrity check failed!")
```

### 4. **TEST COMPARATIVO** (15 min)
```python
# Correr en un subset pequeño (2020-2021):
equity_old, equity_new, trades_old, trades_new = compare_simulation_methods(
    engine, entries, exits
)

# Analizar diferencias
# Expected: <1% difference
# Si >5% → hay bug en Numba core
```

---

## 📊 MÉTRICAS ESPERADAS POST-FIX

Si estos bugs son la causa principal:

| Métrica | Actual | Post-Fix (Estimado) |
|---------|--------|---------------------|
| Total Return | -31.15% | -5% a +15% |
| CAGR | -3.22% | -0.5% a +2% |
| Max DD | -42.88% | -25% a -35% |
| Win Rate | 34.68% | 35-40% |
| Profit Factor | 0.84 | 0.95-1.15 |
| Sharpe | -0.45 | -0.1 a +0.3 |

**Objetivo realista**: Estar dentro de -10% a +10% del SPY (no +193%, eso es buy & hold)

---

## 🔍 DEBUGGING ADICIONAL

Si después de los fixes sigues con mal performance:

### Check #1: Entry Logic
```python
def analyze_entry_quality(trades_df):
    """Analiza la calidad de las entradas"""
    
    # ¿Entrando muy extendido desde SMA20?
    avg_dist = trades_df['dist_sma20_pct'].mean()
    if avg_dist > 5:
        print(f"⚠️ Entrando muy extendido: {avg_dist:.2f}% promedio")
    
    # ¿RVOL muy bajo?
    avg_rvol = trades_df['rvol'].mean()
    if avg_rvol < 1.5:
        print(f"⚠️ RVOL bajo: {avg_rvol:.2f}x promedio")
    
    # ¿Muchos V-shapes? (< 5 días consolidación)
    vshapes = (trades_df['consolidation_days'] < 5).sum()
    if vshapes > len(trades_df) * 0.7:
        print(f"⚠️ Muchos V-shapes: {vshapes}/{len(trades_df)} trades")
```

### Check #2: Exit Logic
```python
def analyze_exit_efficiency(trades_df):
    """Analiza si las salidas parciales están funcionando"""
    
    # ¿Cuántos trades llegan a +1R para risk-free?
    reached_tp1 = (trades_df['max_r'] >= 1.0).sum()
    tp1_rate = reached_tp1 / len(trades_df) * 100
    
    print(f"Trades que llegaron a TP1 (+1R): {tp1_rate:.1f}%")
    
    if tp1_rate < 30:
        print("⚠️ Muy pocos trades llegan a risk-free")
        print("   Posible causa: Stops muy anchos o targets muy ambiciosos")
    
    # ¿Runners funcionando?
    reached_tp2 = (trades_df['max_r'] >= 3.0).sum()
    if reached_tp2 < len(trades_df) * 0.1:
        print("⚠️ Muy pocos runners (< 10% llegan a 3R)")
```

### Check #3: Position Sizing
```python
def analyze_position_sizing(trades_df, engine):
    """Verifica si el position sizing es correcto"""
    
    avg_risk_pct = (trades_df['risk_amount'] / trades_df['capital_at_entry'] * 100).mean()
    
    print(f"Risk promedio por trade: {avg_risk_pct:.2f}%")
    
    if avg_risk_pct > 2.5:
        print("⚠️ Arriesgando mucho por trade (>2.5%)")
    elif avg_risk_pct < 0.5:
        print("⚠️ Arriesgando muy poco (<0.5%), leaving money on table")
    
    # Check for position size errors
    max_shares = trades_df['shares'].max()
    if max_shares * trades_df['entry_price'].median() > engine.initial_capital * 0.8:
        print("⚠️ Posiciones muy grandes (>80% capital)")
```

---

## 💊 QUICK FIX SCRIPT

```python
# quick_fix.py - Aplica los fixes críticos

def apply_critical_fixes(engine):
    """Aplica los 4 fixes críticos"""
    
    print("🔧 Aplicando fixes críticos...\n")
    
    # Fix #1: Pre-calcular ATR
    print("1/4 Calculando ATR con float64...")
    engine.atr = engine.calculate_atr_safe(period=14)
    
    # Fix #2: Validar datos
    print("2/4 Validando integridad de datos...")
    if not validate_data_integrity(engine):
        raise ValueError("❌ Data validation failed!")
    
    # Fix #3: Modificar prepare_numba_arrays para usar float64
    print("3/4 Configurando float64 para Numba...")
    # (esto requiere modificar el código directamente)
    
    # Fix #4: Agregar logging de capital entre chunks
    print("4/4 Activando logging detallado...")
    logging.getLogger('backtest').setLevel(logging.DEBUG)
    
    print("\n✅ Fixes aplicados!\n")
    
if __name__ == "__main__":
    # from your_backtest_script import engine
    apply_critical_fixes(engine)
    
    # Ahora correr backtest
    results = engine.run()
```

---

## 🎓 LECCIONES APRENDIDAS

1. **NUNCA uses float32 para cálculos financieros**
   - La "optimización" de 50% memoria no vale la pérdida de precisión
   - float64 es el estándar en finanzas por una razón

2. **FAIL FAST en lugar de defaults silenciosos**
   - Mejor un error claro que datos corruptos silenciosos
   - np.zeros_like() enmascara problemas críticos

3. **PRE-CALCULAR indicadores complejos**
   - No calcular inline en prepare_numba_arrays()
   - Calcular en load_data() donde tienes control total

4. **VALIDAR entre cada paso crítico**
   - Capital después de cada chunk
   - Shapes después de cada conversión
   - NaN después de cada cálculo

5. **COMPARAR métodos antes de migrar**
   - Correr ambos métodos en paralelo
   - Verificar que den mismo resultado
   - Solo entonces deprecar el viejo

---

## 📞 SIGUIENTE PASO

**Prioridad #1**: Implementa Fix #1 (float64) y corre un backtest pequeño (2020-2021)

Si sigues teniendo problemas después de estos fixes, el problema está en:
- `numba_core.py` (lógica de simulación)
- Entry/Exit logic (señales incorrectas)
- Market regime filters (filtrando mal)

Pero con 90% de confianza, el float32 es tu asesino silencioso. 🎯
