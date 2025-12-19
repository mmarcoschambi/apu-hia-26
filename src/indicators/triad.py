"""
Triad Indicators - The Three Forces
1. Base Detection (El Mapa)
2. AVWAP from ATH (El Peaje)
3. Intraday VWAP (El Pedal)
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class TriadIndicators:
    
    @staticmethod
    def detect_base(df: pd.DataFrame, lookback: int = 20) -> dict:
        """
        Detect consolidation base (El Mapa)
        Returns base high/low and compression metrics
        """
        if df.empty or len(df) < lookback:
            return {'detected': False}
        
        recent = df.tail(lookback)
        
        # Calculate range compression
        range_high = recent['High'].max()
        range_low = recent['Low'].min()
        range_pct = (range_high - range_low) / range_low
        
        # Detect if we're near the highs (compression at top)
        current_price = df['Close'].iloc[-1]
        distance_from_high = (range_high - current_price) / current_price
        
        # Base is valid if range is tight and price is near highs
        is_compressed = range_pct < 0.15  # Within 15% range
        near_highs = distance_from_high < 0.03  # Within 3% of base high
        
        return {
            'detected': is_compressed and near_highs,
            'base_high': range_high,
            'base_low': range_low,
            'compression_pct': range_pct,
            'distance_from_high_pct': distance_from_high,
            'current_price': current_price
        }
    
    @staticmethod
    def calculate_avwap_from_ath(df: pd.DataFrame) -> dict:
        """
        Calculate Anchored VWAP from All-Time High (El Peaje)
        This is where old bag holders are trapped
        """
        if df.empty:
            return {'calculated': False}
        
        # Find ATH
        ath_idx = df['High'].idxmax()
        ath_price = df.loc[ath_idx, 'High']
        
        # Calculate AVWAP from ATH forward
        df_from_ath = df.loc[ath_idx:]
        
        if len(df_from_ath) < 2:
            return {
                'calculated': False,
                'ath_price': ath_price,
                'ath_date': ath_idx
            }
        
        # AVWAP calculation: cumulative (volume * typical_price) / cumulative volume
        typical_price = (df_from_ath['High'] + df_from_ath['Low'] + df_from_ath['Close']) / 3
        cumulative_vp = (typical_price * df_from_ath['Volume']).cumsum()
        cumulative_vol = df_from_ath['Volume'].cumsum()
        
        avwap = cumulative_vp / cumulative_vol
        current_avwap = avwap.iloc[-1]
        
        return {
            'calculated': True,
            'ath_price': ath_price,
            'ath_date': ath_idx,
            'current_avwap': current_avwap,
            'current_price': df['Close'].iloc[-1],
            'distance_to_avwap_pct': (current_avwap - df['Close'].iloc[-1]) / df['Close'].iloc[-1]
        }
    
    @staticmethod
    def calculate_intraday_vwap(df_intraday: pd.DataFrame) -> dict:
        """
        Calculate Intraday VWAP (El Pedal)
        Reset daily - confirms institutional flow
        """
        if df_intraday.empty:
            return {'calculated': False}
        
        # Get today's session only
        today = df_intraday.index[-1].date()
        df_today = df_intraday[df_intraday.index.date == today]
        
        if df_today.empty:
            return {'calculated': False}
        
        # Calculate VWAP for today's session
        typical_price = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
        cumulative_vp = (typical_price * df_today['Volume']).cumsum()
        cumulative_vol = df_today['Volume'].cumsum()
        
        vwap = cumulative_vp / cumulative_vol
        current_vwap = vwap.iloc[-1]
        current_price = df_today['Close'].iloc[-1]
        
        # Detect if price is above/below VWAP
        above_vwap = current_price > current_vwap
        
        # Detect recent cross (last 2 candles)
        if len(vwap) >= 2:
            prev_price = df_today['Close'].iloc[-2]
            prev_vwap = vwap.iloc[-2]
            
            crossed_up = (prev_price <= prev_vwap) and (current_price > current_vwap)
            crossed_down = (prev_price >= prev_vwap) and (current_price < current_vwap)
        else:
            crossed_up = False
            crossed_down = False
        
        return {
            'calculated': True,
            'current_vwap': current_vwap,
            'current_price': current_price,
            'above_vwap': above_vwap,
            'crossed_up': crossed_up,
            'crossed_down': crossed_down,
            'distance_pct': (current_price - current_vwap) / current_vwap,
            'session_open': df_today['Open'].iloc[0],
            'session_high': df_today['High'].max(),
            'session_low': df_today['Low'].min()
        }
    
    @staticmethod
    def detect_gap_down(df_intraday: pd.DataFrame, previous_close: float) -> dict:
        """
        Detect gap down at market open (for Camino 2)
        """
        if df_intraday.empty:
            return {'detected': False}
        
        today = df_intraday.index[-1].date()
        df_today = df_intraday[df_intraday.index.date == today]
        
        if df_today.empty:
            return {'detected': False}
        
        session_open = df_today['Open'].iloc[0]
        gap_pct = (session_open - previous_close) / previous_close
        
        is_gap_down = gap_pct < -0.005  # At least -0.5% gap
        
        return {
            'detected': is_gap_down,
            'gap_pct': gap_pct,
            'session_open': session_open,
            'previous_close': previous_close
        }
