import sys
sys.path.insert(0, "/home/marcos/trade/momentum-v2")
from vcp_signal_scanner import load_ohlcv, identify_swings
import numpy as np

df = load_ohlcv("NVDA", days=160)
swings = identify_swings(df.tail(100))
print(f"NVDA - last 100 days, {len(swings)} swings found:")
print()
i = 0
pairs = []
while i < len(swings)-1:
    if swings[i][1] == "peak" and swings[i+1][1] == "trough":
        p = swings[i]; t = swings[i+1]
        depth = (p[2]-t[2])/p[2]*100
        pairs.append(depth)
        print(f"  Contraction {len(pairs)}: peak={p[2]:.2f} ({p[0].date()}) -> trough={t[2]:.2f} ({t[0].date()}) | depth={depth:.1f}%")
        i+=2
    else: i+=1

if len(pairs) >= 2:
    print(f"\n  Contracting? {all(pairs[i]>pairs[i+1] for i in range(len(pairs)-1))}")
    print(f"  Depths: {[round(d,1) for d in pairs]}")
    print(f"  Last depth: {pairs[-1]:.1f}% (need < 15% for VCP)")