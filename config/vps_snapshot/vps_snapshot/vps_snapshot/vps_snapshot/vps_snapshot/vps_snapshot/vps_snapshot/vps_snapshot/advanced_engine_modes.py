"""
Centralized Mode Configuration for Advanced Engine
===================================================
Single source of truth for CONVERGENCE vs PRODUCTION mode parameters.

MODES:
- convergence: Fixed dollar risk ($150), THOR-compatible logic for signal validation
- production: Percentage risk with compounding for realistic P&L simulation
- optimization: Production mode with extended search spaces for parameter tuning
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# MODE CONFIGURATIONS
# ============================================================================


def get_convergence_config() -> Dict[str, Any]:
    """
    CONVERGENCE MODE: Signal validation vs THOR
    -------------------------------------------
    Goal: Ensure Advanced Engine produces identical signals to legacy THOR engine.

    Features:
    - Fixed dollar risk ($150)
    - No compounding
    - Baseline filters only (Liquid + Momentum)
    - Conservative entry logic

    Use case: Debugging, logic verification, regression testing
    """
    return {
        "mode": "convergence",
        "risk_dollars": 150.0,
        "use_fixed_dollar_risk": True,
        "risk_pct": 0.0,  # Ignored in convergence mode
        # Baseline filters (THOR-compatible)
        "use_market_regime_filter": False,
        "use_composite_sector_scoring": False,
        "use_adaptive_filtering": False,
        "use_rs_percentile": False,
        "use_sma50_atr_filter": False,
        "use_trailing_stop": False,
        "use_earnings_calendar": False,
        # Conservative thresholds
        "min_rvol": 1.0,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "max_stop_pct": 3.0,
        "min_dollar_volume": 5_000_000,
        "min_consolidation_days": 10,
        # Entry logic
        "signal_type": "breakout",
        "require_positive_rs": False,
        # Standard TP distribution
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34,
    }


def get_production_config(load_validated_params: bool = True) -> Dict[str, Any]:
    """
    PRODUCTION MODE: Realistic performance simulation
    -------------------------------------------------
    Goal: Maximize risk-adjusted returns with real-world compounding.

    Features:
    - Percentage risk (default 1.5%, configurable)
    - Compounding enabled
    - Full professional filter suite
    - Market regime awareness
    - Validated parameters (if available)

    Use case: Backtesting, live trading, performance reporting

    Args:
        load_validated_params: If True, load parameters from validated_production_params.json

    Returns:
        Configuration dict with production parameters
    """
    config = {
        "mode": "production",
        "risk_pct": 0.015,  # 1.5% default (overridden by validated params if available)
        "use_fixed_dollar_risk": False,
        "risk_dollars": None,
        # Professional filter suite
        "use_market_regime_filter": True,
        "use_composite_sector_scoring": False,  # Set True for sector rotation
        "use_adaptive_filtering": False,  # Set True for tiered filtering
        "use_rs_percentile": False,  # Set True for IBD-style RS
        "use_sma50_atr_filter": False,  # Set True for extension filter
        "use_trailing_stop": True,  # ENABLED: Move to breakeven after TP1 hit
        "use_earnings_calendar": False,  # Validated: Disabled
        # Market regime filters (professional)
        "require_spy_above_sma50": True,
        "max_vix_threshold": 35.0,
        "block_trades_in_stage3": True,
        "block_trades_in_stage4": False,  # RELAXED: Allow longs in Stage 4 oversold
        "adjust_risk_by_regime": True,
        "use_dynamic_thresholds": False,
        # Validated thresholds (conservative)
        "min_rvol": 1.0,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "max_stop_pct": 3.0,
        "min_dollar_volume": 5_000_000,
        "min_consolidation_days": 10,
        "max_exposure_pct": 0.35,
        # Entry logic
        "signal_type": "breakout",
        "require_positive_rs": False,
        # Target multiples (validated)
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34,
    }

    # Load validated parameters if available
    if load_validated_params:
        validated_params = _load_validated_params()
        if validated_params:
            config.update(validated_params)
            logger.info("✅ Loaded validated production parameters")

    return config


def get_optimization_config() -> Dict[str, Any]:
    """
    OPTIMIZATION MODE: Production mode with extended search spaces
    ---------------------------------------------------------------
    Goal: Find optimal parameters through systematic search (Optuna, walk-forward, etc.)

    Features:
    - Same as production mode
    - Wider parameter ranges for exploration
    - Can enable experimental filters

    Use case: Parameter optimization, strategy development
    """
    config = get_production_config(load_validated_params=False)  # Start from production
    config["mode"] = "optimization"

    # Allow wider exploration
    config["max_exposure_pct"] = 0.50  # Allow up to 50% exposure in optimization

    return config


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _load_validated_params() -> Optional[Dict[str, Any]]:
    """
    Load validated production parameters from config/validated_production_params.json

    Returns:
        Dict with validated parameters or None if not found
    """
    config_path = Path("config/validated_production_params.json")

    if not config_path.exists():
        logger.warning(
            "⚠️  No validated parameters found at config/validated_production_params.json"
        )
        return None

    try:
        with open(config_path, "r") as f:
            data = json.load(f)

        params = data.get("parameters", {})

        # Extract relevant parameters
        validated = {}

        # Risk parameters
        if "risk_pct" in params:
            validated["risk_pct"] = params["risk_pct"]
        if "risk_dollars" in params:
            validated["risk_dollars"] = params["risk_dollars"]

        # Filter thresholds
        for key in [
            "min_rvol",
            "min_adr",
            "max_dist_sma20",
            "max_stop_pct",
            "min_dollar_volume",
            "min_consolidation_days",
            "max_exposure_pct",
            "max_consolidation_range",
            "min_volume",
        ]:
            if key in params:
                validated[key] = params[key]

        # TP parameters
        for key in [
            "tp1_r",
            "tp2_r",
            "tp1_pct",
            "tp2_pct",
            "runner_pct",
            "signal_type",
            "use_phases",
        ]:
            if key in params:
                validated[key] = params[key]

        # Tier 3 risk management parameters
        for key in [
            "rvol_danger",
            "rvol_warning",
            "rvol_danger_size",
            "rvol_warning_size",
            "adr_high",
            "adr_med",
            "max_position_pct",
        ]:
            if key in params:
                validated[key] = params[key]

        # Market regime parameters
        for key in [
            "require_spy_above_sma50",
            "max_vix",
            "use_market_regime_filter",
            "use_dynamic_thresholds",
        ]:
            if key in params:
                validated[key] = params[key]

        # Feature flags
        for key in [
            "use_composite_sector_scoring",
            "use_adaptive_filtering",
            "use_rs_percentile",
            "use_trailing_stop",
            "use_earnings_calendar",
            "require_sector_strength",
            "sector_top_percentile",
            "require_positive_rs",
        ]:
            if key in params:
                validated[key] = params[key]

        # ============================================================
        # UNIT CONVERSION: Config stores decimals (0.04 = 4%),
        # but AdvancedVectorBTEngine constructor expects integers
        # and divides by 100 internally (e.g., max_stop_pct / 100.0).
        # Must convert here to match engine expectations.
        # ============================================================

        # max_stop_pct: config 0.04 (4%) -> engine expects 4.0
        if "max_stop_pct" in validated:
            v = validated["max_stop_pct"]
            if v < 1.0:
                validated["max_stop_pct"] = v * 100.0
                logger.info(
                    f"   max_stop_pct: {v} -> {validated['max_stop_pct']} (converted for engine)"
                )

        # rvol_danger_size: config 0.3 (30%) -> engine expects 30
        if "rvol_danger_size" in validated:
            v = validated["rvol_danger_size"]
            if v <= 1.0:
                validated["rvol_danger_size"] = v * 100.0
                logger.info(
                    f"   rvol_danger_size: {v} -> {validated['rvol_danger_size']} (converted for engine)"
                )

        # rvol_warning_size: config 0.65 (65%) -> engine expects 65
        if "rvol_warning_size" in validated:
            v = validated["rvol_warning_size"]
            if v <= 1.0:
                validated["rvol_warning_size"] = v * 100.0
                logger.info(
                    f"   rvol_warning_size: {v} -> {validated['rvol_warning_size']} (converted for engine)"
                )

        logger.info(f"Validated parameters loaded: {len(validated)} parameters")
        logger.info(f"   Validated on: {data.get('validated_date', 'unknown')}")

        return validated

    except Exception as e:
        logger.error(f"❌ Error loading validated params: {e}")
        return None


def get_mode_config(mode: str = "production", **overrides) -> Dict[str, Any]:
    """
    Get configuration for specified mode with optional overrides.

    Args:
        mode: One of 'convergence', 'production', 'optimization'
        **overrides: Additional parameters to override defaults

    Returns:
        Complete configuration dict for the specified mode

    Example:
        >>> config = get_mode_config('production', risk_pct=0.02, max_exposure_pct=0.40)
    """
    if mode == "convergence":
        config = get_convergence_config()
    elif mode == "production":
        config = get_production_config()
    elif mode == "optimization":
        config = get_optimization_config()
    else:
        raise ValueError(
            f"Unknown mode: {mode}. Must be 'convergence', 'production', or 'optimization'"
        )

    # Apply overrides
    config.update(overrides)

    return config


def get_engine_kwargs(
    mode: str,
    universe: list,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000,
    **overrides,
) -> Dict[str, Any]:
    """
    Get complete kwargs for AdvancedVectorBTEngine instantiation.

    This is the main entry point for scripts that need to instantiate the engine.

    Args:
        mode: 'convergence', 'production', or 'optimization'
        universe: List of tickers to backtest
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_capital: Starting capital (default $100k)
        **overrides: Additional parameters to override mode defaults

    Returns:
        Complete kwargs dict ready for AdvancedVectorBTEngine(**kwargs)

    Example:
        >>> from config.advanced_engine_modes import get_engine_kwargs
        >>> kwargs = get_engine_kwargs('production', ['AAPL', 'MSFT'], '2023-01-01', '2023-12-31')
        >>> engine = AdvancedVectorBTEngine(**kwargs)
    """
    config = get_mode_config(mode, **overrides)

    # Add required runtime parameters
    config.update(
        {
            "universe": universe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
        }
    )

    return config


# ============================================================================
# MODE COMPARISON UTILITIES
# ============================================================================


def print_mode_comparison():
    """Print a comparison table of all modes (for documentation/debugging)"""
    convergence = get_convergence_config()
    production = get_production_config(load_validated_params=False)

    print("=" * 80)
    print("MODE COMPARISON: CONVERGENCE vs PRODUCTION")
    print("=" * 80)
    print()
    print(f"{'Parameter':<30} {'CONVERGENCE':<25} {'PRODUCTION':<25}")
    print("-" * 80)

    # Risk parameters
    print(f"{'Risk Type':<30} {'Fixed Dollar ($150)':<25} {'Percentage (1.5%)':<25}")
    print(f"{'Compounding':<30} {'❌ Disabled':<25} {'✅ Enabled':<25}")
    print()

    # Key differences
    key_params = [
        "use_market_regime_filter",
        "require_spy_above_sma50",
        "max_vix_threshold",
        "min_rvol",
        "min_adr",
        "max_dist_sma20",
        "signal_type",
    ]

    for param in key_params:
        conv_val = convergence.get(param, "N/A")
        prod_val = production.get(param, "N/A")
        print(f"{param:<30} {str(conv_val):<25} {str(prod_val):<25}")

    print("=" * 80)


if __name__ == "__main__":
    # Demo usage
    print_mode_comparison()

    print("\n")
    print("EXAMPLE USAGE:")
    print("-" * 80)
    print()
    print("# Get convergence config")
    print("from config.advanced_engine_modes import get_engine_kwargs")
    print(
        "kwargs = get_engine_kwargs('convergence', ['AAPL'], '2023-01-01', '2023-12-31')"
    )
    print()
    print("# Get production config with overrides")
    print(
        "kwargs = get_engine_kwargs('production', ['AAPL'], '2023-01-01', '2023-12-31',"
    )
    print("                          risk_pct=0.02, max_exposure_pct=0.40)")
