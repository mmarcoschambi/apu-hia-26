import pandas as pd, json
from pathlib import Path

BASE = Path("/home/marcos/trade/momentum-v2/outputs/backtests")
df = pd.read_csv(BASE / "complete_trades_clean.csv")
df["entry_date"] = pd.to_datetime(df["entry_date"])

print("=== RESUMEN SWITCH RUN ===")
print(f"Trades: {len(df)}")
w = df[df.pnl>0].pnl.sum()
l = abs(df[df.pnl<0].pnl.sum())
print(f"WR: {round((df.pnl>0).mean()*100,1)}%")
print(f"PF: {round(w/l,2) if l else 0}")

print("\n=== EXIT PHASES ===")
print(df.exit_phase.value_counts().to_string())

print("\n=== POR MES ===")
monthly = df.groupby(df.entry_date.dt.to_period("M")).pnl.agg(["count","sum"]).round(0)
print(monthly.to_string())

# Intentar detectar si hay columna de modo
for col in ["mode","attack_mode","use_theme","health_score","regime_mode"]:
    if col in df.columns:
        print(f"\n=== DISTRIBUCION {col.upper()} ===")
        print(df.groupby(col).pnl.agg(["count","sum","mean"]).round(0).to_string())

print("\n=== PEORES 10 ===")
print(df.nsmallest(10,"pnl")[["symbol","entry_date","exit_phase","pnl","return_pct"]].to_string())

print("\n=== MEJORES 10 ===")
print(df.nlargest(10,"pnl")[["symbol","entry_date","exit_phase","pnl","return_pct"]].to_string())

# Comparar con runs anteriores
print("\n=== COMPARATIVA TODOS LOS RUNS VALIDOS ===")
runs = {
    "linea_base_gold": "gold_standard_v2/complete_trades_clean.csv",
}
for name, path in runs.items():
    p = BASE / path
    if p.exists():
        d = pd.read_csv(p)
        w2 = d[d.pnl>0].pnl.sum()
        l2 = abs(d[d.pnl<0].pnl.sum())
        print(f"{name}: trades={len(d)} WR={round((d.pnl>0).mean()*100,1)}% PF={round(w2/l2,2) if l2 else 0}")
