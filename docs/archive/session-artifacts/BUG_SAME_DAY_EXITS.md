# 🔴 BUG REPORT: Same-Day Exits (Hold Time = 0)

## 📊 Problem Statement

**ALL trades are exiting on the same day as entry** (`hold_days = 0`), which is impossible for a daily momentum strategy.

## 🔍 Evidence

```
Total Trades: 1074
Same-day exits: 1074/1074 (100%)
Average hold: 0.0 days
Max hold: 0 days

Exit Distribution:
- STOP: 503 (47%)
- TP1: 293 (27%)
- TP2: 142 (13%)
- RUNNER: 136 (13%)
```

## ❌ Why This is Wrong

1. **Strategy uses daily bars** - Should hold multiple days
2. **TP1 at +6.25%** - Rare to hit intraday on entry day
3. **TP2 at +17.5%** - Impossible to hit same day
4. **Trailing runner** - Needs days to trail

## 🔧 Technical Analysis

### Data Structure
```python
# From partial_exits.csv
entry_date,exit_date,entry_price,exit_price,exit_phase,bars_held
2017-02-23,2017-02-23,16.38,17.40,TP1,0  ← +6.25% gain, 0 bars?
2017-03-08,2017-03-08,8.51,10.00,TP2,0   ← +17.5% gain, 0 bars??
```

### Root Causes

#### 1. Numba Core Bug
File: `src/backtest/numba_core.py`

**Hypothesis**: Entry and exit logic use same bar:
```python
# WRONG
if entry_signal[i]:
    entry_idx = i
    entry_price = close[i]
    
if exit_signal[i]:  ← Same i!
    exit_idx = i
    bars_held = exit_idx - entry_idx  # = 0
```

**Should be**:
```python
# CORRECT
if entry_signal[i]:
    entry_idx = i
    entry_price = close[i]
    in_position = True
    
if in_position and exit_signal[i] and i > entry_idx:
    exit_idx = i
    bars_held = exit_idx - entry_idx  # > 0
```

#### 2. TP Price Calculation Bug
If TP prices are set too loose:
```python
# BUG
tp1_price = entry * 1.0625  # 6.25% from entry
# But if entry = close[i], and next bar gaps up 7%
# Then exit on SAME bar at close[i]
```

#### 3. Data Granularity Issue
Using intraday data as daily:
- Data might be 5min bars
- Entry at 09:35, Exit at 15:55
- Same day but different bars
- `bars_held` should count intraday bars

## 🎯 Impact on Metrics

### Inflated Metrics
```
Win Rate: 53.1% ← TOO LOW (should be ~70% with proper hold)
Avg R: 0.00R ← WRONG (should be positive)
Hold Time: 0.0d ← IMPOSSIBLE
```

### UI Display Issues
```
✅ Métricas Corregidas: trades completos agrupados
BUT: No trades with multiple exits!
Reason: All stopped/TP'd same day → no grouping happens
```

## 🐛 Related Bugs

1. **Split Adjustment** - Entry prices don't match chart
2. **R-Multiple = 0** - Because bars_held = 0 → risk calc wrong
3. **Hold Time Distribution** - All "Scalps" (<3d) because 0 days

## 🔧 Fix Required

### Priority 1: Fix Entry/Exit Logic
```python
# src/backtest/numba_core.py
# Ensure entry and exit CANNOT happen on same bar for daily strategy
```

### Priority 2: Calculate bars_held Correctly
```python
# Should be actual index difference, not 0
bars_held = exit_bar_idx - entry_bar_idx
```

### Priority 3: Verify Data Granularity
```python
# Is data daily or intraday?
# If intraday, bars_held should count intraday bars
# If daily, impossible to exit same day
```

## 📝 Test Cases

### Before Fix
```
Entry: 2022-01-25 @ $17.25
Exit: 2022-01-25 @ $19.12 (TP1)
bars_held: 0 ← BUG
```

### After Fix
```
Entry: 2022-01-25 @ $17.25
Exit: 2022-01-28 @ $19.12 (TP1)
bars_held: 3 ← CORRECT
```

## 🎯 Next Steps

1. ✅ Audit `numba_core.py` entry/exit logic
2. ✅ Check data source (daily vs intraday)
3. ✅ Fix bars_held calculation
4. ✅ Re-run backtest and verify hold times > 0
5. ✅ Verify split adjustments match charts

---

**Status**: 🔴 CRITICAL - Affects all backtest results  
**Impact**: Metrics unreliable, strategy evaluation invalid  
**ETA**: Requires core engine audit
