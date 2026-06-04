import pandas as pd
import numpy as np

def calculate_health_score_pit(spy_df: pd.DataFrame, vix_df: pd.DataFrame = None) -> int:
    """
    Calcula el health score 0-7 para una fecha histórica (PIT).
    - SPY > EMA20 (+2)
    - Breadth Improving (+2) - Proxy: SPY > SMA20 or SPY Ascending(5d)
    - GEX/ATR (+1) - Proxy: ATR(5) declining + SPY > EMA10
    - VIX Favorable (+1) - VIX < 20
    - Stage 1 Complete (+1) - Proxy: SMA50 > SMA200
    """
    score = 0
    if len(spy_df) < 200: 
        return 3 # Default if insufficient history
    
    # ensure columns are lowercase for consistency
    spy_df.columns = [c.lower() for c in spy_df.columns]
    if vix_df is not None and not vix_df.empty:
        vix_df.columns = [c.lower() for c in vix_df.columns]

    # 1. SPY > EMA20
    ema20 = spy_df['close'].ewm(span=20, adjust=False).mean()
    if spy_df['close'].iloc[-1] > ema20.iloc[-1]: score += 2
    
    # 2. Breadth Improving
    sma20 = spy_df['close'].rolling(20).mean()
    spy_above_sma20 = spy_df['close'].iloc[-1] > sma20.iloc[-1]
    recent_5 = spy_df['close'].iloc[-5:].mean()
    prev_5 = spy_df['close'].iloc[-10:-5].mean()
    if spy_above_sma20 or recent_5 > prev_5: score += 2
    
    # 3. GEX/ATR
    high_low = spy_df['high'] - spy_df['low']
    atr5 = high_low.rolling(5).mean()
    atr_declining = atr5.iloc[-1] < atr5.iloc[-5] if len(atr5) >= 5 else False
    ema10 = spy_df['close'].ewm(span=10, adjust=False).mean()
    if atr_declining and spy_df['close'].iloc[-1] > ema10.iloc[-1]: score += 1
    
    # 4. VIX Favorable
    if vix_df is not None and not vix_df.empty and vix_df['close'].iloc[-1] < 20: score += 1
    
    # 5. Stage 1 Complete (SMA50 > SMA200)
    sma50 = spy_df['close'].rolling(50).mean()
    sma200 = spy_df['close'].rolling(200).mean()
    if sma50.iloc[-1] > sma200.iloc[-1]: score += 1
    
    return score
