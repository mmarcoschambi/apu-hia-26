
#!/usr/bin/env python3

import argparse, json, sys

from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent

SRC = ROOT / 'config' / 'combo_results'

DST = ROOT / 'outputs' / 'best_combos_run'

DST.mkdir(parents=True, exist_ok=True)



T3D = {

    'rvol_danger': 3.0, 'rvol_warning': 2.0,

    'rvol_danger_size': 0.3, 'rvol_warning_size': 0.65,

    'adr_high': 6.0, 'adr_med': 5.0,

    'adr_high_size': 0.25, 'adr_med_size': 0.33,

    'max_exposure_pct': 0.65, 'max_position_pct': 0.25,

    'earnings_days': 5, 'earnings_cushion': 2,

    'max_stop_pct_hard': 0.08, 'compounding_enabled': False,

}



def sync(name):

    src = SRC / (name + '_optimized.json')

    if not src.exists():

        print('Not found:', src)

        return False

    d = json.loads(src.read_text())

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

    }

    dst = DST / (name + '_config.json')

    dst.write_text(json.dumps(out, indent=2))

    print('Synced:', dst)

    return True



p = argparse.ArgumentParser()

p.add_argument('--combo', default=None)

p.add_argument('--all', action='store_true')

args = p.parse_args()

if args.all:

    [sync(f.stem.replace('_optimized', '')) for f in sorted(SRC.glob('*_optimized.json'))]

elif args.combo:

    sys.exit(0 if sync(args.combo) else 1)

else:

    p.print_help()

