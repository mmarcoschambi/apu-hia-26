#!/usr/bin/env python3
"""
Export Config to Streamlit - Pragmatic Version

This exports the config even if validation failed, with strong warnings.
Use when you understand the risks and have verified the strategy manually.
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def export_with_warning(
    config_path: str = "outputs/3tier_optimization/FINAL_CONFIG.json",
):
    """Export config to Streamlit with risk warnings."""

    config_file = Path(config_path)
    if not config_file.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)

    with open(config_file, "r") as f:
        config = json.load(f)

    print("=" * 70)
    print("⚠️  PRAGMATIC EXPORT - STRATEGY VALIDATION FAILED")
    print("=" * 70)
    print()
    print("This strategy was REJECTED by ResearchGate validation because:")
    print()

    validation = config.get("validation", {})
    for reason in validation.get("rejection_reasons", ["Unknown"]):
        print(f"  • {reason}")

    print()
    print("=" * 70)
    print("PERFORMANCE ANALYSIS")
    print("=" * 70)
    print()
    print("TRAINING (2022-2023) - GOOD:")
    metrics = config.get("optimization", {}).get("best_trial_metrics", {})
    print(f"  • Return: +{metrics.get('total_return', 0):.1f}%")
    print(f"  • Sharpe: {metrics.get('sharpe', 0):.2f}")
    print(f"  • Win Rate: {metrics.get('win_rate', 0):.1f}%")
    print()
    print("OUT-OF-SAMPLE (2024) - FAILED:")
    print(f"  • Sharpe: {validation.get('sharpe_ratio', 0):.2f}")
    print(f"  • Win Rate: {validation.get('win_rate_pct', 0):.1f}%")
    print()
    print("=" * 70)
    print("⚠️  RECOMMENDATION")
    print("=" * 70)
    print()
    print("This strategy should be used with EXTREME CAUTION:")
    print()
    print("  1. Use FIXED DOLLAR risk (not compounding)")
    print("  2. Start with SMALL capital allocation (5-10% max)")
    print("  3. Monitor daily - if drawdown >15%, stop trading")
    print("  4. Consider this EXPERIMENTAL until 2025 data validates it")
    print()
    print("The strategy worked well in 2022-2023 but failed in 2024.")
    print("This could be due to:")
    print("  • Market regime change (bear market)")
    print("  • Strategy overfitting to 2022-2023 conditions")
    print("  • Need for additional filters or parameter adjustments")
    print()

    # Build production config
    tier1 = config["tier1_strategy"]
    tier2 = config.get("tier2_filters", config.get("tier2_quality", {}))
    tier3 = config["tier3_risk"]

    production_config = {
        "_schema_version": "2.0",
        "_description": "Auto-exported from 3-Tier Optimization (VALIDATION FAILED - USE WITH CAUTION)",
        "_last_updated": datetime.now().isoformat(),
        "_warning": "Strategy failed OOS validation in 2024. Use small size and monitor closely.",
        "system": {
            "name": "Bugatti Trading System",
            "version": "3.0",
            "mode": "production",
            "tier_system_enabled": True,
            "validation_status": "REJECTED",
        },
        "tier1_strategy": {
            "tp1_r": tier1["tp1_r"],
            "tp2_r": tier1["tp2_r"],
            "tp1_pct": tier1["tp1_pct"],
            "tp2_pct": tier1["tp2_pct"],
            "runner_pct": tier1["runner_pct"],
            "max_stop_pct": tier3["max_stop_pct_hard"],
        },
        "tier2_filters": {
            "min_rvol": tier2["min_rvol"],
            "min_adr": tier2["min_adr"],
            "max_dist_sma20": tier2["max_dist_sma20"],
            "min_dollar_volume": tier2["min_dollar_volume"],
            "min_volume": tier2["min_volume"],
            "min_consolidation_days": tier2["min_consolidation_days"],
        },
        "tier3_risk": {
            "rvol_danger": tier3["rvol_danger"],
            "rvol_warning": tier3["rvol_warning"],
            "rvol_danger_size": tier3["rvol_danger_size"],
            "rvol_warning_size": tier3["rvol_warning_size"],
            "max_exposure_pct": tier3["max_exposure_pct"],
            "max_position_pct": tier3["max_position_pct"],
            "risk_fraction": tier3["risk_fraction"],
            "max_stop_pct_hard": tier3["max_stop_pct_hard"],
            "compounding_enabled": False,
        },
        "validation_metrics": {
            "training_return": metrics.get("total_return", 0),
            "training_sharpe": metrics.get("sharpe", 0),
            "oos_sharpe": validation.get("sharpe_ratio", 0),
            "oos_win_rate": validation.get("win_rate_pct", 0),
            "status": "REJECTED",
        },
    }

    output_path = Path("config/production_config.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(production_config, f, indent=2)

    print(f"✅ Config exported to: {output_path}")
    print()
    print("You can now run: streamlit run app.py")
    print()
    print("⚠️  REMEMBER: This strategy failed validation. Trade at your own risk!")
    print("=" * 70)


if __name__ == "__main__":
    export_with_warning()
