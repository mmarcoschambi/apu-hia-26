"""
Dynamic Configuration Loader
============================

Carga configuración desde JSON sin hardcodear valores.
Única fuente de verdad: config/production_config.json
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

# Default config path
CONFIG_PATH = Path("config/production_config.json")


from src.config.config_loader import load_production_config as _canonical_load

def load_production_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load production configuration from JSON file.

    Args:
        config_file: Path to config file. If None, uses default.

    Returns:
        Dict with all configuration parameters organized by tiers
    """
    return _canonical_load(config_file)


def flatten_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested config structure into a single dict.
    This is useful for passing to engines that expect flat params.

    Priority: tier1_strategy > tier2_filters > tier3_risk > market_regime

    UNIT CONVERSION: The config stores values in canonical decimal form
    (e.g. rvol_danger_size=0.3 means 30%), but the engine constructors
    expect certain params as integers/percentages and divide by 100 internally.
    This function converts to match engine expectations:
      - rvol_danger_size: 0.3 -> 30 (engine divides by 100 -> 0.30)
      - rvol_warning_size: 0.65 -> 65 (engine divides by 100 -> 0.65)
      - max_stop_pct: 0.04 -> 4.0 (engine divides by 100 -> 0.04)
      - earnings_cushion: 2 -> 2 (no change, engine divides by 100 -> 0.02)
    """
    flat = {}

    # Add all params from each tier
    # Support alias: tier2_quality -> tier2_filters (some optimization scripts use different key)
    tier_keys = {
        "tier1_strategy": ["tier1_strategy"],
        "tier2_filters": ["tier2_filters", "tier2_quality"],
        "tier3_risk": ["tier3_risk"],
        "market_regime": ["market_regime"],
    }
    for tier, aliases in tier_keys.items():
        for alias in aliases:
            if alias in config:
                tier_params = {
                    k: v for k, v in config[alias].items() if not k.startswith("_")
                }
                flat.update(tier_params)
                break

    # ============================================================
    # UNIT CONVERSION: Config (decimal) -> Engine (pct/integer)
    # The engine constructors divide these by 100 internally,
    # so we must pass them as percentages/integers.
    # ============================================================

    # RVOL size adjustments: config stores decimal (0.3 = 30%),
    # engine expects integer (30) and does /100
    for key in ["rvol_danger_size", "rvol_warning_size"]:
        if key in flat and flat[key] <= 1.0:
            flat[key] = int(round(flat[key] * 100))

    # max_stop_pct: config stores decimal (0.04 = 4%),
    # engine expects percentage (4.0) and does /100
    if "max_stop_pct" in flat and flat["max_stop_pct"] < 1.0:
        flat["max_stop_pct"] = flat["max_stop_pct"] * 100

    return flat


def get_tier_params(config: Dict[str, Any], tier: str) -> Dict[str, Any]:
    """
    Get parameters for a specific tier only.

    Args:
        config: Full config dict
        tier: One of 'tier1_strategy', 'tier2_filters', 'tier3_risk', 'market_regime'

    Returns:
        Dict with tier-specific parameters (excluding metadata)
    """
    # Support alias: tier2_quality -> tier2_filters
    aliases = {"tier2_filters": ["tier2_filters", "tier2_quality"]}
    keys_to_try = aliases.get(tier, [tier])

    for key in keys_to_try:
        if key in config:
            return {k: v for k, v in config[key].items() if not k.startswith("_")}

    return {}


def update_production_config(
    updates: Dict[str, Any], config_file: Optional[str] = None
) -> None:
    """
    Update production config with new parameters.

    Args:
        updates: Dict with parameter updates (can be nested by tier)
        config_file: Path to config file
    """
    path = Path(config_file) if config_file else CONFIG_PATH

    # Load existing config
    config = load_production_config(str(path))

    # Deep update
    def deep_update(original: Dict, updates: Dict):
        for key, value in updates.items():
            if (
                key in original
                and isinstance(original[key], dict)
                and isinstance(value, dict)
            ):
                deep_update(original[key], value)
            else:
                original[key] = value

    deep_update(config, updates)

    # Save back
    with open(path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Config updated: {path}")


def get_engine_params(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get flat parameters ready to pass to any engine.

    This is the main function to use when initializing engines.
    """
    config = load_production_config(config_file)
    return flatten_config(config)


# Backwards compatibility with validated_production_params.json
def migrate_from_validated(
    validated_file: str = "config/validated_production_params.json",
    output_file: str = "config/production_config.json",
) -> None:
    """
    Migrate old format (validated_production_params.json) to new modular format.
    """
    with open(validated_file, "r") as f:
        old = json.load(f)

    params = old.get("parameters", {})
    perf = old.get("performance", {})

    new_config = {
        "_schema_version": "2.0",
        "_description": "Migrated from validated_production_params.json",
        "_last_updated": old.get("validated_date", ""),
        "_optimization_method": old.get("source", "unknown"),
        "system": {
            "name": "Bugatti Trading System",
            "version": "3.0",
            "mode": "production",
            "tier_system_enabled": True,
        },
        "tier1_strategy": {
            "tp1_r": params.get("tp1_r", 1.5),
            "tp2_r": params.get("tp2_r", 3.0),
            "tp1_pct": params.get("tp1_pct", 0.5),
            "tp2_pct": params.get("tp2_pct", 0.3),
            "runner_pct": params.get("runner_pct", 0.2),
            "max_stop_pct": params.get("max_stop_pct", 0.04),
            "risk_dollars": params.get("risk_dollars", 250),
            "use_phases": params.get("use_phases", True),
            "signal_type": params.get("signal_type", "any"),
            "_sharpe_validation": perf.get("sharpe_ratio", 0),
        },
        "tier2_filters": {
            "min_rvol": params.get("min_rvol", 1.5),
            "min_adr": params.get("min_adr", 2.0),
            "max_dist_sma20": params.get("max_dist_sma20", 10.0),
            "min_consolidation_days": params.get("min_consolidation_days", 10),
            "min_volume": params.get("min_volume", 200000),
            "min_dollar_volume": params.get("min_dollar_volume", 2000000),
            "require_sector_strength": params.get("require_sector_strength", False),
            "sector_top_percentile": params.get("sector_top_percentile", 0.5),
        },
        "tier3_risk": {
            "rvol_danger": params.get("rvol_danger", 3.0),
            "rvol_warning": params.get("rvol_warning", 2.0),
            "rvol_danger_size": params.get("rvol_danger_size", 0.30),
            "rvol_warning_size": params.get("rvol_warning_size", 0.65),
            "adr_high": params.get("adr_high", 6.0),
            "adr_med": params.get("adr_med", 5.0),
            "max_exposure_pct": params.get("max_exposure_pct", 0.35),
            "max_position_pct": params.get("max_position_pct", 0.25),
        },
        "market_regime": {
            "require_spy_above_sma50": params.get("require_spy_above_sma50", False),
            "max_vix": params.get("max_vix", 40.0),
        },
        "performance": {
            "sharpe_ratio": perf.get("sharpe_ratio", 0),
            "win_rate_pct": perf.get("win_rate_pct", 0),
            "total_trades": perf.get("total_trades", 0),
            "max_drawdown_pct": perf.get("max_drawdown_pct", 0),
        },
    }

    with open(output_file, "w") as f:
        json.dump(new_config, f, indent=2)

    print(f"✅ Migrated config to: {output_file}")


if __name__ == "__main__":
    # Test loading
    print("Testing config loader...")
    config = load_production_config()
    flat = flatten_config(config)
    print(f"\nLoaded {len(flat)} parameters")
    print(f"\nSample params:")
    print(f"  tp1_r: {flat.get('tp1_r')}")
    print(f"  tp1_pct: {flat.get('tp1_pct')}")
    print(f"  min_rvol: {flat.get('min_rvol')}")
    print(f"  rvol_danger: {flat.get('rvol_danger')}")
