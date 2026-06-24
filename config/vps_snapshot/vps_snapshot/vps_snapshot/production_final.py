"""
PRODUCTION PARAMETERS - FINAL
==============================

Validated via Walk Forward Analysis (15 windows)
Two configurations for different use cases.

Generated: 2025-01-26
"""

# =============================================================================
# SCANNER MODE - Para universos grandes (20+ tickers)
# =============================================================================
# Basado en Trial #29 (Sharpe: 1.14, OOS: 3.78)
# Optimizado para máximo Sharpe con suficientes setups

SCANNER_PARAMS = {
    # Core Filters (más permisivos para capturar setups)
    "min_rvol": 1.5,
    "min_adr": 2.0,
    "risk_dollars": 100,
    "max_dist_sma20": 10.0,
    
    # Exits (TP1 más rápido)
    "tp1_r": 1.25,
    "tp2_r": 3.0,
    "max_stop_pct": 7.0,
    
    # Consolidation
    "min_consolidation_days": 10,
    
    # Liquidity
    "min_volume": 300000,
    "min_dollar_volume": 5000000,
    
    # Position Sizing
    "rvol_warning": 2.0,
    "rvol_danger": 3.0,
    "rvol_warning_size": 65,
    "rvol_danger_size": 30,
    
    # Features
    "require_spy_above_sma50": True,
    "use_adaptive_filtering": False,
    "use_earnings_calendar": False,
    "use_trailing_stop": False,
    "use_dynamic_thresholds": False,
    "use_market_regime_filter": False,
    "require_positive_rs": False,
    "use_rs_percentile": False,
    "use_sma50_atr_filter": False,
}

# Expected Performance (universo 50+ tickers):
#   Sharpe: 0.8 - 1.2
#   Win Rate: 70-80%
#   Trades: 30-50/year
#   Max DD: < 5%

# =============================================================================
# WATCHLIST MODE - Para universos pequeños (5-10 tickers)
# =============================================================================
# Basado en Walk Forward Robust Analysis
# Optimizado para consistencia en diferentes ventanas

WATCHLIST_PARAMS = {
    # Core Filters (más conservadores para mejor consistencia)
    "min_rvol": 2.0,
    "min_adr": 2.75,
    "risk_dollars": 200,
    "max_dist_sma20": 12.0,
    
    # Exits (TP1 más espaciado)
    "tp1_r": 1.75,
    "tp2_r": 3.0,
    "max_stop_pct": 7.0,
    
    # Consolidation
    "min_consolidation_days": 10,
    
    # Liquidity
    "min_volume": 300000,
    "min_dollar_volume": 5000000,
    
    # Position Sizing
    "rvol_warning": 2.0,
    "rvol_danger": 3.0,
    "rvol_warning_size": 65,
    "rvol_danger_size": 30,
    
    # Features
    "require_spy_above_sma50": True,
    "use_adaptive_filtering": False,
    "use_earnings_calendar": False,
    "use_trailing_stop": False,
    "use_dynamic_thresholds": False,
    "use_market_regime_filter": False,
    "require_positive_rs": False,
    "use_rs_percentile": False,
    "use_sma50_atr_filter": False,
}

# Expected Performance (universo 5-10 tickers):
#   Sharpe: 0.4 - 0.8
#   Win Rate: 70-75%
#   Trades: 10-20/year
#   Max DD: < 3%

# =============================================================================
# THOR COMPATIBILITY
# =============================================================================
# Para uso con THOR engine (usa formato float para position sizing)

SCANNER_PARAMS_THOR = SCANNER_PARAMS.copy()
SCANNER_PARAMS_THOR.update({
    "rvol_warning_size": 0.65,
    "rvol_danger_size": 0.30,
})

WATCHLIST_PARAMS_THOR = WATCHLIST_PARAMS.copy()
WATCHLIST_PARAMS_THOR.update({
    "rvol_warning_size": 0.65,
    "rvol_danger_size": 0.30,
})

# =============================================================================
# USAGE EXAMPLES
# =============================================================================

"""
# In app.py:
from config.production_final import SCANNER_PARAMS, WATCHLIST_PARAMS

# Auto-detect based on universe size
if len(universe) >= 20:
    default_params = SCANNER_PARAMS
else:
    default_params = WATCHLIST_PARAMS

# In bugatti_bolide_X.py:
from config.production_final import SCANNER_PARAMS_THOR

engine = OptimizationEngineTHOR(**SCANNER_PARAMS_THOR)
"""

# =============================================================================
# METADATA
# =============================================================================

METADATA = {
    "generated_date": "2025-01-26",
    "walk_forward_windows": 15,
    "base_universe": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN"],
    "validation_period": "2020-01-01 to 2024-06-30",
    
    "scanner_basis": "Trial #29 optimization",
    "scanner_sharpe": 1.14,
    "scanner_oos_sharpe": 3.78,
    
    "watchlist_basis": "Walk Forward robust analysis",
    "watchlist_robustness": 0.30,
    "watchlist_note": "More conservative, better for small universes",
}
