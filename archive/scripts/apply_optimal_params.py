#!/usr/bin/env python3
"""
APPLY OPTIMAL PARAMETERS
=========================

Aplica los parámetros óptimos encontrados en la optimización
a los archivos de configuración del sistema.

Usage:
    python3 apply_optimal_params.py
"""

import json
import sys
from pathlib import Path

# Load optimal params
config_file = Path('config/optimal_params_2023.json')

if not config_file.exists():
    print(f"❌ File not found: {config_file}")
    sys.exit(1)

with open(config_file, 'r') as f:
    config = json.load(f)

optimal = config['optimal_parameters']
features = config['recommended_features']

print("="*70)
print("🎯 APPLYING OPTIMAL PARAMETERS")
print("="*70)

print("\n📊 Optimal Parameters (Trial 29):")
for key, val in optimal.items():
    print(f"   {key:<25} = {val}")

print("\n🔧 Recommended Features:")
for key, val in features.items():
    status = "✅ ON" if val else "❌ OFF"
    print(f"   {key:<30} {status}")

# Create config for bugatti scripts
bugatti_config = {
    **optimal,
    **features
}

# Save to multiple formats for different scripts
output_dir = Path('config')
output_dir.mkdir(exist_ok=True)

# 1. Python dict format
py_config = output_dir / 'optimal_config.py'
with open(py_config, 'w') as f:
    f.write('"""\nOptimal Parameters - Auto-generated\n')
    f.write(f'Generated: {config["metadata"]["optimization_date"]}\n')
    f.write(f'Best Sharpe: {config["metadata"]["best_sharpe"]}\n')
    f.write('"""\n\n')
    f.write('OPTIMAL_PARAMS = ')
    f.write(json.dumps(bugatti_config, indent=4))
    f.write('\n')

print(f"\n💾 Saved to:")
print(f"   {py_config}")

# 2. JSON format for general use
json_config = output_dir / 'optimal_config.json'
with open(json_config, 'w') as f:
    json.dump(bugatti_config, f, indent=2)

print(f"   {json_config}")

# 3. Create quick reference
print("\n📋 Quick Copy-Paste for Manual Use:")
print("```python")
print("params = {")
for key, val in bugatti_config.items():
    if isinstance(val, bool):
        print(f"    '{key}': {val},")
    elif isinstance(val, str):
        print(f"    '{key}': '{val}',")
    else:
        print(f"    '{key}': {val},")
print("}")
print("```")

print("\n✅ Configuration ready!")
print("\n💡 Usage:")
print("   from config.optimal_config import OPTIMAL_PARAMS")
print("   engine = AdvancedVectorBTEngine(**OPTIMAL_PARAMS)")
