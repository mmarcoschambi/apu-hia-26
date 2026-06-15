import pandas as pd, json
from pathlib import Path

BASE = Path("/home/marcos/trade/momentum-v2/outputs/backtests")

# Buscar todos los CSVs de trades disponibles
csvs = list(BASE.glob("**/complete_trades_clean.csv")) + [BASE / "complete_trades_clean.csv"]
csvs = [c for c in csvs if c.exists()]
print("CSVs encontrados:")
for c in csvs:
    df = pd.read_csv(c)
    print(f"  {c} -> {len(df)} trades, cols: {list(df.columns)}")

# Leer el actual (gold standard)
df = pd.read_csv(BASE / "complete_trades_clean.csv")
df["entry_date"] = pd.to_datetime(df["entry_date"])

print("\n=== COLUMNAS DISPONIBLES ===")
print(df.columns.tolist())

print("\n=== SAMPLE 10 TRADES ===")
print(df[["symbol","entry_date","exit_date","exit_phase","pnl","return_pct","entry_score"]].head(10).to_string())

print("\n=== ENTRY_SCORE DISTRIBUTION ===")
if "entry_score" in df.columns:
    print(df["entry_score"].describe())
    print("Nulos:", df["entry_score"].isna().sum())
    print("Ceros:", (df["entry_score"]==0).sum())

print("\n=== POR MES ===")
monthly = df.groupby(df.entry_date.dt.to_period("M")).pnl.agg(["count","sum"]).round(0)
print(monthly.to_string())
