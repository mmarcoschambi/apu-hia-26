"""
Centralized Production Defaults
===============================
Lee valores directamente de production_config.json.
Si el JSON no existe o falta una key, usa fallbacks razonables.

USO:
    from config.defaults import get_tier1_defaults, get_tier2_defaults, get_tier3_defaults

    tier2 = get_tier2_defaults()
    min_rvol = tier2.get("min_rvol", 1.0)  # Siempre sincronizado con JSON
"""

import json
from pathlib import Path
from typing import Dict, Any, List

_CONFIG_PATH = Path(__file__).parent / "production_config.json"

# ──────────────────────────────────────────────────────────────────────────────
# TICKER BLACKLIST - Tickers temporalmente excluidos del backtest
# ──────────────────────────────────────────────────────────────────────────────
# Razones típicas: datos no disponibles en Yahoo Finance, errores de API,
# tickers deslistados, formato incompatible, etc.
#
# Para remover un ticker de la blacklist, bórralo de esta lista.
# Para agregar: añade el ticker en mayúsculas.
# ──────────────────────────────────────────────────────────────────────────────
TICKER_BLACKLIST = [
    "7974-T",  # Nintendo Tokyo - formato incompatible con Yahoo Finance (usar 7974.T)
]

# Fallback values if JSON is missing/corrupt
_FALLBACK_TIER1 = {
    "tp1_r": 1.75,
    "tp2_r": 4.5,
    "tp1_pct": 0.4,
    "tp2_pct": 0.45,
    "runner_pct": 0.15,
    "max_stop_pct": 0.08,
    "risk_dollars": 1000,
    # ATR-based Stop System
    "use_atr_stop": False,  # Disabled by default (uses fixed %)
    "atr_stop_multiplier": 1.5,  # Entry stop = ATR × 1.5
    "atr_trailing_multiplier": 2.5,  # Trailing = highest - ATR × 2.5
}

_FALLBACK_TIER2 = {
    "min_rvol": 0.91,
    "min_adr": 1.97,
    "max_dist_sma20": 8.94,
    "min_consolidation_days": 5,
    "min_volume": 100000,
    "min_dollar_volume": 20000000,
}

_FALLBACK_TIER3 = {
    "rvol_danger": 3.0,
    "rvol_warning": 2.0,
    "rvol_danger_size": 0.5,
    "rvol_warning_size": 0.75,
    "adr_high": 6.0,
    "adr_med": 5.0,
    "max_exposure_pct": 0.65,
    "max_position_pct": 0.25,
}

_FALLBACK_MARKET_REGIME = {
    "require_spy_above_sma50": True,
    "max_vix": 35.0,
    "use_market_regime_filter": True,
    "block_trades_in_stage3": True,
    "block_trades_in_stage4": True,
}

_cached_config = None


def _load_config() -> Dict[str, Any]:
    """Load and cache the production config JSON."""
    global _cached_config

    if _cached_config is not None:
        return _cached_config

    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r") as f:
                _cached_config = json.load(f)
                return _cached_config
        except Exception:
            pass

    return {}


def reload_config():
    """Force reload of config (call after optimization)."""
    global _cached_config
    _cached_config = None
    return _load_config()


def get_tier1_defaults() -> Dict[str, Any]:
    """Get TIER 1 (Strategy) defaults from production config."""
    config = _load_config()
    tier1 = config.get("tier1_strategy", {})
    return {**_FALLBACK_TIER1, **tier1}


def get_tier2_defaults() -> Dict[str, Any]:
    """Get TIER 2 (Filters) defaults from production config."""
    config = _load_config()
    tier2 = config.get("tier2_filters", {})
    return {**_FALLBACK_TIER2, **tier2}


def get_tier3_defaults() -> Dict[str, Any]:
    """Get TIER 3 (Risk) defaults from production config."""
    config = _load_config()
    tier3 = config.get("tier3_risk", {})
    return {**_FALLBACK_TIER3, **tier3}


def get_market_regime_defaults() -> Dict[str, Any]:
    """Get Market Regime defaults from production config."""
    config = _load_config()
    mr = config.get("market_regime", {})
    return {**_FALLBACK_MARKET_REGIME, **mr}


def get_all_defaults() -> Dict[str, Dict[str, Any]]:
    """Get all defaults in one call."""
    return {
        "tier1": get_tier1_defaults(),
        "tier2": get_tier2_defaults(),
        "tier3": get_tier3_defaults(),
        "market_regime": get_market_regime_defaults(),
    }


def get_ticker_blacklist() -> List[str]:
    """
    Get list of tickers to exclude from backtesting.

    These tickers are temporarily blocked due to data issues, API errors,
    or format incompatibilities. To restore a ticker, remove it from
    TICKER_BLACKLIST above.

    Returns:
        List of ticker symbols in uppercase
    """
    return TICKER_BLACKLIST.copy()


def filter_blacklisted_tickers(tickers: List[str]) -> List[str]:
    """
    Remove blacklisted tickers from a list.

    Args:
        tickers: List of ticker symbols

    Returns:
        Filtered list with blacklisted tickers removed
    """
    blacklist = set(get_ticker_blacklist())
    return [t for t in tickers if t.upper() not in blacklist]
