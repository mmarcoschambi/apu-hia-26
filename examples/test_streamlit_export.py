#!/usr/bin/env python3
"""
Example: Test Streamlit Export from 3-Tier Optimization
========================================================

This script demonstrates how to manually export optimization results
to Streamlit config format.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from optimize_3tier import export_to_streamlit_config


def main():
    print("=" * 70)
    print("STREAMLIT EXPORT TESTER")
    print("=" * 70)

    # Load optimization results
    final_config_path = Path("outputs/3tier_optimization/FINAL_CONFIG.json")

    if not final_config_path.exists():
        print(f"❌ No optimization results found at: {final_config_path}")
        print("   Run optimize_3tier.py first!")
        return

    with open(final_config_path, "r") as f:
        final_config = json.load(f)

    # Check if strategy was approved
    validation = final_config.get("validation", {})
    approved = validation.get("approved", False)

    print(f"\n📋 Optimization Summary:")
    print(f"   Date: {final_config['timestamp']}")
    print(f"   Universe: {final_config['universe_size']} tickers")
    print(f"   Trials: {final_config['optimization']['trials']}")
    print(f"   Approved: {'✅ YES' if approved else '❌ NO'}")

    if not approved:
        print(f"\n⚠️  Strategy was REJECTED by validation:")
        for reason in validation.get("rejection_reasons", []):
            print(f"      - {reason}")
        print(f"\n   Export aborted. Fix issues and re-run optimization.")
        return

    # Export to Streamlit
    print(f"\n📤 Exporting to Streamlit config...")

    export_to_streamlit_config(
        final_config=final_config,
        output_path="config/production_config.json",
        backup=True,
    )

    print(f"\n✅ Export complete!")
    print(f"\n🚀 Next steps:")
    print(f"   1. Review config: config/production_config.json")
    print(f"   2. Test in Streamlit: streamlit run app.py")
    print(
        f"   3. If issues, restore backup: cp config/production_config.json.bak config/production_config.json"
    )

    # Show key parameters
    tier1 = final_config["tier1_strategy"]
    tier2 = final_config.get("tier2_filters", final_config.get("tier2_quality", {}))

    print(f"\n📊 Key Parameters Exported:")
    print(f"   Strategy: tp1={tier1['tp1_r']}R, tp2={tier1['tp2_r']}R")
    print(f"   Filters: rvol≥{tier2['min_rvol']}x, adr≥{tier2['min_adr']}%")
    print(
        f"   Performance: Sharpe={validation.get('sharpe_ratio', 0):.2f}, DD={validation.get('max_drawdown_pct', 0):.2f}%"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
