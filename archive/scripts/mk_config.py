import json
from pathlib import Path

# Lee el resultado del optimizer
src = json.load(open('config/combo_results/combo_triad_rts_breakout_optimized.json'))

# Construye el formato que espera walk_forward_combos.py
config = {
    'timestamp': src['optimized_at'],
    'pipeline': 'optimize_combo',
    'period': {
        'start': '2021-01-01',
        'end': '2023-12-31',
        'initial_capital': 100000
    },
    'universe_size': 39,
    'tier1_strategy': src['tier1_exits'],
    'tier2_filters': src['tier2_filters'],
    'tier3_risk': {
        **src['tier3_fixed'],
        'rvol_danger': 3.0,
        'rvol_warning': 2.0,
        'rvol_danger_size': 0.3,
        'rvol_warning_size': 0.65,
        'adr_high': 6.0,
        'adr_med': 5.0,
        'adr_high_size': 0.25,
        'adr_med_size': 0.33,
        'max_exposure_pct': 0.65,
        'max_position_pct': 0.25,
        'earnings_days': 5,
        'earnings_cushion': 2,
        'max_stop_pct_hard': 0.08,
        'compounding_enabled': False
    },
    'is_score': src['optimization_score'],
    'screener': src['screener'],
    'pattern': src['pattern']
}

out = Path('outputs/best_combos_run/combo_triad_rts_breakout_config.json')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(config, indent=2))
print('Config escrita en:', out)
print('tier1_strategy:', config['tier1_strategy'])
print('IS score:', src['optimization_score'])
