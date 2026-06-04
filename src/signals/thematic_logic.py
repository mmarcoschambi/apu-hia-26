import pandas as pd
import numpy as np
from typing import List, Dict, Optional

def calculate_equal_weighted_index(
    prices_df: pd.DataFrame, 
    members: List[str], 
    min_members: Optional[int] = 2
) -> pd.Series:
    """
    Calculates an equal-weighted index for a set of member tickers.
    
    Args:
        prices_df: DataFrame with date as index and tickers as columns.
        members: List of tickers to include in the index.
        min_members: Minimum number of members required to have data on a given day.
                    If None, it uses min(5, len(members)).
        
    Returns:
        pd.Series: The cumulative index starting at 100.
    """
    valid_members = [m for m in members if m in prices_df.columns]
    if not valid_members:
        return pd.Series(dtype=float)
        
    # Dynamic min_members if not provided
    if min_members is None:
        actual_min = min(5, len(valid_members))
    else:
        actual_min = min_members
        
    # Check if we have enough members reporting data for each day
    valid_days = prices_df[valid_members].notna().sum(axis=1) >= actual_min
    
    returns = prices_df[valid_members].pct_change()
    # First valid day should have 0 return for the index to start at 100
    first_valid_idx = valid_days.idxmax() if valid_days.any() else None
    if first_valid_idx is not None:
        # If the first valid day is the very first day of the DataFrame, 
        # pct_change() will be NaN, so we fill it with 0 to start the index.
        returns.loc[first_valid_idx] = returns.loc[first_valid_idx].fillna(0)
    
    # Calculate mean return per day
    theme_rets = returns.mean(axis=1)
    theme_rets[~valid_days] = np.nan
    
    # Cumulative index starting at 100
    theme_index = (1 + theme_rets.fillna(0)).cumprod() * 100
    
    # If a day had no valid data, set index to NaN
    theme_index[theme_rets.isna()] = np.nan
    
    return theme_index

def evaluate_variant_e(
    theme_index: pd.Series,
    sector_prices: Optional[pd.Series] = None,
    sma_period: int = 20
) -> Dict:
    """
    Evaluates Variant E: Theme Strong (Index > SMA20) AND Sector Weak (ETF <= SMA20).
    
    Args:
        theme_index: Series of the thematic index.
        sector_prices: Series of the sector ETF prices.
        sma_period: Period for SMA calculation.
        
    Returns:
        Dict with metrics and acceptance decision.
    """
    results = {
        "variant_e_accepted": False,
        "theme_above_sma": False,
        "theme_dist": 0.0,
        "sector_ok": True, # Default to True so divergence fails if no sector data
        "sector_dist": 0.0,
        "theme_vs_sector_20d": 0.0
    }
    
    if len(theme_index) < sma_period:
        return results
        
    # Theme metrics
    t_sma = theme_index.rolling(sma_period).mean().iloc[-1]
    t_current = theme_index.iloc[-1]
    results["theme_dist"] = (t_current / t_sma) - 1 if t_sma > 0 else 0
    results["theme_above_sma"] = t_current > t_sma
    
    # Sector metrics
    if sector_prices is not None and len(sector_prices) >= sma_period:
        # Align series to ensure same dates if needed, but here we assume latest is same
        s_sma = sector_prices.rolling(sma_period).mean().iloc[-1]
        s_current = sector_prices.iloc[-1]
        results["sector_ok"] = s_current > s_sma
        results["sector_dist"] = (s_current / s_sma) - 1 if s_sma > 0 else 0
        
        # Relative strength 20d
        if len(theme_index) >= 21 and len(sector_prices) >= 21:
            t_ret_20d = (theme_index.iloc[-1] / theme_index.iloc[-21]) - 1
            s_ret_20d = (sector_prices.iloc[-1] / sector_prices.iloc[-21]) - 1
            results["theme_vs_sector_20d"] = t_ret_20d - s_ret_20d
            
    # Variant E decision
    results["variant_e_accepted"] = results["theme_above_sma"] and not results["sector_ok"]
    
    return results
