"""
Position Sizing Module
----------------------
Centralized logic for calculating position sizes based on risk, volatility (RVOL),
and portfolio constraints.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional, Tuple

class PositionSizer:
    """
    Calculates optimal position sizes respecting risk limits and market conditions.
    """

    @staticmethod
    def get_fixed_risk_size(
        close: Union[pd.Series, pd.DataFrame],
        risk_dollars: float,
        stop_pct: float,
        min_stop_pct: float = 3.0
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        Calculate position value based on Fixed Dollar Risk.
        Position Value = (Risk $ / Stop %)
        
        Args:
            close: Price data
            risk_dollars: Amount to risk per trade (e.g., $150)
            stop_pct: Stop loss percentage (e.g., 7.0 for 7%)
            min_stop_pct: Minimum stop percentage to avoid huge sizing on tight stops
            
        Returns:
            Position Value ($)
        """
        # Ensure stop_pct is decimal (if passed as > 1, assume percent)
        # However, standard across this codebase seems to be converting dynamically.
        # Let's assume input is in Percentage (0-100) or decimal. 
        # For safety, we enforce a minimum stop width.
        
        # NOTE: Existing code often passes 'max_stop_pct' as the stop distance.
        # We calculate: Stop Distance ($) = Close * (Stop% / 100)
        # Shares = Risk / Stop Distance
        # Value = Shares * Close = Risk / (Stop% / 100)
        
        # Effective stop percentage (max of provided or minimum safety)
        # Note: np.maximum works with DataFrames/Series vs Scalar
        effective_stop_pct = np.maximum(stop_pct, min_stop_pct)
        
        # Prepare denominator (Stop % / 100)
        denominator = effective_stop_pct / 100.0
        
        # Handle division by zero vectorially
        if isinstance(denominator, (pd.DataFrame, pd.Series)):
            # Replace 0 with NaN to avoid ZeroDivisionError, then fillna(inf) or handle after
            denominator = denominator.replace(0, np.nan)
        elif denominator == 0:
            return 0.0
            
        # Formula: Size ($) = Risk ($) / (Stop % / 100)
        position_value = risk_dollars / denominator
        
        if isinstance(close, (pd.Series, pd.DataFrame)):
            if not isinstance(position_value, (pd.Series, pd.DataFrame)):
                # Broadcast scalar result to shape of close
                position_value = pd.DataFrame(position_value, index=close.index, columns=close.columns) \
                                 if isinstance(close, pd.DataFrame) else pd.Series(position_value, index=close.index)
                             
            # Replace infinities/NaNs resulting from zero division
            position_value = position_value.replace([np.inf, -np.inf], 0).fillna(0)
            
        return position_value

    @staticmethod
    def apply_rvol_adjustment(
        position_value: Union[pd.Series, pd.DataFrame],
        rvol: Union[pd.Series, pd.DataFrame],
        warning_level: float = 2.0,
        danger_level: float = 3.0,
        warning_size: float = 0.60,
        danger_size: float = 0.25
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        Scale down position size based on Relative Volume (RVOL) extremes.
        High RVOL -> Higher volatility/risk -> Smaller position.
        
        Args:
            position_value: Base position value ($)
            rvol: RVOL data
            warning_level: RVOL threshold for initial reduction
            danger_level: RVOL threshold for drastic reduction
            warning_size: Multiplier for warning zone (e.g., 0.6 = 60% size)
            danger_size: Multiplier for danger zone (e.g., 0.25 = 25% size)
            
        Returns:
            Adjusted Position Value ($)
        """
        if rvol is None:
            return position_value
            
        # Create multiplier mask (default 1.0)
        if isinstance(position_value, pd.DataFrame):
            multiplier = pd.DataFrame(1.0, index=position_value.index, columns=position_value.columns)
        else:
            multiplier = pd.Series(1.0, index=position_value.index)
            
        # Apply reductions
        # Logic: If RVOL >= Danger -> Danger Size
        #        Elif RVOL >= Warning -> Warning Size
        #        Else -> 1.0
        
        # Note: Vectorized 'where' replaces values where condition is FALSE.
        # So: multiplier.where(rvol < danger, danger_size) keeps 1.0 where rvol < danger, sets danger_size where rvol >= danger
        
        # 1. Apply Warning (Medium Risk)
        # Anything above warning gets reduced
        multiplier = multiplier.where(rvol < warning_level, warning_size)
        
        # 2. Apply Danger (High Risk) - Overwrites Warning if strictly higher
        multiplier = multiplier.where(rvol < danger_level, danger_size)
        
        return position_value * multiplier

    @staticmethod
    def apply_exposure_limit(
        position_value: Union[pd.Series, pd.DataFrame],
        capital: float,
        max_exposure_pct: float
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        Clip position size to maximum allowed portfolio exposure per trade.
        
        Args:
            position_value: Input position value
            capital: Total portfolio capital
            max_exposure_pct: Max % of capital per trade (e.g., 0.25 for 25%%)
            
        Returns:
            Clipped Position Value ($)
        """
        max_dollars = capital * max_exposure_pct
        return position_value.clip(upper=max_dollars)

