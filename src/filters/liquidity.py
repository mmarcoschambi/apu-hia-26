"""
Liquidity Filters Module
------------------------
Centralized logic for filtering assets based on liquidity and volatility metrics.
Used to ensure all engines (THOR, Advanced, V6) use identical filtering standards.
"""

import pandas as pd
import numpy as np
from typing import Union, Optional

class LiquidityFilters:
    """
    Apply liquidity and volatility constraints to generate valid entry masks.
    """

    @staticmethod
    def get_mask(
        # Data Inputs (Series or DataFrames)
        close: Optional[Union[pd.Series, pd.DataFrame]] = None,
        volume: Optional[Union[pd.Series, pd.DataFrame]] = None,
        avg_volume: Optional[Union[pd.Series, pd.DataFrame]] = None,
        dollar_volume: Optional[Union[pd.Series, pd.DataFrame]] = None,
        rvol: Optional[Union[pd.Series, pd.DataFrame]] = None,
        adr: Optional[Union[pd.Series, pd.DataFrame]] = None,
        
        # Thresholds (Scalars)
        min_price: float = 0.0,
        min_volume: float = 0.0,
        min_dollar_volume: float = 0.0,
        min_rvol: float = 0.0,
        min_adr: float = 0.0,
        
        # Configuration
        fillna_value: bool = False
    ) -> Union[pd.Series, pd.DataFrame]:
        """
        Generate a boolean mask where all provided conditions are met.
        Only applies filters for which data AND a threshold (> 0) are provided.
        
        Returns:
            Boolean mask (True = Pass, False = Filtered out)
        """
        # Determine the shape/index from the first available non-None input
        inputs = [x for x in [close, volume, avg_volume, dollar_volume, rvol, adr] if x is not None]
        if not inputs:
            raise ValueError("At least one data input must be provided to generate a mask.")
        
        # Start with a mask of True (Pass all)
        mask = pd.DataFrame(True, index=inputs[0].index, columns=inputs[0].columns) \
               if isinstance(inputs[0], pd.DataFrame) else pd.Series(True, index=inputs[0].index)

        # 1. Price Filter
        if close is not None and min_price > 0:
            mask &= (close >= min_price)

        # 2. Volume Filter (Instantaneous or Average)
        # Note: Usually we filter by Average Volume for universe selection, 
        # but some logic might check current volume.
        if volume is not None and min_volume > 0:
             mask &= (volume >= min_volume)
             
        if avg_volume is not None and min_volume > 0:
             mask &= (avg_volume >= min_volume)

        # 3. Dollar Volume Filter
        # If pre-calculated dollar_volume is passed
        if dollar_volume is not None and min_dollar_volume > 0:
            mask &= (dollar_volume >= min_dollar_volume)
        # Or calculate it on the fly if close/avg_volume are available
        elif close is not None and avg_volume is not None and min_dollar_volume > 0:
            dvol = close * avg_volume
            mask &= (dvol >= min_dollar_volume)

        # 4. RVOL Filter
        if rvol is not None and min_rvol > 0:
            mask &= (rvol >= min_rvol)

        # 5. ADR Filter
        if adr is not None and min_adr > 0:
            mask &= (adr >= min_adr)

        # Handle NaNs (usually False, as NaN means missing data -> unsafe to trade)
        if fillna_value:
             mask = mask.fillna(True)
        else:
             mask = mask.fillna(False)

        return mask
