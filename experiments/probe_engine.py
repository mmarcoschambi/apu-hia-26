import sys
from pathlib import Path
import pandas as pd

# Setup Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

def probe():
    print("🚀 Probing AdvancedVectorBTEngine.run_backtest()...")
    engine = AdvancedVectorBTEngine(
        universe=["AAPL"], # Minimal universe
        start_date="2025-01-01",
        end_date="2025-01-10",
        initial_capital=100000
    )
    
    result = engine.run_backtest()
    print(f"Result type: {type(result)}")
    if isinstance(result, tuple):
        print(f"Result length: {len(result)}")
        for i, val in enumerate(result):
            print(f"  [{i}] type: {type(val)}")
    else:
        print(f"Result: {result}")

if __name__ == "__main__":
    probe()
