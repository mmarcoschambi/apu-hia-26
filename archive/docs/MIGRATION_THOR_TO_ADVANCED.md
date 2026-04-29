# Migration Guide: THOR to Advanced Engine

## Overview

**Effective Date:** 2025-02-11

**Status:** THOR Engine is **DEPRECATED** and will be removed in a future release.

**New Standard:** `AdvancedVectorBTEngine` is now the **Single Engine of Record** for all research and production work.

---

## Why We're Deprecating THOR

The two-engine workflow (THOR for research, Advanced for production) has been proven to cause **parameter collapse** when strategies move from research to production.

### The Problem

| Aspect | THOR Engine | Advanced Engine | Impact |
|--------|-------------|-----------------|--------|
| Trades | ~503 trades | ~138 trades | 73% fewer trades |
| Costs | Ignored | 0.1% fees + 0.1% slippage | Realistic cost drag |
| Liquidity | Basic filters | Full liquidity/sector/regime filters | Survivorship bias |
| Position Sizing | Simple | Adaptive with RVOL adjustment | Size mismatches |
| Market Context | None | Stage Analysis + VIX | Regime blind spots |

**Result:** Parameters optimized in THOR collapse when exposed to production realities.

---

## Migration Path

### Phase 1: Immediate (This Week)

1. **Stop using THOR immediately**
   ```python
   # ❌ OLD - THOR (DEPRECATED)
   from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
   
   engine = OptimizationEngineTHOR(
       tickers=['AAPL', 'MSFT'],
       start_date='2023-01-01',
       end_date='2023-12-31'
   )
   result = engine.backtest(params)
   ```

2. **Switch to Advanced Engine**
   ```python
   # ✅ NEW - Advanced (PRODUCTION STANDARD)
   from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
   
   engine = AdvancedVectorBTEngine(
       universe=['AAPL', 'MSFT'],
       start_date='2023-01-01',
       end_date='2023-12-31',
       mode='production',  # or 'convergence' for validation
       **params
   )
   engine.load_data()
   result = engine.run_backtest()
   ```

### Phase 2: Validation Integration (Next 2 Weeks)

Implement the Three-Phase Research Gate for all strategy development:

```python
from src.validation.research_gate import ResearchGate
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# Define your strategy parameters
# NOTE: Use config/defaults.py to get values synchronized with production_config.json
from config.defaults import get_tier1_defaults, get_tier2_defaults, get_tier3_defaults

tier2 = get_tier2_defaults()
params = {
    'min_rvol': tier2.get("min_rvol", 0.91),
    'min_adr': tier2.get("min_adr", 1.97),
    'max_dist_sma20': tier2.get("max_dist_sma20", 8.94),
    'tp1_r': 1.75,
    'tp2_r': 4.5,
    'risk_dollars': 1000,
    'mode': 'production'
}

# Run validation
gate = ResearchGate()
result = gate.validate_strategy(
    engine_class=AdvancedVectorBTEngine,
    params=params,
    universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],
    train_dates=('2020-01-01', '2022-12-31'),
    test_dates=('2023-01-01', '2024-12-31')
)

if result.promotion_approved:
    print("✅ Strategy approved for production!")
else:
    print("❌ Strategy rejected:")
    for reason in result.rejection_reasons:
        print(f"  - {reason}")
```

### Phase 3: Optimization Update (Ongoing)

Replace simple Sharpe optimization with robust objectives:

```python
from src.validation.robustness_metrics import (
    robust_objective_function,
    RobustObjectiveConfig
)
from config.defaults import get_tier2_defaults

# Get synchronized defaults
tier2 = get_tier2_defaults()

# Configure for robustness
config = RobustObjectiveConfig(
    p5_weight=1.0,        # Prioritize worst-case performance
    p10_weight=0.5,
    max_dd_penalty=2.0,   # Heavy penalty for drawdowns
    sharpe_weight=0.3     # Lower weight for raw Sharpe
)

def objective(trial):
    params = {
        'min_rvol': tier2.get("min_rvol", 0.91),
        'min_adr': tier2.get("min_adr", 1.97),
        # ... other params
    }
    
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start,
        end_date=end,
        **params
    )
    engine.load_data()
    backtest_result = engine.run_backtest()
    
    # Use robust objective instead of raw Sharpe
    return robust_objective_function(backtest_result, config)
```

---

## Centralized Configuration System

**IMPORTANT:** As of 2026-02-22, all default parameter values are centralized in `config/defaults.py`.

### Why This Matters

Previously, defaults were scattered across multiple files:
- `vectorbt_engine_advanced.py` (engine defaults)
- `app.py` (UI fallback values)
- `optimize_3tier.py` (optimization defaults)
- `get_dynamic_thresholds()` (filter function defaults)

This caused **parameter drift** when the JSON was updated but fallbacks weren't.

### New Pattern

```python
# ALWAYS use config.defaults for parameter values
from config.defaults import (
    get_tier1_defaults,  # Strategy params (tp1_r, tp2_r, etc.)
    get_tier2_defaults,  # Filter params (min_rvol, min_adr, etc.)
    get_tier3_defaults,  # Risk params (max_exposure_pct, etc.)
    reload_config,       # Call after re-optimization
)

# Get defaults (reads from production_config.json)
tier2 = get_tier2_defaults()
min_rvol = tier2.get("min_rvol", 0.91)  # Fallback matches JSON

# After re-optimization, reload the config
reload_config()  # Clears cache, reads fresh JSON
```

### Priority Chain

```
1. production_config.json (source of truth - from optimization)
2. config/defaults.py (centralized fallbacks, synced with JSON)
3. Hardcoded value (last resort, should match JSON)
```

---

## Parameter Mapping: THOR → Advanced

| THOR Parameter | Advanced Equivalent | Notes |
|----------------|---------------------|-------|
| `tickers` | `universe` | Same list |
| `start_date` | `start_date` | Same format |
| `end_date` | `end_date` | Same format |
| `initial_capital` | `initial_capital` | Same |
| `lookback_days` | Auto-calculated | Built into load_data() |
| `min_rvol` | `min_rvol` | Same |
| `min_adr` | `min_adr` | Same |
| `min_volume` | `min_volume` | Same |
| `min_dollar_volume` | `min_dollar_volume` | Same |
| `max_dist_sma20` | `max_dist_sma20` | Same |
| `risk_dollars` | `risk_dollars` | Same |
| `max_stop_pct` | `max_stop_pct` | Stored as decimal (0.08 = 8%) in JSON, engine divides by 100 |
| `max_exposure_pct` | `max_exposure_pct` | Same |
| `tp1_r` | `tp1_r` | Same |
| `tp2_r` | `tp2_r` | Same |
| `tp1_pct` | `tp1_pct` | Same |
| `tp2_pct` | `tp2_pct` | Same |
| `runner_pct` | `runner_pct` | Same |
| `use_phases` | Always True | 3-phase exits always enabled |
| `require_bullish_spy` | `require_spy_above_sma50` | Renamed + enhanced |
| `max_vix` | `max_vix_threshold` | Same |
| `require_positive_rs` | `require_positive_rs` | Same |
| `signal_type` | `signal_type` | 'breakout' or 'any' |

### New Advanced-Only Parameters

```python
AdvancedVectorBTEngine(
    # Risk mode
    mode='production',  # 'production' (Pct Risk) or 'convergence' (Fixed $ Risk)
    
    # RVOL-based sizing
    rvol_danger=3.0,
    rvol_warning=2.0,
    rvol_danger_size=30,    # % of normal size when RVOL > danger
    rvol_warning_size=65,   # % of normal size when RVOL > warning
    
    # Market regime
    use_market_regime_filter=True,
    block_trades_in_stage3=True,  # Block in distribution phase
    block_trades_in_stage4=True,  # Block in bear market
    
    # Sector rotation
    use_composite_sector_scoring=True,
    sector_top_percentile=0.40,  # Top 40% sectors only
    
    # Earnings (disabled by default)
    use_earnings_calendar=False,
    earnings_days=5,
    earnings_cushion=10.0,
    
    # RS IBD-style
    use_rs_percentile=False,
    min_rs_percentile=80.0,
    
    # Trailing stops (disabled)
    use_trailing_stop=False,
    
    # Costs (now REQUIRED)
    fees=0.001,      # 0.1%
    slippage=0.001,  # 0.1%
)
```

---

## Key Differences

### 1. Engine Instantiation

**THOR:**
```python
engine = OptimizationEngineTHOR(
    tickers=tickers,
    start_date='2023-01-01',
    end_date='2023-12-31'
)
# Data loaded automatically
result = engine.backtest(params)  # Single method call
```

**Advanced:**
```python
engine = AdvancedVectorBTEngine(
    universe=tickers,
    start_date='2023-01-01',
    end_date='2023-12-31',
    **params  # Params in constructor, not backtest()
)
engine.load_data()  # Explicit data loading
result = engine.run_backtest()  # Separate execution
```

### 2. Result Format

**THOR:**
```python
{
    'profit_factor': 1.5,
    'total_trades': 150,
    'total_return_pct': 25.0,
    'sharpe_ratio': 1.2,
    'max_drawdown_pct': 15.0,
    'win_rate_pct': 55.0,
    'final_value': 125000.0
}
```

**Advanced:**
```python
{
    'total_return_pct': 18.0,  # More realistic with costs
    'sharpe_ratio': 0.9,
    'max_drawdown_pct': 18.0,
    'total_trades': 45,  # Fewer due to stricter filters
    'win_rate_pct': 52.0,
    'profit_factor': 1.4,
    'equity_curve': pd.Series(...),  # Full equity curve
    'trades_df': pd.DataFrame(...)   # Detailed trade log
}
```

### 3. Validation Workflow

**THOR (Deprecated):**
```python
# Simple optimization
study = optuna.create_study()
study.optimize(objective, n_trials=100)
best_params = study.best_params
# No validation - direct to production (DANGEROUS!)
```

**Advanced (Standard):**
```python
# 1. Optimization with robust objectives
study = optuna.create_study(direction='maximize')
study.optimize(robust_objective, n_trials=100)

# 2. Three-Phase Validation
gate = ResearchGate()
validation = gate.validate_strategy(
    engine_class=AdvancedVectorBTEngine,
    params=study.best_params,
    universe=universe,
    train_dates=train_dates,
    test_dates=test_dates
)

# 3. Stress Testing
stress_suite = StressTestSuite(AdvancedVectorBTEngine)
stress_results = stress_suite.run_full_stress_test(...)

# 4. Only promote if ALL gates pass
if validation.promotion_approved and stress_results.all_passed:
    deploy_to_production(study.best_params)
```

---

## Quality Gates

All strategies must pass these gates before production:

### Phase 1: Discovery
- ✅ Valid parameter structure
- ✅ Parameter bounds respected
- ✅ Strategy logic compiles

### Phase 2: Validation
- ✅ **PBO < 50%** (Probability of Backtest Overfitting)
- ✅ **Bootstrap p5 > 0%** (Worst-case annual return positive)
- ✅ **Bootstrap p10 > 2%** (10th percentile decent)
- ✅ **Max Drawdown < 25%**
- ✅ **Sharpe > 0.8**
- ✅ **Minimum 50 trades** (statistical significance)

### Phase 3: Productionization
- ✅ **2x costs impact > -10%**
- ✅ **3x costs impact > -20%**
- ✅ **Wider spreads impact > -15%**
- ✅ **Worst-case scenario > -50%**
- ✅ **Capacity constraints met**

---

## Quick Reference

### Import Statements

```python
# Backtesting
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# Validation
from src.validation.research_gate import ResearchGate, ValidationThresholds
from src.validation.stress_testing import StressTestSuite
from src.validation.robustness_metrics import (
    robust_objective_function,
    RobustObjectiveConfig
)
```

### Minimal Working Example

```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.validation.research_gate import ResearchGate
from config.defaults import get_tier1_defaults, get_tier2_defaults, get_tier3_defaults

# Get synchronized defaults from production_config.json
tier1 = get_tier1_defaults()
tier2 = get_tier2_defaults()
tier3 = get_tier3_defaults()

# Strategy parameters (values from JSON, not hardcoded)
params = {
    'min_rvol': tier2.get("min_rvol", 0.91),
    'min_adr': tier2.get("min_adr", 1.97),
    'max_dist_sma20': tier2.get("max_dist_sma20", 8.94),
    'tp1_r': tier1.get("tp1_r", 1.75),
    'tp2_r': tier1.get("tp2_r", 4.5),
    'risk_dollars': tier1.get("risk_dollars", 1000),
    'mode': 'production',
    'fees': 0.001,
    'slippage': 0.001
}

# Run with validation
gate = ResearchGate()
result = gate.validate_strategy(
    engine_class=AdvancedVectorBTEngine,
    params=params,
    universe=['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'],
    train_dates=('2022-01-01', '2023-12-31'),
    test_dates=('2024-01-01', '2024-12-31')
)

print(f"Approved: {result.promotion_approved}")
print(f"PBO: {result.pbo_score:.2%}")
print(f"Bootstrap p5: {result.bootstrap_p5:.2f}%")
```

---

## Support

For migration questions:
1. Check existing scripts in `backtest_dynamic_universe.py`
2. Review `bugatti_optuna.py` for optimization examples
3. See validation modules in `src/validation/`

**DO NOT use THOR for new development. It will be removed in Q2 2025.**
