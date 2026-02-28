# Dual Mode Quick Reference

## When to Use Each Mode

| Scenario | Mode | Command |
|----------|------|---------|
| 🔍 **Validating strategy logic** | CONVERGENCE | `python3 debug_convergence.py --tickers all --limit 50` |
| 🐛 **Debugging entry/exit signals** | CONVERGENCE | `python3 debug_convergence.py --tickers AAPL,MSFT` |
| 🧪 **Testing code changes** | CONVERGENCE | `python3 debug_convergence.py --tickers spy --limit 50` |
| 📊 **Backtesting performance** | PRODUCTION | `python3 backtest_vectorbt_advanced.py --mode production` |
| 💰 **Evaluating P&L** | PRODUCTION | `python3 backtest_vectorbt_advanced.py --mode production` |
| 🚀 **Live trading prep** | PRODUCTION | `python3 backtest_vectorbt_advanced.py --mode production` |
| 🔬 **Parameter optimization** | OPTIMIZATION | Use with Optuna/walk-forward scripts |

---

## Universe Options

### Available Universes

| Universe | Command | Tickers | Use Case |
|----------|---------|---------|----------|
| **Database (Top Liquid)** | `--tickers all --limit 100` | ~100-500 | Match Streamlit universe |
| **S&P 500** | `--tickers spy` | ~500 | Full market coverage |
| **NASDAQ 100** | `--tickers nasdaq100` | ~100 | Tech-heavy universe |
| **Custom List** | `--tickers AAPL,MSFT,NVDA` | Custom | Quick tests |

### Show Available Universes
```bash
python3 show_convergence_universes.py
```

---

## Quick Commands

### Convergence (Signal Validation)
```bash
# Basic convergence check (compare signals to THOR)
python3 debug_convergence.py --tickers AAPL,MSFT --start 2023-01-01 --end 2023-12-31

# Full S&P 500 validation
python3 debug_convergence.py --tickers spy --start 2023-01-01 --end 2023-12-31

# Top 100 liquid stocks from database (same as Streamlit uses)
python3 debug_convergence.py --tickers all --limit 100 --start 2023-01-01 --end 2023-12-31

# Top 50 for faster testing
python3 debug_convergence.py --tickers all --limit 50 --start 2023-01-01 --end 2023-03-31

# Expected output: Signal overlap % and pass/fail verdict
```

### Production (Performance Simulation)
```bash
# Basic production backtest (uses validated params automatically)
python3 backtest_vectorbt_advanced.py \
    --mode production \
    --tickers AAPL,MSFT \
    --start 2023-01-01 \
    --end 2023-12-31

# Custom risk percentage
python3 backtest_vectorbt_advanced.py \
    --mode production \
    --tickers AAPL,MSFT \
    --risk 2.0 \
    --start 2023-01-01 \
    --end 2023-12-31

# Ignore validated params
python3 backtest_vectorbt_advanced.py \
    --mode production \
    --tickers AAPL,MSFT \
    --no-validated
```

### Full Pipeline (Recommended)
```bash
# Run convergence check then production backtest
./run_production_pipeline.sh --tickers AAPL,MSFT,NVDA --start 2023-01-01 --end 2023-12-31

# Pipeline stops if convergence fails (signals diverge)
```

---

## Key Differences

| Aspect | CONVERGENCE | PRODUCTION |
|--------|-------------|------------|
| **Risk Type** | Fixed $150 | 1.5% of equity |
| **Compounding** | ❌ No | ✅ Yes |
| **Market Regime Filter** | ❌ Off | ✅ On |
| **Sector Rotation** | ❌ Off | ✅ Optional |
| **Goal** | Signal validation | P&L simulation |
| **Compare to THOR** | ✅ Yes | ❌ Never |

---

## What to Compare

### ✅ Convergence Mode (Compare These)
- Entry signal dates (date + ticker)
- Signal count (within 15% tolerance)
- Entry triggers (breakout logic)
- Filter application (baseline only)

### ❌ Production Mode (Don't Compare to THOR)
- Final returns (compounding differs)
- Sharpe ratio (execution timing differs)
- Max drawdown (partial exits differ)
- Trade P&L (position sizing differs)

**Why?** Production mode uses:
- Percentage risk → Position sizes grow with equity
- Advanced filters → Different signal counts
- Market regime → Adaptive risk/thresholds
- Compounding → Exponential growth vs linear

---

## Common Mistakes

### ❌ Mistake 1: Comparing Production to THOR
**Wrong**:
```
"Production Sharpe is 2.5 but THOR was 1.8, something's broken"
```

**Right**:
```
"Convergence signals overlap 94%, logic is validated.
Production Sharpe is 2.5 with compounding enabled."
```

### ❌ Mistake 2: Using Wrong Mode
**Wrong**:
```bash
# Using production mode to validate signals
python3 backtest_vectorbt_advanced.py --mode production  # Then comparing to THOR
```

**Right**:
```bash
# Use convergence for validation, production for performance
python3 debug_convergence.py  # Signal validation
python3 backtest_vectorbt_advanced.py --mode production  # Performance
```

### ❌ Mistake 3: Hardcoding Parameters
**Wrong**:
```python
engine = AdvancedVectorBTEngine(
    universe=tickers,
    mode="production",
    risk_pct=0.015,
    min_rvol=1.0,
    # ... duplicating 20+ parameters
)
```

**Right**:
```python
from config.advanced_engine_modes import get_engine_kwargs

kwargs = get_engine_kwargs('production', tickers, start, end)
engine = AdvancedVectorBTEngine(**kwargs)
```

---

## Troubleshooting

### Convergence Fails (Signals Diverge)

**Symptoms**: Signal overlap < 85%, count difference > 15%

**Possible Causes**:
1. Filter parameters misaligned
2. Advanced filters not disabled in convergence mode
3. Data cache inconsistency
4. Code change broke THOR compatibility

**Solution**:
```bash
# 1. Check centralized config is being used
python3 -c "from config.advanced_engine_modes import print_mode_comparison; print_mode_comparison()"

# 2. Review THOR-only and Advanced-only signals
python3 debug_convergence.py --tickers AAPL,MSFT | grep "only signals"

# 3. Refresh data cache if needed
python3 populate_market_data.py --tickers AAPL,MSFT

# 4. Compare with last working version
git diff src/backtest/vectorbt_engine_advanced.py
```

### Production Metrics Look Wrong

**Symptoms**: Returns too high/low, or metrics unexpected

**Check**:
1. Mode is set correctly: `--mode production`
2. Validated params loaded (see console output)
3. Risk percentage correct (not $150)
4. Not comparing to THOR/convergence

**Verify**:
```bash
# Check what config is being loaded
python3 backtest_vectorbt_advanced.py --mode production --tickers AAPL --start 2023-01-01 --end 2023-01-31 | head -20

# Should show:
# ✅ Using centralized PRODUCTION configuration
#    Risk: 1.50%
#    Filters: Professional
```

---

## Integration with Other Scripts

### Using Centralized Config in Your Scripts

```python
from config.advanced_engine_modes import get_engine_kwargs

# Method 1: Standard usage
kwargs = get_engine_kwargs('production', tickers, start_date, end_date)
engine = AdvancedVectorBTEngine(**kwargs)

# Method 2: With overrides
kwargs = get_engine_kwargs(
    'production', 
    tickers, 
    start_date, 
    end_date,
    risk_pct=0.02,  # Override default
    max_exposure_pct=0.40
)
engine = AdvancedVectorBTEngine(**kwargs)

# Method 3: Get config dict only
from config.advanced_engine_modes import get_production_config
config = get_production_config()
# Modify config dict, then pass to engine
```

### In Optimization Scripts

```python
from config.advanced_engine_modes import get_optimization_config

# Start from optimization defaults
base_config = get_optimization_config()

# Optuna suggests parameters
trial_config = base_config.copy()
trial_config['risk_pct'] = trial.suggest_float('risk_pct', 0.01, 0.03)
trial_config['max_exposure_pct'] = trial.suggest_float('max_exp', 0.20, 0.50)

# Run trial
engine = AdvancedVectorBTEngine(**trial_config)
```

---

## Files to Know

| File | Purpose |
|------|---------|
| `config/advanced_engine_modes.py` | ⭐ **Centralized mode configuration** |
| `debug_convergence.py` | Signal validation script |
| `backtest_vectorbt_advanced.py` | Main backtest runner |
| `run_production_pipeline.sh` | Convergence → production workflow |
| `DUAL_MODE_ARCHITECTURE.md` | Full documentation |
| `DUAL_MODE_IMPLEMENTATION_SUMMARY.md` | Implementation details |
| `config/validated_production_params.json` | Validated parameters |

---

## Decision Tree

```
┌─────────────────────────────────────┐
│  What do you want to do?           │
└─────────────────────────────────────┘
              │
      ┌───────┴────────┐
      │                │
   Validate         Measure
   Signals        Performance
      │                │
      ▼                ▼
┌──────────┐    ┌──────────────┐
│  CONV-   │    │  PRODUCTION  │
│ ERGENCE  │    │     MODE     │
│   MODE   │    │              │
└──────────┘    └──────────────┘
      │                │
      │                │
      ▼                ▼
debug_convergence   backtest_vectorbt
     .py            _advanced.py
                    --mode production
```

---

## Remember

1. ✅ **Always use centralized config** (`get_engine_kwargs`)
2. ✅ **Compare signals in convergence mode** (not metrics)
3. ✅ **Never compare production to THOR** (different implementations)
4. ✅ **Run convergence before production** (validate logic first)
5. ✅ **Use validated params in production** (automatic loading)

---

## Getting Help

1. **Quick reference**: This file
2. **Full docs**: `DUAL_MODE_ARCHITECTURE.md`
3. **Implementation**: `DUAL_MODE_IMPLEMENTATION_SUMMARY.md`
4. **Mode comparison**: `python3 config/advanced_engine_modes.py`
5. **Validation test**: See DUAL_MODE_IMPLEMENTATION_SUMMARY.md
