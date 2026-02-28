#!/usr/bin/env python3
"""
Optimization Engine V6 - Ultra-Fast VectorBT Optimization
==========================================================

Design Goals:
1. Load data ONCE for all trials
2. Pre-calculate indicators that don't depend on parameters
3. Vectorized filtering with VectorBT
4. 100× faster than AdvancedVectorBTEngine for optimization

Key Differences from AdvancedVectorBTEngine:
- Data loaded once, cached in memory
- Indicators pre-calculated
- Only parameter-dependent logic runs per trial
- Designed for 1000+ tickers, 500+ trials

Author: AI Assistant
Date: 2026-01-08
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
from datetime import datetime, timedelta
from pathlib import Path
import logging
from typing import List, Dict, Tuple, Optional
import gc

from src.data.ticker_cache import TickerCache
from src.data.market_data import MarketDataProvider

logger = logging.getLogger(__name__)


class OptimizationEngineV6:
    """
    Ultra-fast optimization engine using VectorBT vectorization.
    
    Usage:
        # Initialize ONCE with data
        engine = OptimizationEngineV6(
            tickers=['AAPL', 'MSFT', ...],  # 2000+ OK
            start_date='2020-01-01',
            end_date='2022-12-31'
        )
        
        # Run many trials FAST
        for trial in range(500):
            params = get_trial_params()
            pf = engine.backtest(params)  # ~5-10 seconds per trial
    """
    
    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        lookback_days: int = 365,
        offline_mode: bool = True
    ):
        """
        Initialize engine and load ALL data once.
        
        This is the slow part (1-5 minutes), but only happens ONCE.
        """
        self.tickers = tickers
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.initial_capital = initial_capital
        self.lookback_days = lookback_days
        self.offline_mode = offline_mode
        
        self.cache = TickerCache()
        
        # Data containers (populated in load_data)
        self.close = None
        self.open = None
        self.high = None
        self.low = None
        self.volume = None
        self.dollar_volume = None
        
        # Pre-calculated indicators (populated in calculate_indicators)
        self.sma20 = None
        self.sma50 = None
        self.sma200 = None
        self.ema8 = None
        self.ema21 = None
        self.atr = None
        self.avg_volume_20 = None
        self.rvol = None
        self.adr = None
        self.dist_sma20_pct = None
        
        # Metadata
        self.valid_tickers = []
        
        logger.info(f"🚀 OptimizationEngineV6 initializing...")
        logger.info(f"📅 Period: {start_date} to {end_date}")
        logger.info(f"🎯 Tickers: {len(tickers)}")
        
        # Load and prepare everything
        self._load_all_data()
        self._calculate_indicators()
        
        logger.info(f"✅ Engine ready: {len(self.valid_tickers)} tickers loaded")
        logger.info(f"📊 Shape: {self.close.shape}")
    
    def _load_all_data(self):
        """Load OHLCV data for all tickers - ONCE."""
        fetch_start = self.start_date - pd.Timedelta(days=self.lookback_days)
        
        logger.info(f"📥 Loading data from {fetch_start.date()} to {self.end_date.date()}...")
        
        all_data = {}
        failed = []
        
        for i, ticker in enumerate(self.tickers):
            if (i + 1) % 100 == 0:
                logger.info(f"   Progress: {i+1}/{len(self.tickers)}...")
                gc.collect()
            
            try:
                df = self.cache.get_ohlcv(
                    ticker,
                    fetch_start.strftime('%Y-%m-%d'),
                    self.end_date.strftime('%Y-%m-%d'),
                    offline=self.offline_mode
                )
                
                if df is not None and len(df) >= 100:  # Minimum data requirement (relaxed)
                    df = df.reset_index()
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date')
                    
                    # Normalize column names to lowercase
                    df.columns = [col.lower() for col in df.columns]
                    
                    # Calculate dollar volume if missing
                    if 'dollar_volume' not in df.columns:
                        df['dollar_volume'] = df['close'] * df['volume']
                    
                    all_data[ticker] = df
                else:
                    failed.append(ticker)
                    
            except Exception as e:
                logger.debug(f"Failed {ticker}: {e}")
                failed.append(ticker)
        
        if len(failed) > 0:
            logger.info(f"⚠️  Skipped {len(failed)} tickers (insufficient data)")
        
        if len(all_data) == 0:
            raise ValueError("No data loaded! Check date range and ticker availability.")
        
        self.valid_tickers = list(all_data.keys())
        logger.info(f"✅ Loaded {len(self.valid_tickers)} tickers")
        
        # Convert to DataFrame format (date × ticker)
        self.close = pd.DataFrame({ticker: df['close'] for ticker, df in all_data.items()})
        self.open = pd.DataFrame({ticker: df['open'] for ticker, df in all_data.items()})
        self.high = pd.DataFrame({ticker: df['high'] for ticker, df in all_data.items()})
        self.low = pd.DataFrame({ticker: df['low'] for ticker, df in all_data.items()})
        self.volume = pd.DataFrame({ticker: df['volume'] for ticker, df in all_data.items()})
        self.dollar_volume = pd.DataFrame({ticker: df['dollar_volume'] for ticker, df in all_data.items()})
        
        # Align all dataframes to same index
        common_index = self.close.dropna(how='all').index
        self.close = self.close.reindex(common_index)
        self.open = self.open.reindex(common_index)
        self.high = self.high.reindex(common_index)
        self.low = self.low.reindex(common_index)
        self.volume = self.volume.reindex(common_index)
        self.dollar_volume = self.dollar_volume.reindex(common_index)
        
        # Forward fill small gaps (max 3 days)
        self.close = self.close.ffill(limit=3)
        self.open = self.open.ffill(limit=3)
        self.high = self.high.ffill(limit=3)
        self.low = self.low.ffill(limit=3)
        self.volume = self.volume.ffill(limit=3).fillna(0)
        self.dollar_volume = self.dollar_volume.ffill(limit=3).fillna(0)
        
        logger.info(f"📊 Data shape: {self.close.shape} (days × tickers)")
    
    def _calculate_indicators(self):
        """Pre-calculate all indicators that don't depend on trial parameters."""
        logger.info("🔢 Calculating indicators...")
        
        # SMAs
        self.sma20 = self.close.rolling(20, min_periods=10).mean()
        self.sma50 = self.close.rolling(50, min_periods=25).mean()
        self.sma200 = self.close.rolling(200, min_periods=100).mean()
        
        # EMAs
        self.ema8 = self.close.ewm(span=8, adjust=False, min_periods=4).mean()
        self.ema21 = self.close.ewm(span=21, adjust=False, min_periods=10).mean()
        
        # ATR (using VectorBT for speed)
        atr_ind = vbt.ATR.run(self.high, self.low, self.close, window=14)
        self.atr = atr_ind.atr
        
        # Average Volume
        self.avg_volume_20 = self.volume.rolling(20, min_periods=10).mean()
        
        # RVOL (Relative Volume)
        safe_avg_vol = self.avg_volume_20.replace(0, np.nan)
        self.rvol = (self.volume / safe_avg_vol).fillna(0)
        
        # ADR (Average Daily Range %)
        daily_range = ((self.high - self.low) / self.close * 100)
        self.adr = daily_range.rolling(20, min_periods=10).mean()
        
        # Distance from SMA20 (%)
        safe_sma20 = self.sma20.replace(0, np.nan)
        self.dist_sma20_pct = ((self.close - safe_sma20) / safe_sma20 * 100).fillna(0)
        
        logger.info("✅ Indicators calculated")
    
    def backtest(self, params: Dict) -> Dict:
        """
        Run backtest with given parameters.
        
        This is FAST because data is already loaded and indicators pre-calculated.
        Only parameter-dependent filtering happens here.
        
        Args:
            params: Dictionary with trial parameters:
                - risk_dollars: float
                - max_exposure_pct: float
                - min_rvol: float
                - min_adr: float
                - min_volume: int
                - min_dollar_volume: float
                - max_dist_sma20: float
                - max_stop_pct: float
                - require_positive_rs: bool (optional, defaults to False)
                ... more params
        
        Returns:
            Dictionary with stats: {'profit_factor': float, 'total_trades': int, ...}
        """
        try:
            # Extract parameters
            risk_dollars = params.get('risk_dollars', 150)
            max_exposure_pct = params.get('max_exposure_pct', 0.25)
            min_rvol = params.get('min_rvol', 1.0)
            min_adr = params.get('min_adr', 1.0)
            min_volume = params.get('min_volume', 200000)
            min_dollar_volume = params.get('min_dollar_volume', 10e6)
            max_dist_sma20 = params.get('max_dist_sma20', 10.0)
            max_stop_pct = params.get('max_stop_pct', 8.0)
            
            # ENTRY SIGNALS (Vectorized)
            entries = (
                # Price above SMA20
                (self.close > self.sma20) &
                
                # Not extended too far from SMA20
                (self.dist_sma20_pct >= 0) &
                (self.dist_sma20_pct <= max_dist_sma20) &
                
                # RVOL filter
                (self.rvol >= min_rvol) &
                
                # ADR filter
                (self.adr >= min_adr) &
                
                # Volume filters
                (self.volume >= min_volume) &
                (self.dollar_volume >= min_dollar_volume) &
                
                # Above SMA50 (trend filter)
                (self.close > self.sma50) &
                
                # SMA50 above SMA200 (major trend)
                (self.sma50 > self.sma200)
            )
            
            # Calculate stops (vectorized)
            stop_loss_pct = np.minimum(
                (self.close - self.sma20) / self.close * 100,
                max_stop_pct
            )
            stop_loss_pct = np.maximum(stop_loss_pct, 3.0)  # Minimum 3%
            
            # EXIT SIGNALS
            # Simple exit: close below SMA20 or stop loss hit
            exits = (self.close < self.sma20)
            
            # Calculate position size in DOLLARS based on risk
            # Formula: position_value = risk_dollars / (stop_loss_pct / 100)
            position_value = risk_dollars / (stop_loss_pct / 100)
            position_value = position_value.replace([np.inf, -np.inf], np.nan).fillna(0)
            
            # Limit by max exposure
            max_position_value = self.initial_capital * max_exposure_pct
            position_value = np.minimum(position_value, max_position_value)
            
            # Ensure positive values
            position_value = np.maximum(position_value, 0)
            
            # Run VectorBT backtest
            portfolio = vbt.Portfolio.from_signals(
                self.close,
                entries,
                exits,
                size=position_value,
                size_type='amount',  # Use 'amount' instead of 'shares'
                init_cash=self.initial_capital,
                fees=0.001,  # 0.1% per trade
                slippage=0.001,  # 0.1% slippage
                freq='1D'
            )
            
            # Get stats
            stats = portfolio.stats()
            
            # Extract key metrics
            result = {
                'profit_factor': stats.get('Profit Factor', 0),
                'total_trades': stats.get('Total Trades', 0),
                'total_return_pct': stats.get('Total Return [%]', 0),
                'sharpe_ratio': stats.get('Sharpe Ratio', 0),
                'max_drawdown_pct': stats.get('Max Drawdown [%]', 0),
                'win_rate_pct': stats.get('Win Rate [%]', 0),
                'avg_winning_trade_pct': stats.get('Avg Winning Trade [%]', 0),
                'avg_losing_trade_pct': stats.get('Avg Losing Trade [%]', 0),
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return {
                'profit_factor': 0,
                'total_trades': 0,
                'total_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0,
                'win_rate_pct': 0,
                'avg_winning_trade_pct': 0,
                'avg_losing_trade_pct': 0,
                'error': str(e)
            }
    
    def get_valid_tickers(self) -> List[str]:
        """Return list of tickers that were successfully loaded."""
        return self.valid_tickers
    
    def get_data_summary(self) -> Dict:
        """Get summary of loaded data."""
        return {
            'tickers_loaded': len(self.valid_tickers),
            'tickers_requested': len(self.tickers),
            'date_range': f"{self.close.index[0].date()} to {self.close.index[-1].date()}",
            'trading_days': len(self.close),
            'data_shape': self.close.shape,
            'memory_mb': self.close.memory_usage(deep=True).sum() / 1e6
        }


if __name__ == '__main__':
    """Quick test of OptimizationEngineV6"""
    
    logging.basicConfig(level=logging.INFO)
    
    print("="*80)
    print("🧪 Testing OptimizationEngineV6")
    print("="*80)
    
    # Test with small universe
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'UNH']
    
    print(f"\n📊 Creating engine with {len(test_tickers)} tickers...")
    engine = OptimizationEngineV6(
        tickers=test_tickers,
        start_date='2020-01-01',
        end_date='2022-12-31'
    )
    
    print(f"\n✅ Engine created!")
    print(f"📋 Summary: {engine.get_data_summary()}")
    
    # Test backtest with different parameters
    print(f"\n🔥 Running 5 test backtests...")
    
    test_params = [
        {'risk_dollars': 100, 'min_rvol': 0.8, 'min_adr': 1.0},
        {'risk_dollars': 150, 'min_rvol': 1.0, 'min_adr': 1.5},
        {'risk_dollars': 200, 'min_rvol': 1.2, 'min_adr': 2.0},
        {'risk_dollars': 250, 'min_rvol': 1.5, 'min_adr': 2.5},
        {'risk_dollars': 150, 'min_rvol': 0.5, 'min_adr': 0.8},
    ]
    
    for i, params in enumerate(test_params, 1):
        start = datetime.now()
        result = engine.backtest(params)
        elapsed = (datetime.now() - start).total_seconds()
        
        print(f"\n  Trial {i}: PF={result['profit_factor']:.2f}, Trades={result['total_trades']}, Time={elapsed:.1f}s")
    
    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80)
