import json, shutil
from pathlib import Path

ROOT = Path('/home/marcos/trade/momentum-v2')
COMBOS = ROOT / 'config' / 'combos'

# Experimento C1: triad_rts x vcp
vcp = json.loads((COMBOS / 'combo_triad_rts_breakout.json').read_text())
vcp['name'] = 'combo_triad_rts_vcp'
vcp['description'] = 'Triad RTS VCP: Pipeline completo con patron VCP'
vcp['pattern']['signal_type'] = 'vcp'
vcp['pattern']['description'] = 'VCP (Volatility Contraction Pattern) con validacion RTS'
(COMBOS / 'combo_triad_rts_vcp.json').write_text(json.dumps(vcp, indent=2))
print('Created: combo_triad_rts_vcp.json')

# Experimento C2: triad_rts x pocket_pivot
pp = json.loads((COMBOS / 'combo_triad_rts_breakout.json').read_text())
pp['name'] = 'combo_triad_rts_pocket_pivot'
pp['description'] = 'Triad RTS Pocket Pivot: Pipeline completo con patron pocket pivot'
pp['pattern']['signal_type'] = 'pocket_pivot'
pp['pattern']['description'] = 'Pocket Pivot con validacion RTS completa'
(COMBOS / 'combo_triad_rts_pocket_pivot.json').write_text(json.dumps(pp, indent=2))
print('Created: combo_triad_rts_pocket_pivot.json')

print()
print('Para correr Experimento C1 (VCP):')
print('  python3 optimize_combo.py --combo combo_triad_rts_vcp --start 2021-01-01 --end 2023-12-31 --trials 100 --tickers 39 --seed 42 --skip-validation')
print()
print('Para correr Experimento C2 (pocket_pivot):')
print('  python3 optimize_combo.py --combo combo_triad_rts_pocket_pivot --start 2021-01-01 --end 2023-12-31 --trials 100 --tickers 39 --seed 42 --skip-validation')
