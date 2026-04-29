# AGENTS.md - Momentum Trading V2 (Triad Protocol)

## Project Overview

Python-based institutional momentum breakout trading system implementing the "Triad Protocol"
(Base + AVWAP + VWAP). Core components: Streamlit dashboard, backtesting engines, live scanner,
and Optuna-based parameter optimization. No formal build system -- scripts run directly with Python.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install vectorbt numba openbb scipy  # Additional dependencies

# Run applications
streamlit run app.py              # Main dashboard
python3 live_scanner.py           # Real-time scanner
python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
python3 bugatti_optuna.py         # Parameter optimization
python3 morning_workflow.py       # Pre-market workflow

# Linting & formatting
ruff check .               # Lint
ruff check --fix .         # Lint with auto-fix
ruff format .              # Format
ruff format --check .      # Check formatting only
```

## Testing

No formal test framework (pytest not in requirements.txt). The `tests/` directory is empty.

```bash
python3 test_validation_framework.py     # Run specific test
python3 test_exit_logic_fix.py
pytest test_validation_framework.py -v   # If pytest installed
```

When writing validation scripts: standalone scripts that import from `src/` and `config/`,
run a specific scenario, and print/log results.

## Code Style

### Language
- Python 3 with modern features: dataclasses, typing, f-strings, pathlib, walrus operator
- **Bilingual codebase**: Comments mix English and Spanish. Both acceptable.

### Imports
- **Absolute imports** from project root:
  ```python
  from src.data.market_data import MarketDataProvider
  from config.settings import CACHE_DIR
  ```
- **sys.path manipulation** in standalone scripts:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  ```
- **Import order**: standard library → third-party → project (PEP 8)

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `TriadScanner`, `RiskManager` |
| Functions/methods | snake_case | `scan_symbol()` |
| Variables | snake_case | `base_high`, `avwap_price` |
| Constants | UPPER_SNAKE_CASE | `CACHE_DIR` |
| Private members | `_underscore_prefix` | `_init_db()` |
| Enum members | UPPER_SNAKE_CASE | `Camino.BLUE_SKY` |
| Dataclass fields | snake_case | `entry_price` |

### Type Annotations
Use type hints on all function signatures. Use `@dataclass` for structured data.
No Pydantic or runtime type validation.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Signal:
    camino: Optional[Camino]
    action: str
    entry_price: Optional[float]
    stop_loss: Optional[float] = None
```

### Error Handling
- **try/except with logging** -- catch broad `Exception`, log with `exc_info=True`,
  return dict instead of re-raising:
  ```python
  try:
      result = process(symbol)
  except Exception as e:
      logger.error(f"Error: {symbol} -> {e}", exc_info=True)
      return {'symbol': symbol, 'signal': None, 'error': str(e)}
  ```
- **Guard clauses** for early returns on invalid input
- **Graceful degradation** with silent fallbacks to defaults

### Logging
```python
import logging
logger = logging.getLogger(__name__)
```
Emoji prefixes common: `"✅ APPROVED..."`, `"🚫 REJECTED..."`, `"Loading..."`

### Docstrings
- Every module starts with a module-level docstring
- Method docstrings use Google-style with `Args:` and `Returns:` sections

### File & Path Handling
- Use `pathlib.Path` everywhere, never `os.path`
- Project root: `BASE_DIR = Path(__file__).resolve().parent.parent`

## Active Agents Status (April 2026)

| Agent Name | Strategy | Status | Notes |
|------------|----------|--------|-------|
| `combo_pure_momentum` | Momentum | **ACTIVE** | Core high-frequency agent. |
| `combo_stage2_breakout` | Breakout | **ACTIVE** | Classic Stage 2 confirmation. |
| `combo_pullback_entry` | Pullback | **ACTIVE** | Mean reversion in uptrend. |
| `combo_ideal_setup` | Multi-Factor | **ACTIVE** | High precision, medium volume. |
| `triad_rts` | Institutional | **RANKING ONLY** | Discarded as execution trigger due to extreme selectivity (<50 trades/yr). Use only for quality filtering. |

## Configuration Architecture
- **Single source of truth**: `config/production_config.json`
- **Python fallback defaults**: `config/defaults.py`
- **Feature flags**: `config/feature_flags.py`
- **Tiered parameters**: Tier 1 (Strategy), Tier 2 (Filters), Tier 3 (Risk)
- Never hardcode parameter values -- always read from config

### Performance Patterns
- Use `@njit(cache=True, fastmath=True)` from Numba for hot simulation loops
- Numba functions in `src/backtest/numba_core.py` -- accept only NumPy arrays and scalars
- Use `@st.cache_data` for expensive Streamlit computations

### Quick Reference
- `@staticmethod` for stateless utility methods
- `Enum` for categorical values (e.g., `Camino`)
- f-strings for string formatting
- Line length: ~100-120 characters (not strictly enforced)
- No CI/CD, Docker, or GitHub Actions configured
