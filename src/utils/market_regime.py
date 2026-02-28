"""
Professional Market Regime Classifier
=====================================
Classify market conditions to adjust trading aggressiveness.
Based on SPY price structure and VIX levels.

Stage 1: Bull Trend - Aggressive Longs
Stage 2: Consolidation - Selective Longs  
Stage 3: Distribution - No Longs
Stage 4: Bear Trend - Shorts Only

'No operar en Stage 3-4 (mercado bajista/distribución)'
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MarketRegimeClassifier:
    """
    Classifies market regime based on SPY structure and VIX levels.
    Adjusts position sizing and filters based on market context.
    """
    
    STAGES = {
        'STAGE_1': 'Bull Trend - Aggressive Longs',
        'STAGE_2': 'Consolidation - Selective Longs',
        'STAGE_3': 'Distribution - No Longs',
        'STAGE_4': 'Bear Trend - Shorts Only'
    }
    
    def __init__(self, spy_data: pd.DataFrame, vix_data: Optional[pd.DataFrame] = None):
        """
        Initialize with SPY and VIX data.
        
        Args:
            spy_data: DataFrame with columns ['close', 'volume', 'high', 'low']
            vix_data: Optional DataFrame with column ['close']
        """
        self.spy = spy_data.copy()
        self.vix = vix_data.copy() if vix_data is not None else None
        
        # Ensure datetimes
        if not isinstance(self.spy.index, pd.DatetimeIndex):
            self.spy.index = pd.to_datetime(self.spy.index)
        if self.vix is not None and not isinstance(self.vix.index, pd.DatetimeIndex):
            self.vix.index = pd.to_datetime(self.vix.index)
            
        self._precompute_indicators()
    
    def _precompute_indicators(self):
        """Calculate key indicators used by professionals"""
        # Moving averages
        self.spy['sma20'] = self.spy['close'].rolling(20).mean()
        self.spy['sma50'] = self.spy['close'].rolling(50).mean()
        self.spy['sma200'] = self.spy['close'].rolling(200).mean()
        self.spy['ema20'] = self.spy['close'].ewm(span=20, adjust=False).mean()
        
        # Relative volatility
        self.spy['range_pct'] = (self.spy['high'] - self.spy['low']) / self.spy['close'] * 100
        self.spy['volatility_20'] = self.spy['range_pct'].rolling(20).mean()
        
        # Momentum
        self.spy['mom_20'] = self.spy['close'].pct_change(20)
        
        # VIX regimes (if available)
        if self.vix is not None:
            self.vix['vix_sma20'] = self.vix['close'].rolling(20).mean()
            self.vix['vix_regime'] = pd.cut(
                self.vix['close'], 
                bins=[0, 15, 25, 35, 100],
                labels=['CALM', 'NORMAL', 'HIGH', 'EXTREME']
            )

    def get_regime_mask(
        self, 
        target_index: pd.DatetimeIndex, 
        regime_type: str = 'bullish_spy'
    ) -> pd.Series:
        """
        Get a boolean mask aligned with target_index for specific regime conditions.
        
        Args:
            target_index: Index to align the mask with (e.g., self.close.index)
            regime_type: Type of mask ('bullish_spy', 'safe_vix', 'stage_1')
            
        Returns:
            pd.Series (boolean) aligned with target_index
        """
        # Reindex SPY/VIX to target index (ffill to propagate last known state)
        aligned_spy = self.spy.reindex(target_index, method='ffill')
        aligned_vix = self.vix.reindex(target_index, method='ffill') if self.vix is not None else None
        
        mask = pd.Series(False, index=target_index)
        
        if regime_type == 'bullish_spy':
            # SPY > EMA20 (Short term trend)
            mask = aligned_spy['close'] > aligned_spy['ema20']
            
        elif regime_type == 'spy_above_sma50':
             mask = aligned_spy['close'] > aligned_spy['sma50']
             
        elif regime_type == 'spy_above_sma200':
             mask = aligned_spy['close'] > aligned_spy['sma200']
             
        elif regime_type == 'safe_vix':
            if aligned_vix is not None:
                mask = aligned_vix['close'] < 20.0
            else:
                mask = pd.Series(True, index=target_index) # Assume safe if no VIX
                
        elif regime_type == 'stage_1':
            # Strict Stage 1: Bull Trend
            trend = (aligned_spy['close'] > aligned_spy['sma200']) & \
                    (aligned_spy['close'] > aligned_spy['sma50']) & \
                    (aligned_spy['mom_20'] > 0.03)
            
            vix_ok = (aligned_vix['close'] < 20.0) if aligned_vix is not None else True
            mask = trend & vix_ok
            
        elif regime_type == 'no_crash':
            # Avoid Stage 4 (Crash mode)
            # Crash: Price < SMA200 AND Momentum < -5%
            crash = (aligned_spy['close'] < aligned_spy['sma200']) & \
                    (aligned_spy['mom_20'] < -0.05)
            mask = ~crash
            
        return mask.fillna(False)
    
    def get_market_stage(self, date: pd.Timestamp) -> str:
        """
        Determine market regime for a specific date.
        
        Rules:
        - Stage 4: Clear downtrend (price < SMA200, SMA50, momentum < -5%)
        - Stage 3: Distribution (price < SMA50, high vol, VIX > 25)
        - Stage 1: Clear uptrend (price > SMA200, SMA50, momentum > 3%, VIX < 20)
        - Stage 2: Consolidation (everything else)
        """
        try:
            if date not in self.spy.index:
                # Find nearest date
                idx = self.spy.index.searchsorted(date)
                if idx >= len(self.spy):
                    idx = len(self.spy) - 1
            else:
                idx = self.spy.index.get_loc(date)
        except (KeyError, IndexError):
            return 'STAGE_2'  # Default to consolidation
        
        row = self.spy.iloc[idx]
        spy_price = row['close']
        
        # Get VIX value if available
        vix_value = 20.0  # Default neutral VIX
        if self.vix is not None:
            try:
                if date in self.vix.index:
                    vix_value = self.vix.loc[date, 'close']
                else:
                    vix_idx = self.vix.index.searchsorted(date)
                    if vix_idx < len(self.vix):
                        vix_value = self.vix.iloc[vix_idx]['close']
            except (KeyError, IndexError):
                pass
        
        # Stage 4: Clear bear trend
        if (spy_price < row['sma200'] and 
            spy_price < row['sma50'] and
            row['mom_20'] < -0.05):
            return 'STAGE_4'
        
        # Stage 3: Distribution
        elif (spy_price < row['sma50'] and
              row['volatility_20'] > 2.0 and
              vix_value > 25):
            return 'STAGE_3'
        
        # Stage 1: Clear bull trend
        elif (spy_price > row['sma200'] and
              spy_price > row['sma50'] and
              row['mom_20'] > 0.03 and
              vix_value < 20):
            return 'STAGE_1'
        
        # Stage 2: Consolidation (default)
        return 'STAGE_2'
    
    def get_market_context(self, date: pd.Timestamp) -> Dict[str, any]:
        """
        Get detailed market context for a date.
        
        Returns:
            Dict with market stage, metrics, and trading parameters
        """
        stage = self.get_market_stage(date)
        
        try:
            if date not in self.spy.index:
                idx = self.spy.index.searchsorted(date)
                if idx >= len(self.spy):
                    idx = len(self.spy) - 1
            else:
                idx = self.spy.index.get_loc(date)
        except (KeyError, IndexError):
            idx = len(self.spy) - 1
        
        row = self.spy.iloc[idx]
        
        # Get VIX data if available
        vix_value = 20.0
        vix_regime = 'NORMAL'
        if self.vix is not None:
            try:
                if date in self.vix.index:
                    vix_value = self.vix.loc[date, 'close']
                    vix_regime = self.vix.loc[date, 'vix_regime']
                else:
                    vix_idx = self.vix.index.searchsorted(date)
                    if vix_idx < len(self.vix):
                        vix_value = self.vix.iloc[vix_idx]['close']
                        vix_regime = self.vix.iloc[vix_idx]['vix_regime']
            except (KeyError, IndexError):
                pass
        
        return {
            'market_stage': stage,
            'stage_description': self.STAGES[stage],
            'spy_price': row['close'],
            'spy_above_sma200': row['close'] > row['sma200'],
            'spy_above_sma50': row['close'] > row['sma50'],
            'vix_value': vix_value,
            'vix_regime': vix_regime,
            'market_volatility': row['volatility_20'],
            'spy_momentum_20d': row['mom_20'],
            'max_exposure_pct': self._get_max_exposure_by_stage(stage),
            'risk_multiplier': self._get_risk_multiplier_by_stage(stage),
            'should_trade_longs': stage in ['STAGE_1', 'STAGE_2'],
            'aggressiveness': self._get_aggressiveness_by_stage(stage)
        }
    
    def _get_max_exposure_by_stage(self, stage: str) -> float:
        """Maximum portfolio exposure by market stage"""
        sizing = {
            'STAGE_1': 0.35,  # 35% max exposure (aggressive)
            'STAGE_2': 0.25,  # 25% max exposure (moderate)
            'STAGE_3': 0.10,  # 10% max exposure (defensive)
            'STAGE_4': 0.00   # 0% max exposure (no longs)
        }
        return sizing[stage]
    
    def _get_risk_multiplier_by_stage(self, stage: str) -> float:
        """Risk per trade multiplier by market stage"""
        multiplier = {
            'STAGE_1': 1.0,   # Full risk (100%)
            'STAGE_2': 0.75,  # Reduced risk (75%)
            'STAGE_3': 0.25,  # Quarter risk (25%) - CHANGED FROM 0.50
            'STAGE_4': 0.00   # No risk (no longs)
        }
        return multiplier[stage]
    
    def _get_aggressiveness_by_stage(self, stage: str) -> str:
        """Trading aggressiveness level"""
        return {
            'STAGE_1': 'AGGRESSIVE',
            'STAGE_2': 'SELECTIVE',
            'STAGE_3': 'DEFENSIVE',
            'STAGE_4': 'NO_LONGS'
        }[stage]
    
    def get_stage_series(self) -> pd.Series:
        """
        Get a time series of market stages for entire SPY data.
        
        Returns:
            Series indexed by date with market stage values
        """
        stages = []
        for date in self.spy.index:
            stage = self.get_market_stage(date)
            stages.append(stage)
        
        return pd.Series(stages, index=self.spy.index, name='market_stage')
    
    def get_context_series(self) -> pd.DataFrame:
        """
        Get a DataFrame with all market context metrics over time.
        
        Returns:
            DataFrame with market context for each date
        """
        contexts = []
        for date in self.spy.index:
            context = self.get_market_context(date)
            contexts.append(context)
        
        return pd.DataFrame(contexts, index=self.spy.index)


def load_spy_vix_data(start_date: str, end_date: str, cache=None) -> tuple:
    """
    Load SPY and VIX data for market regime classification.
    
    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        cache: Optional TickerCache instance
        
    Returns:
        Tuple of (spy_data, vix_data) DataFrames
    """
    import yfinance as yf
    
    logger.info(f"📊 Loading SPY and VIX data ({start_date} to {end_date})...")
    
    # Load SPY data
    if cache is not None:
        try:
            if hasattr(cache, 'get_daily_data'):
                spy_data = cache.get_daily_data('SPY', start_date=start_date, end_date=end_date)
            elif hasattr(cache, 'get_ohlcv'):
                spy_data = cache.get_ohlcv('SPY', start_date, end_date)
            else:
                spy_data = None
                
            if spy_data is not None and not spy_data.empty:
                logger.info(f"   ✅ SPY loaded from cache: {len(spy_data)} bars")
            else:
                raise ValueError("No SPY data in cache")
        except Exception as e:
            logger.warning(f"   ⚠️  SPY not in cache, loading from yfinance: {e}")
            spy_data = yf.download('SPY', start=start_date, end=end_date, progress=False)
    else:
        spy_data = yf.download('SPY', start=start_date, end=end_date, progress=False)
    
    # Load VIX data (optional)
    vix_data = None
    try:
        if cache is not None:
            if hasattr(cache, 'get_daily_data'):
                vix_data = cache.get_daily_data('^VIX', start_date=start_date, end_date=end_date)
                # Try VIX if ^VIX fails (sometimes stored differently)
                if vix_data is None or vix_data.empty:
                    vix_data = cache.get_daily_data('VIX', start_date=start_date, end_date=end_date)
            elif hasattr(cache, 'get_ohlcv'):
                vix_data = cache.get_ohlcv('^VIX', start_date, end_date)
                if vix_data is None or vix_data.empty:
                    vix_data = cache.get_ohlcv('VIX', start_date, end_date)
            
            if vix_data is not None and not vix_data.empty:
                logger.info(f"   ✅ VIX loaded from cache: {len(vix_data)} bars")
            else:
                raise ValueError("No VIX data in cache")
        else:
            vix_data = yf.download('^VIX', start=start_date, end=end_date, progress=False)
    except Exception as e:
        logger.warning(f"   ⚠️  VIX data not available: {e}")
    
    # Standardize column names (handle MultiIndex from yfinance)
    if spy_data is not None and isinstance(spy_data.columns, pd.MultiIndex):
        # Extract 'Close' if present at level 0, otherwise simplify
        try:
            spy_data = spy_data.xs('SPY', axis=1, level=1)
        except:
             spy_data.columns = spy_data.columns.get_level_values(0)

    if spy_data is not None:
        spy_data.columns = [c.lower() for c in spy_data.columns]
    
    if vix_data is not None and isinstance(vix_data.columns, pd.MultiIndex):
        try:
             # Try to find ^VIX or VIX in level 1
             if '^VIX' in vix_data.columns.get_level_values(1):
                 vix_data = vix_data.xs('^VIX', axis=1, level=1)
             elif 'VIX' in vix_data.columns.get_level_values(1):
                 vix_data = vix_data.xs('VIX', axis=1, level=1)
             else:
                 vix_data.columns = vix_data.columns.get_level_values(0)
        except:
             vix_data.columns = vix_data.columns.get_level_values(0)

    if vix_data is not None:
        vix_data.columns = [c.lower() for c in vix_data.columns]
    
    logger.info(f"   ✅ Market data loaded successfully")
    
    return spy_data, vix_data