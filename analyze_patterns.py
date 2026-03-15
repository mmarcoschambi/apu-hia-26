import pandas as pd
import numpy as np

df = pd.read_csv("/home/marcos/trade/momentum-v2/outputs/backtests/backtest_results.csv")
print(f"Total trades: {len(df)}")
print(f"Columnas pattern: {[c for c in df.columns if 'pattern' in c.lower()]}")
print()

has_pattern = df["pattern_confidence"] > 0
print(f"Con patron: {has_pattern.sum()} ({has_pattern.mean()*100:.1f}%)")
print(f"Sin patron: {(~has_pattern).sum()} ({(~has_pattern).mean()*100:.1f}%)")
print()

print("Tipos de patron:")
print(df[has_pattern]["pattern_type"].value_counts().to_string())
print()

for label, mask in [("CON patron", has_pattern), ("SIN patron", ~has_pattern)]:
    sub = df[mask]
    if len(sub) == 0: continue
    winners = sub[sub["pnl"] > 0]
    losers = sub[sub["pnl"] <= 0]
    wr = len(winners) / len(sub) * 100
    avg_win = winners["pnl"].mean() if len(winners) > 0 else 0
    avg_loss = losers["pnl"].mean() if len(losers) > 0 else 0
    pf = abs(winners["pnl"].sum() / losers["pnl"].sum()) if len(losers) > 0 else 999
    avg_conf = df[mask]["pattern_confidence"].mean()
    print(f"{label}: n={len(sub)} | WR={wr:.1f}% | AvgW=${avg_win:.0f} | AvgL=${avg_loss:.0f} | PF={pf:.2f} | conf={avg_conf:.3f}")

print()
print("=== POR TIPO DE PATRON ===")
for ptype in df[has_pattern]["pattern_type"].unique():
    sub = df[df["pattern_type"] == ptype]
    if len(sub) < 5: continue
    winners = sub[sub["pnl"] > 0]
    losers = sub[sub["pnl"] <= 0]
    wr = len(winners)/len(sub)*100
    pf = abs(winners["pnl"].sum()/losers["pnl"].sum()) if len(losers)>0 else 999
    conf = sub["pattern_confidence"].mean()
    print(f"  {ptype}: n={len(sub)} | WR={wr:.1f}% | PF={pf:.2f} | conf_media={conf:.3f}")

print()
print("=== CONFIANZA vs PERFORMANCE ===")
bins = [(0,0.3,"Baja"), (0.3,0.5,"Media-Baja"), (0.5,0.7,"Media"), (0.7,0.9,"Alta"), (0.9,1.01,"Muy Alta")]
for lo, hi, label in bins:
    mask = (df["pattern_confidence"] >= lo) & (df["pattern_confidence"] < hi)
    sub = df[mask]
    if len(sub) < 3: continue
    winners = sub[sub["pnl"] > 0]
    wr = len(winners)/len(sub)*100
    avg_pnl = sub["pnl"].mean()
    print(f"  Conf {label} ({lo:.1f}-{hi:.1f}): n={len(sub)} | WR={wr:.1f}% | avg_pnl=${avg_pnl:.0f}")