#!/usr/bin/env python3
import sys
from pathlib import Path

# Asegurar que el root del proyecto esté en el path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from src.integration.combo_loader import load_combo_merged
except ImportError as e:
    print(f"Error al importar combo_loader: {e}")
    sys.exit(1)

combo_name = 'combo_pure_momentum'
try:
    cfg, meta = load_combo_merged(combo_name)

    print(f"--- Inspección de {combo_name} ---")
    print('Source:', getattr(meta, 'source', 'N/A'))
    print('Sections Merged:', getattr(meta, 'sections_merged', []))
    
    t2 = cfg.get('tier2_filters', {})
    print('Min RS Percentile:', t2.get('min_rs_percentile'))
    print('Min Dollar Volume:', t2.get('min_dollar_volume'))
    print('Tier1 Strategy:', cfg.get('tier1_strategy'))
except Exception as e:
    print(f"Error cargando el combo: {e}")
