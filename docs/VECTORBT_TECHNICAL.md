# VectorBT Technical Implementation Guide

## Architecture Overview

### Data Flow

```
┌─────────────────┐
│ ticker_cache.db │ SQLite database with OHLCV
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  VectorBT Engine (vectorized)       │
│                                     │
│  1. Load data (all tickers at once)│
│  2. Calculate indicators (pandas)   │
│  3. Generate signals (boolean df)   │
│  4. Calculate position sizes (ATR)  │
│  5. Run simulation (vbt.Portfolio)  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Results                            │
│  - Equity curve (pandas Series)     │
│  - Trades (DataFrame)               │
│  - Metrics (Sharpe, DD, Win Rate)   │
└─────────────────────────────────────┘
```

## Key Components

### 1. VectorBTEngine (Basic)
**File:** `src/backtest/vectorbt_engine.py`

**Purpose:** Simplified vectorized backtesting without custom exit logic.

**Key Methods:**
- `load_data()`: Loads OHLCV for all tickers into MultiIndex DataFrames
- `calculate_signals()`: Implements Triad Protocol logic vectorized
- `calculate_atr()`: ATR calculation for all tickers simultaneously
- `calculate_position_sizes()`: Risk-based sizing using ATR stops
- `run_backtest()`: Orchestrates the full backtest flow

**Usage:**
```python
from src.backtest.vectorbt_engine import run_vectorbt_backtest

results = run_vectorbt_backtest(
    universe=['AAPL', 'MSFT', 'NVDA'],
    start_date='2021-01-01',
    end_date='2021-12-31',
    initial_capital=100000,
    risk_pct=0.5,
    max_exposure=25.0
)
```

### 2. AdvancedVectorBTEngine (Recommended)
**File:** `src/backtest/vectorbt_engine_advanced.py`

**Purpose:** Full featured engine with 2-phase exit system (TP1/TP2).

**Key Difference:** Uses custom simulation loop instead of `vbt.Portfolio.from_signals()` to support partial exits.

**Exit Logic:**
```python
# TP1 (50% position)
- Trigger: 1.5R profit OR AVWAP breakdown
- Action: Exit 50% of shares

# TP2 (remaining 50%)
- Trigger: 3R profit OR trailing stop
- Action: Exit remaining shares

# Stop Loss
- Trigger: Price drops 1 ATR below entry
- Action: Exit all remaining shares
```

**Usage:**
```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

engine = AdvancedVectorBTEngine(
    universe=['AAPL', 'MSFT'],
    start_date='2021-01-01',
    end_date='2021-12-31',
    initial_capital=100000,
    risk_pct=0.005,
    max_exposure_pct=0.25
)

results = engine.run_backtest()
trades_df = results['trades']
```

## Triad Protocol Implementation

### Signal Types (Vectorized)

#### Camino 1: Blue Sky Breakout
```python
# Conditions (all vectorized across tickers)
price_above_base = close > base_high
avwap_converged = abs(avwap - base_high) / base_high < 0.02
uptrend = sma20 > sma50
high_volume = volume > (avg_vol_20 * 1.5)

blue_sky_signal = price_above_base & avwap_converged & uptrend & high_volume
```

#### Camino 2: VWAP Reclaim
```python
# Gap down recovery
below_vwap_yesterday = close.shift(1) < vwap.shift(1)
above_vwap_today = close > vwap
near_avwap = abs((close - avwap) / avwap) < 0.05

vwap_reclaim = below_vwap_yesterday & above_vwap_today & high_volume & near_avwap
```

#### Camino 3: Safety Check
```python
# Wait for AVWAP when it's too far above
avwap_far_above = (avwap > close) & ((close - avwap) / avwap < -0.05)
wait_signal = avwap_far_above & price_above_base
```

## Performance Optimization Techniques

### 1. Vectorization Best Practices
```python
# ❌ BAD: Loop through tickers
for ticker in tickers:
    sma = calculate_sma(data[ticker])
    
# ✅ GOOD: Vectorized operation
sma = data.rolling(20).mean()  # Applies to all columns at once
```

### 2. Memory Management
```python
# Use appropriate dtypes
close_df = close_df.astype('float32')  # vs float64 (saves 50% memory)

# Drop intermediate calculations
del temp_df  # Free memory when done
```

### 3. Caching Strategy
```python
# Cache expensive calculations
@functools.lru_cache(maxsize=128)
def get_ticker_data(ticker, start, end):
    return cache.get_ohlcv(ticker, start, end)
```

## Debugging Guide

### Common Issues

#### Issue 1: Dimension Mismatch
```
ValueError: operands could not be broadcast together with shapes (252,50) (252,100)
```

**Cause:** DataFrames have different number of columns (tickers loaded vs tickers in signal)

**Fix:**
```python
# Ensure all DataFrames use same ticker list
self.universe = [t for t in self.universe if t in self.close.columns]
```

#### Issue 2: No Trades Generated
**Symptoms:** `total_trades = 0`

**Debug:**
```python
# Check signal counts
print(f"Blue Sky signals: {blue_sky.sum().sum()}")
print(f"VWAP Reclaim signals: {vwap_reclaim.sum().sum()}")

# Check data quality
print(f"Data loaded: {len(self.close.columns)} tickers")
print(f"Date range: {self.close.index[0]} to {self.close.index[-1]}")
```

#### Issue 3: AttributeError with VectorBT
```
AttributeError: 'Portfolio' object has no attribute 'total_trades'
```

**Cause:** VectorBT API changed between versions

**Fix:**
```python
# Check attribute exists
if hasattr(portfolio, 'total_trades'):
    trades = portfolio.total_trades
else:
    trades = len(portfolio.trades.records)
```

## Testing Strategy

### Unit Tests
```python
def test_signal_generation():
    engine = VectorBTEngine(['AAPL'], '2021-01-01', '2021-12-31')
    engine.load_data()
    signals = engine.calculate_signals()
    
    assert signals['entries'].shape == engine.close.shape
    assert signals['entries'].dtype == bool
```

### Integration Tests
```python
def test_full_backtest():
    results = run_vectorbt_backtest(
        universe=['AAPL'],
        start_date='2021-01-01',
        end_date='2021-12-31'
    )
    
    assert 'total_return' in results
    assert results['total_trades'] >= 0
```

### Validation Against Original
```python
def test_vs_original_engine():
    """Compare results with daily_engine.py"""
    # Run both engines with same config
    vbt_results = run_vectorbt_backtest(...)
    orig_results = run_daily_engine(...)
    
    # Compare key metrics (allow small differences due to implementation)
    assert abs(vbt_results['total_return'] - orig_results['total_return']) < 0.01
```

## Performance Benchmarks

### Measured Performance (2021 data)

| Tickers | VectorBT Time | Original Time | Speedup |
|---------|---------------|---------------|---------|
| 10      | 0.12s         | ~60s          | 500x    |
| 50      | 0.46s         | ~300s         | 650x    |
| 100     | 1.35s         | ~900s         | 666x    |
| 500     | ~6s           | ~3600s+       | 600x+   |

### Bottlenecks

1. **Data Loading** (~30-40% of time)
   - Mitigated by: Batch loading, better indexing in SQLite

2. **Indicator Calculation** (~20-30% of time)
   - Already optimized via pandas/numpy

3. **Portfolio Simulation** (~20-30% of time)
   - VectorBT's C++ backend handles this

4. **Results Extraction** (~10% of time)
   - Minimal overhead

## Extension Points

### Adding New Signals
```python
# In calculate_signals()
def calculate_signals(self):
    # ... existing signals ...
    
    # Add your custom signal
    custom_condition = self.close > self.close.shift(5) * 1.10  # 10% up in 5 days
    custom_signal = custom_condition & high_volume
    
    # Combine with existing
    all_signals = blue_sky | vwap_reclaim | custom_signal
    return {'entries': all_signals, ...}
```

### Custom Exit Logic
```python
# In AdvancedVectorBTEngine.simulate_with_partial_exits()
# Add your exit condition
if your_exit_condition:
    # Execute exit
    cash += exit_price * shares
    trade_log.append({...})
    del positions[ticker]
```

### New Indicators
```python
def calculate_my_indicator(self) -> pd.DataFrame:
    """Your custom indicator (vectorized)"""
    # Must return DataFrame with same shape as self.close
    result = self.close.rolling(window=X).apply(your_function)
    return result
```

## Resources

- **VectorBT Docs:** https://vectorbt.dev/
- **Pandas Performance:** https://pandas.pydata.org/docs/user_guide/enhancingperf.html
- **NumPy Broadcasting:** https://numpy.org/doc/stable/user/basics.broadcasting.html

## Contributing

When adding new features:

1. Ensure vectorization (no loops over tickers/dates)
2. Add unit tests
3. Benchmark performance
4. Update this documentation
5. Validate against original engine

---

**Last Updated:** 2026-01-05  
**Version:** 1.0.0  
**Maintainer:** Momentum V2 Team
