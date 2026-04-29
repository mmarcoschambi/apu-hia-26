#!/usr/bin/env python3
"""
Quick Script: Enable Sector Rotation Filter
============================================
Este script hace 3 cosas:
1. Actualiza production_config.json para habilitar sector filter
2. Crea un backup del config anterior
3. Valida que los cambios sean correctos

Usage:
    python enable_sector_filter_quick.py
    
    # Para revertir:
    python enable_sector_filter_quick.py --revert
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse


def backup_config():
    """Crear backup del config actual"""
    config_path = Path("config/production_config.json")
    backup_path = Path(f"config/production_config.json.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    if config_path.exists():
        shutil.copy(config_path, backup_path)
        print(f"✅ Backup creado: {backup_path}")
        return backup_path
    else:
        print(f"❌ Config no encontrado: {config_path}")
        return None


def enable_sector_filter():
    """Habilitar sector rotation filter en config"""
    config_path = Path("config/production_config.json")
    
    if not config_path.exists():
        print(f"❌ Config no encontrado: {config_path}")
        return False
    
    # Leer config actual
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Modificar tier2_filters
    if 'tier2_filters' in config:
        print("\n📝 Cambios a realizar:")
        print(f"   require_sector_strength: {config['tier2_filters'].get('require_sector_strength')} → True")
        print(f"   require_positive_rs: {config['tier2_filters'].get('require_positive_rs')} → True")
        print(f"   sector_top_percentile: {config['tier2_filters'].get('sector_top_percentile')} → 0.40")
        
        config['tier2_filters']['require_sector_strength'] = True
        config['tier2_filters']['require_positive_rs'] = True
        config['tier2_filters']['sector_top_percentile'] = 0.40
        
        # Añadir metadata de cambio
        config['_last_updated'] = datetime.now().isoformat()
        config['_modification_note'] = "Enabled sector rotation filter for improved performance"
        
        # Guardar config modificado
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n✅ Sector filter HABILITADO en production_config.json")
        return True
    else:
        print("❌ No se encontró 'tier2_filters' en el config")
        return False


def disable_sector_filter():
    """Deshabilitar sector rotation filter"""
    config_path = Path("config/production_config.json")
    
    if not config_path.exists():
        print(f"❌ Config no encontrado: {config_path}")
        return False
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    if 'tier2_filters' in config:
        print("\n📝 Revirtiendo cambios:")
        print(f"   require_sector_strength: {config['tier2_filters'].get('require_sector_strength')} → False")
        print(f"   require_positive_rs: {config['tier2_filters'].get('require_positive_rs')} → False")
        
        config['tier2_filters']['require_sector_strength'] = False
        config['tier2_filters']['require_positive_rs'] = False
        
        config['_last_updated'] = datetime.now().isoformat()
        config['_modification_note'] = "Disabled sector rotation filter"
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print("\n✅ Sector filter DESHABILITADO")
        return True
    else:
        print("❌ No se encontró 'tier2_filters' en el config")
        return False


def validate_config():
    """Validar que el config tenga la estructura correcta"""
    config_path = Path("config/production_config.json")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print("\n🔍 Validando configuración...")
    
    required_keys = [
        ('tier2_filters', 'require_sector_strength'),
        ('tier2_filters', 'require_positive_rs'),
        ('tier2_filters', 'sector_top_percentile'),
    ]
    
    all_valid = True
    for section, key in required_keys:
        if section in config and key in config[section]:
            value = config[section][key]
            print(f"   ✅ {section}.{key} = {value}")
        else:
            print(f"   ❌ {section}.{key} MISSING")
            all_valid = False
    
    if all_valid:
        print("\n✅ Configuración válida")
    else:
        print("\n❌ Configuración incompleta")
    
    return all_valid


def test_sector_integration():
    """Test rápido de que sector_rotation.py funciona"""
    print("\n🧪 Testing sector rotation integration...")
    
    try:
        from src.utils.sector_rotation import SectorRotationAnalyzer, SECTOR_ETFS, SECTOR_MAP
        
        print(f"   ✅ sector_rotation.py importado correctamente")
        print(f"   ✅ {len(SECTOR_ETFS)} sector ETFs disponibles")
        print(f"   ✅ {len(SECTOR_MAP)} tickers mapeados a sectores")
        
        # Test básico
        analyzer = SectorRotationAnalyzer(
            start_date='2024-01-01',
            end_date='2024-01-31'
        )
        print(f"   ✅ SectorRotationAnalyzer instanciado")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Enable/Disable Sector Rotation Filter")
    parser.add_argument('--revert', action='store_true', help='Revert to disabled state')
    parser.add_argument('--test-only', action='store_true', help='Only test, don\'t modify config')
    args = parser.parse_args()
    
    print("=" * 70)
    print("SECTOR ROTATION FILTER - QUICK ENABLE")
    print("=" * 70)
    
    if args.test_only:
        # Solo validar y testear
        validate_config()
        test_sector_integration()
        return
    
    # Crear backup
    backup_path = backup_config()
    
    if not backup_path:
        print("\n❌ No se pudo crear backup. Abortando.")
        return
    
    # Modificar config
    if args.revert:
        success = disable_sector_filter()
    else:
        success = enable_sector_filter()
    
    if success:
        # Validar cambios
        if validate_config():
            print("\n" + "=" * 70)
            print("🎉 CAMBIOS APLICADOS EXITOSAMENTE")
            print("=" * 70)
            print("\nPróximos pasos:")
            print("1. Correr backtest de prueba:")
            print("   python optimize_3tier.py --trials 50 --tickers 20")
            print("\n2. Comparar resultados con/sin sector filter")
            print("\n3. Si hay mejora, correr optimization completo:")
            print("   python optimize_3tier.py --trials 300 --tickers 80 --use-pit-universe")
        else:
            print("\n❌ Validación falló. Revierte con:")
            print(f"   cp {backup_path} config/production_config.json")
    else:
        print("\n❌ No se pudieron aplicar cambios")
        print(f"Restaura el backup con:")
        print(f"   cp {backup_path} config/production_config.json")


if __name__ == "__main__":
    main()
