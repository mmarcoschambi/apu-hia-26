import json
from pathlib import Path
from typing import Dict, Any

CONFIG_PATH = Path("config/production_config.json")

def load_production_config() -> Dict[str, Any]:
    """
    Loads config/production_config.json and performs strict schema validation.
    Raises FileNotFoundError if missing, or KeyError if required sections/keys are absent.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing production configuration at: {CONFIG_PATH}")
    
    with open(CONFIG_PATH, "r") as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format in production_config.json: {e}")
            
    # Schema validation
    required_sections = ["tier1_strategy", "tier2_filters", "tier3_risk", "market_regime", "risk_gate", "ml_entry_filter"]
    for section in required_sections:
        if section not in config:
            raise KeyError(f"Schema validation failed: Missing required section '{section}' in production_config.json")
            
    # Key validation inside sections
    required_keys = {
        "tier1_strategy": ["tp1_r", "tp2_r", "tp1_pct", "tp2_pct", "runner_pct", "max_stop_pct", "risk_dollars"],
        "tier2_filters": ["min_rvol", "min_adr", "max_dist_sma20", "min_volume", "min_dollar_volume"],
        "market_regime": ["max_vix", "require_spy_above_sma50"],
        "risk_gate": ["capital_total_usd", "risk_per_trade_usd", "max_allowed_stop_pct"],
        "ml_entry_filter": ["enabled", "threshold", "model_path"]
    }
    
    for section, keys in required_keys.items():
        for key in keys:
            if key not in config[section]:
                raise KeyError(f"Schema validation failed: Section '{section}' is missing key '{key}' in production_config.json")
                
    return config
