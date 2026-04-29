import pandas as pd
df = pd.read_csv("/home/marcos/trade/momentum-v2/outputs/backtests/backtest_results.csv")
print("Todas las columnas:")
for c in df.columns.tolist():
    print(f"  {c}")
print(f"\nPrimera fila:")
print(df.iloc[0].to_string())