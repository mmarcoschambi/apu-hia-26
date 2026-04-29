#!/usr/bin/env python3
import os
import shutil
import sys
from glob import glob
from datetime import datetime

def save_variant(variant_name):
    outputs_dir = "outputs/backtests"
    if not os.path.exists(outputs_dir):
        print(f"Error: {outputs_dir} not found")
        return

    # Find most recent IS and OOS files
    is_files = sorted(glob(os.path.join(outputs_dir, "analytics_bt_*_IS.json")), key=os.path.getmtime, reverse=True)
    oos_files = sorted(glob(os.path.join(outputs_dir, "analytics_bt_*_OOS.json")), key=os.path.getmtime, reverse=True)

    if not is_files or not oos_files:
        print("Error: No recent analytics files found")
        return

    latest_is = is_files[0]
    latest_oos = oos_files[0]

    # Target names
    target_is = os.path.join(outputs_dir, f"variant_{variant_name}_IS.json")
    target_oos = os.path.join(outputs_dir, f"variant_{variant_name}_OOS.json")

    shutil.copy2(latest_is, target_is)
    shutil.copy2(latest_oos, target_oos)

    print(f"Saved latest results as:")
    print(f"  IS: {target_is}")
    print(f"  OOS: {target_oos}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/save_variant.py <variant_name>")
        sys.exit(1)
    
    save_variant(sys.argv[1])
