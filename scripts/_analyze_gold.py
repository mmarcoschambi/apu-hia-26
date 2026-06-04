import pandas as pd, json

df = pd.read_csv("/home/marcos/trade/momentum-v2/outputs/backtests/complete_trades_clean.csv")
df["entry_date"] = pd.to_datetime(df["entry_date"])
df["exit_date"] = pd.to_datetime(df["exit_date"])

w = df[df.pnl>0].pnl.sum()
l = abs(df[df.pnl<0].pnl.sum())
pf = round(w/l,2) if l else 0
avg_ret = round(df.return_pct.mean(),2)

print("KPIs | Trades:", len(df), "| WR:", round((df.pnl>0).mean()*100,1), "| PF:", pf, "| Avg ret%:", avg_ret)
print()
print("EXIT PHASES")
print(df.exit_phase.value_counts().to_string())
print()
print("POR MES (count, sum pnl)")
monthly = df.groupby(df.entry_date.dt.to_period("M")).pnl.agg(["count","sum"])
monthly["sum"] = monthly["sum"].round(0)
print(monthly.to_string())
print()
print("TOP 5 WIN")
cols = ["symbol","entry_date","exit_date","exit_phase","pnl","return_pct"]
print(df.nlargest(5,"pnl")[cols].to_string())
print()
print("TOP 5 LOSS")
print(df.nsmallest(5,"pnl")[cols].to_string())
print()
print("PnL POR PHASE")
print(df.groupby("exit_phase").pnl.agg(["count","mean","sum"]).round(0).to_string())
print()
with open("/home/marcos/trade/momentum-v2/outputs/backtests/backtest_metrics.json") as f:
    m = json.load(f)
print("METRICS JSON")
for k,v in m.items():
    print(" ", k, ":", v)
