from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
import pandas as pd

universe = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX"]

engine = AdvancedVectorBTEngine(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000,
    max_positions=10,
    universe=universe,
)

results = engine.run_backtest()
trades = results["trades"]

trades.to_csv("outputs/backtests/test_trades.csv", index=False)
print(f"Guardados {len(trades)} trades")

print("Columnas:", list(trades.columns))
print()
sample = trades[
    [
        "symbol",
        "entry_price",
        "stop_loss",
        "tp1_target",
        "tp2_target",
        "pnl",
        "r_multiple",
    ]
].head(5)
print(sample.to_string())
