#!/usr/bin/env python3
import sys
import os
import re

def set_variant(variant_name):
    file_path = "src/screeners/triad_rts.py"
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    if variant_name == "T3":
        new_pct = 70.0
        new_green = "False"
    elif variant_name == "T4":
        new_pct = 60.0
        new_green = "False"
    elif variant_name == "baseline":
        new_pct = 90.0
        new_green = "True"
    else:
        print("Unknown variant. Use T3, T4 or baseline.")
        return

    # Replace min_rts_pct
    content = re.sub(r'("min_rts_pct":\s*)\d+\.\d+', f'\\g<1>{new_pct}', content)
    # Replace require_green_candle
    content = re.sub(r'("require_green_candle":\s*)(True|False)', f'\\g<1>{new_green}', content)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"File {file_path} updated to {variant_name}:")
    print(f"  min_rts_pct = {new_pct}")
    print(f"  require_green_candle = {new_green}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/set_triad_variant.py <T3|T4|baseline>")
        sys.exit(1)
    
    set_variant(sys.argv[1])
