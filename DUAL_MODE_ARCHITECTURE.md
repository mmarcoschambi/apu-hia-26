# Dual Mode Architecture: THOR vs Advanced Engine

## Overview
This project implements a **Dual Mode Architecture** with a centralized configuration system to solve the dilemma between logic validation and realistic performance simulation.

### The Dilemma
- **Validation** requires **Fixed Dollar Risk** to ensure signals are identical regardless of account size or compounding effects.
- **Production** requires **Percentage Risk + Compounding** to simulate real-world growth ("snowball effect").
- Doing both in one engine confuses the metrics and breaks convergence.

### The Solution
We separated the concerns into two distinct modes with **centralized configuration** to prevent parameter drift:

| Feature | **Mode: CONVERGENCE** | **Mode: PRODUCTION** |
| :--- | :--- | :--- |
| **Engine** | Advanced Engine (mimicking THOR) | Advanced Engine (Native) |
| **Goal** | Validate signal logic & rules | Simulate real P&L & Growth |
| **Risk Type** | **Fixed Dollar ($150)** | **Percentage (1.5%)** |
| **Compounding** | ❌ Disabled | ✅ **Enabled** |
| **Filters** | Baseline (Liquid + Momentum) | Full Professional Suite |
| **Use Case** | Debugging, Logic Check | Backtesting, Live Trading |
| **Config Source** | `config/advanced_engine_modes.py` | `config/advanced_engine_modes.py` |

---

## Centralized Configuration

**NEW**: All mode configurations are managed in `config/advanced_engine_modes.py` to ensure consistency across scripts.

### Key Functions

```python
from config.advanced_engine_modes import get_engine_kwargs

# Get convergence configuration
kwargs = get_engine_kwargs('convergence', ['AAPL', 'MSFT'], '2023-01-01', '2023-12-31')
engine = AdvancedVectorBTEngine(**kwargs)

# Get production configuration (loads validated params automatically)
kwargs = get_engine_kwargs('production', ['AAPL', 'MSFT'], '2023-01-01', '2023-12-31')
engine = AdvancedVectorBTEngine(**kwargs)

# Override specific parameters
kwargs = get_engine_kwargs('production', tickers, start, end, risk_pct=0.02)
```

### Benefits
- **Single source of truth**: No parameter duplication across scripts
- **Automatic validation**: Production mode loads validated params from `config/validated_production_params.json`
- **Type safety**: Centralized validation of parameter types and ranges
- **Documentation**: Mode differences clearly documented in one place

---

## 1. Convergence Mode (THOR Validation)
Designed to match the legacy **THOR** engine signal-for-signal.

### Purpose
- **Signal validation**: Ensure Advanced engine produces identical entry/exit signals to THOR
- **Regression testing**: Detect logic changes that break THOR compatibility
- **Debugging**: Isolate signal generation from performance metrics

### Configuration
- **Command:** `python3 debug_convergence.py`
- **Logic:** 
  - Forces `risk_dollars = 150` (fixed)
  - Uses `is_baseline_mode = True` (THOR-compatible filters)
  - Disables advanced filters (Market Regime, Sector Rotation, etc.)
  - Signal type: `breakout` (close > 20d high)
  
### Success Criteria
- **Primary**: Entry signals match THOR within 15% tolerance (signal-by-signal comparison)
- **Secondary**: Trade counts within 15% margin of THOR
- **Note**: Aggregate metrics (returns, Sharpe) are NOT compared because implementations differ

### What to Compare
✅ **Compare these (convergence-critical)**:
- Entry signal dates (date + ticker pairs)
- Total signal count
- Entry logic triggers

❌ **Don't compare these (implementation-dependent)**:
- Final returns (compounding differences)
- Sharpe ratio (execution timing)
- Max drawdown (partial exit order)
- Individual exit prices (fill assumptions)

---

## 2. Production Mode (Realistic Simulation)
Designed for maximum performance and realistic growth simulation.

### Purpose
- **Backtesting**: Evaluate strategy performance with real-world constraints
- **Parameter optimization**: Find optimal settings for live trading
- **Performance reporting**: Generate metrics for decision making

### Configuration
- **Command:** `python3 backtest_vectorbt_advanced.py --mode production`
- **Logic:**
  - Uses `risk_pct = 1.5%` (default, loads from validated params if available)
  - Enables **Compounding** (Position size grows with Equity)
  - Enables all Advanced Filters (Dynamic VIX, Market Regime, etc.)
  - Loads validated parameters from `config/validated_production_params.json`
  
### Metrics
- **Sharpe Ratio** (Risk-adjusted returns)
- **CAGR** (Compound Annual Growth Rate)
- **Max Drawdown** (Peak-to-trough decline)
- **Win Rate** (Profitable exits / Total exits)
- **Total Return** (With compounding)

### Important Rules
⚠️ **NEVER compare production metrics to THOR/convergence metrics**
- Production uses compounding → Higher returns over time
- Production uses advanced filters → Different signal counts
- Production uses professional risk management → Different drawdowns

---

## Workflow Pipeline

### Unified Pipeline Script
```bash
./run_production_pipeline.sh --tickers AAPL,MSFT,NVDA
```

**Steps:**
1. **Runs Convergence Check:**
   - Compares THOR vs Advanced (Fixed Risk, signal-level)
   - If signals diverge > 15%, it FAILS and stops
   
2. **Runs Production Sim:**
   - If convergence passes, runs the Production Backtest (Pct Risk)
   - Uses validated parameters automatically
   - Generates final performance reports

### Individual Commands

**Convergence Check (Signal Validation)**:
```bash
# Quick test with specific tickers
python3 debug_convergence.py --tickers AAPL,MSFT --start 2023-01-01 --end 2023-12-31

# Full S&P 500 universe
python3 debug_convergence.py --tickers spy --start 2023-01-01 --end 2023-12-31

# Top 50 liquid stocks from database
python3 debug_convergence.py --tickers all --limit 50 --start 2023-01-01 --end 2023-12-31

# NASDAQ 100 style universe
python3 debug_convergence.py --tickers nasdaq100 --start 2023-01-01 --end 2023-12-31
```

**Production Backtest (Performance Simulation)**:
```bash
python3 backtest_vectorbt_advanced.py \
    --tickers AAPL,MSFT \
    --start 2023-01-01 \
    --end 2023-12-31 \
    --mode production \
    --equity 100000 \
    --risk 1.5
```

**Optimization (Parameter Search)**:
```bash
python3 backtest_vectorbt_advanced.py \
    --mode optimization \
    --tickers AAPL,MSFT \
    --start 2023-01-01 \
    --end 2023-12-31
```

---

## Key Files

### Core Modules
- **`config/advanced_engine_modes.py`**: ⭐ Centralized mode configuration
- **`src/backtest/vectorbt_engine_advanced.py`**: Supports `mode="convergence"` vs `mode="production"`
- **`src/backtest/optimization_engine_thor.py`**: Legacy THOR engine for validation
- **`debug_convergence.py`**: Signal-level comparison script
- **`backtest_vectorbt_advanced.py`**: Main runner script with mode support
- **`run_production_pipeline.sh`**: Automated convergence → production workflow

### Configuration Files
- **`config/validated_production_params.json`**: Validated parameters for production mode
- **`config/feature_flags.py`**: Feature enablement flags
- **`config/settings.py`**: Global settings

---

## Best Practices

### For Development
1. **Always run convergence check** before deploying new logic changes
2. **Use centralized config** (`get_engine_kwargs`) instead of hardcoding parameters
3. **Document mode-specific behavior** in docstrings
4. **Keep THOR engine frozen** (it's the validation baseline)

### For Backtesting
1. **Start with convergence mode** to validate signals
2. **Switch to production mode** for performance metrics
3. **Don't mix metrics** from different modes in the same report
4. **Use validated params** in production (automatic via centralized config)

### For Optimization
1. **Use optimization mode** for parameter search
2. **Validate results** in convergence mode before production
3. **Save validated params** to `config/validated_production_params.json`
4. **Run walk-forward** to prevent overfitting

---

## Troubleshooting

### Convergence Check Fails
**Problem**: Signals diverge beyond 15% tolerance

**Possible Causes**:
- Filter parameters misaligned between THOR and Advanced
- Different signal_type settings
- Advanced filters not disabled in convergence mode
- Data cache inconsistency

**Solution**:
1. Check `config/advanced_engine_modes.py` convergence config
2. Verify `mode="convergence"` triggers baseline filters in engine
3. Refresh data cache if necessary
4. Compare THOR-only and Advanced-only signals for clues

### Production Metrics Look Wrong
**Problem**: Returns too low/high, or Sharpe ratio unexpected

**Possible Causes**:
- Using convergence metrics instead of production
- Not loading validated parameters
- Wrong risk percentage setting
- Missing market regime filter

**Solution**:
1. Confirm `--mode production` is set
2. Check if validated params loaded (see console output)
3. Verify risk_pct in output (should be ~1.5%, not $150)
4. Review enabled filters in configuration

### Parameter Drift
**Problem**: Different scripts use different parameter values

**Solution**:
- ✅ Always use `config/advanced_engine_modes.py`
- ❌ Never hardcode parameters in scripts
- Update centralized config when changing defaults
- Use `get_engine_kwargs()` for consistency

---

## Migration from Old System

If you have scripts using the old parameter system:

**Before (❌ Deprecated)**:
```python
engine = AdvancedVectorBTEngine(
    universe=tickers,
    start_date=start,
    end_date=end,
    mode="production",
    risk_pct=0.015,
    min_rvol=1.0,
    # ... 20 more parameters
)
```

**After (✅ New Centralized System)**:
```python
from config.advanced_engine_modes import get_engine_kwargs

kwargs = get_engine_kwargs('production', tickers, start, end)
engine = AdvancedVectorBTEngine(**kwargs)
```

The centralized config automatically:
- Loads validated params for production
- Sets correct risk type per mode
- Enables/disables filters appropriately
- Prevents parameter drift
