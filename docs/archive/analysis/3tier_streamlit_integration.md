# 3-Tier Optimization → Streamlit Integration

## Overview

The 3-tier optimization pipeline now automatically exports validated strategies to the Streamlit app configuration.

## How It Works

When a strategy **passes all ResearchGate validation phases**, the pipeline automatically:

1. **Backs up** existing `config/production_config.json` to `.json.bak`
2. **Converts** the 3-tier output to Streamlit format
3. **Exports** to `config/production_config.json`
4. **Appends** the run to optimization history

## Usage

### Automatic Export (Default)

```bash
python3 optimize_3tier.py --trials 300 --tickers 50 --keep-pct 60
```

If the strategy passes validation, it will be automatically exported and you'll see:

```
======================================================================
PHASE 5: AUTO-EXPORT TO STREAMLIT
======================================================================
  ✅ Backed up existing config to: config/production_config.json.bak
  ✅ Exported to: config/production_config.json
  📊 Strategy ready for Streamlit app testing
======================================================================

  🚀 Strategy exported to Streamlit app!
     Run: streamlit run app.py
```

### Manual Export (Skip Automatic)

```bash
python3 optimize_3tier.py --trials 300 --tickers 50 --skip-streamlit-export
```

Then manually export later:

```python
import json
from optimize_3tier import export_to_streamlit_config

with open('outputs/3tier_optimization/FINAL_CONFIG.json', 'r') as f:
    final_config = json.load(f)

export_to_streamlit_config(
    final_config=final_config,
    output_path='config/production_config.json',
    backup=True,
)
```

## Testing in Streamlit

After successful export:

```bash
streamlit run app.py
```

The app will automatically load the new parameters from `config/production_config.json`.

## What Gets Exported

### Tier 1 (Strategy Parameters)
- `tp1_r`, `tp2_r`: Take profit targets
- `tp1_pct`, `tp2_pct`, `runner_pct`: Position sizing distribution
- `risk_dollars`: Fixed dollar risk per trade

### Tier 2 (Quality Filters)
- `min_rvol`: Minimum relative volume
- `min_adr`: Minimum average daily range
- `max_dist_sma20`: Maximum distance from SMA20
- `min_consolidation_days`: Minimum consolidation period
- `min_volume`, `min_dollar_volume`: Liquidity filters

### Tier 3 (Risk Management)
- `rvol_danger`, `rvol_warning`: Volatility risk thresholds
- `rvol_danger_size`, `rvol_warning_size`: Position size adjustments
- `adr_high`, `adr_med`: ADR risk thresholds
- `max_exposure_pct`: Maximum portfolio exposure
- `earnings_days`, `earnings_cushion`: Earnings event filters

### Performance Metrics
- Sharpe ratio, win rate, max drawdown
- PBO score, bootstrap percentiles
- Total trades, total return

### Optimization History
- Appends current run to history array
- Tracks: date, method, trials, performance, approval status

## Validation Gates

The strategy must pass **all 3 ResearchGate phases** for export:

1. **Discovery**: Parameter structure and bounds
2. **Validation**: PBO, bootstrap, Sharpe, win rate, drawdown
3. **Productionization**: Stress tests on costs/spreads

If validation fails, you'll see:

```
  VALIDATION: REJECTED
    - PBO score too high (52.3% > 50%)
    - Bootstrap p10 below threshold (1.8% < 2.0%)
  
  ❌ Strategy NOT exported (failed validation)
```

## Safety Features

- **Automatic backup**: Old config saved before overwriting
- **Validation required**: Only approved strategies are exported
- **History tracking**: All runs logged with performance metrics
- **Unit conversion**: Automatic conversion between decimal/percentage formats

## Example Output

```json
{
  "_schema_version": "2.0",
  "_last_updated": "2026-02-11T21:51:08.837473",
  "_optimization_method": "3Tier_AdvancedVectorBT",
  "tier1_strategy": {
    "tp1_r": 1.25,
    "tp2_r": 6.0,
    "tp1_pct": 0.5,
    "tp2_pct": 0.25,
    "runner_pct": 0.25
  },
  "tier2_filters": {
    "min_rvol": 1.13,
    "min_adr": 2.65,
    "max_dist_sma20": 14.74
  },
  "performance": {
    "sharpe_ratio": 1.65,
    "win_rate_pct": 64.9,
    "max_drawdown_pct": 3.29,
    "pbo_score": 0.0
  }
}
```

## CLI Options

```
--skip-streamlit-export    Skip automatic export (for testing)
--skip-validation          Skip ResearchGate validation (dev mode)
--trials N                 Number of Optuna trials (default: 100)
--tickers N                Universe size (default: 50)
--keep-pct N               Tier 2 filter aggressiveness (default: 80)
```

## Troubleshooting

### Export Failed

```
❌ Failed to export to Streamlit: [error]
```

Check:
- `config/` directory exists
- Write permissions on `config/production_config.json`
- `outputs/3tier_optimization/FINAL_CONFIG.json` exists

### Config Not Loading in Streamlit

```python
# Test config loader
from src.config.dynamic_config import load_production_config, flatten_config

config = load_production_config()
flat = flatten_config(config)
print(flat)
```

### Restore Backup

```bash
cp config/production_config.json.bak config/production_config.json
```
