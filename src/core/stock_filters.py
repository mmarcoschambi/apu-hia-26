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
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class StockFilters:
    """Pre-trade quality filters"""
    
    def __init__(self,
                 min_dollar_volume: float = 100_000_000,  # $100M
                 min_adr_pct: float = 2.5,                # 2.5% (more realistic)
                 require_trend_alignment: bool = True,
                 db_path: Optional[str] = None):
        """
        Initialize filters
        
        Args:
            min_dollar_volume: Minimum avg daily dollar volume ($100M default)
            min_adr_pct: Minimum ADR percentage (2.5% default, 4% for high vol stocks)
            require_trend_alignment: Require Price > SMA50 > SMA200
            db_path: Path to ticker_cache.db (for fast lookups)
        """
        self.min_dollar_volume = min_dollar_volume
        self.min_adr_pct = min_adr_pct
        self.require_trend_alignment = require_trend_alignment
        
        # Database connection for fast lookups
        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            db_path = base_dir / "data" / "ticker_cache.db"
        self.db_path = db_path
        self.conn = None
    
    def _get_connection(self):
        """Lazy database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        return self.conn
    
    def passes_filters(self, ticker: str, date: str, df: Optional[pd.DataFrame] = None) -> Dict:
        """
        SMART VERSION: Auto-switches between fast (cached) and slow (calculated) versions
        
        This method tries to use pre-calculated cache first. If cache is not available
        or not populated, it falls back to calculating from the DataFrame.
        
        Args:
            ticker: Stock symbol
            date: Date to check (YYYY-MM-DD)
            df: Optional DataFrame for fallback calculation
            
        Returns: Dict with filter results
        """
        # Try fast version first (using cache)
        try:
            result = self.passes_filters_fast(ticker, date)
            
            # Check if cache has valid data (adr_pct is a key metric)
            if result['metrics'].get('adr_pct', 0) > 0:
                return result
        except Exception as e:
            logger.debug(f"Fast filter failed for {ticker} on {date}: {e}")
        
        # Fallback to slow version if cache not available
        if df is not None and not df.empty:
            logger.debug(f"Using calculated filters for {ticker} on {date} (cache not available)")
            return self.passes_all_filters(df, ticker)
        
        # No data available at all
        return {
            'passed': False,
            'liquidity_ok': False,
            'volatility_ok': False,
            'trend_ok': False,
            'details': 'No data available (cache or DataFrame)',
            'metrics': {}
        }
    
    def passes_filters_fast(self, ticker: str, date: str) -> Dict:
        """
        FAST VERSION: Check filters using pre-calculated database values
        
        Args:
            ticker: Stock symbol
            date: Date to check (YYYY-MM-DD)
            
        Returns: Same dict as passes_all_filters but MUCH faster
        """
        conn = self._get_connection()
        
        query = """
            SELECT 
                close as price,
                adr_pct_14,
                sma_50,
                sma_200,
                trend_aligned,
                rolling_dollar_vol_20,
                avg_volume_20,
                volume
            FROM ohlcv_cache
            WHERE ticker = ? AND date = ?
        """
        
        cursor = conn.execute(query, (ticker, date))
        row = cursor.fetchone()
        
        if not row:
            return {
                'passed': False,
                'liquidity_ok': False,
                'volatility_ok': False,
                'trend_ok': False,
                'details': 'No data for date',
                'metrics': {}
            }
        
        price, adr_pct, sma50, sma200, trend_aligned, rolling_dollar_vol, avg_vol, volume = row
        
        # Check filters
        liquidity_ok = rolling_dollar_vol is not None and rolling_dollar_vol >= self.min_dollar_volume
        volatility_ok = adr_pct is not None and adr_pct >= self.min_adr_pct
        trend_ok = trend_aligned == 1 if self.require_trend_alignment else True
        
        all_passed = liquidity_ok and volatility_ok and trend_ok
        
        # Build details
        details_parts = []
        if not liquidity_ok:
            vol_m = rolling_dollar_vol / 1e6 if rolling_dollar_vol else 0
            details_parts.append(f"Liquidity: ${vol_m:.1f}M < ${self.min_dollar_volume/1e6:.0f}M")
        if not volatility_ok:
            details_parts.append(f"ADR: {adr_pct if adr_pct else 0:.2f}% < {self.min_adr_pct}%")
        if not trend_ok:
            details_parts.append(f"Trend not aligned")
        
        if all_passed:
            details = f"✓ All filters passed"
        else:
            details = " | ".join(details_parts)
        
        return {
            'passed': all_passed,
            'liquidity_ok': liquidity_ok,
            'volatility_ok': volatility_ok,
            'trend_ok': trend_ok,
            'details': details,
            'metrics': {
                'dollar_volume': rolling_dollar_vol or 0,
                'avg_volume': avg_vol or 0,
                'price': price or 0,
                'adr_pct': adr_pct or 0,
                'adr_value': 0,  # Not stored, would need calculation
                'sma50': sma50 or 0,
                'sma200': sma200 or 0,
                'trend_aligned': trend_aligned == 1
            }
        }
    
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
