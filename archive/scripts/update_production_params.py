#!/usr/bin/env python3
"""
UPDATE PRODUCTION PARAMETERS
=============================

Actualiza app.py y otros scripts con los parámetros de producción
derivados del análisis de rangos robustos.

Usage:
    python3 update_production_params.py
"""

import json
import sys
from pathlib import Path

def load_production_params():
    """Carga parámetros de producción."""
    config_file = Path('config/production_params.json')
    
    if not config_file.exists():
        print("⚠️ Production params not found. Using optimal params...")
        config_file = Path('config/optimal_config.json')
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Extract just parameters (handle both formats)
    if 'parameters' in config:
        return config['parameters']
    else:
        return config

def update_app_defaults():
    """Actualiza defaults en app.py."""
    app_file = Path('app.py')
    
    if not app_file.exists():
        print(f"❌ File not found: {app_file}")
        return False
    
    print("⚠️  Manual update required for app.py")
    print("    Update sidebar defaults with production params")
    print("    See: config/production_params.json")
    
    return True

def create_quick_config():
    """Crea config.py importable."""
    params = load_production_params()
    
    config_file = Path('config/production.py')
    
    with open(config_file, 'w') as f:
        f.write('"""\n')
        f.write('PRODUCTION PARAMETERS\n')
        f.write('=====================\n')
        f.write('Validated via Walk Forward Analysis\n')
        f.write('Center of robust parameter ranges\n')
        f.write('"""\n\n')
        f.write('PRODUCTION_PARAMS = {\n')
        for key, val in sorted(params.items()):
            if isinstance(val, bool):
                f.write(f'    "{key}": {val},\n')
            elif isinstance(val, str):
                f.write(f'    "{key}": "{val}",\n')
            else:
                f.write(f'    "{key}": {val},\n')
        f.write('}\n')
    
    print(f"✅ Created: {config_file}")
    return True

def main():
    print("="*70)
    print("🏭 PRODUCTION PARAMETERS UPDATE")
    print("="*70)
    
    # Load params
    params = load_production_params()
    
    print("\n📊 Production Parameters:")
    for key, val in sorted(params.items()):
        print(f"   {key:<25} = {val}")
    
    # Create importable config
    create_quick_config()
    
    # Instructions
    print("\n" + "="*70)
    print("📝 MANUAL STEPS REQUIRED")
    print("="*70)
    print("\n1. Update app.py sidebar defaults:")
    print("   • min_rvol slider: default = production_params['min_rvol']")
    print("   • min_adr slider: default = production_params['min_adr']")
    print("   • etc...")
    
    print("\n2. Update bugatti_bolide_X.py:")
    print("   • Import: from config.production import PRODUCTION_PARAMS")
    print("   • Use as defaults in argument parser")
    
    print("\n3. Test with production params:")
    print("   ```bash")
    print("   python3 bugatti_bolide_X.py --use-production-params")
    print("   ```")
    
    print("\n✅ Configuration ready for deployment!")

if __name__ == '__main__':
    main()
