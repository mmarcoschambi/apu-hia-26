import pandas as pd
import sys

try:
    df = pd.read_csv('outputs/advanced_trades_20260204_010554.csv')
    
    # Sort by entry date
    df['entry_date'] = pd.to_datetime(df['entry_date'])
    df = df.sort_values('entry_date')
    
    # Calculate position value (approx)
    # Note: 'initial_risk' column should be there from the engine
    
    print("First 5 Trades:")
    cols = ['entry_date', 'symbol', 'initial_risk', 'shares', 'entry_price']
    print(df[cols].head(5))
    
    print("\nLast 5 Trades:")
    print(df[cols].tail(5))
    
    # Check trend
    first_risk = df['initial_risk'].iloc[:5].mean()
    last_risk = df['initial_risk'].iloc[-5:].mean()
    
    print(f"\nAvg Risk Start: ${first_risk:.2f}")
    print(f"Avg Risk End:   ${last_risk:.2f}")
    
    if last_risk > first_risk * 1.05:
        print("✅ SNOWBALL CONFIRMED: Risk increased as equity grew.")
    elif last_risk < first_risk * 0.95:
        print("❌ REVERSE SNOWBALL: Risk decreased (equity drawdown).")
    else:
        print("⚠️  FLAT: Risk remained similar (flat equity or fixed risk).")
        
except Exception as e:
    print(f"Error: {e}")
