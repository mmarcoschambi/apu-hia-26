# 🎯 ANÁLISIS ENFOCADO: El Verdadero Bug

## ✅ Lo que YA sabemos NO es el problema
- **Float32 precision**: Error de solo $0.10 en 519 trades (despreciable)
- El problema debe estar en la **LÓGICA DE SIMULACIÓN**, no en la precisión numérica

## 🔍 Los Sospechosos Reales

### 🚨 SOSPECHOSO #1: Lógica de Salidas Parciales en Numba
**Ubicación**: `src/backtest/numba_core.py` (no disponible)

Tu sistema tiene 3 fases de salida:
```
TP1: 50% at 1.5R (Breakeven Stop)
TP2: 30% at 3R  
Phase 3: 20% Runner (EMA8 < EMA21)
```

**Bugs comunes en salidas parciales**:

```python
# ❌ BUG COMÚN #1: No actualizar posición restante
if price >= tp1_price:
    pnl += shares * 0.5 * (price - entry)  # ✅ OK
    # ❌ FALTA: shares = shares * 0.5  # Actualizar shares restantes
    
# Resultado: Doble contabilización de PnL en siguientes salidas
```

```python
# ❌ BUG COMÚN #2: Breakeven stop no actualizado
if phase == 1:
    exit_price = tp1_price
    # ❌ FALTA: stop_price = entry_price  # Mover stop a breakeven
    
# Resultado: Stop original sigue activo, puede ser hit prematuramente
```

```python
# ❌ BUG COMÚN #3: Orden incorrecto de checks
# INCORRECTO:
if price <= stop:  # Check stop primero
    exit_all()
if price >= tp1:   # Nunca llega si stop fue hit
    exit_partial()

# CORRECTO:
if price >= tp1:   # Check target primero
    exit_partial()
elif price <= stop:  # Solo si no hit target
    exit_all()
```

**EVIDENCIA de tu backtest**:
- ❌ Solo 181 trades ejecutaron Fase 1 (risk-free)
- ❌ Solo 123 ejecutaron Fase 2
- ❌ De 519 trades, 338 (65%) NO llegaron a risk-free
- ⚠️ Esto sugiere que stops están siendo hit ANTES de dar chance a TP1

**DIAGNÓSTICO**:
Tu ratio Risk/Reward de 1.58 sugiere que cuando ganas, ganas bien. Pero tu Win Rate de solo 34.68% indica que estás siendo stopped out demasiado pronto.

**¿Por qué pasaste de ~10% SPY a -31%?**
ANTES de Numba probablemente:
- Las salidas parciales NO estaban implementadas
- Dejabas correr winners más tiempo
- Simple exit en algún nivel fijo

DESPUÉS de Numba:
- Implementaste salidas parciales
- Pero el stop sigue siendo el ORIGINAL (demasiado amplio)
- No se mueve a breakeven después de TP1
- Resultado: Sales 50% en ganancia pequeña, pero luego stop original se activa y pierdes TODO

---

### 🚨 SOSPECHOSO #2: Stop Loss Calculation
**Ubicación**: Cómo calculas el stop

```python
# Tu dashboard dice: "Stop: Session Low (Risk)"
# Esto podría ser:

# ❌ INCORRECTO:
stop = low_of_entry_day  # Fixed al día de entrada

# ✅ CORRECTO (trailing):
stop = lowest_low_since_entry  # Se mueve con el trade
```

**EVIDENCIA**:
- Tu AVG LOSS es -4.37%
- Tu MAX DRAWDOWN es -42.88%
- Tu PROFIT FACTOR es 0.84 (pierdes $0.16 por cada $1 arriesgado)

Si tus stops fueran dinámicos (trailing), esperaríamos:
- AVG LOSS más pequeño (~2-3%)
- Menos drawdown severo
- Mejor profit factor

**DIAGNÓSTICO**:
Probablemente estás usando stops FIJOS muy amplios. Cuando el precio se mueve a tu favor, no proteges ganancias.

---

### 🚨 SOSPECHOSO #3: Position Sizing con Salidas Parciales

```python
# Cuando calculas shares inicial:
risk_per_share = entry - stop
shares = (capital * risk_pct) / risk_per_share  # ✅ OK

# Pero después de TP1 (50% out):
remaining_shares = shares * 0.5

# ❌ BUG POTENCIAL: Capital restante no actualizado
# Si entras con $10k:
# - TP1 sale con $5k profit (+50%)
# - Pero capital_at_risk sigue siendo $10k original
# - Resultado: No estás compounding correctamente
```

**EVIDENCIA de tu gráfico**:
El gráfico "Position Sizing Impact" muestra valores erráticos. Si el position sizing fuera correcto, debería ser más suave y proporcional al equity curve.

---

### 🚨 SOSPECHOSO #4: Multi-Chunk Slicing Errors

```python
# En _run_multi_chunk_backtest, línea 3070-3078:
chunk_entries = entries.iloc[start_idx:end_idx]
chunk_atr = atr.iloc[start_idx:end_idx]
chunk_avwap = avwap.iloc[start_idx:end_idx]

# ❌ PROBLEMA POTENCIAL: Off-by-one errors
# Si los índices no alinean perfectamente:
# - chunk_entries tiene 100 rows
# - chunk_atr tiene 99 rows (missing first row debido a rolling calc)
# - chunk_avwap tiene 101 rows
# Resultado: Numpy broadcasting errors o señales desfasadas
```

**CÓMO VERIFICAR**:
```python
print(f"Entries shape: {chunk_entries.shape}")
print(f"ATR shape: {chunk_atr.shape}")
print(f"AVWAP shape: {chunk_avwap.shape}")
# Todas deben ser IDÉNTICAS
```

---

## 🎯 PLAN DE DEBUGGING PRIORIZADO

### PASO 1: Verificar Lógica de Exits (CRÍTICO)
```python
def debug_exit_logic(trades_df):
    """Analiza la lógica de exits"""
    
    # Check 1: ¿Cuántos llegaron a cada fase?
    reached_tp1 = trades_df['phases_executed'].str.contains('1').sum()
    reached_tp2 = trades_df['phases_executed'].str.contains('2').sum()
    reached_runner = trades_df['phases_executed'].str.contains('3').sum()
    
    print(f"Trades reaching TP1: {reached_tp1}/{len(trades_df)} ({reached_tp1/len(trades_df)*100:.1f}%)")
    print(f"Trades reaching TP2: {reached_tp2}/{len(trades_df)} ({reached_tp2/len(trades_df)*100:.1f}%)")
    print(f"Trades reaching Runner: {reached_runner}/{len(trades_df)} ({reached_runner/len(trades_df)*100:.1f}%)")
    
    # Check 2: ¿Breakeven stop funciona?
    stopped_after_tp1 = trades_df[
        (trades_df['phases_executed'].str.contains('1')) & 
        (trades_df['exit_reason'] == 'STOP')
    ]
    
    print(f"\nStopped AFTER reaching TP1: {len(stopped_after_tp1)}")
    print("   (Should be ~0 if breakeven stop works)")
    
    # Check 3: Average R por fase
    avg_r_tp1_only = trades_df[trades_df['phases_executed'] == '1']['total_r'].mean()
    avg_r_tp1_tp2 = trades_df[trades_df['phases_executed'] == '1,2']['total_r'].mean()
    avg_r_full = trades_df[trades_df['phases_executed'] == '1,2,3']['total_r'].mean()
    
    print(f"\nAvg R by phases reached:")
    print(f"   TP1 only: {avg_r_tp1_only:.2f}R")
    print(f"   TP1+TP2: {avg_r_tp1_tp2:.2f}R")
    print(f"   Full trade: {avg_r_full:.2f}R")
```

**Resultado esperado**:
```
Trades reaching TP1: 180/519 (34.7%)  ← ACTUAL
Trades reaching TP2: 123/519 (23.7%)  ← ACTUAL
Trades reaching Runner: ???/519

Stopped AFTER reaching TP1: 0  ← Debería ser 0
   (Should be ~0 if breakeven stop works)

Avg R by phases reached:
   TP1 only: +0.5R to +1.0R   ← Parcial profit
   TP1+TP2: +1.5R to +2.5R    ← Better
   Full trade: +3.0R to +5.0R  ← Best
```

Si ves:
- ✅ Stopped AFTER TP1 = 0 → Breakeven funciona
- ❌ Stopped AFTER TP1 > 0 → **BUG: Breakeven NO actualizado**

---

### PASO 2: Comparar vs Backtest Simple (CRÍTICO)
```python
def compare_with_simple_exit(engine, entries):
    """Compara salidas parciales vs salida simple"""
    
    # Test 1: Exit simple en 2R
    simple_exits = (engine.close >= entries * 1.02)  # +2R simple
    equity_simple, trades_simple = engine.simulate_simple(entries, simple_exits)
    
    # Test 2: Exit con partial exits (actual)
    equity_partial, trades_partial = engine.simulate_with_partial_exits(entries)
    
    # Comparar
    return_simple = (equity_simple.iloc[-1] / engine.initial_capital - 1) * 100
    return_partial = (equity_partial.iloc[-1] / engine.initial_capital - 1) * 100
    
    print(f"Simple Exit (2R target): {return_simple:+.2f}%")
    print(f"Partial Exits (TP1/TP2/Runner): {return_partial:+.2f}%")
    print(f"Difference: {return_partial - return_simple:+.2f}%")
    
    if return_simple > return_partial:
        print("⚠️ WARNING: Simple exits perform BETTER than partial exits")
        print("   This suggests partial exit logic has a bug")
```

**Si Simple Exit > Partial Exits**:
→ **BUG en la implementación de partial exits**

**Si Partial Exits > Simple Exit**:
→ La lógica funciona, el problema está en otra parte

---

### PASO 3: Verificar Índices y Alignment
```python
def verify_data_alignment(engine):
    """Verifica que todos los DataFrames estén alineados"""
    
    ref_index = engine.close.index
    
    for attr in ['high', 'low', 'volume', 'atr', 'sma_20', 'ema_8', 'ema_21']:
        if hasattr(engine, attr):
            df = getattr(engine, attr)
            if df is not None:
                # Check index match
                index_match = ref_index.equals(df.index)
                print(f"{attr}: {'✅' if index_match else '❌'} Index match")
                
                if not index_match:
                    print(f"   close: {len(ref_index)} rows, first={ref_index[0]}, last={ref_index[-1]}")
                    print(f"   {attr}: {len(df.index)} rows, first={df.index[0]}, last={df.index[-1]}")
```

---

### PASO 4: Audit Un Trade Específico
```python
def audit_single_trade(trade_id: str = "2025-11-25_AACBU"):
    """Audita un trade específico paso a paso"""
    
    # De tu PDF: AACBU entry 2025-11-25
    entry_date = "2025-11-25"
    exit_date = "2025-12-01"
    
    entry_price = 156.92
    exit_price = 149.83
    shares = 64
    
    # Expected calculations:
    risk_per_share = entry_price - exit_price  # = $7.09
    total_risk = risk_per_share * shares       # = $453.76
    actual_loss = -453.59  # From your data
    
    print(f"Trade: {trade_id}")
    print(f"   Expected loss: ${total_risk:.2f}")
    print(f"   Actual loss: ${actual_loss:.2f}")
    print(f"   Difference: ${actual_loss - (-total_risk):.2f}")
    
    # Now check if partial exits were attempted:
    # Should this trade have:
    # - Attempted TP1 at entry + 1.5R = $156.92 + (1.5 * $7.09) = $167.55
    # - Attempted TP2 at entry + 3R = $156.92 + (3 * $7.09) = $178.19
    
    # Get high during trade
    high_during_trade = max(daily_highs[entry_date:exit_date])
    
    print(f"\n   TP1 target: ${entry_price + (1.5 * risk_per_share):.2f}")
    print(f"   TP2 target: ${entry_price + (3 * risk_per_share):.2f}")
    print(f"   High reached: ${high_during_trade:.2f}")
    
    if high_during_trade >= entry_price + (1.5 * risk_per_share):
        print("   ✅ TP1 WAS REACHABLE but not executed → BUG!")
    else:
        print("   ❌ TP1 never reached (stop hit first)")
```

---

## 💡 MI HIPÓTESIS PRINCIPAL

Basado en tu data:
- Win Rate: 34.68% (bajo)
- Avg Win: +7.07%
- Avg Loss: -4.37%
- Solo 34.7% llegan a TP1

**Creo que el problema es**:

1. **Stops muy amplios** (-4.37% avg loss es grande)
2. **Breakeven stop NO funciona** (deberías tener avg loss ~0% en trades que llegan a TP1)
3. **Check order incorrecto** (stop checked before targets)

**Secuencia probable**:
```
1. Enter trade
2. Price moves up to +1.2R (casi TP1)
3. Price pulls back to -1R
4. ❌ Stop hit ANTES de que TP1 check ocurra
5. Trade cerrado en pérdida
6. En el código: nunca llegó a ejecutar tp1_check porque stop_check fue primero
```

**FIX esperado**:
```python
# ANTES (incorrecto):
for bar in range(len(prices)):
    if prices[bar] <= stop:
        exit_full()
        break
    if prices[bar] >= tp1:
        exit_partial_1()

# DESPUÉS (correcto):
for bar in range(len(prices)):
    if prices[bar] >= tp1:
        exit_partial_1()
        stop = entry  # Update to breakeven
    elif prices[bar] <= stop:  # Use elif, not separate if
        exit_full()
        break
```

---

## 🎯 TU ACCIÓN INMEDIATA

**Paso 1**: Revisa `src/backtest/numba_core.py`, busca la línea donde checks stop vs target:

```python
# Busca algo como:
if low <= stop_loss:  # ← Este if statement
    # close trade
    
if high >= take_profit:  # ← Este if statement
    # take partial profit
```

**Si ves dos `if` separados** → **ESE ES TU BUG**

**Debe ser `if` / `elif`** para que targets tengan prioridad

---

**Paso 2**: Verifica que breakeven stop se actualiza:

```python
# Después de tp1 executed, debería haber:
stop_loss = entry_price  # ← Esta línea
```

Si no existe esa línea → **ESE ES TU BUG**

---

¿Quieres que cree un script para auditar tu numba_core.py si lo tienes?
