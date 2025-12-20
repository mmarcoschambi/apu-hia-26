"""
Institutional Screener - Deterministic Scanning Logic
-----------------------------------------------------
Filters candidates based on:
1. Volatility: ADR(20) > threshold (default 1.5%)
2. Liquidity: Avg Volume > 300k AND Avg Dollar Volume > $15M
3. Quality: Price > $5
4. Relative Strength: Outperforming SPY (50 days)
5. Structure: Base Breakout
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional

class InstitutionalScreener:
    def __init__(self, 
                 adr_threshold: float = 1.5, 
                 min_price: float = 5.0,
                 min_avg_vol: int = 300000,
                 min_dollar_vol: float = 15000000.0,
                 rs_window: int = 50):
        self.adr_threshold = adr_threshold
        self.min_price = min_price
        self.min_avg_vol = min_avg_vol
        self.min_dollar_vol = min_dollar_vol
        self.rs_window = rs_window

    def scan(self, symbol: str, df: pd.DataFrame, spy_df: pd.DataFrame, date: pd.Timestamp) -> Optional[Dict]:
        """
        Scan a single symbol at a specific point in time with institutional filters.
        """
        try:
            if date not in df.index: return None
            
            idx = df.index.get_loc(date)
            if idx < self.rs_window: return None # Need history for RS and averages
            
            # Slice history up to 'today' (avoid look-ahead)
            hist = df.iloc[:idx+1]
            spy_hist = spy_df.iloc[:spy_df.index.get_loc(date)+1] if date in spy_df.index else pd.DataFrame()
            
            current = hist.iloc[-1]
            recent_20 = hist.tail(20)
            
            # --- FILTER 1: PRICE ---
            if current['close'] < self.min_price:
                return None

            # --- FILTER 2: ADR (20) ---
            # ADR % = Average of ((High-Low)/Low) over 20 days
            adr_pct = ((recent_20['high'] - recent_20['low']) / recent_20['low']).mean() * 100
            if adr_pct < self.adr_threshold:
                return None

            # --- FILTER 3: LIQUIDITY (VOLUME & DOLLAR VOLUME) ---
            avg_vol = recent_20['volume'].mean()
            if avg_vol < self.min_avg_vol:
                return None
                
            avg_dollar_vol = (recent_20['close'] * recent_20['volume']).mean()
            if avg_dollar_vol < self.min_dollar_vol:
                return None

            # --- FILTER 4: RELATIVE STRENGTH ---
            if not spy_hist.empty and len(spy_hist) >= self.rs_window:
                stock_perf = (current['close'] / hist.iloc[-self.rs_window]['close']) - 1
                spy_perf = (spy_hist['close'].iloc[-1] / spy_hist['close'].iloc[-self.rs_window]['close']) - 1
                relative_strength = stock_perf - spy_perf
                if relative_strength < 0:
                    return None
            else:
                relative_strength = 0.0

            # --- FILTER 5: STRUCTURE (BREAKOUT) ---
            is_trending = current['close'] > current['sma_20'] and current['sma_20'] > current['sma_50']
            base_high = hist.iloc[-21:-1]['high'].max()
            is_breakout = current['close'] > base_high and current['volume'] > current['sma_volume_20']
            
            if is_trending and is_breakout:
                return {
                    'symbol': symbol,
                    'date': date,
                    'setup': 'INSTITUTIONAL_BREAKOUT',
                    'price': current['close'],
                    'adr_pct': adr_pct,
                    'avg_vol': avg_vol,
                    'avg_dollar_vol': avg_dollar_vol,
                    'rs_value': relative_strength,
                    'entry_trigger': current['high'],
                    'stop_loss': current['low']
                }
            
            return None

        except Exception as e:
            return None