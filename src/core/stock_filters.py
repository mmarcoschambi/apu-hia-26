"""
Stock Quality Filters
Filters stocks by liquidity, volatility, and trend before analyzing setups

FILTERS:
1. Liquidity: Avg Volume(20) * Price > $100M
2. Volatility: ADR(14) > 4%
3. Trend: Price > SMA50 > SMA200
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class StockFilters:
    """Pre-trade quality filters"""
    
    def __init__(self,
                 min_dollar_volume: float = 100_000_000,  # $100M
                 min_adr_pct: float = 2.5,                # 2.5% (more realistic)
                 require_trend_alignment: bool = True):
        """
        Initialize filters
        
        Args:
            min_dollar_volume: Minimum avg daily dollar volume ($100M default)
            min_adr_pct: Minimum ADR percentage (2.5% default, 4% for high vol stocks)
            require_trend_alignment: Require Price > SMA50 > SMA200
        """
        self.min_dollar_volume = min_dollar_volume
        self.min_adr_pct = min_adr_pct
        self.require_trend_alignment = require_trend_alignment
    
    def passes_all_filters(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict:
        """
        Check if stock passes ALL quality filters
        
        Returns dict with:
        - passed: bool
        - liquidity_ok: bool
        - volatility_ok: bool
        - trend_ok: bool
        - details: str
        - metrics: dict
        """
        if df.empty or len(df) < 200:
            return {
                'passed': False,
                'liquidity_ok': False,
                'volatility_ok': False,
                'trend_ok': False,
                'details': 'Insufficient data',
                'metrics': {}
            }
        
        # Check each filter
        liquidity_result = self.check_liquidity(df)
        volatility_result = self.check_volatility(df)
        trend_result = self.check_trend(df)
        
        # All must pass
        all_passed = (
            liquidity_result['passed'] and
            volatility_result['passed'] and
            trend_result['passed']
        )
        
        # Build details
        details_parts = []
        if not liquidity_result['passed']:
            details_parts.append(f"Liquidity: ${liquidity_result['dollar_volume']/1e6:.1f}M < ${self.min_dollar_volume/1e6:.0f}M")
        if not volatility_result['passed']:
            details_parts.append(f"ADR: {volatility_result['adr_pct']:.2f}% < {self.min_adr_pct}%")
        if not trend_result['passed']:
            details_parts.append(trend_result['reason'])
        
        if all_passed:
            details = f"✓ All filters passed | Dollar Vol: ${liquidity_result['dollar_volume']/1e6:.0f}M | ADR: {volatility_result['adr_pct']:.1f}% | Trend aligned"
        else:
            details = " | ".join(details_parts)
        
        return {
            'passed': all_passed,
            'liquidity_ok': liquidity_result['passed'],
            'volatility_ok': volatility_result['passed'],
            'trend_ok': trend_result['passed'],
            'details': details,
            'metrics': {
                'dollar_volume': liquidity_result['dollar_volume'],
                'avg_volume': liquidity_result['avg_volume'],
                'price': liquidity_result['price'],
                'adr_pct': volatility_result['adr_pct'],
                'adr_value': volatility_result['adr_value'],
                'price': trend_result['price'],
                'sma50': trend_result['sma50'],
                'sma200': trend_result['sma200'],
                'trend_aligned': trend_result['aligned']
            }
        }
    
    def check_liquidity(self, df: pd.DataFrame) -> Dict:
        """
        Filter 1: Liquidity
        Avg Volume(20) * Price > $100M
        """
        try:
            avg_volume_20 = df['Volume'].tail(20).mean()
            current_price = df['Close'].iloc[-1]
            dollar_volume = avg_volume_20 * current_price
            
            passed = dollar_volume >= self.min_dollar_volume
            
            return {
                'passed': passed,
                'dollar_volume': dollar_volume,
                'avg_volume': avg_volume_20,
                'price': current_price
            }
        except Exception as e:
            logger.error(f"Error in liquidity filter: {e}")
            return {'passed': False, 'dollar_volume': 0, 'avg_volume': 0, 'price': 0}
    
    def check_volatility(self, df: pd.DataFrame) -> Dict:
        """
        Filter 2: Volatility
        ADR(14) > 4%
        
        ADR = Average Daily Range = Avg((High - Low) / Low) over 14 days
        """
        try:
            # Calculate daily ranges for last 14 days
            recent = df.tail(14)
            daily_ranges_pct = ((recent['High'] - recent['Low']) / recent['Low']) * 100
            adr_pct = daily_ranges_pct.mean()
            
            # Also calculate absolute ADR
            daily_ranges = recent['High'] - recent['Low']
            adr_value = daily_ranges.mean()
            
            passed = adr_pct >= self.min_adr_pct
            
            return {
                'passed': passed,
                'adr_pct': adr_pct,
                'adr_value': adr_value
            }
        except Exception as e:
            logger.error(f"Error in volatility filter: {e}")
            return {'passed': False, 'adr_pct': 0, 'adr_value': 0}
    
    def check_trend(self, df: pd.DataFrame) -> Dict:
        """
        Filter 3: Trend Alignment
        Price > SMA50 > SMA200
        
        This ensures we're only trading strong uptrends
        """
        try:
            if len(df) < 200:
                return {
                    'passed': False,
                    'aligned': False,
                    'price': 0,
                    'sma50': 0,
                    'sma200': 0,
                    'reason': 'Insufficient data for SMA200'
                }
            
            current_price = df['Close'].iloc[-1]
            sma50 = df['Close'].tail(50).mean()
            sma200 = df['Close'].tail(200).mean()
            
            # Check alignment: Price > SMA50 > SMA200
            price_above_sma50 = current_price > sma50
            sma50_above_sma200 = sma50 > sma200
            aligned = price_above_sma50 and sma50_above_sma200
            
            # Build reason if not aligned
            if not aligned:
                if not price_above_sma50:
                    reason = f"Price ${current_price:.2f} below SMA50 ${sma50:.2f}"
                elif not sma50_above_sma200:
                    reason = f"SMA50 ${sma50:.2f} below SMA200 ${sma200:.2f}"
                else:
                    reason = "Trend not aligned"
            else:
                reason = "Trend aligned"
            
            passed = aligned if self.require_trend_alignment else True
            
            return {
                'passed': passed,
                'aligned': aligned,
                'price': current_price,
                'sma50': sma50,
                'sma200': sma200,
                'reason': reason
            }
        except Exception as e:
            logger.error(f"Error in trend filter: {e}")
            return {
                'passed': False,
                'aligned': False,
                'price': 0,
                'sma50': 0,
                'sma200': 0,
                'reason': f'Error: {e}'
            }
    
    def get_filter_summary(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> str:
        """Get a human-readable summary of filter results"""
        result = self.passes_all_filters(df, symbol)
        
        if result['passed']:
            return f"✅ {symbol} PASSES all filters | {result['details']}"
        else:
            return f"❌ {symbol} FAILS filters | {result['details']}"


def quick_filter_check(df: pd.DataFrame, symbol: str = "UNKNOWN") -> bool:
    """
    Quick check with default parameters
    Returns True if stock passes all filters
    """
    filters = StockFilters()
    result = filters.passes_all_filters(df, symbol)
    return result['passed']
