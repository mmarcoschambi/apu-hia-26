"""
Institutional Screener - Deterministic Scanning Logic
-----------------------------------------------------
Filters candidates based on:
1. Volatility: ADR(20) > threshold (default 1.5%)
2. Liquidity: Avg Volume > 300k AND Avg Dollar Volume > $15M
3. Quality: Price > $5
4. Relative Volume: RVOL > threshold (default 1.5x)
5. Relative Strength: Outperforming SPY (50 days)
6. Structure: Base Breakout
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
                 rs_window: int = 50,
                 min_rvol: float = 1.5):
        self.adr_threshold = adr_threshold
        self.min_price = min_price
        self.min_avg_vol = min_avg_vol
        self.min_dollar_vol = min_dollar_vol
        self.rs_window = rs_window
        self.min_rvol = min_rvol

    def scan(self, symbol: str, df: pd.DataFrame, spy_df: pd.DataFrame, date: pd.Timestamp) -> Optional[Dict]:
        """
        Scan a single symbol (Standard Mode) - Returns Dict if pass, None if fail.
        """
        res, _ = self.scan_verbose(symbol, df, spy_df, date)
        return res

    def scan_verbose(self, symbol: str, df: pd.DataFrame, spy_df: pd.DataFrame, date: pd.Timestamp) -> tuple[Optional[Dict], str]:
        """
        Scan with verbose output for debugging.
        Returns: (ResultDict or None, RejectionReason)
        """
        try:
            if date not in df.index: return None, "No Data for Date"
            
            idx = df.index.get_loc(date)
            if idx < self.rs_window: return None, "Not Enough History"
            
            # Slice history up to 'today'
            hist = df.iloc[:idx+1]
            spy_hist = spy_df.iloc[:spy_df.index.get_loc(date)+1] if date in spy_df.index else pd.DataFrame()
            
            current = hist.iloc[-1]
            recent_20 = hist.tail(20)
            
            # --- FILTER 1: PRICE ---
            if current['close'] < self.min_price:
                return None, f"Price ${current['close']:.2f} < ${self.min_price}"

            # --- FILTER 2: ADR (20) ---
            adr_pct = ((recent_20['high'] - recent_20['low']) / recent_20['low']).mean() * 100
            if adr_pct < self.adr_threshold:
                return None, f"Low ADR: {adr_pct:.2f}% < {self.adr_threshold}%"

            # --- FILTER 3: LIQUIDITY ---
            avg_vol = recent_20['volume'].mean()
            if avg_vol < self.min_avg_vol:
                return None, f"Low Vol: {avg_vol/1000:.0f}k < {self.min_avg_vol/1000:.0f}k"
                
            avg_dollar_vol = (recent_20['close'] * recent_20['volume']).mean()
            if avg_dollar_vol < self.min_dollar_vol:
                return None, f"Low $Vol: ${avg_dollar_vol/1e6:.1f}M < ${self.min_dollar_vol/1e6:.1f}M"

            # --- FILTER 3B: RVOL (RELATIVE VOLUME) ---
            # Calculate RVOL: Current volume vs 20-day average (excluding current bar)
            if len(hist) >= 21:
                prior_bars = hist.iloc[:-1]  # Exclude current bar
                avg_vol_20 = prior_bars['volume'].tail(20).mean()
                rvol = current['volume'] / avg_vol_20 if avg_vol_20 > 0 else 0
                if rvol < self.min_rvol:
                    return None, f"Low RVOL: {rvol:.2f}x < {self.min_rvol}x"
            else:
                rvol = 0
                return None, "Insufficient history for RVOL calculation"

            # --- FILTER 4: RELATIVE STRENGTH ---
            if not spy_hist.empty and len(spy_hist) >= self.rs_window:
                stock_perf = (current['close'] / hist.iloc[-self.rs_window]['close']) - 1
                spy_perf = (spy_hist['close'].iloc[-1] / spy_hist.iloc[-self.rs_window]['close']) - 1
                relative_strength = stock_perf - spy_perf
                if relative_strength < 0:
                    return None, f"Weak RS: {relative_strength:.4f} vs SPY"
            else:
                pass # Skip RS if no SPY data

            # --- FILTER 5: STRUCTURE (BREAKOUT) ---
            # Trend Check
            is_trending = current['close'] > current['sma_20'] and current['sma_20'] > current['sma_50']
            if not is_trending:
                return None, "Not in Uptrend (Price < SMA20 or SMA20 < SMA50)"

            # Breakout Check
            base_high = hist.iloc[-21:-1]['high'].max()
            is_breakout = current['close'] > base_high
            # Volume confirmation
            vol_confirm = current['volume'] > current['sma_volume_20']
            
            if not is_breakout:
                return None, "No Breakout (Price < 20d High)"
            
            if not vol_confirm:
                return None, "No Volume Confirmation"
            
            return {
                'symbol': symbol,
                'date': date,
                'setup': 'INSTITUTIONAL_BREAKOUT',
                'price': current['close'],
                'adr_pct': adr_pct,
                'avg_vol': avg_vol,
                'avg_dollar_vol': avg_dollar_vol,
                'rvol': rvol,
                'rs_value': 0.0, # Placeholder or calc above
                'entry_trigger': current['high'],
                'stop_loss': current['low']
            }, "OK"

        except Exception as e:
            return None, f"Error: {str(e)}"