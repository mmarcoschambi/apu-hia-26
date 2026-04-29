import pandas as pd

try:
    df = pd.read_csv("outputs/backtests/backtest_results.csv")
    
    # 1. Total Rows
    total_rows = len(df)
    
    # 2. Unique Trades (Grouping by Symbol + Entry Price)
    # Rounding entry price to avoid float precision issues
    df['entry_price_rounded'] = df['entry_price'].round(4)
    unique_trades = df.groupby(['symbol', 'entry_price_rounded']).size().reset_index()
    total_unique_trades = len(unique_trades)
    
    # 3. Distribution
    phases = df['exit_phase'].value_counts()
    
    print(f"TOTAL_ROWS:{total_rows}")
    print(f"UNIQUE_TRADES:{total_unique_trades}")
    print(f"PHASES:{phases.to_dict()}")
    
except Exception as e:
    print(f"ERROR:{e}")