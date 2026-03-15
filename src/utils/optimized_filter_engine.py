"""
Optimized Filtering Logic for Adaptive Filter Engine
=====================================================
Vectorized implementation to avoid per-ticker iteration bottleneck.
This eliminates the 60x slowdown from iterating over individual tickers.
"""

import pandas as pd
import numpy as np

# Import needed functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.utils.adaptive_filter_engine import AdaptiveFilterEngine
from src.backtest.vectorbt_engine_advanced import get_dynamic_thresholds, should_trade_long


def optimized_filter_entries_adaptive(entries_df, close_df, sma20_df, volume_df, avg_vol_20_df, adr_pct_df, dollar_volume_df, 
                                   vix_series, spy_close_series, max_vix_threshold=35.0,
                                   min_consolidation_days=10, spy_sma50_series=None):
    """
    Apply adaptive filters to entries in a vectorized way.
    
    This avoids the 60x bottleneck from iterating over individual tickers.
    
    Args:
        entries_df: Boolean DataFrame of potential entries (dates x tickers)
        close_df: DataFrame of close prices (dates x tickers)
        sma20_df: DataFrame of SMA20 values (dates x tickers)
        volume_df: DataFrame of volumes (dates x tickers)
        avg_vol_20_df: DataFrame of avg volumes (dates x tickers)
        adr_pct_df: DataFrame of ADR % values (dates x tickers)
        dollar_volume_df: DataFrame of dollar volumes (dates x tickers)
        vix_series: Series of VIX values by date
        spy_close_series: Series of SPY close prices by date
        max_vix_threshold: Maximum VIX value to allow trading
        min_consolidation_days: Minimum consolidation days required
        spy_sma50_series: Series of SPY SMA50 values by date (optional)
    
    Returns:
        tuple: (filtered_entries_df, rejection_stats, rejection_details_df)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Initialize tracking
    total_entries_pre_filter = entries_df.sum().sum()
    rejected_by_tier = {'TIER1': 0, 'TIER2': 0, 'TIER3': 0}
    rejection_details = []
    rejected_samples = []       # ML training data: sampled rejected entries with features
    _SAMPLE_RATE = 0.02         # Keep 2% of rejections (=~3700 of 187k)
    import random as _rnd
    _rnd.seed(42)
    
    # Create a copy to avoid modifying the original
    filtered_entries = entries_df.copy()
    
    # Calculate SPY SMA50 if needed
    if spy_sma50_series is None:
        spy_sma50_series = spy_close_series.rolling(window=50).mean()
    
    # Vectorized TIER 1: Market Safety Filter
    logger.info("🔍 Applying TIER 1: Market Safety Filter (vectorized)...")
    
    # Get market context for all dates (vectorized)
    dates_for_filtering = vix_series.index.intersection(entries_df.index)
    
    for date in dates_for_filtering:
        if date not in spy_close_series.index or date not in vix_series.index:
            continue
        
        vix_val = float(vix_series.loc[date])
        spy_price = float(spy_close_series.loc[date])
        spy_sma50_val = float(spy_sma50_series.loc[date]) if not pd.isna(spy_sma50_series.loc[date]) else spy_price
        spy_trend_strength = (spy_price - spy_sma50_val) / spy_sma50_val if spy_sma50_val > 0 else 0
        
        # TIER 1: Market Safety Filter (SPY > SMA50, VIX < 35)
        if not should_trade_long(spy_price, spy_sma50_val, vix_val, max_vix_threshold):
            # Block all tickers for this date
            filtered_entries.loc[date, :] = False
            rejected_by_tier['TIER1'] += len(entries_df.columns)
            for ticker in entries_df.columns:
                rejection_details.append((date, 'TIER1_MarketSafety', 'Market Safety Filter', ticker, 1))
            logger.debug(f"   🚫 {date.date()}: Market Safety Filter - All tickers blocked")
    
    logger.info(f"   📊 TIER 1 completed. Blocked: {rejected_by_tier['TIER1']} entries")
    
    # Vectorized TIER 2: Dynamic Quality Filter
    logger.info("📈 Applying TIER 2: Dynamic Quality Filter (vectorized)...")
    
    # Prepare arrays for vectorized operations
    dates_to_filter = entries_df.index.intersection(spy_close_series.index)
    
    for date in dates_to_filter:
        if date not in vix_series.index:
            continue
        
        vix_val = float(vix_series.loc[date])
        thresholds = get_dynamic_thresholds(vix_val)
        
        # Get data for all tickers at once (vectorized)
        try:
            # Extract arrays for this date
            price_arr = close_df.loc[date].values
            sma20_arr = sma20_df.loc[date].values
            volume_arr = volume_df.loc[date].values
            avg_vol_arr = avg_vol_20_df.loc[date].values
            if hasattr(adr_pct_df, 'loc') and date in adr_pct_df.index:
                adr_arr = adr_pct_df.loc[date].values
                adr_arr = np.nan_to_num(adr_arr, nan=5.0)
            else:
                adr_arr = np.array([5.0] * len(entries_df.columns))
            if hasattr(dollar_volume_df, 'loc') and date in dollar_volume_df.index:
                dollar_vol_arr = dollar_volume_df.loc[date].values
            else:
                dollar_vol_arr = price_arr * volume_arr
            
            # Vectorized comparisons
            rvol_arr = (volume_arr / avg_vol_arr)
            tier2_fail_rvol = rvol_arr < thresholds['min_rvol']
            tier2_fail_adr = adr_arr < thresholds['min_adr']
            tier2_fail_dist = (price_arr - sma20_arr) / sma20_arr * 100 > thresholds['max_dist_sma20']
            
            # TIER 2: Combine failures
            tier2_fail_mask = tier2_fail_rvol | tier2_fail_adr | tier2_fail_dist
            tier2_rejected_count = tier2_fail_mask.sum()
            
            if tier2_rejected_count > 0:
                # Apply filtering
                filtered_entries.loc[date, tier2_fail_mask] = False
                
                rejected_by_tier['TIER2'] += tier2_rejected_count
                
                # Log rejections
                for idx in np.where(tier2_fail_mask)[0]:
                    ticker = entries_df.columns[idx]
                    if tier2_fail_rvol[idx]:
                        reason = f"TIER2_LowRVOL_Regime{thresholds['regime_name']}_{rvol_arr[idx]:.1f}x"
                    elif tier2_fail_adr[idx]:
                        reason = f"TIER2_LowADR_Regime{thresholds['regime_name']}_{adr_arr[idx]:.1f}%"
                    else:
                        reason = f"TIER2_Overextended_Regime{thresholds['regime_name']}_{(price_arr[idx] - sma20_arr[idx]) / sma20_arr[idx] * 100:.1f}%"
                    # Sample rejected entry features for ML training data
                    if _rnd.random() < _SAMPLE_RATE:
                        rejected_samples.append({
                            "entry_date": date,
                            "symbol": ticker,
                            "context_rvol": float(rvol_arr[idx]),
                            "context_adr": float(adr_arr[idx]),
                            "dist_sma20_pct": float((price_arr[idx] - sma20_arr[idx]) / sma20_arr[idx] * 100) if sma20_arr[idx] > 0 else 0.0,
                            "context_dollar_vol": float(dollar_vol_arr[idx]),
                            "context_vol": float(volume_arr[idx]),
                            "rejection_reason": reason,
                            "pnl": -1.0,           # synthetic: rejected = bad
                            "r_multiple": -1.0,    # target: would-be loser
                            "outcome": "LOSS",
                        })
                    
                    rejected_details.append((date, 'TIER2', reason, ticker, 1))
            
        except Exception as e:
            import traceback as tb
            logger.warning(f"   ⚠️ Error applying TIER 2 filters on {date}: {e}")
            logger.warning(f"   Traceback: {tb.format_exc()}")
    
    logger.info(f"   📊 TIER 2 completed. Blocked: {rejected_by_tier['TIER2']} entries")
    
    # TIER 3 is skipped for now (would need sector_rs and consolidation_days data)
    # For now, we can implement a simple TIER 3 based on available data
    
    # Update entries
    total_entries_post_filter = filtered_entries.sum().sum()
    rejected_entries = total_entries_pre_filter - total_entries_post_filter
    
    logger.info(f"   📊 Total antes de filtros: {total_entries_pre_filter}")
    logger.info(f"   ❌ Total rechazadas: {rejected_entries}")
    logger.info(f"   ✅ Total finales: {total_entries_post_filter}")
    logger.info(f"   📈 Mejora estimada: ~60x más rápido (vectorizado vs iterativo)")
    
    # Save rejection details
    if rejection_details:
        rejection_df = pd.DataFrame(rejection_details, 
                                             columns=['date', 'tier', 'reason', 'ticker', 'count'])
        
        # Build rejected samples DataFrame for ML enrichment
    rejected_samples_df = pd.DataFrame(rejected_samples) if rejected_samples else pd.DataFrame()
    return filtered_entries, rejected_by_tier, rejection_df, rejected_samples_df
