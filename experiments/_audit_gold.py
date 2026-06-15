import pandas as pd, json
from pathlib import Path

BASE = Path("/home/marcos/trade/momentum-v2/outputs/backtests")

# Buscar todos los runs disponibles
print("=== RUNS DISPONIBLES ===")
for d in sorted(BASE.iterdir()):
    m = d / "backtest_metrics.json"
    t = d / "complete_trades_clean.csv"
    if m.exists() and t.exists():
        with open(m) as f:
            met = json.load(f)
        n = len(pd.read_csv(t))
        print(f"{d.name:35s} | trades={n:4d} | ret={met.get('total_return','?'):7.2f}% | mdd={met.get('max_drawdown','?'):7.2f}% | sharpe={met.get('sharpe_ratio','?'):.3f}")

# Leer el gold standard actual
df = pd.read_csv(BASE / "complete_trades_clean.csv")
df["entry_date"] = pd.to_datetime(df["entry_date"])

print("\n=== ESTADISTICAS JULIO (patron de fallo recurrente) ===")
julios = df[df.entry_date.dt.month == 7]
print(f"Total trades en julios: {len(julios)}")
print(f"PnL total julios: {julios.pnl.sum():.0f}")
print(f"WR julios: {(julios.pnl>0).mean()*100:.1f}%")
print(julios[["symbol","entry_date","exit_phase","pnl","return_pct"]].to_string())

print("\n=== PEORES 10 TRADES GLOBALES ===")
print(df.nsmallest(10,"pnl")[["symbol","entry_date","exit_phase","pnl","return_pct"]].to_string())

print("\n=== WR POR TRIMESTRE ===")
df["quarter"] = df.entry_date.dt.to_period("Q")
q = df.groupby("quarter").agg(
    trades=("pnl","count"),
    pnl=("pnl","sum"),
    wr=("pnl", lambda x: (x>0).mean()*100)
).round(1)
print(q.to_string())
