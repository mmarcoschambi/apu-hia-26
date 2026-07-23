"""
RVOL Context Integration Module - FIXED VERSION
------------------------------------------------
Implements unified position sizing with RVOL context and multiple filters.
NOW WITH PROPER EPISODIC PIVOT DETECTION.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def integrate_with_unified_position_size(
    entry_price: float,
    stop_price: float,
    price_history: pd.Series,
    volume_history: pd.Series,
    current_rvol: float,
    sma20: float,
    base_risk_dollars: float = 150.0,
    is_high_volatility: bool = False,
    days_to_earnings: int = -1,
    market_regime: str = "SAFE",
    is_overextended: bool = False,
    max_position_value: float = float('inf')
) -> Dict[str, Any]:
    """
    Unified position sizing with RVOL context and multiple filters.
    
    FIXED: Now properly detects Episodic Pivots with strict criteria.
    """
    
    # Calculate base risk per share
    risk_per_share = abs(entry_price - stop_price)
    
    if risk_per_share == 0:
        return {
            'shares': 0,
            'rvol_classification': 'ERROR',
            'rvol_details': 'Zero risk per share',
            'size_reductions': [],
            'original_shares': 0,
            'final_shares': 0,
            'position_value': 0,
            'adjusted_risk': 0,
            'reduction_factor': 0
        }
    
    # Calculate base shares using fixed dollar risk
    base_shares = int(base_risk_dollars / risk_per_share)
    original_shares = base_shares
    
    # Initialize tracking variables
    size_reductions = []
    rvol_classification = 'NORMAL'
    rvol_details = f'RVOL={current_rvol:.2f}x'
    
    # =========================================================================
    # STEP 1: CLASSIFY RVOL CONTEXT
    # =========================================================================
    
    # Check for EPISODIC PIVOT (most bullish setup)
    is_episodic_pivot = False
    
    if current_rvol >= 2.5 and len(price_history) >= 20:  # Need volume AND history
        
        # Requirement 1: Tight consolidation (< 15% range in 20 days)
        price_high = price_history.max()
        price_low = price_history.min()
        price_range = price_high - price_low
        avg_price = price_history.mean()
        consolidation_pct = (price_range / avg_price) * 100
        
        # Requirement 2: Breaking OUT of consolidation (entry near high)
        distance_from_high = ((price_high - entry_price) / price_high) * 100
        is_near_high = distance_from_high < 3.0  # Within 3% of 20d high
        
        # Requirement 3: Price above SMA20 (uptrend)
        is_above_sma20 = (sma20 > 0 and entry_price > sma20)
        
        # Requirement 4: NOT overextended (< 10% above SMA20)
        extension = ((entry_price - sma20) / sma20 * 100) if sma20 > 0 else 100
        is_not_extended = extension < 10.0
        
        # Requirement 5: Volume dried up DURING consolidation, now spiking
        if len(volume_history) >= 20:
            avg_vol_last_10 = volume_history.iloc[-10:].mean()
            avg_vol_prev_10 = volume_history.iloc[-20:-10].mean()
            vol_was_dry = avg_vol_last_10 < (avg_vol_prev_10 * 0.8)  # Volume declined
        else:
            vol_was_dry = False
        
        # ALL REQUIREMENTS MUST BE MET
        if (consolidation_pct < 15.0 and 
            is_near_high and 
            is_above_sma20 and 
            is_not_extended and
            vol_was_dry):
            
            is_episodic_pivot = True
            rvol_classification = 'EPISODIC_PIVOT'
            rvol_details = (f'RVOL={current_rvol:.2f}x, '
                           f'Consolidation={consolidation_pct:.1f}%, '
                           f'Near_High={distance_from_high:.1f}%, '
                           f'Extension={extension:.1f}%')
            
            logger.info(f"[U+1F680] EPISODIC PIVOT DETECTED: {rvol_details}")
    
    # If not Episodic Pivot, check for other contexts
    if not is_episodic_pivot:
        
        # Check if it's a CLIMAX (extended + high volume = top)
        if current_rvol >= 3.0:
            # High volume after big move = likely climax
            if len(price_history) >= 5:
                price_5d_ago = price_history.iloc[-5] if len(price_history) > 5 else price_history.iloc[0]
                momentum_5d = ((entry_price - price_5d_ago) / price_5d_ago * 100) if price_5d_ago > 0 else 0
                
                # If up >10% in 5 days with huge volume = CLIMAX
                if momentum_5d > 10.0:
                    rvol_classification = 'CLIMAX'
                    rvol_details = f'RVOL={current_rvol:.2f}x, Momentum_5d={momentum_5d:.1f}% (EXHAUSTION)'
                else:
                    rvol_classification = 'DANGER'
                    rvol_details = f'RVOL={current_rvol:.2f}x (High Risk - no clear context)'
            else:
                rvol_classification = 'DANGER'
                rvol_details = f'RVOL={current_rvol:.2f}x (High Risk)'
        
        elif current_rvol >= 2.0:
            rvol_classification = 'WARNING'
            rvol_details = f'RVOL={current_rvol:.2f}x (Medium Risk)'
        
        else:
            rvol_classification = 'NORMAL'
            rvol_details = f'RVOL={current_rvol:.2f}x (Normal)'
    
    # =========================================================================
    # STEP 2: APPLY SIZE ADJUSTMENTS BASED ON CLASSIFICATION
    # =========================================================================
    
    if rvol_classification == 'EPISODIC_PIVOT':
        # INCREASE size for confirmed Episodic Pivot (+50% instead of +100%)
        # Conservative multiplier to avoid over-sizing
        base_shares = int(base_shares * 1.5)  # +50% size
        size_reductions.append('EPISODIC_PIVOT: +50% size')
    
    elif rvol_classification == 'CLIMAX':
        # DRASTICALLY reduce for climax tops
        base_shares = int(base_shares * 0.15)  # Keep only 15%
        size_reductions.append('CLIMAX_TOP: -85%')
    
    elif rvol_classification == 'DANGER':
        # Reduce for dangerous high volume
        base_shares = int(base_shares * 0.25)  # -75%
        size_reductions.append('RVOL_DANGER: -75%')
    
    elif rvol_classification == 'WARNING':
        # Moderate reduction
        base_shares = int(base_shares * 0.5)  # -50%
        size_reductions.append('RVOL_WARNING: -50%')
    
    # No adjustment for NORMAL
    
    # =========================================================================
    # STEP 3: APPLY OTHER FILTERS (AFTER RVOL adjustment)
    # =========================================================================
    
    # High volatility filter
    if is_high_volatility:
        base_shares = int(base_shares * 0.5)  # -50% (not -75%, already adjusted by RVOL)
        size_reductions.append('HIGH_VOLATILITY(ADR>6%): -50%')
    
    # Earnings filter
    if 0 <= days_to_earnings < 5:
        base_shares = int(base_shares * 0.5)  # -50% (not -75%)
        size_reductions.append(f'EARNINGS_RISK({days_to_earnings}d): -50%')
    
    # Market regime filter - IMPLEMENTING SEMÁFORO (VolTrig) LOGIC
    # REDUCE RISK TO $75 IF SPX < EMA20 (Danger)
    if market_regime == "DANGER":
        # Reduce risk to $75 (half size) when market is in danger mode
        reduced_risk_dollars = base_risk_dollars / 2  # $150 -> $75
        # Recalculate shares based on reduced risk
        base_shares = int(reduced_risk_dollars / risk_per_share)
        size_reductions.append('MARKET_DANGER: Half Risk ($150->$75)')
    elif market_regime == "SAFE":
        # Keep full $150 risk when market is safe
        size_reductions.append('MARKET_SAFE: Full Risk ($150)')
    
    # Overextension filter
    if is_overextended:
        base_shares = int(base_shares * 0.5)  # -50%
        size_reductions.append('OVEREXTENDED(>7%SMA20): -50%')
    
    # =========================================================================
    # STEP 4: APPLY CAPS AND MINIMUMS
    # =========================================================================
    
    # Ensure minimum 1 share if we had shares before
    if base_shares == 0 and original_shares > 0:
        base_shares = 1
        size_reductions.append('MIN_SHARE_CAP: 0->1')
    
    # Apply max position size constraint
    position_value = base_shares * entry_price
    if position_value > max_position_value:
        base_shares = int(max_position_value / entry_price)
        size_reductions.append(f'MAX_POSITION_CAP: ${position_value:.0f}->${max_position_value:.0f}')
    
    # Ensure non-negative shares
    base_shares = max(0, base_shares)
    
    # Calculate adjusted risk and reduction factor
    final_risk_dollars = base_shares * risk_per_share
    reduction_factor = final_risk_dollars / base_risk_dollars if base_risk_dollars > 0 else 0
    
    return {
        'shares': base_shares,
        'rvol_classification': rvol_classification,
        'rvol_details': rvol_details,
        'size_reductions': size_reductions,
        'original_shares': original_shares,
        'final_shares': base_shares,
        'position_value': base_shares * entry_price,
        'adjusted_risk': final_risk_dollars,
        'reduction_factor': reduction_factor,
        'is_episodic_pivot': is_episodic_pivot  # NEW: Flag for logging
    }


# Helper function for debugging
def analyze_rvol_context(
    entry_price: float,
    price_history: pd.Series,
    volume_history: pd.Series,
    current_rvol: float,
    sma20: float,
    ticker: str = "UNKNOWN"
) -> str:
    """
    Analyze and return a human-readable explanation of RVOL context.
    Useful for debugging why a trade was/wasn't classified as Episodic Pivot.
    """
    
    if len(price_history) < 20:
        return f"{ticker}: Insufficient history ({len(price_history)}d)"
    
    # Calculate metrics
    price_high = price_history.max()
    price_low = price_history.min()
    price_range = price_high - price_low
    avg_price = price_history.mean()
    consolidation_pct = (price_range / avg_price) * 100
    
    distance_from_high = ((price_high - entry_price) / price_high) * 100
    is_above_sma20 = (sma20 > 0 and entry_price > sma20)
    extension = ((entry_price - sma20) / sma20 * 100) if sma20 > 0 else 0
    
    avg_vol_last_10 = volume_history.iloc[-10:].mean()
    avg_vol_prev_10 = volume_history.iloc[-20:-10].mean()
    vol_change = ((avg_vol_last_10 - avg_vol_prev_10) / avg_vol_prev_10 * 100) if avg_vol_prev_10 > 0 else 0
    
    # Build analysis
    analysis = f"""
{ticker} RVOL Analysis:
+- RVOL: {current_rvol:.2f}x {'[OK]' if current_rvol >= 2.5 else '[FAIL] (need >=2.5x)'}
+- Consolidation: {consolidation_pct:.1f}% {'[OK]' if consolidation_pct < 15 else '[FAIL] (need <15%)'}
+- Near High: {distance_from_high:.1f}% below 20d high {'[OK]' if distance_from_high < 3 else '[FAIL] (need <3%)'}
+- Above SMA20: {'[OK]' if is_above_sma20 else '[FAIL]'}
+- Extension: {extension:.1f}% {'[OK]' if extension < 10 else '[FAIL] (need <10%)'}
+- Volume dried: {vol_change:+.1f}% {'[OK]' if vol_change < -20 else '[FAIL] (need volume decline)'}

Verdict: {'[U+1F680] EPISODIC PIVOT' if all([
    current_rvol >= 2.5,
    consolidation_pct < 15,
    distance_from_high < 3,
    is_above_sma20,
    extension < 10,
    vol_change < -20
]) else '[FAIL] Not Episodic Pivot'}
"""
    
    return analysis.strip()
