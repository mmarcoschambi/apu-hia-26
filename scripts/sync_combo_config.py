#!/usr/bin/env python3
"""
sync_combo_config.py — Synchronize optimized combo configs

ARCHITECTURE NOTE: tier3_fixed → tier3_risk Merge
==================================================
This script reads tier3_fixed from optimized configs and merges them into
tier3_risk for the final output. This is intentional and correct because:

1. When optimize_combo.py exports a combo, it includes tier3_fixed with
   optimized risk parameters (max_exposure_pct, max_position_pct, etc).

2. This script merges tier3_fixed INTO tier3_risk, creating
   a unified risk section in outputs/best_combos_run/{name}_config.json

3. The canonical loader (src/integration/combo_loader.py) loads this merged
   tier3_risk and passes it to signal_engine.py, which knows how to interpret it.

4. Signal engine resolves risk params via:
       t3 = combo_cfg.get("tier3_fixed", combo_cfg.get("tier3_risk", {}))
   Since tier3_fixed was already merged INTO tier3_risk in the output,
   this always finds the merged params under tier3_risk. ✓ CORRECT

UPSHOT: The final production config always has a single tier3_risk block
with all risk parameters merged in. No ambiguity, no lookup failures.
"""

import argparse
import json
import sys
import math
from pathlib import Path
from datetime import datetime

# Salvaguarda para prevenir UnicodeEncodeError en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, IOError):
        pass

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'config' / 'combo_results'
DST = ROOT / 'outputs' / 'best_combos_run'

# Create production directory if not exists
DST.mkdir(parents=True, exist_ok=True)

# Default Tier 3 Risk Parameters
T3D = {
    'rvol_danger': 3.0, 'rvol_warning': 2.0,
    'rvol_danger_size': 0.3, 'rvol_warning_size': 0.65,
    'adr_high': 6.0, 'adr_med': 5.0,
    'adr_high_size': 0.25, 'adr_med_size': 0.33,
    'max_exposure_pct': 0.65, 'max_position_pct': 0.25,
    'earnings_days': 5, 'earnings_cushion': 2,
    'max_stop_pct_hard': 0.08, 'compounding_enabled': False,
    'use_dynamic_extension_sizing': True,
    'dynamic_extension_sizing': {
        'version': 'v2_atlas_informed',
        'comfort_pct': 6.76,
        'valley_pct': 10.0,
        'mid_pct': 15.0,
        'high_pct': 25.0,
        'extreme_pct': 35.0,
        'max_pct': 50.0,
        'min_factor': 0.5,
        'extreme_factor': 0.2
    }
}


def sync(name, promote=False):
    src = SRC / (name + '_optimized.json')

    if not src.exists():
        print('Not found:', src)
        return False

    # Comparación de paths por objeto Path resuelto
    resolved_src = src.resolve()
    resolved_src_dir = SRC.resolve()
    if resolved_src.parent != resolved_src_dir:
        print(f"ERROR: Source path '{resolved_src}' must be directly under '{resolved_src_dir}'")
        return False

    d = json.loads(src.read_text())

    # Gate de Integridad: Si el resultado de optimización falló el ResearchGate / validación,
    # bloqueamos la sincronización para proteger la configuración de producción.
    validation_passed = d.get('validation_passed', False)
    if not validation_passed:
        print(f"WARNING: ABORT SYNC for {name}: Optimization did not pass validation (validation_passed = False)")
        return False

    # Umbral de sanidad duro para profit_factor (bug de 999 o infinitos/NaN)
    validation_data = d.get('validation', {})
    profit_factor = validation_data.get('profit_factor', 0.0)
    try:
        pf_val = float(profit_factor)
    except (TypeError, ValueError):
        print(f"ERROR: profit_factor '{profit_factor}' no es un número válido.")
        return False

    if pf_val >= 99.0 or math.isinf(pf_val) or math.isnan(pf_val) or pf_val < 0:
        print(f"ERROR: ABORT SYNC for {name}: profit_factor {pf_val} violates sanity threshold (< 99.0).")
        return False

    out = {
        'timestamp': d.get('optimized_at', d.get('timestamp', '')),
        'pipeline': 'optimize_combo',
        'period': d.get('period', {'start': 'N/A', 'end': 'N/A', 'initial_capital': 100000}),
        'universe_size': d.get('universe_size', 39),
        'tier1_strategy': d.get('tier1_exits', d.get('tier1_strategy', {})),
        'tier2_filters': d.get('tier2_filters', {}),
        'tier3_risk': {**T3D, **d.get('tier3_fixed', {})},
        'is_score': d.get('optimization_score', d.get('is_score', 0)),
        'screener': d.get('screener', ''),
        'pattern': d.get('pattern', ''),
        'validation': d.get('validation', {}),
        'validation_passed': d.get('validation_passed', False),
        'oos_metrics': d.get('oos_metrics', {}),
        'params_json_source': d.get('params_json_source', '')
    }

    dst = DST / (name + '_config.json')
    resolved_dst = dst.resolve()
    resolved_dst_dir = DST.resolve()

    # Validar que el path destino sea seguro y esté bajo la carpeta de producción oficial
    if resolved_dst.parent != resolved_dst_dir:
        print(f"ERROR: Destination path '{resolved_dst}' must be directly under '{resolved_dst_dir}'")
        return False

    # Modo DRY-RUN (sin --promote)
    if not promote:
        print(f"[*] DRY-RUN check for '{name}':")
        print(f"  - Validation status: PASSED")
        print(f"  - Sanity check: PASSED (profit_factor = {pf_val:.4f})")
        print(f"  - Destination path: {dst}")

        if dst.exists():
            try:
                existing_data = json.loads(dst.read_text())
                if existing_data.get('approved', False):
                    print("  - Notice: A production-approved file already exists. Sync without '--promote' will NOT touch it.")
            except Exception:
                pass
        print("  - [OK] Candidate is clean and eligible for promotion.")
        return True

    # Modo PROMOCIÓN (con --promote)
    import sys
    from pathlib import Path
    
    # Ensure src is in sys.path to import ParamGate
    if str(resolved_dst_dir.parent.parent) not in sys.path:
        sys.path.insert(0, str(resolved_dst_dir.parent.parent))
    from src.validation.param_gate import ParamGate
    
    # We must construct the candidate object and include validation metrics if present
    # to feed into ParamGate.
    # We will map 'validation' to 'oos_metrics' if oos_metrics isn't present,
    # because some pipelines store metrics under 'validation'.
    if 'oos_metrics' not in out and 'validation' in out:
        out['oos_metrics'] = out['validation']
    
    out['approved_source'] = "sync_combo_config"
    # La bandera validation_passed debe venir ya izada por el script validador real.
    # No la derivamos heurísticamente aquí.
    
    bak_path = dst.with_suffix('.json.bak')
    
    backup_created = False
    try:
        # Si ya existe en producción, hacer backup de un paso
        if dst.exists():
            try:
                existing_data = json.loads(dst.read_text())
                if existing_data.get('approved', False) or existing_data.get('governance_hash'):
                    print(f"[*] Overwriting existing approved config for '{name}' via explicit '--promote'.")
            except Exception:
                pass

            if bak_path.exists():
                bak_path.unlink()
            dst.rename(bak_path)
            backup_created = True

        # Usar ParamGate para validación criptográfica y promoción segura
        print(f"[*] Executing Phase 6 ParamGate for {name}...")
        success = ParamGate.promote(out, dst)
        
        if success:
            print(f"SUCCESS: Promoted and synced '{name}' to {dst}")
            return True
        else:
            print(f"CRITICAL ERROR: ParamGate REJECTED '{name}'. Check logs.")
            raise ValueError("Governance check failed")

    except Exception as e:
        print(f"CRITICAL ERROR during promotion of '{name}': {e}")
        if backup_created and bak_path.exists():
            print("[*] Restoring destination from backup (.json.bak)...")
            if dst.exists():
                dst.unlink()
            bak_path.rename(dst)
        return False


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument('--combo', default=None)
    p.add_argument('--all', action='store_true')
    p.add_argument('--promote', action='store_true', help='Ejecutar la promoción real del combo verificado.')
    args = p.parse_args()

    if args.all:
        success_count = 0
        total_count = 0
        for f in sorted(SRC.glob('*_optimized.json')):
            name = f.name.replace('_optimized.json', '')
            total_count += 1
            if sync(name, promote=args.promote):
                success_count += 1
        print(f"\n[*] Sincronización masiva finalizada. Éxito: {success_count}/{total_count}")
        sys.exit(0 if success_count == total_count else 1)

    elif args.combo:
        sys.exit(0 if sync(args.combo, promote=args.promote) else 1)
    else:
        p.print_help()
