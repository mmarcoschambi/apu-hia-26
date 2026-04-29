# Momentum Trading V2 - Project Context

## Project Overview

**Momentum Trading V2** (Bugatti Trading System) is an institutional-grade automated momentum breakout trading system implementing the **"Triad Protocol"** (Base + AVWAP + VWAP). The system is designed to capture momentum breakouts with professional risk management.

### Architecture

- **Language**: Python 3 (bilingual codebase: English/Spanish)
- **UI**: Streamlit dashboard (`app.py`)
- **Backtesting**: VectorBT + Numba-optimized engines
- **Optimization**: Optuna Bayesian optimization with Walk-Forward validation
- **Data**: yfinance, OpenBB for market data
- **Analytics**: QuantStats for performance reporting

### Dual Mode Architecture

The system uses **two distinct modes** for different purposes:

| Mode | Purpose | Risk Type | Command |
|------|---------|-----------|---------|
| **CONVERGENCE** | Signal validation & debugging | Fixed $150 | `python3 debug_convergence.py` |
| **PRODUCTION** | Performance simulation & live trading | 1.5% with compounding | `python3 backtest_vectorbt_advanced.py --mode production` |

**Key Files**:
- `config/advanced_engine_modes.py` - Centralized mode configuration
- `src/backtest/vectorbt_engine_advanced.py` - Advanced engine with mode support
- `src/backtest/optimization_engine_thor.py` - Legacy THOR engine for validation

---

## Building and Running

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Additional dependencies (used but not in requirements.txt)
pip install vectorbt numba openbb scipy
```

### Key Commands

| Action | Command | Description |
|--------|---------|-------------|
| **Dashboard** | `streamlit run app.py` | Main Streamlit UI - charts, signals, backtests |
| **Scanner** | `python3 live_scanner.py` | Real-time market scanner for setups |
| **Backtest** | `python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31` | Historical simulation |
| **Optimization** | `python3 bugatti_optuna.py --trials 50 --tickers 30` | Optuna parameter search |
| **Convergence** | `python3 debug_convergence.py --tickers AAPL,MSFT` | Signal validation vs THOR |
| **Universe** | `python3 manage_universe.py --info` | Manage tickers and cache |

### Daily Workflow

1. **Pre-Market (9:00 AM)**: `python3 morning_workflow.py` - Market health check
2. **Market Open (9:30 AM)**: `streamlit run app.py` - Monitor signals
3. **Post-Market (4:00 PM)**: `python3 position_tracker.py` - Review positions

---

## Project Structure

```
momentum-v2/
├── app.py                          # Main Streamlit dashboard
├── live_scanner.py                 # Real-time market scanner
├── backtest_dynamic_universe.py    # Backtesting engine
├── manage_universe.py              # Ticker management
├── bugatti_optuna.py               # Optuna optimization
├── debug_convergence.py            # Signal validation
│
├── config/
│   ├── production_config.json      # Single source of truth (3-tier)
│   ├── advanced_engine_modes.py    # Dual mode configuration
│   ├── validated_production_params.json  # Validated parameters
│   ├── defaults.py                 # Fallback defaults
│   └── feature_flags.py            # Feature enablement
│
├── src/
│   ├── strategies/
│   │   └── triad_protocol.py       # Entry logic (3 Caminos)
│   ├── backtest/
│   │   ├── vectorbt_engine_advanced.py
│   │   ├── numba_core.py           # Numba-optimized loops
│   │   └── optimization_engine_*.py
│   ├── analytics/
│   │   └── quantstats_analyzer.py  # Performance analytics
│   ├── data/
│   │   ├── market_data.py
│   │   ├── ticker_cache.py
│   │   └── openbb_data.py
│   ├── filters/                    # Market/ticker filters
│   ├── indicators/                 # Technical indicators
│   ├── risk/                       # Risk management
│   └── optimization/               # Parameter optimization
│
├── data/
│   ├── cache/                      # Historical data cache
│   └── universe/                   # Ticker lists (JSON)
│
├── outputs/
│   ├── backtests/                  # Backtest results (CSV)
│   ├── logs/                       # Execution logs
│   └── walk_forward_v6_pro_optuna/ # Optimization results
│
└── docs/
    ├── guides/                     # Detailed guides
    └── archive/                    # Historical notes
```

---

## Configuration System

### 3-Tier Parameter Architecture

All parameters are centralized in `config/production_config.json`:

```json
{
  "tier1_strategy": {
    "tp1_r": 1.5,              // Take Profit 1 (R-multiple)
    "tp2_r": 4.75,             // Take Profit 2 (R-multiple)
    "tp1_pct": 0.45,           // % shares at TP1
    "tp2_pct": 0.4,            // % shares at TP2
    "runner_pct": 0.15,        // % runner shares
    "signal_type": "any"       // VCP, Breakout, ATH
  },
  "tier2_filters": {
    "min_rvol": 0.94,          // Minimum relative volume
    "min_adr": 1.38,           // Minimum average daily range
    "max_dist_sma20": 3.0,     // Max distance from SMA20
    "min_consolidation_days": 5
  },
  "tier3_risk": {
    "rvol_danger": 3.0,        // RVOL danger threshold
    "max_exposure_pct": 0.65,  // Max portfolio exposure
    "max_position_pct": 0.25,  // Max single position
    "earnings_days": 5         // Avoid earnings
  },
  "market_regime": {
    "require_spy_above_sma50": true,
    "max_vix": 35.0
  }
}
```

### Using Centralized Config

```python
from config.advanced_engine_modes import get_engine_kwargs

# Get production configuration (loads validated params automatically)
kwargs = get_engine_kwargs('production', tickers, start, end)
engine = AdvancedVectorBTEngine(**kwargs)

# Get convergence configuration (fixed risk, baseline filters)
kwargs = get_engine_kwargs('convergence', tickers, start, end)
engine = AdvancedVectorBTEngine(**kwargs)
```

---

## Development Conventions

### Language & Style

- **Bilingual codebase**: Comments/docstrings mix English and Spanish
  - Public API docstrings: English
  - Inline comments: Often Spanish
- **Absolute imports** from project root: `from src.data.market_data import ...`
- **Type hints** on all function signatures
- **Dataclasses** for structured data (`Signal`, `Camino`, etc.)
- **f-strings** for string formatting
- **pathlib.Path** everywhere (no `os.path`)

### Naming Conventions

| Element | Convention | Examples |
|---------|------------|----------|
| Classes | `PascalCase` | `TriadScanner`, `RiskManager` |
| Functions | `snake_case` | `scan_symbol()`, `calculate_position_size()` |
| Variables | `snake_case` | `base_high`, `avwap_price` |
| Constants | `UPPER_SNAKE_CASE` | `CACHE_DIR`, `MARKET_INDICES` |
| Private | `_underscore_prefix` | `_init_db()`, `_cached_config` |

### Error Handling

```python
# Guard clauses with early returns
if df is None or len(df) == 0:
    return

# Try/except with logging
try:
    result = process(symbol)
except Exception as e:
    logger.error(f"Error scanning {symbol}: {e}", exc_info=True)
    return {'symbol': symbol, 'signal': None, 'error': str(e)}
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Emoji prefixes common
logger.info("✅ Loading data...")
logger.info("🔍 APPROVED: Signal detected")
logger.error("❌ REJECTED: Invalid setup")
```

### Performance-Critical Code

```python
from numba import njit

@njit(cache=True, fastmath=True)
def process_signals(prices, signals):
    # Numba-compiled hot loops
    # Accepts only NumPy arrays and primitives
    pass
```

---

## Testing Practices

### No Formal Test Framework

- The `tests/` directory is empty
- Test-like scripts (`test_*.py`) are ad-hoc verification scripts
- Run full backtesting pipelines for validation

```bash
# Run verification scripts
python3 test_validation_framework.py
python3 test_exit_logic_fix.py

# If pytest installed
pytest test_validation_framework.py -v
```

### Convergence Testing

```bash
# Quick convergence test
python3 debug_convergence.py --tickers AAPL,MSFT --start 2023-01-01 --end 2023-12-31

# Full universe test
python3 debug_convergence.py --tickers spy --start 2023-01-01 --end 2023-12-31
```

**Success Criteria**:
- Entry signals match THOR within 15% tolerance
- Trade counts within 15% margin

---

## Linting & Formatting

Ruff is used with default settings:

```bash
ruff check .               # Lint
ruff check --fix .         # Lint with auto-fix
ruff format .              # Format
ruff format --check .      # Check formatting
```

---

## Key Concepts

### Triad Protocol - 3 Caminos (Entry Paths)

1. **Camino 1 (Blue Sky)**: Historical breakout or clear base with no nearby resistance. Requires **RVOL > 1.5x**.
2. **Camino 2 (VWAP Reclaim)**: Recovery of intraday VWAP after a flush.
3. **Camino 3 (Safety)**: Conservative entries waiting for AVWAP confirmation.

### Market Health Filters

The system does NOT trade if:
- SPY is below SMA20 (bearish trend)
- VIX > 25 (high volatility)

### Position Sizing

- **Convergence Mode**: Fixed $150 risk per trade
- **Production Mode**: 1.5% risk with compounding
- **RVOL-based adjustment**: Reduce size if RVOL > 2.0 (warning) or > 3.0 (danger)

### Exit Logic

Multi-phase exits (optimized via Optuna):
- **TP1**: 45% of position at 1.5R
- **TP2**: 40% of position at 4.75R
- **Runner**: 15% trailing (no cap)

---

## Important Files Reference

| File | Purpose |
|------|---------|
| `app.py` | Streamlit dashboard (Trade Log, QuantStats, Charts) |
| `config/production_config.json` | Single source of truth for all parameters |
| `config/advanced_engine_modes.py` | Dual mode configuration |
| `src/strategies/triad_protocol.py` | Entry logic (3 Caminos) |
| `src/backtest/numba_core.py` | Numba-optimized simulation loops |
| `src/analytics/quantstats_analyzer.py` | Performance analytics |
| `docs/guides/` | Detailed guides (Backtesting, Live Trading, Filters) |
| `INDICE_DOCUMENTACION.md` | Complete documentation index |
| `AGENTS.md` | Development guidelines for AI agents |

---

## Recent Changes (2026-03-05)

### Trade Log Score Column

The `entry_score` column is now displayed in both "Complete Trades" and "All Partial Exits" views in the Streamlit Trade Log tab. Each trade row shows its corresponding entry score as a column instead of just being a filter option.

**Modified**: `app.py` - Trade Log tab (lines ~1411-1446)

---

## Troubleshooting

### Convergence Check Fails
- Check `config/advanced_engine_modes.py` convergence config
- Verify `mode="convergence"` triggers baseline filters
- Refresh data cache if needed

### Production Metrics Look Wrong
- Confirm `--mode production` is set
- Check if validated params loaded (console output)
- Verify risk_pct (should be ~1.5%, not $150)

### No Data/Cache Issues
```bash
# Quick cache population
python3 quick_populate_cache.py

# Full historical download
python3 populate_historical_cache.py

# Inspect cache status
python3 inspect_cache.py
```

---

## Documentation

Start here (recommended order):
1. `INDICE_DOCUMENTACION.md` - Complete documentation index
2. `DUAL_MODE_ARCHITECTURE.md` - Understanding convergence vs production
3. `docs/guides/BACKTESTING.md` - Backtesting guide
4. `docs/guides/LIVE_TRADING.md` - Live trading protocol
5. `AGENTS.md` - Development guidelines
