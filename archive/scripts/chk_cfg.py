import json, sys
p = 'outputs/best_combos_run/combo_triad_rts_breakout_config.json'
try:
    d = json.load(open(p))
    keys = list(d.keys())
    print('Keys:', keys)
    has_t1 = 'tier1_strategy' in d
    has_t2 = 'tier2_filters' in d
    has_t3 = 'tier3_risk' in d
    print('tier1_strategy:', has_t1, '|', d.get('tier1_strategy'))
    print('tier2_filters:', has_t2)
    print('tier3_risk:', has_t3)
    print('screener:', d.get('screener'))
    print('pattern:', d.get('pattern'))
    if has_t1 and has_t2 and has_t3:
        print('FORMAT OK - WF can run')
    else:
        print('FORMAT INCOMPLETE - needs sync_combo_config.py')
except Exception as e:
    print('ERROR:', e)
