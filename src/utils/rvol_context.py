"""
RVOL Context Integration Module
-------------------------------
Implements unified position sizing with RVOL context and multiple filters.
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
    
    Args:
        entry_price: Entry price for the position
        stop_price: Stop loss price
        price_history: Last 30 days of price data
        volume_history: Last 30 days of volume data
        current_rvol: Current relative volume
        sma20: 20-day simple moving average
        base_risk_dollars: Base risk amount per trade ($150 default)
        is_high_volatility: Whether the stock is in high volatility mode
        days_to_earnings: Days to next earnings (-1 if no earnings)
        market_regime: Current market regime ("SAFE", "DANGER", etc.)
        is_overextended: Whether the stock is overextended (>7% above SMA20)
        max_position_value: Maximum allowed position value
    
    Returns:
        Dict with position size and context information
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
    
    # Determine RVOL classification
    if current_rvol >= 4.0:
        rvol_classification = 'INSTITUTIONAL'
        rvol_details += ' (Institutional Breakout)'
    elif current_rvol >= 3.0:
        rvol_classification = 'DANGER'
        rvol_details += ' (High Risk)'
    elif current_rvol >= 2.0:
        rvol_classification = 'WARNING'
        rvol_details += ' (Medium Risk)'
    else:
        rvol_classification = 'NORMAL'
        rvol_details += ' (Normal)'
    
    # Apply size adjustments based on classification
    if rvol_classification == 'INSTITUTIONAL':
        # For institutional breakouts, check for consolidation pattern
        if len(price_history) >= 20:
            # Check for consolidation in last 20 days (low volatility)
            price_range = price_history.max() - price_history.min()
            avg_price = price_history.mean()
            consolidation_pct = (price_range / avg_price) * 100
            
            if consolidation_pct < 10.0:  # Tight consolidation
                # This is likely an episodic pivot - increase size
                #base_shares = int(base_shares * 2.0)  # Double the size
                base_shares = int(base_shares * 1.0)  # Double the size
                size_reductions.append(f'EPISODIC_PIVOT_DETECTED (no size change)')
                rvol_details += f', Episodic Pivot (consolidation={consolidation_pct:.1f}%)'
    
    elif rvol_classification == 'DANGER':
        # Reduce size for danger level RVOL
        base_shares = int(base_shares * 0.25)  # 75% reduction
        size_reductions.append('RVOL_DANGER: -75%')
    
    elif rvol_classification == 'WARNING':
        # Reduce size for warning level RVOL
        base_shares = int(base_shares * 0.5)  # 50% reduction
        size_reductions.append('RVOL_WARNING: -50%')
    
    # Apply high volatility filter
    if is_high_volatility:
        base_shares = int(base_shares * 0.25)  # 75% reduction
        size_reductions.append('HIGH_VOLATILITY: -75%')
    
    # Apply earnings filter
    if 0 <= days_to_earnings < 5:  # Earnings within 5 days
        base_shares = int(base_shares * 0.25)  # 75% reduction
        size_reductions.append(f'EARNINGS_RISK({days_to_earnings}d): -75%')
    
    # Apply market regime filter
    if market_regime == "DANGER":
        base_shares = int(base_shares * 0.5)  # 50% reduction
        size_reductions.append('MARKET_DANGER: -50%')
    
    # Apply overextension filter
    if is_overextended:
        base_shares = int(base_shares * 0.5)  # 50% reduction
        size_reductions.append('OVEREXTENDED: -50%')
    
    # Ensure minimum 1 share if we had shares before
    if base_shares == 0 and original_shares > 0:
        base_shares = 1
        size_reductions.append('MIN_SHARE_ADJUSTMENT: 0→1')
    
    # Apply max position size constraint
    position_value = base_shares * entry_price
    if position_value > max_position_value:
        base_shares = int(max_position_value / entry_price)
        size_reductions.append(f'MAX_POSITION_CAP: {position_value:.0f}→{max_position_value:.0f}')
    
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
        'adjusted_risk': final_risk_dollars,  # NEW
        'reduction_factor': reduction_factor  # NEW
    }
