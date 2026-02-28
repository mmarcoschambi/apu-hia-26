"""
Technical Indicators Module
---------------------------
Centralized library for technical indicators to avoid code duplication across engines.
Optimized for both pandas Series/DataFrames and vectorbt applications.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional

class TechnicalIndicators:
    """
    Collection of static methods for calculating technical indicators.
    """

    @staticmethod
    def rvol(volume: Union[pd.Series, pd.DataFrame], 
             period: int = 20, 
             min_periods: Optional[int] = None) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Relative Volume (RVOL).
        RVOL = Volume / SMA(Volume, period)
        
        Args:
            volume: Volume data
            period: Rolling window period (default 20)
            min_periods: Minimum periods for rolling window (default None)
            
        Returns:
            RVOL values
        """
        if min_periods is None:
            min_periods = period
            
        avg_vol = volume.rolling(window=period, min_periods=min_periods).mean()
        
        # Avoid division by zero
        rvol = volume / avg_vol.replace(0, np.nan)
        
        # Handle infinite values and fill NaNs
        rvol = rvol.replace([np.inf, -np.inf], np.nan).fillna(1.0)
        
        return rvol

    @staticmethod
    def daily_range_pct(high: Union[pd.Series, pd.DataFrame], 
                        low: Union[pd.Series, pd.DataFrame], 
                        close: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Daily Range Percentage.
        DR% = (High - Low) / Close * 100
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            
        Returns:
            Daily Range Percentage
        """
        dr_pct = (high - low) / close * 100
        return dr_pct.fillna(0)

    @staticmethod
    def adr(high: Union[pd.Series, pd.DataFrame], 
            low: Union[pd.Series, pd.DataFrame], 
            close: Union[pd.Series, pd.DataFrame],
            period: int = 20) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Average Daily Range (ADR).
        ADR = SMA(Daily Range Percentage, period)
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Rolling window period (default 20)
            
        Returns:
            ADR values
        """
        dr_pct = TechnicalIndicators.daily_range_pct(high, low, close)
        adr = dr_pct.rolling(window=period).mean()
        return adr.fillna(0)

    @staticmethod
    def sma(data: Union[pd.Series, pd.DataFrame], 
            period: int = 20) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Simple Moving Average (SMA).
        
        Args:
            data: Input data (price, volume, etc.)
            period: Rolling window period
            
        Returns:
            SMA values
        """
        return data.rolling(window=period).mean()
        
    @staticmethod
    def ema(data: Union[pd.Series, pd.DataFrame], 
            span: int = 20) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            data: Input data
            span: Span for EMA calculation
            
        Returns:
            EMA values
        """
        return data.ewm(span=span, adjust=False).mean()

    @staticmethod
    def dollar_volume(close: Union[pd.Series, pd.DataFrame],
                      volume: Union[pd.Series, pd.DataFrame],
                      period: Optional[int] = 20) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate Dollar Volume (Liquidity).
        Can be instantaneous (period=None) or average (period=int).
        
        Args:
            close: Close prices
            volume: Volume
            period: Optional rolling window for average dollar volume
            
        Returns:
            Dollar Volume
        """
        dvol = close * volume
        if period:
            return dvol.rolling(window=period).mean()
        return dvol
