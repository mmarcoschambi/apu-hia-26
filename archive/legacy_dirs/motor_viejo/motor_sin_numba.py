"""
Advanced VectorBT Engine with Partial Exits
--------------------------------------------
Implements Triad Protocol with 3-phase exit system:
- TP1: 50% at 1.5R (Breakeven Stop)
- TP2: 30% at 3R
- Phase 3: 20% Runner (EMA8 < EMA21)
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import yfinance as yf
import gc
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from tqdm import tqdm

from src.data.ticker_cache import TickerCache
from src.data.market_data import MarketDataProvider
from src.utils.sector_rotation import SectorRotationAnalyzer, integrate_sector_filter_in_backtest, SECTOR_MAP
from src.utils.rvol_context_v2 import integrate_with_unified_position_size
from src.utils.market_regime import MarketRegimeClassifier, load_spy_vix_data
from src.utils.adaptive_filter_engine import AdaptiveFilterEngine
from src.indicators.technical import TechnicalIndicators
from src.filters.liquidity import LiquidityFilters
from src.risk.position_sizing import PositionSizer

logger = logging.getLogger(__name__)


def get_dynamic_thresholds(current_vix: float, 
                          base_min_rvol: float = 1.5,
                          base_min_adr: float = 2.5,
                          base_max_dist_sma20: float = 7.0,
                          base_max_stop_pct: float = 6.5,
                          base_min_dollar_volume: float = 3_000_000,
                          base_min_consolidation_days: int = 8) -> Dict[str, float]:
    """
    Ajusta umbrales según volatilidad del mercado (VIX).
    DYNAMIC: Usa validated params como base y aplica multiplicadores por régimen.

    Args:
        current_vix: Valor actual del VIX
        base_*: Parámetros base de validated params (usados en NEUTRAL regime)

    Returns:
        Diccionario con umbrales ajustados por régimen
    """
    if current_vix < 20:  # Mercado tranquilo/bullish
        return {
            'regime_name': 'BULL',
            'min_rvol': base_min_rvol * 1.0,  # Relax (same as base)
            'min_adr': base_min_adr * 1.0,    # Relax (same as base)
            'max_dist_sma20': base_max_dist_sma20 * 1.15,  # Allow +15% extension
            'max_stop_pct': base_max_stop_pct * 1.08,      # Allow +8% wider stops
            'min_dollar_volume': base_min_dollar_volume * 0.67,  # Relax liquidity -33%
            'min_consolidation_days': max(5, int(base_min_consolidation_days * 0.6)),  # Shorter consolidation
            'strict_sector': False
        }
    elif current_vix < 30:  # Mercado normal - USE BASE PARAMS
        return {
            'regime_name': 'NEUTRAL',
            'min_rvol': base_min_rvol,
            'min_adr': base_min_adr,
            'max_dist_sma20': base_max_dist_sma20,
            'max_stop_pct': base_max_stop_pct,
            'min_dollar_volume': base_min_dollar_volume,
            'min_consolidation_days': base_min_consolidation_days,
            'strict_sector': False
        }
    else:  # Mercado volátil/bear - TIGHTEN
        return {
            'regime_name': 'BEAR',
            'min_rvol': base_min_rvol * 1.2,   # +20% más estricto
            'min_adr': base_min_adr * 1.6,     # +60% más estricto
            'max_dist_sma20': base_max_dist_sma20 * 0.71,  # -29% menos extensión
            'max_stop_pct': base_max_stop_pct * 0.92,      # -8% stops más ajustados
            'min_dollar_volume': base_min_dollar_volume * 1.67,  # +67% más liquidez requerida
            'min_consolidation_days': int(base_min_consolidation_days * 1.2),  # +20% más consolidación
            'strict_sector': True
        }


@lru_cache(maxsize=256)
def should_trade_long(spy_price: float, spy_sma50: float, vix_value: float, max_vix_threshold: float = 35.0) -> bool:
    """
    Determina si se debe operar en largo basándose en SPY y VIX.

    Args:
        spy_price: Precio actual de SPY
        spy_sma50: SMA50 de SPY
        vix_value: Valor actual del VIX
        max_vix_threshold: Umbral máximo de VIX (default 35.0)

    Returns:
        True si se permite operar en largo, False en caso contrario
    """
    if spy_price <= spy_sma50:
        return False

    if vix_value > max_vix_threshold:
        return False

    return True


def get_position_size(entry_price, stop_loss, risk_per_trade=150):
    """
    Calculate position size based on fixed dollar risk per trade.

    Args:
        entry_price: Entry price for the position
        stop_loss: Stop loss price for the position
        risk_per_trade: Dollar amount to risk per trade (default $150)

    Returns:
        Number of shares to buy based on fixed risk amount
    """
    RISK_PER_TRADE = risk_per_trade  # Dólares Fijos. Puede ser sobrescrito por parametro.

    risk_per_share = abs(entry_price - stop_loss)

    if risk_per_share == 0:
        return 0

    shares = int(RISK_PER_TRADE / risk_per_share)

    return shares

class AdvancedVectorBTEngine:
    """
    Advanced vectorized backtesting with partial exits support.
    Simulates realistic position management with scaled exits.
    """
    
    def __init__(self, 
                 universe: List[str],
                 start_date: str,
                 end_date: str,
                 initial_capital: float = 100000,
                 risk_pct: float = 0.005,
                 risk_dollars: Optional[float] = None,  # NEW: Fixed dollar risk
                 max_exposure_pct: float = 0.35,  # INCREASED: 35% (was 25%) to reduce zero_shares rejections
        # Filter parameters (configurable)
        max_dist_sma20: float = 15.0,  # OPTIMIZED: 15.0% (was 2.5%)
        # RVOL filters
        min_rvol: float = 2.0,  # OPTIMIZED: 2.0x (was 2.5x)
        rvol_danger: float = 4.0,  # PROFESSIONAL: Danger zone (was 3.0)
        rvol_warning: float = 3.0,  # PROFESSIONAL: Warning zone (was 2.0)
        rvol_danger_size: int = 40,  # RELAXED: 40% (was 25%) to reduce zero_shares
        rvol_warning_size: int = 70,  # RELAXED: 70% (was 60%) to reduce zero_shares
        # ADR filters
        min_adr: float = 2.0,  # OPTIMIZED: 2.0% (was 5.0%)
        adr_high: float = 6.0,
        adr_med: float = 5.0,
        # Target Multiples (Optimized)
        tp1_r: float = 1.75,
        tp2_r: float = 3.5,
        # Volume filters
        min_volume: int = 300000,  # Min daily volume (300k shares)
        min_dollar_volume: float = 5000000,  # PROFESSIONAL: $5M (was $15M, too restrictive)
        max_stop_pct: float = 6.5,  # PROFESSIONAL: Max 6.5% (was 8.0%)
        earnings_days: int = 5,
        earnings_cushion: float = 10.0,
        use_earnings_calendar: bool = True,
        offline_mode: bool = True,
        # Sector rotation parameters (NEW)
        use_composite_sector_scoring: bool = False,  # Use Top 40% methodology
        sector_top_percentile: float = 0.40,  # Top 40% of sectors
        require_positive_rs: bool = False,  # CONVERGENCE: False by default (was True)
        # Market regime parameters (NEW)
        use_market_regime_filter: bool = False,  # Enable market context filter
        block_trades_in_stage3: bool = True,  # Block longs in distribution
        block_trades_in_stage4: bool = True,  # Block longs in bear market
        adjust_risk_by_regime: bool = True,  # Adjust position size by market stage
        use_dynamic_thresholds: bool = False,  # Use VIX-based dynamic thresholds
        max_vix_threshold: float = 35.0,  # PROFESSIONAL: VIX > 35 = NO trades (was 30)
        require_spy_above_sma50: bool = True,  # PROFESSIONAL: SPY > SMA50 required
        min_consolidation_days: int = 10,  # PROFESSIONAL: VCP quality (was 5)
        use_adaptive_filtering: bool = False,  # NEW: Use AdaptiveFilterEngine with tiered filtering
        # NEW: RS IBD-style parameters
        use_rs_percentile: bool = False,  # Use IBD-style RS ranking (0-100 percentile)
        min_rs_percentile: float = 80.0,  # Minimum RS percentile (80 = Top 20%)
        rs_lookback_days: int = 60,  # Lookback for RS calculation (60 = 3 months)
        # NEW: SMA50/ATR Extension filter
        use_sma50_atr_filter: bool = False,  # Filter overextended stocks
        max_sma50_atr_extension: float = 2.0,  # Max ATR extension from SMA50
        # NEW: Trailing Stop parameters
        use_trailing_stop: bool = True,  # Enable trailing stop to break-even
        be_trailing_threshold: float = 0.8,  # Move stop to BE when +this R
        # NEW: Signal type for convergence with THOR
        signal_type: str = 'breakout',  # 'breakout' (close > 20d high) or 'any' (close > SMA20)
                 **kwargs):

        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()
        self.initial_capital = initial_capital
        self.risk_pct = risk_pct

        # CRITICAL: Use parameter if provided, otherwise default to 100
        if risk_dollars is not None:
            self.risk_dollars = risk_dollars
            self.use_fixed_dollar_risk = True
            logger.info(f"💰 Using FIXED DOLLAR RISK: ${self.risk_dollars} per trade (from parameter)")
        else:
            self.risk_dollars = 100.0
            self.use_fixed_dollar_risk = True
            logger.info(f"💰 Using FIXED DOLLAR RISK: ${self.risk_dollars} per trade (default)")

        # Store original risk_dollars parameter for market regime adjustments
        self.base_risk_dollars = self.risk_dollars
        
        # Store Target Multiples
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r
        
        # TP exit percentages (optimizable)
        self.tp1_pct = kwargs.get('tp1_pct', 0.5)  # Default 50%
        self.tp2_pct = kwargs.get('tp2_pct', 0.3)  # Default 30%
        self.runner_pct = kwargs.get('runner_pct', 0.2)  # Default 20%

        # Sector rotation parameters (NEW)
        self.use_composite_sector_scoring = use_composite_sector_scoring
        self.sector_top_percentile = sector_top_percentile

        # Market regime parameters (NEW)
        self.use_market_regime_filter = use_market_regime_filter
        self.block_trades_in_stage3 = block_trades_in_stage3
        self.block_trades_in_stage4 = block_trades_in_stage4
        self.adjust_risk_by_regime = adjust_risk_by_regime
        self.market_regime_classifier = None  # Initialized in run()
        self.use_dynamic_thresholds = use_dynamic_thresholds
        self.max_vix_threshold = max_vix_threshold
        self.require_spy_above_sma50 = require_spy_above_sma50
        self.min_consolidation_days = min_consolidation_days

        self.max_exposure_pct = max_exposure_pct
        self.offline_mode = offline_mode

        # Trailing stop parameters
        self.use_trailing_stop = use_trailing_stop
        self.be_trailing_threshold = be_trailing_threshold
        
        # Signal type
        self.signal_type = signal_type

        # Filter thresholds
        self.max_dist_sma20 = max_dist_sma20
        # RVOL filters
        self.min_rvol = min_rvol  # NEW: Minimum RVOL to enter
        self.rvol_danger = rvol_danger
        self.rvol_warning = rvol_warning
        self.rvol_danger_size = rvol_danger_size / 100.0  # Convert to decimal
        self.rvol_warning_size = rvol_warning_size / 100.0  # Convert to decimal
        # ADR filters
        self.min_adr = min_adr  # NEW: Minimum ADR to enter
        self.adr_high = adr_high
        self.adr_med = adr_med
        # Volume filters
        self.min_volume = min_volume  # NEW: Min daily volume
        self.min_dollar_volume = min_dollar_volume  # NEW: Min dollar volume
        self.max_stop_pct = max_stop_pct / 100.0  # Convert to decimal
        self.earnings_days = earnings_days
        self.earnings_cushion = earnings_cushion / 100.0  # Convert to decimal
        self.use_earnings_calendar = use_earnings_calendar  # NEW flag
        
        # Market regime parameters (NEW)
        self.use_market_regime_filter = use_market_regime_filter
        self.block_trades_in_stage3 = block_trades_in_stage3
        self.block_trades_in_stage4 = block_trades_in_stage4
        self.adjust_risk_by_regime = adjust_risk_by_regime
        self.market_regime_classifier = None  # Initialized in run()
        self.use_dynamic_thresholds = use_dynamic_thresholds
        self.max_vix_threshold = max_vix_threshold
        self.require_spy_above_sma50 = require_spy_above_sma50
        self.min_consolidation_days = min_consolidation_days
        self.use_adaptive_filtering = use_adaptive_filtering
        self.require_positive_rs = require_positive_rs
        
        # NEW: RS IBD-style parameters
        self.use_rs_percentile = use_rs_percentile
        self.min_rs_percentile = min_rs_percentile
        self.rs_lookback_days = rs_lookback_days
        
        # NEW: SMA50/ATR Extension filter
        self.use_sma50_atr_filter = use_sma50_atr_filter
        self.max_sma50_atr_extension = max_sma50_atr_extension
        self.min_consolidation_days = min_consolidation_days
        self.use_adaptive_filtering = use_adaptive_filtering  # NEW: Adaptive filter engine flag
        self.require_positive_rs = require_positive_rs  # NEW: Require RS > 0 to eliminate weak stocks
        
        # Initialize AdaptiveFilterEngine (will be reconfigured if use_adaptive_filtering=True)
        self.filter_engine = None
        self.rejection_stats_tier = {}  # Store rejection stats from vectorized filtering
        
        self.cache = TickerCache()
        self.data_provider = MarketDataProvider()  # For earnings data
        self.data: Dict[str, pd.DataFrame] = {}
        
        logger.info(f"🚀 Advanced VectorBT Engine initialized")
        logger.info(f"📅 Period: {start_date} to {end_date}")
        logger.info(f"🎯 Universe: {len(universe)} tickers")
        logger.info(f"🎛️  Liquidity: vol≥{min_volume/1000:.0f}k, $vol≥${min_dollar_volume/1e6:.0f}M, ADR≥{min_adr}%, RVOL≥{min_rvol}x")
        logger.info(f"🎛️  Position Size: RVOL Danger≥{rvol_danger}x→{rvol_danger_size}%, Warning≥{rvol_warning}x→{rvol_warning_size}%")
        if self.use_rs_percentile:
            logger.info(f"📊 IBD-Style RS: RS≥{self.min_rs_percentile}%, Lookback={self.rs_lookback_days}d")
        if self.use_sma50_atr_filter:
            logger.info(f"📏 SMA50/ATR: Max extension={self.max_sma50_atr_extension}x ATR")
        
        # Initialize market regime classifier if enabled
        if self.use_market_regime_filter:
            logger.info("="*60)
            logger.info("🌍 MARKET REGIME FILTER ENABLED")
            logger.info("="*60)
            try:
                spy_data, vix_data = load_spy_vix_data(
                    self.start_date.strftime('%Y-%m-%d'),
                    self.end_date.strftime('%Y-%m-%d'),
                    cache=self.data_provider
                )
                self.market_regime_classifier = MarketRegimeClassifier(spy_data, vix_data)
                logger.info("   ✅ Market regime classifier initialized")
                logger.info(f"   🚫 Block Stage 3: {self.block_trades_in_stage3}")
                logger.info(f"   🚫 Block Stage 4: {self.block_trades_in_stage4}")
                logger.info(f"   📊 Adjust risk by regime: {self.adjust_risk_by_regime}")
            except Exception as e:
                logger.error(f"   ❌ Failed to initialize market regime classifier: {e}")
                logger.warning("   ⚠️  Continuing without market regime filter")
                self.use_market_regime_filter = False
    
    def load_data(self) -> pd.DataFrame:
        """Load OHLCV data for all tickers with 1 year lookback for valid signals"""
        # Add 365 days lookback for ATH/VCP calculation
        fetch_start_date = self.start_date - pd.Timedelta(days=365)
        
        logger.info(f"📥 Loading data from {fetch_start_date.date()} (buffer) to {self.end_date.date()}...")
        logger.info(f"🎯 Universe size: {len(self.universe)} tickers")
        
        if len(self.universe) == 0:
            logger.error("❌ Universe is EMPTY! No tickers to load.")
            raise ValueError(f"Universe is empty - no tickers provided")
        
        all_data = {}
        failed = []
        partial_data = []
        
        # Calculate expected days based on FULL fetch range
        expected_days = (self.end_date - fetch_start_date).days
        expected_trading_days = int(expected_days * 0.7)
        min_required_days = max(100, int(expected_trading_days * 0.4))
        
        # Use ThreadPoolExecutor for parallel data fetching
        # Reduced max_workers from 10 to 4 to avoid SQLite lock contention
        def fetch_ticker(ticker):
            try:
                df = self.cache.get_ohlcv(
                    ticker,
                    fetch_start_date.strftime('%Y-%m-%d'),
                    self.end_date.strftime('%Y-%m-%d'),
                    offline=self.offline_mode
                )
                
                if df is not None and len(df) >= min_required_days:
                    # Basic preprocessing
                    df = df.reset_index()
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.set_index('date')
                    
                    # Track incomplete data
                    partial = None
                    if len(df) < expected_days * 0.8:
                        partial = f"{ticker} ({len(df)}/{expected_days} days)"
                    
                    return ticker, df, None, partial
                else:
                    reason = "None returned" if df is None else f"len={len(df)} < min={min_required_days}"
                    return ticker, None, reason, None
            except Exception as e:
                return ticker, None, f"Exception: {str(e)}", None

        logger.info(f"⚡ Fetching data for {len(self.universe)} tickers in parallel...")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_ticker = {executor.submit(fetch_ticker, t): t for t in self.universe}
            
            for i, future in enumerate(as_completed(future_to_ticker)):
                if (i + 1) % 100 == 0:
                    logger.info(f"   {i+1}/{len(self.universe)}...")
                
                ticker, df, failure_reason, partial_msg = future.result()
                
                if df is not None:
                    all_data[ticker] = df
                    if partial_msg:
                        partial_data.append(partial_msg)
                else:
                    if len(failed) < 10:
                        logger.warning(f"❌ SKIP {ticker}: {failure_reason}")
                    failed.append(f"{ticker} ({failure_reason})")
        
        if failed:
            logger.warning(f"⚠️  Skipped {len(failed)} tickers (insufficient data)")
            if len(failed) <= 10:
                logger.info(f"   Failed tickers: {failed}")
            else:
                logger.info(f"   First 10 failed: {failed[:10]}")
        
        if partial_data and len(partial_data) <= 5:
            logger.info(f"ℹ️  Partial data: {', '.join(partial_data)}")
        elif len(partial_data) > 5:
            logger.info(f"ℹ️  {len(partial_data)} tickers with partial data (gaps in history)")
        
        if len(all_data) == 0:
            raise ValueError(f"No data available for period {self.start_date.date()} to {self.end_date.date()}")
        
        # Update universe to only include loaded tickers
        self.universe = list(all_data.keys())
        
        # Build DataFrames
        close_data = {t: df['Close'] for t, df in all_data.items()}
        high_data = {t: df['High'] for t, df in all_data.items()}
        low_data = {t: df['Low'] for t, df in all_data.items()}
        volume_data = {t: df['Volume'] for t, df in all_data.items()}
        
        self.close = pd.DataFrame(close_data)
        self.high = pd.DataFrame(high_data)
        self.low = pd.DataFrame(low_data)
        self.volume = pd.DataFrame(volume_data)
        
        # Initialize precomputed metrics from cache
        sma20_data = {}
        sma50_data = {}
        adr_pct_data = {}
        
        # Check how many tickers have precomputed data
        cache_available_count = 0
        
        for t, df in all_data.items():
            if 'sma20' in df.columns and not df['sma20'].isna().all():
                sma20_data[t] = df['sma20']
                cache_available_count += 1
            if 'sma50' in df.columns and not df['sma50'].isna().all():
                sma50_data[t] = df['sma50']
            if 'adr_pct_20' in df.columns and not df['adr_pct_20'].isna().all():
                adr_pct_data[t] = df['adr_pct_20']
        
        # Build SMAs from precomputed data
        self.sma_20 = pd.DataFrame(sma20_data) if sma20_data else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        self.sma_50 = pd.DataFrame(sma50_data) if sma50_data else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        self.adr_pct = pd.DataFrame(adr_pct_data) if adr_pct_data else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        
        # ALIGNMENT FIX: Ensure all have same shape as Close to prevent ValueError
        self.sma_20 = self.sma_20.reindex(index=self.close.index, columns=self.close.columns)
        self.sma_50 = self.sma_50.reindex(index=self.close.index, columns=self.close.columns)
        self.adr_pct = self.adr_pct.reindex(index=self.close.index, columns=self.close.columns)
        
        # Log cache utilization
        if cache_available_count > 0:
            logger.info(f"   ✅ Using precomputed metrics for {cache_available_count}/{len(all_data)} tickers from SQLite cache")
        else:
            logger.warning("   ⚠️ No precomputed metrics found in cache, will calculate on the fly")
        
        # Extract context columns (ADR, RVOL, trend, etc.)
        # Calculate context metrics on the fly if missing (crucial fix for missing cache data)
        self.avg_volume_20 = pd.DataFrame(index=self.close.index, columns=self.close.columns)
        self.trend_aligned = pd.DataFrame(index=self.close.index, columns=self.close.columns)
        self.dollar_volume = pd.DataFrame(index=self.close.index, columns=self.close.columns)

        for t, df in all_data.items():
            # ADR already loaded from cache if available, calculate if missing
            if t not in adr_pct_data:
                if 'adr_pct_14' in df.columns:
                    self.adr_pct[t] = df['adr_pct_14']
                else:
                    high_low_pct = ((df['High'] - df['Low']) / df['Low']) * 100
                    self.adr_pct[t] = high_low_pct.rolling(20).mean()
            
            # 2. Avg Volume (20 days)
            if 'avg_volume_20' in df.columns:
                self.avg_volume_20[t] = df['avg_volume_20']
            else:
                self.avg_volume_20[t] = df['Volume'].rolling(20).mean()
            
            # 3. Dollar Volume
            if 'dollar_volume' in df.columns:
                self.dollar_volume[t] = df['dollar_volume']
            else:
                self.dollar_volume[t] = df['Close'] * df['Volume']
            
            # 4. Trend Alignment (Simple: Close > SMA50 > SMA200)
            if 'trend_aligned' in df.columns:
                self.trend_aligned[t] = df['trend_aligned']
            else:
                self.trend_aligned[t] = 0

        # Fill NaNs
        self.adr_pct = self.adr_pct.fillna(0)
        self.avg_volume_20 = self.avg_volume_20.fillna(1)
        self.dollar_volume = self.dollar_volume.fillna(0)
        self.trend_aligned = self.trend_aligned.fillna(0)
        self.sma_20 = self.sma_20.fillna(0)
        self.sma_50 = self.sma_50.fillna(0)
        
        # Ensure SMAs are populated (calculate if missing in cache)
        cache_hit_rate = (self.sma_20 != 0).sum().sum() / (self.sma_20.shape[0] * self.sma_20.shape[1])
        
        if cache_hit_rate < 0.1:
            logger.info("   ⚠️ Precomputed metrics not available, calculating on the fly...")
            self.sma_20 = self.close.rolling(20, min_periods=1).mean()
            logger.info("   ⚠️ SMA50 missing in cache, calculating on the fly...")
            self.sma_50 = self.close.rolling(50, min_periods=1).mean()
        elif self.sma_20.sum().sum() == 0:
            logger.info("   ⚠️ SMA20 empty, calculating on the fly...")
            self.sma_20 = self.close.rolling(20, min_periods=1).mean()
        elif self.sma_50.sum().sum() == 0:
            logger.info("   ⚠️ SMA50 empty, calculating on the fly...")
            self.sma_50 = self.close.rolling(50, min_periods=1).mean()
        
        # Ensure ADR is populated (calculate if missing in cache) - CRITICAL FIX
        if self.adr_pct.sum().sum() == 0:
            logger.warning("   ⚠️ ADR missing in cache, calculating on the fly...")
            daily_range_pct = ((self.high - self.low) / self.close * 100)
            self.adr_pct = daily_range_pct.rolling(20, min_periods=1).mean()
            logger.info(f"   ✅ ADR calculated - Mean: {self.adr_pct.mean().mean():.2f}%, Max: {self.adr_pct.max().max():.2f}%")
            
        # Calculate EMAs for Phase 3 (Runner) - Pre-compute once
        self.ema_8 = self.close.ewm(span=8, adjust=False, min_periods=1).mean()
        self.ema_21 = self.close.ewm(span=21, adjust=False, min_periods=1).mean()
        self.ema_10 = self.close.ewm(span=10, adjust=False, min_periods=1).mean()

        # Calculate additional quality metrics (vectorized)
        # 1. Distance from SMA20 (% extension)
        safe_sma20 = self.sma_20.replace(0, np.nan)
        self.dist_sma20_pct = ((self.close - safe_sma20) / safe_sma20 * 100).fillna(0)
        
        # 2. RVOL (Relative Volume) - Sanitize calculation
        # Uses centralized TechnicalIndicators with robust handling
        self.rvol = TechnicalIndicators.rvol(self.volume, period=20)
        
        # Mask unrealistic RVOLs (e.g., caused by avg_vol=1)
        # If avg_volume was default (1) or extremely low, RVOL will be huge. 
        # We cap valid avg_volume check at 500 shares.
        valid_vol_mask = self.avg_volume_20 > 500
        self.rvol = self.rvol.where(valid_vol_mask, 1.0).fillna(1.0)
        
        # Debug: Verify RVOL calculation
        logger.debug(f"RVOL Debug - First ticker sample:")
        logger.debug(f"  Volume: {self.volume.iloc[0, 0]}")
        logger.debug(f"  Avg Volume 20: {self.avg_volume_20.iloc[0, 0]}")
        logger.debug(f"  RVOL calculated: {self.rvol.iloc[0, 0]}")
        
        # 3. Consolidation days (días con rango < 5% en ventana de 20 días)
        daily_range_pct = TechnicalIndicators.daily_range_pct(self.high, self.low, self.close)
        self.is_consolidating = daily_range_pct < 5
        self.consolidation_days = self.is_consolidating.rolling(20).sum().fillna(0)
        
        # 3. Market Regime Data (SPY & VIX)
        try:
            logger.info("   Loading SPY and VIX data for Market Regime...")
            
            # Use centralized loader
            spy_data, vix_data = load_spy_vix_data(
                start_date=(self.start_date - pd.Timedelta(days=365)).strftime('%Y-%m-%d'),
                end_date=self.end_date.strftime('%Y-%m-%d'),
                cache=self.cache
            )
            
            # Assign to internal variables
            if spy_data is not None and not spy_data.empty:
                # Reindex SPY data to match close index
                self.spy_close = spy_data['close'].reindex(self.close.index).ffill()
                
                # We need the full dataframe for the classifier (High/Low/Close)
                # Reindex all columns
                spy_aligned = spy_data.reindex(self.close.index).ffill()
            else:
                self.spy_close = pd.Series(0, index=self.close.index)
                spy_aligned = pd.DataFrame({'close': self.spy_close, 'high': self.spy_close, 'low': self.spy_close})
                
            if vix_data is not None and not vix_data.empty:
                self.vix_close = vix_data['close'].reindex(self.close.index).ffill()
                vix_aligned = vix_data.reindex(self.close.index).ffill()
            else:
                self.vix_close = pd.Series(0, index=self.close.index)
                vix_aligned = pd.DataFrame({'close': self.vix_close})

            # Initialize classifier
            self.market_regime_classifier = MarketRegimeClassifier(
                spy_data=spy_aligned, 
                vix_data=vix_aligned
            )
            
            # Calculate Indicators for SPY (using classifier logic internally)
            # But kept here for legacy access if needed
            self.spy_ema20 = self.spy_close.ewm(span=20, adjust=False).mean()
            self.spy_sma200 = self.spy_close.rolling(window=200).mean()
            self.spy_sma50 = self.spy_close.rolling(window=50).mean()

            # Calculate Market Regime
            self.market_is_bullish = (self.spy_close > self.spy_sma200) & (self.vix_close < 20)
            self.market_is_safe = (self.spy_close > self.spy_ema20) & (self.vix_close < 20)
            
            logger.info(f"   ✅ Market Data Loaded & Aligned")

        except Exception as e:
            logger.warning(f"⚠️ Failed to load market data (SPY/VIX): {e}")
            import traceback
            logger.warning(traceback.format_exc())
            # Initialize with default safe values
            self.market_is_safe = pd.Series(True, index=self.close.index)
            self.spy_close = pd.Series(0, index=self.close.index)
            self.vix_close = pd.Series(0, index=self.close.index)

        actual_start = self.close.index.min().date()
        actual_end = self.close.index.max().date()
        
        logger.info(f"✅ Loaded: {len(self.close.columns)} tickers")
        logger.info(f"   Date range: {actual_start} to {actual_end} ({len(self.close)} days)")
        
        if actual_start > self.start_date.date() or actual_end < self.end_date.date():
            logger.warning(f"⚠️  Actual range differs from requested: {self.start_date.date()} to {self.end_date.date()}")
        
        return self.close
    
    def _build_trade_dict(self, ticker, pos, exit_date, exit_price, pnl, exit_phase, 
                          hit_target=False, was_stopped_out=True, r_multiple=0.0, 
                          outcome_category='', hold_time_days=0):
        """
        Helper function to build trade dictionary with all fields.
        OPTIMIZATION: Avoids code duplication across exit scenarios.
        """
        shares = pos['shares']
        risk_per_share = pos.get('risk_per_share', 1.0)
        
        return {
            'ticker': ticker,
            'entry_date': pos['entry_date'],
            'exit_date': exit_date,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'shares': shares,
            'pnl': pnl,
            'exit_phase': exit_phase,
            'entry_signal': pos.get('entry_signal_type', 'UNKNOWN'),
            'initial_shares': pos.get('original_shares', shares),
            'R_inicial': pos.get('adjusted_risk_dollars', 0),
            'adr_valor': pos['entry_price'] * (pos.get('context_adr', 0) / 100.0),
            'reason': exit_phase,
            'r_multiple': r_multiple if r_multiple > 0 else pnl / (shares * risk_per_share) if risk_per_share > 0 else 0,
            'outcome_category': outcome_category or (
                'BIG_WIN' if pnl > shares * 3 * risk_per_share else (
                'WIN' if pnl > 0 else (
                'SMALL_LOSS' if pnl > -shares * 0.5 * risk_per_share else 'BIG_LOSS'
            ))),
            'was_stopped_out': was_stopped_out,
            'hit_target': hit_target,
            'hold_time_category': (
                'SCALP' if hold_time_days < 3 else (
                'SWING' if hold_time_days < 10 else (
                'POSITION' if hold_time_days < 30 else 'LONG'
            ))),
            'context_adr': pos.get('context_adr', 0),
            'context_rvol': pos.get('context_rvol', 0),
            'context_trend': pos.get('context_trend', 'N/A'),
            'context_vol': pos.get('context_vol', 0),
            'context_dollar_vol': pos.get('context_dollar_vol', 0),
            'dist_sma20_pct': pos.get('dist_sma20_pct', 0),
            'consolidation_days': pos.get('consolidation_days', 0),
            'sector': pos.get('sector', 'UNKNOWN'),
            'sector_strength': pos.get('sector_strength', 0),
            'time_since_earnings': pos.get('time_since_earnings', -1),
            'spx_vs_voltrig': pos.get('spx_vs_voltrig', False),
            'spy_at_entry': pos.get('spy_at_entry', 0.0),
            'vix_at_entry': pos.get('vix_at_entry', 0.0),
            'spy_ema20_at_entry': pos.get('spy_ema20_at_entry', 0.0),
            'base_risk_dollars': pos.get('base_risk_dollars', 0),
            'adjusted_risk_dollars': pos.get('adjusted_risk_dollars', 0),
            'risk_reduction_factor': pos.get('risk_reduction_factor', 1.0),
            'size_multipliers_applied': pos.get('size_multipliers_applied', ''),
            'rvol_classification': pos.get('rvol_classification', 'UNKNOWN'),
            'price_vs_sma20': pos.get('price_vs_sma20', 0),
            'price_vs_sma50': pos.get('price_vs_sma50', 0),
            'volume_at_entry': pos.get('volume_at_entry', 0),
            'avg_volume_20d': pos.get('avg_volume_20d', 0),
            'atr_at_entry': pos.get('atr_at_entry', 0),
            'atr_pct_price': pos.get('atr_pct_price', 0),
            'volatility_regime': pos.get('volatility_regime', 'UNKNOWN'),
            'consolidation_quality': pos.get('consolidation_quality', 'B'),
            'is_vcp_pattern': pos.get('is_vcp_pattern', False),
            'days_to_next_earnings': pos.get('days_to_next_earnings', -1),
            'earnings_risk_level': pos.get('earnings_risk_level', 'UNKNOWN'),
            'vix_regime': pos.get('vix_regime', 'UNKNOWN'),
            'spy_above_ema20': pos.get('spy_above_ema20', False),
        }

    def simulate_with_partial_exits(self, entries: pd.DataFrame,
                                    entry_prices: pd.DataFrame,
                                    atr: pd.DataFrame,
                                    avwap: pd.DataFrame,
                                    signal_types: pd.DataFrame = None) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Custom simulation with partial exits and advanced filters.
        OPTIMIZED: Slices DataFrames per day to avoid .loc overhead inside ticker loop.
        Refactored to fix indentation and performance issues.
        """
        cash = self.initial_capital
        equity_curve = []
        positions = {}  # {ticker: {'shares': X, 'entry_price': Y, 'tp1_done': False, ...}}
        trade_log = []

        # --- PRE-CALCULATIONS & SETUP ---
        
        # 1. Sector Analyzer
        sector_analyzer = SectorRotationAnalyzer(
            start_date=self.start_date.strftime('%Y-%m-%d'),
            end_date=self.end_date.strftime('%Y-%m-%d')
        )
        try:
            sector_analyzer.load_sector_data()
            sector_analyzer.calculate_relative_strength(lookback_days=20)
            
            if self.use_composite_sector_scoring:
                logger.info("📊 Pre-calculating composite sector scores (Top 40% method)...")
                sector_analyzer.composite_scores = sector_analyzer.calculate_composite_score_vectorized()
        except Exception as e:
            logger.warning(f"⚠️ Sector analyzer initialization failed: {e}")

        # 2. Earnings Cache (Parallel Load)
        earnings_cache = {}
        if self.use_earnings_calendar:
            logger.info("📅 Pre-loading earnings calendar from cache (PARALLEL)...")
            loaded = 0
            
            def load_earnings_for_ticker(ticker):
                try:
                    cached_earnings = self.cache.get_earnings_history(ticker)
                    if cached_earnings is not None and not cached_earnings.empty:
                        dates = pd.to_datetime(cached_earnings['report_date']).sort_values()
                        return (ticker, dates, True)
                    return (ticker, None, False)
                except Exception:
                    return (ticker, None, False)

            max_workers = min(4, len(self.universe))  # Reduced from 8 to avoid SQLite locks
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(load_earnings_for_ticker, t): t for t in self.universe}
                for future in as_completed(futures):
                    ticker, dates, success = future.result()
                    if success:
                        earnings_cache[ticker] = dates
                        loaded += 1
            logger.info(f"   ✅ Loaded {loaded} tickers earnings")

        # 3. Pre-load Arrays for Vectorized Access
        close_arr = self.close.values
        high_arr = self.high.values
        low_arr = self.low.values
        volume_arr = self.volume.values
        atr_arr = atr.values
        avwap_arr = avwap.values
        entries_arr = entries.values
        
        # Safe array getters with defaults
        def get_arr(df, default_val=0.0):
            return df.values if hasattr(df, 'values') and not df.empty else np.full_like(close_arr, default_val)
            
        adr_arr = get_arr(self.adr_pct, 0.0)
        avg_vol_arr = get_arr(self.avg_volume_20, 1.0)
        sma50_arr = get_arr(self.sma_50, 0.0)
        trend_arr = get_arr(self.trend_aligned, 0)
        dollar_vol_arr = get_arr(self.dollar_volume, 0.0)
        dist_sma20_arr = get_arr(self.dist_sma20_pct, 0.0)
        consolidation_arr = self.consolidation_days.values if hasattr(self, 'consolidation_days') else np.zeros_like(close_arr)
        
        ema8_arr = self.ema_8.values if hasattr(self, 'ema_8') else np.zeros_like(close_arr)
        ema10_arr = self.ema_10.values if hasattr(self, 'ema_10') else np.zeros_like(close_arr)
        ema21_arr = self.ema_21.values if hasattr(self, 'ema_21') else np.zeros_like(close_arr)
        sma20_arr = self.sma_20.values if hasattr(self, 'sma_20') else np.zeros_like(close_arr)

        # Market Regime Arrays
        mkt_safe_arr = self.market_is_safe.values if hasattr(self, 'market_is_safe') else np.zeros(len(self.close), dtype=bool)
        mkt_bullish_arr = self.market_is_bullish.values if hasattr(self, 'market_is_bullish') else np.zeros(len(self.close), dtype=bool)
        mkt_spy_arr = self.spy_close.values if hasattr(self, 'spy_close') else np.zeros(len(self.close))
        mkt_vix_arr = self.vix_close.values if hasattr(self, 'vix_close') else np.zeros(len(self.close))
        mkt_ema20_arr = self.spy_ema20.values if hasattr(self, 'spy_ema20') else np.zeros(len(self.close))
        mkt_sma200_arr = self.spy_sma200.values if hasattr(self, 'spy_sma200') else np.zeros(len(self.close))

        # Ticker Index Map
        ticker_to_idx = {ticker: idx for idx, ticker in enumerate(self.close.columns)}

        # Filter Statistics
        filter_stats = {k: 0 for k in ['weak_sector', 'max_daily', 'low_volume', 'earnings_too_close',
                                     'gap_down', 'sector_concentration', 'time_since_earnings',
                                     'consolidation_too_short', 'negative_sector_strength',
                                     'missing_sector_strength', 'error_sector_strength', 'zero_shares']}
        sector_positions = {}  # Now stores total exposure by sector (in $)
        max_sector_exposure_pct = 0.50  # Max 50% of capital per sector

        # --- SIMULATION LOOP ---
        sim_dates = self.close.index[self.close.index >= self.start_date]
        date_indices = [self.close.index.get_loc(date) for date in sim_dates]

        for date_idx in tqdm(date_indices, desc="   ⚡ Simulating"):
            date = self.close.index[date_idx]
            daily_entry_count = 0
            
            # --- DAILY CONTEXT ---
            # Pre-fetch scalar market values
            mkt_safe = bool(mkt_safe_arr[date_idx])
            mkt_bullish = bool(mkt_bullish_arr[date_idx])
            mkt_spy = float(mkt_spy_arr[date_idx])
            mkt_vix = float(mkt_vix_arr[date_idx])
            
            # Dynamic Regime Configuration
            current_stop_atr_mult = 1.0
            current_max_risk_cap = 0.08
            current_max_exposure = 0.25
            current_target_rr_1 = self.tp1_r
            current_target_rr_2 = self.tp2_r
            
            if self.use_dynamic_thresholds and hasattr(self, 'max_stop_pct_dynamic'):
                try:
                    current_max_risk_cap = float(self.max_stop_pct_dynamic.iloc[date_idx])
                    current_stop_atr_mult = 1.5 if mkt_vix < 15 else 1.0
                except: pass
            else:
                # Use configured static parameters (Baseline Mode)
                current_max_risk_cap = float(self.max_stop_pct)
                # To match THOR (Fixed % Stop), we make ATR stop irrelevant by setting it high
                # This forces the logic to use current_max_risk_cap as the stop
                current_stop_atr_mult = 50.0
            
            # Growth Mode
            is_growth = (mkt_spy > mkt_sma200_arr[date_idx]) and (mkt_vix < 20)
            if is_growth:
                current_max_exposure = 0.50
                current_target_rr_1 = 2.5
                current_target_rr_2 = 5.0

            # Daily Arrays (Slicing)
            day_close = close_arr[date_idx]
            day_high = high_arr[date_idx]
            day_low = low_arr[date_idx]
            day_atr = atr_arr[date_idx]
            day_avwap = avwap_arr[date_idx]
            day_entries = entries_arr[date_idx]
            day_ema10 = ema10_arr[date_idx]
            day_sma20 = sma20_arr[date_idx]
            day_sma50 = sma50_arr[date_idx]
            
            # Helper for daily ticker value
            def get_val(arr, idx): return arr[idx]

            # --- PROCESS EXITS (Existing Positions) ---
            # Use list(keys) to allow modification during iteration
            for ticker in list(positions.keys()):
                pos = positions[ticker]
                idx = ticker_to_idx.get(ticker)
                if idx is None: continue

                current_price = get_val(day_close, idx)
                if pd.isna(current_price): continue
                
                # Setup Exit Variables
                exit_signal = False
                exit_price = current_price
                exit_reason = "UNKNOWN"
                shares_to_sell = 0
                
                r_value = get_val(day_atr, idx)
                ticker_high = get_val(day_high, idx)
                ticker_low = get_val(day_low, idx)
                
                # Baseline Convergence: Match THOR's Close-Only logic
                if not self.use_dynamic_thresholds:
                    ticker_high = current_price
                    ticker_low = current_price
                
                # Targets
                tp1_price = pos['entry_price'] + (r_value * current_target_rr_1)
                tp2_price = pos['entry_price'] + (r_value * current_target_rr_2)

                # --- TRAILING STOP TO BREAK-EVEN ---
                if self.use_trailing_stop:
                    # Si el precio se mueve +threshold R a favor, mueve el stop a entrada
                    unrealized_pnl = (current_price - pos['entry_price']) / pos['risk_per_share']
                    be_trailing_done = pos.get('be_trailing_done', False)
                    be_threshold = self.be_trailing_threshold  # Usar el parámetro configurable

                    if not be_trailing_done and unrealized_pnl >= be_threshold and not pos['tp1_done']:
                        pos['stop_price'] = pos['entry_price']  # Mover a break-even y guardar en posición
                        pos['be_trailing_done'] = True
                        be_trailing_done = True

                # Current Stop (get from position dict to preserve trailing stop changes)
                stop_price = pos['entry_price'] if pos['tp1_done'] else pos['stop_price']

                # 1. EARNINGS EXIT CHECK
                if self.use_earnings_calendar and ticker in earnings_cache:
                    dates = earnings_cache[ticker]
                    future_earnings = dates[dates > date]
                    if not future_earnings.empty:
                        days_to = (future_earnings.iloc[0] - date).days
                        unrealized_pnl = (current_price - pos['entry_price']) / pos['entry_price']
                        
                        if unrealized_pnl < self.earnings_cushion and 0 <= days_to < self.earnings_days:
                            exit_signal = True
                            exit_reason = f"EARNINGS_EXIT(<{self.earnings_cushion*100:.0f}%,{days_to}d)"
                            shares_to_sell = pos['shares']
                
                if not exit_signal:
                    # 2. STOP LOSS CHECK
                    if ticker_low <= stop_price:
                        exit_signal = True
                        exit_price = stop_price
                        # Check open gap
                        if hasattr(self, 'open'):
                             day_open_val = self.open.values[date_idx, idx]
                             if not pd.isna(day_open_val) and day_open_val < stop_price:
                                  exit_price = day_open_val

                        shares_to_sell = pos['shares']
                        # Si el stop está en break-even (entry_price), es STOP_BE, no STOP
                        if stop_price >= pos['entry_price'] - 0.001:  # Tolerancia para flotantes
                            exit_reason = 'STOP_BE' if pos['tp1_done'] else ('RUNNER_STOP' if pos['tp2_done'] else 'STOP_BE')
                        else:
                            # Stop está por debajo del entry (pérdida real)
                            exit_reason = 'STOP'  # STOP completo cuando el stop está por debajo de BE

                if not exit_signal:
                    # 3. TP1 CHECK
                    if not pos['tp1_done']:
                        if ticker_high >= tp1_price: # Hit target
                            shares_to_sell = int(pos['original_shares'] * 0.5)
                            shares_to_sell = min(shares_to_sell, pos['shares'])
                            exit_price = tp1_price
                            # Cap at high? In backtest, we assume fill at limit. 
                            # But if gap up? Let's use max(tp1, open) if open > tp1? 
                            # Simpler: max(tp1, min(high, ...))
                            exit_reason = 'TP1'
                            exit_signal = True
                            # Note: Partial exit, so we continue to check other conditions? 
                            # No, one action per day usually simpler.

                if not exit_signal:
                    # 4. TP2 CHECK
                    if pos['tp1_done'] and not pos['tp2_done']:
                        if ticker_high >= tp2_price:
                            shares_to_sell = int(pos['original_shares'] * 0.3)
                            shares_to_sell = min(shares_to_sell, pos['shares'])
                            exit_price = tp2_price
                            exit_reason = 'TP2'
                            exit_signal = True

                if not exit_signal:
                    # 5. PHASE 3 (RUNNER) CHECK
                    if pos['tp2_done']:
                        # Logic for runner exit (EMA/SMA break)
                        current_adr = pos.get('context_adr', 0)
                        runner_exit = False
                        reason = ""
                        
                        if current_adr > 6.0: # Rocket Mode
                            ema10 = get_val(day_ema10, idx)
                            if ema10 > 0 and current_price < ema10:
                                runner_exit = True; reason = "EMA10_BREAK"
                        elif 3.0 <= current_adr <= 5.0: # Trend Mode
                            if mkt_bullish:
                                sma20 = get_val(day_sma20, idx)
                                if sma20 > 0 and current_price < sma20: runner_exit = True; reason = "SMA20_BREAK"
                            else:
                                ema10 = get_val(day_ema10, idx)
                                if ema10 > 0 and current_price < ema10: runner_exit = True; reason = "EMA10_BREAK_DEF"
                        else: # Default
                            sma20 = get_val(day_sma20, idx)
                            if sma20 > 0 and current_price < sma20: runner_exit = True; reason = "SMA20_BREAK"
                        
                        if runner_exit:
                            exit_signal = True
                            exit_reason = "RUNNER"  # Simplified for consistency with VectorBT baseline
                            shares_to_sell = pos['shares']
                            exit_price = current_price

                # EXECUTE EXIT
                if exit_signal and shares_to_sell > 0:
                    pnl = (exit_price - pos['entry_price']) * shares_to_sell
                    cash += (exit_price * shares_to_sell)
                    
                    # Log Trade
                    hold_time = (date - pos['entry_date']).days
                    r_mult = 0 # Calculated in helper
                    
                    trade_record = self._build_trade_dict(
                        ticker, pos, date, exit_price, pnl, exit_reason,
                        hit_target=('TP' in exit_reason),
                        was_stopped_out=('STOP' in exit_reason),
                        hold_time_days=hold_time
                    )
                    trade_log.append(trade_record)
                    
                    # Update Position
                    pos['shares'] -= shares_to_sell
                    if exit_reason == 'TP1': pos['tp1_done'] = True
                    if exit_reason == 'TP2': pos['tp2_done'] = True
                    
                    if pos['shares'] <= 0:
                        del positions[ticker]
                        # Update sector exposure (remove position value at entry price)
                        sec = pos.get('sector', 'UNKNOWN')
                        if sec in sector_positions:
                            sector_positions[sec] = max(0, sector_positions[sec] - pos.get('cost', 0))

            # Calculate position value before entries (for sector concentration check)
            pos_val = sum(positions[t]['shares'] * get_val(day_close, ticker_to_idx[t]) for t in positions)

            # --- PROCESS ENTRIES (New Positions) ---
            # Vectorized entry check
            valid_entry_indices = np.where(day_entries)[0]
            
            for idx in valid_entry_indices:
                ticker = self.close.columns[idx]
                if ticker in positions: continue
                
                # 1. Max Daily
                if daily_entry_count >= 3:
                    filter_stats['max_daily'] += 1
                    break
                
                # 2. Sector Checks (Max 50% exposure per sector)
                ticker_sector = SECTOR_MAP.get(ticker, 'UNKNOWN')
                current_sector_exposure = sector_positions.get(ticker_sector, 0)
                if current_sector_exposure > (cash + pos_val) * max_sector_exposure_pct:
                    filter_stats['sector_concentration'] += 1
                    continue
                
                # Sector Strength
                sector_strength = 0.0
                if sector_analyzer and sector_analyzer.sector_strength is not None:
                    try:
                        if ticker_sector in sector_analyzer.sector_strength.columns:
                            val = sector_analyzer.sector_strength.loc[date, ticker_sector]
                            if not pd.isna(val): sector_strength = float(val)
                    except: pass

                if self.require_positive_rs and sector_strength <= 0:
                    filter_stats['negative_sector_strength'] += 1
                    continue

                # Debug: Log first few entry attempts
                if len(trade_log) == 0 and len(filter_stats) < 10:
                    logger.debug(f"🔍 Entry attempt {ticker}: ADR={get_val(adr_arr[date_idx], idx):.2f}%, RVOL={vol/avg_vol if avg_vol>0 else 1:.2f}x, "
                               f"Vol=${vol*entry_price/1e6:.1f}M, Sector_RS={sector_strength:.2f}")
                    
                # 3. Consolidation Check
                consol_days = get_val(consolidation_arr[date_idx], idx) if hasattr(self, 'consolidation_days') else 10
                if consol_days < self.min_consolidation_days:
                    filter_stats['consolidation_too_short'] += 1
                    continue

                # 4. Earnings Check (Entry)
                days_to_earnings = -1
                if ticker in earnings_cache:
                    dates = earnings_cache[ticker]
                    future = dates[dates > date]
                    if not future.empty:
                        days_to_earnings = (future.iloc[0] - date).days
                        
                    # Check "Time since earnings" (e.g. don't buy immediately after?)
                    past = dates[dates < date]
                    if not past.empty:
                        since = (date - past.iloc[-1]).days
                        if since < 1: 
                            filter_stats['time_since_earnings'] += 1
                            continue

                # --- POSITION SIZING ---
                entry_price = get_val(day_close, idx)
                r_val = get_val(day_atr, idx)
                if pd.isna(entry_price) or pd.isna(r_val) or r_val <= 0: continue
                
                # Dynamic Stop
                stop_dist = r_val * current_stop_atr_mult
                technical_stop = entry_price - stop_dist
                
                # Risk Cap
                adr_val = get_val(adr_arr[date_idx], idx)
                max_risk_adr = (adr_val / 100.0) * 2.0
                # In baseline (static) mode, we trust current_max_risk_cap (max_stop_pct) to match THOR
                if not self.use_dynamic_thresholds:
                    allowed_risk_pct = current_max_risk_cap
                else:
                    allowed_risk_pct = min(max_risk_adr, current_max_risk_cap)
                
                current_risk_pct = (entry_price - technical_stop) / entry_price
                if current_risk_pct > allowed_risk_pct:
                    stop_price = entry_price * (1 - allowed_risk_pct)
                else:
                    stop_price = technical_stop

                # Risk Amount
                risk_amt = self.risk_dollars
                # Only reduce risk in dynamic mode
                if self.use_dynamic_thresholds and not mkt_bullish: 
                    risk_amt *= 0.5 # Half risk in bad market
                
                # Unified Position Size
                # (Simplified call for speed, assuming helper does heavy lifting)
                # To be perfectly safe, we'll do simple calc here or call the helper?
                # The user wants "cleaner code". Calling the helper `integrate_with_unified_position_size` is good but slow if called in loop?
                # It does some string parsing. Let's do basic sizing here to be fast, or use the helper if critical.
                # Actually, `integrate...` provides important logic (RVOL adjustments).
                # I will implement the logic inline for speed.
                
                shares = int(risk_amt / (entry_price - stop_price)) if (entry_price - stop_price) > 0 else 0
                
                # RVOL Adjustment
                vol = get_val(volume_arr[date_idx], idx)
                avg_vol = get_val(avg_vol_arr[date_idx], idx)
                rvol = vol / avg_vol if avg_vol > 0 else 1.0
                
                reduction = 1.0
                if rvol >= self.rvol_danger: reduction = self.rvol_danger_size
                elif rvol >= self.rvol_warning: reduction = self.rvol_warning_size
                
                shares = int(shares * reduction)
                cost = shares * entry_price
                
                if cost > (cash * current_max_exposure):
                    shares = int((cash * current_max_exposure) / entry_price)
                    cost = shares * entry_price
                
                if cost > cash:
                    shares = int(cash / entry_price)
                    cost = shares * entry_price

                if shares == 0:
                    logger.debug(f"   ⚠️ Zero shares for {ticker}: Price={entry_price:.2f}, Stop={stop_price:.2f}, Risk=${risk_amt:.0f}, Shares (init)={int(risk_amt / (entry_price - stop_price)) if (entry_price - stop_price) > 0 else 0}, Cash=${cash:.0f}")

                if shares > 0:
                    cash -= (shares * entry_price)
                    daily_entry_count += 1
                    sector_positions[ticker_sector] = sector_positions.get(ticker_sector, 0) + (shares * entry_price)

                    # Create Position Record
                    positions[ticker] = {
                        'shares': shares,
                        'original_shares': shares,
                        'entry_price': entry_price,
                        'stop_price': stop_price,
                        'risk_per_share': entry_price - stop_price,
                        'entry_date': date,
                        'tp1_done': False,
                        'tp2_done': False,
                        'sector': ticker_sector,
                        'sector_strength': sector_strength,
                        'context_adr': adr_val,
                        'context_rvol': rvol,
                        'consolidation_days': consol_days,
                        'base_risk_dollars': self.risk_dollars,
                        'adjusted_risk_dollars': risk_amt,
                        'cost': shares * entry_price,
                        'be_trailing_done': False,
                        # ... Add other fields as needed for _build_trade_dict ...
                    }
                else:
                    filter_stats['zero_shares'] += 1
                    logger.debug(f"   ⚠️ Zero shares for {ticker}: Price={entry_price:.2f}, Stop={stop_price:.2f}, Risk=${risk_amt:.0f}, RVOL={rvol:.2f}x")

            # Update Equity
            pos_val = sum(positions[t]['shares'] * get_val(day_close, ticker_to_idx[t]) for t in positions)
            equity_curve.append(cash + pos_val)

        # --- FINALIZE ---
        logger.info("\n🎯 FILTER EFFECTIVENESS:")
        for r, c in sorted(filter_stats.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   {r:20s}: {c:4d} rejections")
        
        # Log summary of entry filtering
        total_entries = sum([entries_arr[d].sum() for d in date_indices if d < len(entries_arr)])
        total_trades = len(trade_log)
        logger.info(f"\n📊 ENTRY TO TRADE CONVERSION:")
        logger.info(f"   Total entries processed: {total_entries}")
        logger.info(f"   Total trades executed: {total_trades}")
        if total_entries > 0:
            conversion_rate = (total_trades / total_entries) * 100
            logger.info(f"   Conversion rate: {conversion_rate:.2f}%")

        equity_series = pd.Series(equity_curve, index=sim_dates)
        trades_df = pd.DataFrame(trade_log)
        
        # Post-process trades_df
        if not trades_df.empty:
            trades_df['returns_pct'] = ((trades_df['exit_price'] - trades_df['entry_price']) / trades_df['entry_price'] * 100)
            trades_df['is_profitable'] = trades_df['pnl'] > 0
            trades_df['position_value'] = trades_df['entry_price'] * trades_df['shares']
            trades_df['source'] = 'vectorbt_advanced'

        return equity_series, trades_df
    def calculate_atr(self, period: int = 14) -> pd.DataFrame:
        """Calculate Average True Range vectorized - OPTIMIZED"""
        high_low = self.high - self.low
        high_close = np.abs(self.high - self.close.shift())
        low_close = np.abs(self.low - self.close.shift())
        
        # Fully vectorized - use np.maximum for element-wise max
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        
        # Rolling mean on the entire DataFrame at once
        atr = pd.DataFrame(tr, index=self.high.index, columns=self.high.columns).rolling(period).mean()
        
        return atr

    def calculate_rs_percentile(self, lookback_days: int = 60) -> pd.DataFrame:
        """
        Calculate RS (Relative Strength) as percentile ranking vs market.
        IBD-style: RS 80+ means stock is better than 80% of market (Top 20%).
        
        Args:
            lookback_days: Period to calculate performance (default 60 = 3 months)
            
        Returns:
            DataFrame with RS percentile (0-100) for each ticker per day
        """
        logger.info(f"📈 Calculating RS Percentile (IBD-style, {lookback_days}d lookback)...")
        
        # Calculate performance for each ticker
        performance = self.close.pct_change(lookback_days)
        
        # Calculate percentile rank across all tickers for each day
        # RS = percentile of performance vs all stocks that day
        rs_percentile = performance.rank(axis=1, pct=True) * 100
        
        logger.info(f"   ✅ RS Percentile calculated (mean: {rs_percentile.mean().mean():.1f})")
        
        return rs_percentile

    def calculate_sma50_atr_extension(self, atr_mult: float = 2.0) -> pd.DataFrame:
        """
        Calculate how far price is from SMA50 in terms of ATR.
        This prevents buying overextended stocks.
        
        Extension = (Price - SMA50) / ATR
        Extension > threshold: Price too extended (avoid entry)
        
        Args:
            atr_mult: Maximum ATR multiplier allowed (default 2.0)
            
        Returns:
            DataFrame with ATR extension for each ticker
        """
        logger.info(f"📏 Calculating SMA50/ATR Extension (max {atr_mult}x ATR)...")
        
        # Calculate SMA50
        sma50 = self.close.rolling(50).mean()
        
        # Calculate ATR
        atr = self.calculate_atr(14)
        
        # Extension = (Price - SMA50) / ATR
        extension = (self.close - sma50) / atr
        
        logger.info(f"   ✅ Extension calculated (mean: {extension.mean().mean():.2f}x ATR)")
        
        return extension
    
    def run_backtest(self) -> Dict:
        """Execute backtest with partial exits"""
        logger.info("🎯 Starting advanced backtest with partial exits...")
        
        # Load data
        self.load_data()
        
        if len(self.close.columns) == 0:
            return self._empty_results()
        
        # Calculate entry signals using built-in logic
        logger.info("🔍 Calculating entry signals...")

        # =====================================================================
        # BASELINE MODE: Use THOR-compatible logic when all filters are OFF
        # =====================================================================
        # Detect if we're in baseline mode (all advanced filters OFF)
        is_baseline_mode = (
            not self.use_dynamic_thresholds and
            not self.use_adaptive_filtering and
            not self.require_spy_above_sma50 and
            not self.use_market_regime_filter and
            not self.require_positive_rs and
            not self.use_rs_percentile and
            not self.use_sma50_atr_filter
        )

        if is_baseline_mode:
            # BASELINE MODE: Use THOR-compatible logic
            # This ensures convergence between THOR and Advanced engines
            logger.info("   🔧 BASELINE MODE: Using THOR-compatible entry logic")

            # Step 1: Calculate indicators (THOR-style)
            safe_sma20 = self.sma_20.fillna(0)
            safe_avg_vol = self.avg_volume_20.fillna(1)
            dollar_volume = self.close * safe_avg_vol

            # RVOL (THOR style: volume / vol_sma20)
            rvol = self.rvol

            # ADR (THOR style: Now using 20-day rolling average for consistency)
            adr = TechnicalIndicators.adr(self.high, self.low, self.close, period=20)

            # Distance to SMA20
            dist_sma20_pct = ((self.close - safe_sma20) / safe_sma20 * 100)

            # Consolidation days (THOR: count days inside BB)
            bb_std = self.close.rolling(20).std()
            bb_upper = safe_sma20 + (bb_std * 2)
            bb_lower = safe_sma20 - (bb_std * 2)
            inside_bb = (self.close >= bb_lower) & (self.close <= bb_upper)
            consolidation_days = inside_bb.rolling(20).sum()

            # Step 2: Apply THOR baseline filters
            # Liquidity: rvol >= min_rvol, adr >= min_adr, vol >= 200k, $vol >= $5M
            liquidity = LiquidityFilters.get_mask(
                rvol=rvol,
                adr=adr,
                avg_volume=safe_avg_vol,
                dollar_volume=dollar_volume,
                min_rvol=self.min_rvol,
                min_adr=self.min_adr,
                min_volume=200000,
                min_dollar_volume=5e6
            )

            # Quality: dist_sma20 <= max_dist_sma20
            quality = (dist_sma20_pct <= self.max_dist_sma20)

            # Consolidation: days >= min_consolidation_days (THOR uses 10 by default)
            consolidation = (consolidation_days >= self.min_consolidation_days)

            # Breakout signal (THOR: close > 20d high)
            breakout_signal = (self.close > self.high.shift().rolling(20).max())

            # Combine: THOR baseline = liquidity & quality & consolidation & breakout
            entries = liquidity & quality & consolidation & breakout_signal

            logger.info(f"   📊 THOR-baseline entries: {entries.sum().sum()}")
            logger.info(f"      Liquidity passed: {liquidity.sum().sum()}")
            logger.info(f"      Quality passed: {quality.sum().sum()}")
            logger.info(f"      Consolidation passed: {consolidation.sum().sum()}")
            logger.info(f"      Breakout passed: {breakout_signal.sum().sum()}")

        else:
            # ADVANCED MODE: Use original Advanced logic with all filters
            safe_sma20 = self.sma_20.fillna(0)
            safe_avg_vol = self.avg_volume_20.fillna(1)

            # Base entry: Close > SMA20 AND Volume > 1.5x average
            base_entry = (
                (self.close > safe_sma20) &  # Above SMA20
                (self.volume > safe_avg_vol * 1.5)  # High volume
            )
            
            # Add breakout requirement if signal_type='breakout' (THOR convergence)
            if self.signal_type == 'breakout':
                breakout_signal = (self.close > self.high.shift().rolling(20).max())
                entries = base_entry & breakout_signal
                logger.info(f"   🎯 Using BREAKOUT signal (close > 20d high) for THOR convergence")
            else:
                entries = base_entry
                logger.info(f"   🎯 Using TREND signal (close > SMA20)")

        # Signal types: Mark all as BREAKOUT for now
        signal_types = pd.DataFrame(index=self.close.index, columns=self.close.columns, dtype=object)
        signal_types[entries] = 'BREAKOUT'

        # =====================================================================
        # BASELINE MODE: Use VECTORBT directly (IDENTICAL to THOR)
        # =====================================================================
        if is_baseline_mode:
            logger.info("   ⚡ BASELINE MODE: Using IDENTICAL THOR logic")

            # === THOR-COMPATIBLE SIMULATION ===
            # Use the same logic as THOR's 3-phase exits

            # Calculate position sizing (THOR style: fixed dollar risk)
            # Refactored to use centralized PositionSizer
            position_value_base = PositionSizer.get_fixed_risk_size(
                close=self.close,
                risk_dollars=self.risk_dollars,
                stop_pct=self.max_stop_pct * 100, # Convert decimal back to pct if needed, or unify. 
                                                  # Note: max_stop_pct in this class is decimal (0.07). 
                                                  # get_fixed_risk_size expects PCT (7.0).
                min_stop_pct=3.0
            )

            # Apply RVOL adjustments
            position_value = PositionSizer.apply_rvol_adjustment(
                position_value=position_value_base,
                rvol=self.rvol,
                warning_level=self.rvol_warning,
                danger_level=self.rvol_danger,
                warning_size=self.rvol_warning_size,
                danger_size=self.rvol_danger_size
            )

            # Limit exposure
            position_value = PositionSizer.apply_exposure_limit(
                position_value, 
                self.initial_capital, 
                0.25
            ).fillna(0)

            # Valid close prices
            valid_close = self.close.replace([np.inf, -np.inf], np.nan).ffill().bfill()
            valid_prices_mask = (valid_close > 0) & valid_close.notna()
            entries = entries & valid_prices_mask

            # Calculate indicators for exits
            ema8 = self.close.ewm(span=8, adjust=False).mean()
            ema21 = self.close.ewm(span=21, adjust=False).mean()

            # 3-PHASE EXITS (IDENTICAL TO THOR)
            entry_price = valid_close.where(entries, np.nan).ffill()
            stop_target = entry_price * (1 - self.max_stop_pct)
            tp1_target = entry_price * (1 + self.max_stop_pct * self.tp1_r)
            tp2_target = entry_price * (1 + self.max_stop_pct * self.tp2_r)

            position_active = entries.cumsum() > 0

            # Phase 1: 50% @ TP1 or stop
            exits_tp1 = (
                ((valid_close >= tp1_target) | (valid_close < stop_target)) &
                position_active
            )

            pf1 = vbt.Portfolio.from_signals(
                valid_close,
                entries,
                exits_tp1,
                size=position_value * self.tp1_pct,
                size_type='value',
                init_cash=self.initial_capital * self.tp1_pct,
                fees=0.001,
                slippage=0.001,
                freq='1D'
            )

            # Phase 2: 30% @ TP2 or stop
            exits_tp2 = (
                ((valid_close >= tp2_target) | (valid_close < stop_target)) &
                position_active
            )

            pf2 = vbt.Portfolio.from_signals(
                valid_close,
                entries,
                exits_tp2,
                size=position_value * self.tp2_pct,
                size_type='value',
                init_cash=self.initial_capital * self.tp2_pct,
                fees=0.001,
                slippage=0.001,
                freq='1D'
            )

            # Phase 3: 20% runner (EMA8 < EMA21)
            exits_runner = (
                ((ema8 < ema21) | (valid_close < stop_target)) &
                position_active
            )

            pf3 = vbt.Portfolio.from_signals(
                valid_close,
                entries,
                exits_runner,
                size=position_value * self.runner_pct,
                size_type='value',
                init_cash=self.initial_capital * self.runner_pct,
                fees=0.001,
                slippage=0.001,
                freq='1D'
            )

            # Aggregate results
            equity1 = pf1.value().sum(axis=1) if isinstance(pf1.value(), pd.DataFrame) else pf1.value()
            equity2 = pf2.value().sum(axis=1) if isinstance(pf2.value(), pd.DataFrame) else pf2.value()
            equity3 = pf3.value().sum(axis=1) if isinstance(pf3.value(), pd.DataFrame) else pf3.value()
            total_equity = equity1 + equity2 + equity3

            trades1 = pf1.trades.records_readable
            trades2 = pf2.trades.records_readable
            trades3 = pf3.trades.records_readable
            
            # Smart Labeling based on PnL
            def label_phase(df, win_label):
                if 'PnL' in df.columns:
                    return np.where(df['PnL'] > 0, win_label, 'STOP')
                return win_label

            trades1['exit_phase'] = label_phase(trades1, 'TP1')
            trades2['exit_phase'] = label_phase(trades2, 'TP2')
            trades3['exit_phase'] = label_phase(trades3, 'RUNNER')
            
            all_trades = pd.concat([trades1, trades2, trades3], ignore_index=True)
            
            # --- NORMALIZATION FOR APP COMPATIBILITY ---
            # Rename VectorBT columns to App standard
            column_map = {
                'Column': 'ticker',
                'Entry Date': 'entry_date',
                'Exit Date': 'exit_date',
                'Entry Price': 'entry_price',
                'Exit Price': 'exit_price',
                'Size': 'shares',
                'PnL': 'pnl'
            }
            all_trades.rename(columns=column_map, inplace=True)
            
            # Add entry_signal if missing
            if 'entry_signal' not in all_trades.columns:
                all_trades['entry_signal'] = 'THOR_BASELINE'
            
            # Add missing risk/context columns to prevent KeyErrors in App
            defaults = {
                'context_adr': 0.0, 'context_rvol': 0.0, 'context_trend': 'N/A', 
                'context_vol': 0, 'context_dollar_vol': 0,
                'base_risk_dollars': self.risk_dollars, 
                'adjusted_risk_dollars': self.risk_dollars, 
                'risk_reduction_factor': 1.0, 
                'size_multipliers_applied': '',
                'time_since_earnings': -1,
                'sector_strength': 0.0,
                'dist_sma20_pct': 0.0,
                'consolidation_days': 0,
                'spx_vs_voltrig': False,
                'spy_at_entry': 0.0,
                'vix_at_entry': 0.0,
                'spy_ema20_at_entry': 0.0
            }
            for col, val in defaults.items():
                if col not in all_trades.columns:
                    all_trades[col] = val

            # Calculate metrics
            if len(all_trades) > 0:
                total_profit = all_trades[all_trades['PnL'] > 0]['PnL'].sum()
                total_loss = abs(all_trades[all_trades['PnL'] < 0]['PnL'].sum())
                profit_factor = total_profit / total_loss if total_loss > 0 else 0
                total_trades = len(all_trades)
                final_value = total_equity.iloc[-1]
                total_invested = self.initial_capital * len(self.close.columns)
                if total_invested > 0:
                    total_return = (final_value / total_invested - 1)
                else:
                    total_return = 0.0
                
                # Sanitize NaN
                if pd.isna(total_return): total_return = 0.0

                win_rate = len(all_trades[all_trades['PnL'] > 0]) / total_trades * 100

                returns = total_equity.pct_change().dropna()
                sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

                cummax = total_equity.cummax()
                drawdown = (total_equity - cummax) / cummax
                max_dd = abs(drawdown.min()) * 100
            else:
                profit_factor = 0
                total_trades = 0
                total_return = 0
                sharpe = 0
                max_dd = 0
                win_rate = 0
                final_value = self.initial_capital

            logger.info(f"   📊 THOR-baseline trades: {total_trades}")
            logger.info(f"      TP1: {len(trades1)}, TP2: {len(trades2)}, Runner: {len(trades3)}")

            return {
                'sharpe_ratio': sharpe,
                'total_trades': total_trades,
                'win_rate': win_rate / 100.0,
                'total_return': total_return,
                'max_drawdown': max_dd / 100.0,
                'profit_factor': profit_factor,
                'final_value': final_value,
                'trades': all_trades, # Added for compatibility
                'trades_df': all_trades # Added for compatibility
            }

        # ═══════════════════════════════════════════════════════════════
        # ADVANCED MODE: Continue with manual simulation
        # ═══════════════════════════════════════════════════════════════
        if self.use_dynamic_thresholds and hasattr(self, 'vix_close'):
            logger.info("📊 Aplicando umbrales dinámicos basados en VIX...")

            # Calcular SMA50 de SPY si no existe
            if not hasattr(self, 'spy_sma50'):
                self.spy_sma50 = self.spy_close.rolling(window=50).mean()

            # Crear DataFrame de thresholds dinámicos por fecha
            dynamic_thresholds = pd.DataFrame(index=self.vix_close.index)

            for date in self.vix_close.index:
                try:
                    vix_val = float(self.vix_close.loc[date])
                    # Pass validated params as base for dynamic adjustment
                    thresholds = get_dynamic_thresholds(
                        vix_val,
                        base_min_rvol=self.min_rvol,
                        base_min_adr=self.min_adr,
                        base_max_dist_sma20=self.max_dist_sma20,
                        base_max_stop_pct=self.max_stop_pct,
                        base_min_dollar_volume=self.min_dollar_volume,
                        base_min_consolidation_days=self.min_consolidation_days
                    )
                    dynamic_thresholds.loc[date, 'min_rvol'] = thresholds['min_rvol']
                    dynamic_thresholds.loc[date, 'min_adr'] = thresholds['min_adr']
                    dynamic_thresholds.loc[date, 'max_dist_sma20'] = thresholds['max_dist_sma20']
                    dynamic_thresholds.loc[date, 'max_stop_pct'] = thresholds['max_stop_pct']
                except:
                    # Fallback to defaults if VIX data is missing
                    dynamic_thresholds.loc[date, 'min_rvol'] = self.min_rvol
                    dynamic_thresholds.loc[date, 'min_adr'] = self.min_adr
                    dynamic_thresholds.loc[date, 'max_dist_sma20'] = self.max_dist_sma20
                    dynamic_thresholds.loc[date, 'max_stop_pct'] = self.max_stop_pct * 100

            # Usar thresholds dinámicos en lugar de estáticos
            self.min_rvol_dynamic = dynamic_thresholds['min_rvol']
            self.min_adr_dynamic = dynamic_thresholds['min_adr']
            self.max_dist_sma20_dynamic = dynamic_thresholds['max_dist_sma20']
            self.max_stop_pct_dynamic = dynamic_thresholds['max_stop_pct'] / 100.0

            # Sample dynamic thresholds for logging
            if len(dynamic_thresholds) > 0:
                sample_date = dynamic_thresholds.index[0]
                sample_vix = float(self.vix_close.loc[sample_date])
                logger.info(f"   📊 Ejemplo ({sample_date.date()}): VIX={sample_vix:.1f}, "
                           f"min_rvol={dynamic_thresholds.loc[sample_date, 'min_rvol']:.1f}, "
                           f"min_adr={dynamic_thresholds.loc[sample_date, 'min_adr']:.1f}, "
                           f"max_dist={dynamic_thresholds.loc[sample_date, 'max_dist_sma20']:.1f}%")
        else:
            # Use static thresholds
            self.min_rvol_dynamic = self.min_rvol
            self.min_adr_dynamic = self.min_adr
            self.max_dist_sma20_dynamic = self.max_dist_sma20
            self.max_stop_pct_dynamic = self.max_stop_pct

        # ═══════════════════════════════════════════════════════════════
        # 🛡️ SPY > SMA50 + VIX FILTER (should_trade_long)
        # ═══════════════════════════════════════════════════════════════
        if self.use_dynamic_thresholds and hasattr(self, 'spy_close') and hasattr(self, 'spy_sma50'):
            logger.info("🌍 Aplicando filtro SPY > SMA50 y VIX < 35...")

            # Create mask for dates where trading is allowed
            trade_allowed_mask = pd.DataFrame(False, index=entries.index, columns=entries.columns)

            for date in entries.index:
                try:
                    spy_price = float(self.spy_close.loc[date])
                    spy_sma50_val = float(self.spy_sma50.loc[date]) if not pd.isna(self.spy_sma50.loc[date]) else 0.0
                    vix_val = float(self.vix_close.loc[date])

                    should_trade = should_trade_long(spy_price, spy_sma50_val, vix_val, self.max_vix_threshold)

                    if should_trade:
                        trade_allowed_mask.loc[date, :] = True
                    else:
                        # Log why trading is blocked
                        if spy_price <= spy_sma50_val:
                            logger.debug(f"   ❌ {date.date()}: Trading bloqueado - SPY ({spy_price:.2f}) ≤ SMA50 ({spy_sma50_val:.2f})")
                        elif vix_val > self.max_vix_threshold:
                            logger.debug(f"   ❌ {date.date()}: Trading bloqueado - VIX ({vix_val:.1f}) > {self.max_vix_threshold:.1f}")
                except Exception as e:
                    logger.debug(f"   ⚠️ Error checking market conditions for {date}: {e}")
                    continue

            # Apply filter: Only allow entries when market conditions are favorable
            total_entries_before_spy = entries.sum().sum()
            entries = entries & trade_allowed_mask
            total_entries_after_spy = entries.sum().sum()

            blocked_entries = total_entries_before_spy - total_entries_after_spy
            logger.info(f"   📊 Entries antes del filtro SPY/VIX: {total_entries_before_spy}")
            logger.info(f"   ❌ Entries bloqueadas (SPY≤SMA50 o VIX>{self.max_vix_threshold:.0f}): {blocked_entries}")
            logger.info(f"   ✅ Entries finales: {total_entries_after_spy}")

        # ═══════════════════════════════════════════════════════════════
        # 🛡️ FILTRO PRIMARIO: SPY > SMA50 (Siempre activo)
        # ═══════════════════════════════════════════════════════════════
        if self.require_spy_above_sma50 and hasattr(self, 'spy_sma50'):
            logger.info("🌍 Aplicando filtro SPY > SMA50 (PRIMARY FILTER)...")

            # Crear máscara: TRUE donde SPY > SMA50 OR SMA50 is NaN (allow trading during warmup)
            spy_above_sma50_mask = (self.spy_close > self.spy_sma50) | (self.spy_sma50.isna())

            # Convertir a Series de 1D con el mismo índice que entries
            # FIX: Alinear índices para evitar bloquear todos los trades
            spy_above_series = spy_above_sma50_mask.reindex(entries.index)

            # Crear máscara de broadcast: una columna de valores TRUE/FALSE para todos los tickers
            spy_above_broadcast = pd.DataFrame(
                spy_above_series.values.repeat(len(entries.columns)).reshape(-1, len(entries.columns)),
                index=entries.index,
                columns=entries.columns
            )

            # Contar rechazos
            total_entries_pre_spy = entries.sum().sum()
            rejected_spy = (entries & ~spy_above_broadcast).sum().sum()

            # Aplicar filtro: Solo entries cuando SPY > SMA50 (or warmup period)
            entries = entries & spy_above_broadcast

            total_entries_post_spy = entries.sum().sum()

            logger.info(f"   📊 Entries antes del filtro SPY: {total_entries_pre_spy}")
            logger.info(f"   ❌ Entries bloqueadas (SPY ≤ SMA50): {rejected_spy}")
            logger.info(f"   ✅ Entries finales: {total_entries_post_spy}")
        
        # Calculate AVWAP for exits
        typical_price = (self.high + self.low + self.close) / 3
        pv = typical_price * self.volume
        cum_pv = pv.cumsum()
        cum_vol = self.volume.cumsum()
        avwap = cum_pv / cum_vol
        
        # ═══════════════════════════════════════════════════════════════
        # 🔧 ADAPTIVE FILTER ENGINE - TIERED FILTERING SYSTEM (OPTIMIZADO)
        # ═════════════════════════════════════════════════════════
        if self.use_adaptive_filtering:
            logger.info("🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO...")
            
            # Initialize filter engine
            self.filter_engine = AdaptiveFilterEngine(use_dynamic=True, logger_obj=logger)
            
            total_entries_pre_filter = entries.sum().sum()
            self.rejection_stats_tier = {'TIER1': 0, 'TIER2': 0, 'TIER3': 0}
            rejected_details = []
            
            # ┌─────────────────────────────────────────────────────────────────┐
            # TIER 1: MARKET SAFETY FILTER (Vectorizado - 60x más rápido)
            # └─────────────────────────────────────────────────────────────────┘
            # FIX: Iterate over unique dates to prevent indexing errors
            for date in tqdm(entries.index.unique(), desc="   ⚡ Applying Adaptive Filter", unit="day"):
                if date in self.vix_close.index and date in self.spy_close.index:
                    # Robust scalar extraction handling duplicates
                    vix_series = self.vix_close.loc[date]
                    vix_val = float(vix_series.iloc[0]) if isinstance(vix_series, pd.Series) else float(vix_series)
                    
                    spy_series = self.spy_close.loc[date]
                    spy_price = float(spy_series.iloc[0]) if isinstance(spy_series, pd.Series) else float(spy_series)
                    
                    # Calculate SPY SMA50 if needed
                    if not hasattr(self, 'spy_sma50'):
                        self.spy_sma50 = self.spy_close.rolling(window=50).mean()
                    
                    spy_sma50_res = self.spy_sma50.loc[date]
                    if isinstance(spy_sma50_res, pd.Series):
                        spy_sma50_val = float(spy_sma50_res.iloc[0]) if not pd.isna(spy_sma50_res.iloc[0]) else None
                    else:
                        spy_sma50_val = float(spy_sma50_res) if not pd.isna(spy_sma50_res) else None
                        
                    spy_trend_strength = (spy_price - spy_sma50_val) / spy_sma50_val if spy_sma50_val is not None and spy_sma50_val > 0 else 0

                    # TIER 1: Market Safety Filter (SPY > SMA50, VIX < 35)
                    # Skip warm-up period if SMA50 is not available
                    if spy_sma50_val is None:
                        entries.loc[date, :] = False
                        self.rejection_stats_tier['TIER1'] += len(entries.columns)
                        rejected_details.append((date, 'TIER1_WarmUp', f'Warm-up period (SMA50 not ready)', len(entries.columns)))
                        continue

                    should_trade = should_trade_long(spy_price, spy_sma50_val, vix_val, self.max_vix_threshold)
                    if not should_trade:
                        entries.loc[date, :] = False
                        self.rejection_stats_tier['TIER1'] += len(entries.columns)
                        rejected_details.append((date, 'TIER1_MarketSafety', f'All tickers blocked (SPY={spy_price:.2f}, SMA50={spy_sma50_val:.2f}, VIX={vix_val:.2f}, threshold={self.max_vix_threshold})', len(entries.columns)))
                        logger.debug(f"   🚫 {date.date()}: Market Safety Filter - All tickers blocked (SPY={spy_price:.2f}, SMA50={spy_sma50_val:.2f}, VIX={vix_val:.2f})")
                    else:
                        # ┌─────────────────────────────────────────────────────────────────┐
                        # TIER 2: DYNAMIC QUALITY FILTER (Vectorizado)
                        # └─────────────────────────────────────────────────────────────────┘
                        # Get data for all tickers at once (vectorized)
                        try:
                            # Helper to safely get 1D array even with duplicates
                            def get_vals(df, d, cols):
                                res = df.loc[d, cols]
                                if isinstance(res, pd.DataFrame):
                                    return res.iloc[0].values
                                return res.values

                            # Use entries.columns to ensure alignment
                            price_arr = get_vals(self.close, date, entries.columns)
                            sma20_arr = get_vals(self.sma_20, date, entries.columns)
                            volume_arr = get_vals(self.volume, date, entries.columns)
                            avg_vol_arr = get_vals(self.avg_volume_20, date, entries.columns)
                            
                            if hasattr(self, 'adr_pct'):
                                adr_arr = get_vals(self.adr_pct, date, entries.columns)
                            else:
                                adr_arr = np.array([5.0] * len(entries.columns))
                                
                            if hasattr(self, 'dollar_volume'):
                                dollar_vol_arr = get_vals(self.dollar_volume, date, entries.columns)
                            else:
                                dollar_vol_arr = (price_arr * volume_arr)
                            
                            # Get VIX-based thresholds using validated params as base
                            thresholds = get_dynamic_thresholds(
                                vix_val,
                                base_min_rvol=self.min_rvol,
                                base_min_adr=self.min_adr,
                                base_max_dist_sma20=self.max_dist_sma20,
                                base_max_stop_pct=self.max_stop_pct,
                                base_min_dollar_volume=self.min_dollar_volume,
                                base_min_consolidation_days=self.min_consolidation_days
                            )
                            rvol_threshold = thresholds['min_rvol']
                            adr_threshold = thresholds['min_adr']
                            dist_threshold = thresholds['max_dist_sma20']
                            dollar_vol_threshold = thresholds['min_dollar_volume']
                            
                            # Safe casting and handling of NaN/None/Zero
                            try:
                                volume_arr = np.array(volume_arr, dtype=float)
                                avg_vol_arr = np.array(avg_vol_arr, dtype=float)
                                price_arr = np.array(price_arr, dtype=float)
                                sma20_arr = np.array(sma20_arr, dtype=float)
                                adr_arr = np.array(adr_arr, dtype=float)
                                
                                # Handle cases where original data was invalid (force fail if data missing)
                                invalid_data_mask = np.isnan(avg_vol_arr) | (avg_vol_arr <= 0) | np.isnan(sma20_arr) | (sma20_arr <= 0)

                                # Only process valid data
                                valid_mask = ~invalid_data_mask
                                avg_vol_safe = np.where(valid_mask, avg_vol_arr, 1.0)
                                sma20_safe = np.where(valid_mask, sma20_arr, 1.0)

                                # Calculate RVOL array (vectorized) - only for valid data
                                rvol_arr = np.zeros_like(volume_arr, dtype=float)
                                rvol_arr[valid_mask] = volume_arr[valid_mask] / avg_vol_safe[valid_mask]

                                # Vectorized comparisons
                                tier2_fail_rvol = (rvol_arr < rvol_threshold) | invalid_data_mask
                                tier2_fail_adr = (adr_arr < adr_threshold) | np.isnan(adr_arr)
                                tier2_fail_dist = ((price_arr - sma20_safe) / sma20_safe * 100 > dist_threshold) | invalid_data_mask
                            
                            except Exception as e_conv:
                                logger.warning(f"   ⚠️ Error converting data for TIER 2: {e_conv}")
                                # Fallback to prevent crash, assuming all fail if conversion fails
                                rvol_arr = np.zeros_like(volume_arr)
                                tier2_fail_rvol = np.ones_like(volume_arr, dtype=bool)
                                tier2_fail_adr = np.ones_like(volume_arr, dtype=bool)
                                tier2_fail_dist = np.ones_like(volume_arr, dtype=bool)

                            # TIER 2: Combine failures
                            tier2_fail_mask = tier2_fail_rvol | tier2_fail_adr | tier2_fail_dist
                            tier2_rejected_count = tier2_fail_mask.sum()
                            
                            if tier2_rejected_count > 0:
                                self.rejection_stats_tier['TIER2'] += tier2_rejected_count
                                for idx in np.where(tier2_fail_mask)[0]:
                                    ticker = entries.columns[idx]
                                    if tier2_fail_rvol[idx]:
                                        reason = f"TIER2_LowRVOL_Regime{thresholds['regime_name']}_{rvol_arr[idx]:.1f}x"
                                    elif tier2_fail_adr[idx]:
                                        reason = f"TIER2_LowADR_Regime{thresholds['regime_name']}_{adr_arr[idx]:.1f}%"
                                    else:
                                        reason = f"TIER2_Overextended_Regime{thresholds['regime_name']}_{(price_arr[idx] - sma20_arr[idx]) / sma20_arr[idx] * 100:.1f}%"
                                    rejected_details.append((date, 'TIER2', reason, ticker, 1))
                                entries.loc[date, tier2_fail_mask] = False
                        
                        except Exception as e:
                            logger.warning(f"   ⚠️ Error applying TIER 2 filters: {e}")
                        
                        # ┌─────────────────────────────────────────────────────────────────┐
                        # TIER 3: OPTIONAL FILTERS (Configurables - Vectorizado)
                        # └─────────────────────────────────────────────────────────────────┘
                        # Only process TIER 3 for entries that passed TIER 1 and TIER 2
                        if len(entries.columns) > 0:  # Only process if there are entries left
                            try:
                                # Get consolidation days and sector RS (vectorized if available)
                                # FIX: Use self.consolidation_days DataFrame instead of non-existent method
                                if hasattr(self, 'consolidation_days') and not self.consolidation_days.empty and date in self.consolidation_days.index:
                                    consolidation_arr = get_vals(self.consolidation_days, date, entries.columns).astype(float)
                                else:
                                    consolidation_arr = np.array([float(self.min_consolidation_days)] * len(entries.columns))
                                
                                # Sector RS - default to 0 if not available
                                sector_rs_arr = np.array([0.0] * len(entries.columns))
                                
                                # Get regime for consolidation and sector requirements
                                thresholds = get_dynamic_thresholds(vix_val)
                                consolidation_threshold = thresholds.get('min_consolidation_days', self.min_consolidation_days)
                                require_sector_strong = thresholds.get('strict_sector', False)
                                
                                # Vectorized comparisons
                                tier3_fail_consol = consolidation_arr < consolidation_threshold
                                tier3_fail_sector = require_sector_strong & (sector_rs_arr < 0)
                                tier3_fail_mask = tier3_fail_consol | tier3_fail_sector
                                tier3_rejected_count = tier3_fail_mask.sum()
                                
                                if tier3_rejected_count > 0:
                                    self.rejection_stats_tier['TIER3'] += tier3_rejected_count
                                    for idx in np.where(tier3_fail_mask)[0]:
                                        ticker = entries.columns[idx]
                                        if tier3_fail_consol[idx]:
                                            reason = f"TIER3_ShortConsolidation_{consolidation_arr[idx]}d_Req{consolidation_threshold}d"
                                        else:
                                            reason = "TIER3_WeakSector"
                                            rejected_details.append((date, 'TIER3', reason, ticker, 1))
                                    entries.loc[date, tier3_fail_mask] = False
                            
                            except Exception as e:
                                logger.warning(f"   ⚠️ Error applying TIER 3 filters: {e}")
            
            # Log summary statistics
            total_entries_post_filter = entries.sum().sum()
            rejected_entries = total_entries_pre_filter - total_entries_post_filter
            
            logger.info(f"   📊 Entries antes de Adaptive Filter: {total_entries_pre_filter}")
            logger.info(f"   ❌ Entries rechazadas por TIER:")
            logger.info(f"      TIER 1 (Market Safety): {self.rejection_stats_tier['TIER1']}")
            logger.info(f"      TIER 2 (Dynamic Quality): {self.rejection_stats_tier['TIER2']}")
            logger.info(f"      TIER 3 (Optional): {self.rejection_stats_tier['TIER3']}")
            logger.info(f"   ✅ Entries finales: {total_entries_post_filter}")
            
            # Save rejection details for Streamlit dashboard
            if rejected_details:
                # Convert to DataFrame for display
                rejection_df = pd.DataFrame(rejected_details, 
                                              columns=['date', 'tier', 'reason', 'ticker', 'count'])
                self.rejection_details_df = rejection_df
                
                # Save to CSV for detailed analysis
                rejection_df.to_csv('outputs/backtests/adaptive_filter_rejections_detailed.csv', index=False)
            
            # Print summary
            print("\n" + "="*70)
            print("📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)")
            print("="*70)
            print(f"  Total de Rechazos: {total_entries_pre_filter - total_entries_post_filter}")
            print(f"  • TIER 1 (Market Safety): {self.rejection_stats_tier['TIER1']}")
            print(f"  • TIER 2 (Dynamic Quality): {self.rejection_stats_tier['TIER2']}")
            print(f"  TIER 3 (Optional): {self.rejection_stats_tier['TIER3']}")
            print("="*70)
        elif is_baseline_mode:
            # BASELINE MODE: Skip all additional filtering (already applied in entry logic)
            logger.info("   ⚡ Skipping additional filters (baseline mode)")
        else:
            # FALLBACK: Use legacy sequential filtering
            logger.info("⚠️ Using legacy sequential filtering")
            
            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTRO DE RIESGO 0: HARD FLOOR (Precio < SMA20)
            # ═══════════════════════════════════════════════════════════════
            logger.info("🔍 Aplicando filtro HARD FLOOR: Precio >= SMA20 (Trend Alignment)...")
            
            safe_sma20_check = self.sma_20.reindex(self.close.index).fillna(0)
            below_sma20_mask = self.close < safe_sma20_check
            
            total_entries_raw = entries.sum().sum()
            rejected_below = (entries & below_sma20_mask).sum().sum()
            entries = entries & ~below_sma20_mask
            
            logger.info(f"   📊 Entries iniciales: {total_entries_raw}")
            logger.info(f"   ❌ Entries rechazadas (Bajo SMA20): {rejected_below}")
            
            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTRO DE RIESGO: SOBREEXTENSIÓN (Dist SMA20 > threshold)
            # ═══════════════════════════════════════════════════════════════
            logger.info(f"🔍 Aplicando filtro de sobreextensión (dist_sma20_pct > threshold)...")
            
            if self.use_dynamic_thresholds and hasattr(self, 'max_dist_sma20_dynamic'):
                overextended_mask = pd.DataFrame(False, index=self.dist_sma20_pct.index, columns=self.dist_sma20_pct.columns)
                for date in self.dist_sma20_pct.index:
                    if date in self.max_dist_sma20_dynamic.index:
                        threshold = self.max_dist_sma20_dynamic.loc[date]
                        overextended_mask.loc[date] = self.dist_sma20_pct.loc[date] > threshold
            else:
                overextended_mask = self.dist_sma20_pct > self.max_dist_sma20
            
            total_entries_before = entries.sum().sum()
            rejected_entries = (entries & overextended_mask).sum().sum()
            entries = entries & ~overextended_mask
            
            total_entries_after = entries.sum().sum()
            
            logger.info(f"   📊 Entries antes del filtro: {total_entries_before}")
            logger.info(f"   ❌ Entries rechazadas (>7% sobre SMA20): {rejected_entries}")
            logger.info(f"   ✅ Entries finales: {total_entries_after}")
            
            if rejected_entries > 0:
                rejection_pct = (rejected_entries / total_entries_before * 100) if total_entries_before > 0 else 0
                logger.info(f"   📉 Tasa de rechazo: {rejection_pct:.1f}%")
            
            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTRO DE LIQUIDEZ: RVOL Mínimo, ADR Mínimo, Volumen Mínimo
            # ═══════════════════════════════════════════════════════════════
            if self.use_dynamic_thresholds and hasattr(self, 'min_rvol_dynamic'):
                logger.info("🔍 Aplicando filtros de liquidez con UMBRALES DINÁMICOS...")
                
                low_rvol_mask = pd.DataFrame(False, index=self.rvol.index, columns=self.rvol.columns)
                low_adr_mask = pd.DataFrame(False, index=self.adr_pct.index, columns=self.adr_pct.columns)
                
                for date in self.rvol.index:
                    if date in self.min_rvol_dynamic.index:
                        rvol_threshold = self.min_rvol_dynamic.loc[date]
                        adr_threshold = self.min_adr_dynamic.loc[date]
                        low_rvol_mask.loc[date] = self.rvol.loc[date] < rvol_threshold
                        low_adr_mask.loc[date] = self.adr_pct.loc[date] < adr_threshold
            else:
                logger.info(f"🔍 Aplicando filtros de liquidez estáticos (RVOL≥{self.min_rvol}x, ADR≥{self.min_adr}%)...")
                
                low_rvol_mask = self.rvol < self.min_rvol
                low_adr_mask = self.adr_pct < self.min_adr
            
            low_volume_mask = self.volume < self.min_volume
            low_dollar_volume_mask = self.dollar_volume < self.min_dollar_volume
            
            total_entries_pre_liquidity = entries.sum().sum()
            rejected_low_rvol = (entries & low_rvol_mask).sum().sum()
            rejected_low_adr = (entries & low_adr_mask).sum().sum()
            rejected_low_volume = (entries & low_volume_mask).sum().sum()
            rejected_low_dollar_volume = (entries & low_dollar_volume_mask).sum().sum()
            
            entries = entries & ~low_rvol_mask & ~low_adr_mask & ~low_volume_mask & ~low_dollar_volume_mask
            
            total_entries_post_liquidity = entries.sum().sum()
            
            logger.info(f"   📊 Entries antes de filtros de liquidez: {total_entries_pre_liquidity}")
            logger.info(f"   ❌ Rechazadas por RVOL<{self.min_rvol}x: {rejected_low_rvol}")
            logger.info(f"   ❌ Rechazadas por ADR<{self.min_adr}%: {rejected_low_adr}")
            logger.info(f"   ❌ Rechazadas por Vol<{self.min_volume/1000:.0f}k: {rejected_low_volume}")
            logger.info(f"   ❌ Rechazadas por $Vol<${self.min_dollar_volume/1e6:.0f}M: {rejected_low_dollar_volume}")
            logger.info(f"   ✅ Entries finales: {total_entries_post_liquidity}")
            
            # ═══════════════════════════════════════════════════════════════
            # 🌍 FILTRO DE RÉGIMEN DE MERCADO (Market Context)
            # ═══════════════════════════════════════════════════════════════
            if self.use_market_regime_filter and self.market_regime_classifier is not None:
                logger.info("🌍 Aplicando filtro de régimen de mercado...")
                
                market_stages = {}
                blocked_entries = 0
                total_entries_pre_regime = entries.sum().sum()
                
                blocked_mask = pd.DataFrame(False, index=entries.index, columns=entries.columns)
                
                for date in entries.index:
                    context = self.market_regime_classifier.get_market_context(date)
                    market_stages[date] = context
                    
                    should_block = False
                    if self.block_trades_in_stage4 and context['market_stage'] == 'STAGE_4':
                        should_block = True
                    elif self.block_trades_in_stage3 and context['market_stage'] == 'STAGE_3':
                        should_block = True
                    
                    if should_block:
                        blocked_mask.loc[date, :] = True
                        blocked_entries += entries.loc[date, :].sum()
                    
                    if self.adjust_risk_by_regime:
                        risk_mult = context['risk_multiplier']
                        if not hasattr(self, 'regime_risk_multipliers'):
                            self.regime_risk_multipliers = {}
                        self.regime_risk_multipliers[date] = risk_mult
                
                total_entries_post_regime = entries.sum().sum()
                
                logger.info(f"   📊 Entries antes de filtro de régimen: {total_entries_pre_regime}")
                logger.info(f"   ❌ Entries bloqueadas por régimen: {blocked_entries}")
                logger.info(f"   ✅ Entries finales: {total_entries_post_regime}")
                
                if self.adjust_risk_by_regime:
                    logger.info(f"   📊 Risk adjustment by regime: ENABLED")
                
                # Count stages
                stage_counts = {}
                for context in market_stages.values():
                    stage = context['market_stage']
                    stage_counts[stage] = stage_counts.get(stage, 0) + 1
                
                logger.info(f"   📊 Market Regime Distribution:")
                for stage, count in sorted(stage_counts.items()):
                    pct = count / len(market_stages) * 100 if market_stages else 0
                    logger.info(f"      {stage}: {count} days ({pct:.1f}%)")
        
        # ═══════════════════════════════════════════════════════════════
        # 🛡️ FILTRO 3: VolTrig Classification (Size Reduction)
        # ═══════════════════════════════════════════════════════════════
        # No rechazamos entries, solo clasificamos para size reduction
        # Danger (RVOL >= 3x): Reduce size 50%
        # Warning (RVOL >= 2x): Reduce size 25%
        # Safe (RVOL < 2x): No reduction
        
        logger.info("🔍 Clasificando riesgo por RVOL (VolTrig)...")
        
        # Crear máscaras de clasificación
        self.voltrig_danger = self.rvol >= self.rvol_danger
        self.voltrig_warning = (self.rvol >= self.rvol_warning) & (self.rvol < self.rvol_danger)
        self.voltrig_safe = self.rvol < self.rvol_warning
        
        # Contar entries por categoría
        danger_entries = (entries & self.voltrig_danger).sum().sum()
        warning_entries = (entries & self.voltrig_warning).sum().sum()
        safe_entries = (entries & self.voltrig_safe).sum().sum()
        
        logger.info(f"   ☔ Danger (RVOL>={self.rvol_danger}x): {danger_entries} entries → Size {int(self.rvol_danger_size*100)}%")
        logger.info(f"   ⚠️  Warning (RVOL>={self.rvol_warning}x): {warning_entries} entries → Size {int(self.rvol_warning_size*100)}%")
        logger.info(f"   ✅ Safe (RVOL<{self.rvol_warning}x): {safe_entries} entries → Size 100%")
        
        # ═══════════════════════════════════════════════════════════════
        # 🛡️ FILTRO 4: High Volatility ADR Check
        # ═══════════════════════════════════════════════════════════════
        # ADR > 6%: Reduce size to 25%
        # ADR > 5%: Reduce size to 33%
        
        logger.info("🔍 Clasificando riesgo por ADR (volatilidad)...")
        
        self.high_adr = self.adr_pct > self.adr_high
        self.med_adr = (self.adr_pct > self.adr_med) & (self.adr_pct <= self.adr_high)
        
        high_adr_entries = (entries & self.high_adr).sum().sum()
        med_adr_entries = (entries & self.med_adr).sum().sum()
        
        logger.info(f"   🔥 High ADR (>{self.adr_high}%): {high_adr_entries} entries → Size 25%")
        logger.info(f"   ⚠️  Med ADR (>{self.adr_med}%): {med_adr_entries} entries → Size 33%")
        
        # ═══════════════════════════════════════════════════════════════
        # 📊 FILTRO 5: IBD-Style RS Percentile (Ranking vs Market)
        # ═══════════════════════════════════════════════════════════════
        if self.use_rs_percentile:
            logger.info(f"📊 Aplicando filtro RS Percentile (IBD-style, RS≥{self.min_rs_percentile})...")
            
            # Calculate RS percentile (0-100)
            rs_percentile = self.calculate_rs_percentile(lookback_days=self.rs_lookback_days)
            
            # Filter: Only entries with RS >= threshold
            low_rs_mask = rs_percentile < self.min_rs_percentile
            
            total_entries_pre_rs = entries.sum().sum()
            entries = entries & ~low_rs_mask
            total_entries_post_rs = entries.sum().sum()
            
            rejected_low_rs = total_entries_pre_rs - total_entries_post_rs
            
            logger.info(f"   📊 Entries antes del filtro RS Percentile: {total_entries_pre_rs}")
            logger.info(f"   ❌ Rechazadas por RS<{self.min_rs_percentile}: {rejected_low_rs}")
            logger.info(f"   ✅ Entries finales: {total_entries_post_rs}")
        
        # ═══════════════════════════════════════════════════════════════
        # 📏 FILTRO 6: SMA50/ATR Extension (Avoid Overextended)
        # ═══════════════════════════════════════════════════════════════
        if self.use_sma50_atr_filter:
            logger.info(f"📏 Aplicando filtro SMA50/ATR Extension (max {self.max_sma50_atr_extension}x ATR)...")
            
            # Calculate extension from SMA50 in terms of ATR
            sma50_atr_extension = self.calculate_sma50_atr_extension(atr_mult=self.max_sma50_atr_extension)
            
            # Filter: Only entries where extension < threshold
            overextended_mask = sma50_atr_extension > self.max_sma50_atr_extension
            
            total_entries_pre_extension = entries.sum().sum()
            entries = entries & ~overextended_mask
            total_entries_post_extension = entries.sum().sum()
            
            rejected_overextended = total_entries_pre_extension - total_entries_post_extension
            
            logger.info(f"   📊 Entries antes del filtro Extension: {total_entries_pre_extension}")
            logger.info(f"   ❌ Rechazadas por extensión>{self.max_sma50_atr_extension}x ATR: {rejected_overextended}")
            logger.info(f"   ✅ Entries finales: {total_entries_post_extension}")
        
        # ═══════════════════════════════════════════════════════════════
        
        # Calculate ATR
        atr = self.calculate_atr(14)
        
        # Run custom simulation
        logger.info("⚡ Simulating with partial exits...")
        equity_curve, trades_df = self.simulate_with_partial_exits(
            entries, self.close, atr, avwap, signal_types
        )
        
        # Calculate metrics
        total_return = (equity_curve.iloc[-1] - self.initial_capital) / self.initial_capital
        returns = equity_curve.pct_change().dropna()
        sharpe = returns.mean() / (returns.std() + 1e-10) * np.sqrt(252) if len(returns) > 0 else 0
        
        cum_max = equity_curve.cummax()
        drawdown = (equity_curve - cum_max) / cum_max
        max_dd = drawdown.min()
        
        # Calculate MAR Ratio and Calmar Ratio
        days_trading = len(equity_curve)
        years_trading = days_trading / 252  # 252 trading days per year
        annualized_return = (equity_curve.iloc[-1] / self.initial_capital) ** (1 / years_trading) - 1 if years_trading > 0 and total_return > -1 else 0
        
        # MAR Ratio = Annualized Return / Max Drawdown
        # Calmar Ratio = Annualized Return / Absolute Max Drawdown
        mar_ratio = annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0
        calmar_ratio = annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0
        
        winners = len(trades_df[trades_df['pnl'] > 0]) if len(trades_df) > 0 else 0
        win_rate = winners / len(trades_df) if len(trades_df) > 0 else 0
        
        # Calculate Profit Factor
        total_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum() if len(trades_df) > 0 else 0
        total_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum()) if len(trades_df) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        results = {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'annualized_return': annualized_return,
            'mar_ratio': mar_ratio,
            'calmar_ratio': calmar_ratio,
            'total_trades': len(trades_df),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'equity_curve': equity_curve,
            'trades': trades_df,
            'trades_df': trades_df  # Add alias for compatibility
        }
        
        logger.info(f"✅ Backtest complete!")
        logger.info(f"   Return: {total_return*100:.2f}%")
        logger.info(f"   Annualized Return: {annualized_return*100:.2f}%")
        logger.info(f"   Sharpe: {sharpe:.2f}")
        logger.info(f"   Max DD: {max_dd*100:.2f}%")
        logger.info(f"   MAR Ratio: {mar_ratio:.2f}")
        logger.info(f"   Calmar Ratio: {calmar_ratio:.2f}")
        logger.info(f"   Win Rate: {win_rate*100:.1f}%")
        logger.info(f"   Trades: {len(trades_df)} (including partial exits)")
        
        return results
    
    def get_position_size_by_regime(self, date: pd.Timestamp, base_risk_dollars: float) -> float:
        """
        Ajusta tamaño de posición según régimen de mercado.
        
        Args:
            date: Fecha del trade
            base_risk_dollars: Riesgo base en dólares
            
        Returns:
            Riesgo ajustado según régimen de mercado
        """
        if self.market_regime_classifier is None:
            return base_risk_dollars
        
        try:
            market_regime = self.market_regime_classifier.get_market_stage(date)
        except Exception as e:
            self.logger.warning(f"⚠️ Error getting market stage for {date}: {e}")
            return base_risk_dollars
        
        position_multipliers = {
            'STAGE_1': 1.0,  # Bull market: 100% del riesgo base
            'STAGE_2': 0.75, # Consolidation: 75% del riesgo base
            'STAGE_3': 0.25, # Distribution: 25% del riesgo base
            'STAGE_4': 0.0   # Bear market: NO operar
        }
        
        multiplier = position_multipliers.get(market_regime, 0.5)
        return base_risk_dollars * multiplier
    
    def _empty_results(self):
        return {
            'total_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'equity_curve': pd.Series(),
            'trades': pd.DataFrame(),
            'trades_df': pd.DataFrame()
        }
    
    def get_rejection_stats(self) -> Dict[str, int]:
        """
        Get combined rejection statistics from all filter sources.
        
        Returns:
            Dictionary with rejection reasons and counts
        """
        combined_stats = {}
        
        # Add tier stats from vectorized filtering
        if hasattr(self, 'rejection_stats_tier') and self.rejection_stats_tier:
            combined_stats.update({
                'TIER1_MarketSafety': self.rejection_stats_tier.get('TIER1', 0),
                'TIER2_DynamicQuality': self.rejection_stats_tier.get('TIER2', 0),
                'TIER3_Optional': self.rejection_stats_tier.get('TIER3', 0)
            })
        
        # Add stats from AdaptiveFilterEngine (if used)
        if hasattr(self, 'filter_engine') and self.filter_engine is not None:
            filter_stats = self.filter_engine.get_rejection_stats()
            if filter_stats:
                combined_stats.update(filter_stats)
        
        return combined_stats
    
    def cleanup(self):
        if hasattr(self, 'cache'):
            self.cache.close()
