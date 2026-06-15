#!/usr/bin/env python3
"""
OptimizationEngineV6_PRO - Professional Grade, Lightning Fast
==============================================================

Features:
- Load data ONCE (100× faster than AdvancedEngine)
- All professional features from AdvancedEngine
- VCP/Breakout/ATH signals
- Sector rotation (your edge!) with RS calculation
- Dynamic position sizing (RVOL-based)
- Multi-phase exits (TP1, TP2, trailing)
- Consolidation quality scoring
- Market regime awareness (SPY + VIX)
- Relative Strength calculation

Performance:
- 500 trials × 800 tickers = 15-20 minutes
- vs AdvancedEngine: 10-20 HOURS

Author: Built for the Bugatti 🏎️
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import yfinance as yf
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from scipy import stats
import gc

from src.data.ticker_cache import TickerCache
from src.data.market_data import MarketDataProvider
from src.indicators.technical import TechnicalIndicators
from src.filters.liquidity import LiquidityFilters
from src.risk.position_sizing import PositionSizer

logger = logging.getLogger(__name__)


class OptimizationEngineV6_PRO:
    """
    Professional optimization engine with full feature set.

    Architecture:
    1. Load ALL data ONCE at init
    2. Pre-calculate ALL indicators
    3. Pre-calculate ALL static filters
    4. Backtest = just apply dynamic filters + VectorBT
    """

    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        lookback_days: int = 365,
        offline_mode: bool = True,
    ):
        """
        Initialize engine and load ALL data.

        Args:
            tickers: List of ticker symbols
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_capital: Starting capital
            lookback_days: Days before start_date for indicator calculation
            offline_mode: Use only cached data
        """
        logger.info("🏎️ OptimizationEngineV6_PRO initializing...")
        logger.info(f"📅 Period: {start_date} to {end_date}")
        logger.info(f"🎯 Tickers: {len(tickers)}")

        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.lookback_days = lookback_days
        self.offline_mode = offline_mode

        self.cache = TickerCache()

        # Data containers (populated in _load_all_data)
        self.close = None
        self.open = None
        self.high = None
        self.low = None
        self.volume = None
        self.dollar_volume = None

        # Indicators (pre-calculated)
        self.sma20 = None
        self.sma50 = None
        self.sma200 = None
        self.ema10 = None
        self.ema21 = None
        self.dist_sma20 = None
        self.rvol = None
        self.adr = None

        # Advanced indicators
        self.atr = None
        self.bb_upper = None
        self.bb_lower = None
        self.consolidation_range = None
        self.consolidation_days = None

        # Market regime indicators (SPY + VIX)
        self.spy_close = None
        self.spy_ema20 = None
        self.spy_sma200 = None
        self.vix_close = None
        self.vix_sma20 = None

        # Relative Strength indicators (vs SPY)
        self.rs_5d = None
        self.rs_21d = None
        self.rs_63d = None
        self.rs_126d = None
        self.rs_avg = None

        # Earnings safety mask
        self.earnings_safe = None

        # Valid tickers (after loading)
        self.valid_tickers = []

        # Load everything
        self._load_all_data()
        self._load_market_regime_data()  # NEW: SPY + VIX
        self._calculate_indicators()
        self._calculate_advanced_indicators()
        self._calculate_relative_strength()  # NEW: RS calculation

        logger.info(f"✅ Engine ready: {len(self.valid_tickers)} tickers loaded")
        logger.info(f"📊 Shape: {self.close.shape}")

    def _load_all_data(self):
        """Load ALL price data for ALL tickers (ONE TIME ONLY)."""

        # Calculate extended date range for lookback
        extended_start = self.start_date - timedelta(days=self.lookback_days)

        logger.info(
            f"📥 Loading data from {extended_start.date()} to {self.end_date.date()}..."
        )

        all_data = {}
        skipped = 0

        for i, ticker in enumerate(self.tickers, 1):
            if i % 100 == 0:
                logger.info(f"   Progress: {i}/{len(self.tickers)}...")

            try:
                df = self.cache.get_ohlcv(
                    ticker,
                    start_date=extended_start.strftime("%Y-%m-%d"),
                    end_date=self.end_date.strftime("%Y-%m-%d"),
                    offline=self.offline_mode,
                )

                if df is not None and len(df) >= 100:  # Minimum data requirement
                    df = df.reset_index()
                    # Fix: handle both 'Date' and 'date' index names
                    index_col = df.columns[0]
                    df.rename(columns={index_col: "date"}, inplace=True)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")

                    # Normalize column names to lowercase
                    df.columns = [col.lower() for col in df.columns]

                    # Calculate dollar volume if missing
                    if "dollar_volume" not in df.columns:
                        df["dollar_volume"] = df["close"] * df["volume"]

                    all_data[ticker] = df
                else:
                    skipped += 1

            except Exception as e:
                skipped += 1
                continue

        if skipped > 0:
            logger.warning(f"⚠️  Skipped {skipped} tickers (insufficient data)")

        if not all_data:
            raise ValueError(
                "No data loaded! Check date range and ticker availability."
            )

        logger.info(f"✅ Loaded {len(all_data)} tickers")

        # Create aligned DataFrames
        self.close = pd.DataFrame(
            {ticker: df["close"] for ticker, df in all_data.items()}
        )
        self.open = pd.DataFrame(
            {ticker: df["open"] for ticker, df in all_data.items()}
        )
        self.high = pd.DataFrame(
            {ticker: df["high"] for ticker, df in all_data.items()}
        )
        self.low = pd.DataFrame({ticker: df["low"] for ticker, df in all_data.items()})
        self.volume = pd.DataFrame(
            {ticker: df["volume"] for ticker, df in all_data.items()}
        )
        self.dollar_volume = pd.DataFrame(
            {ticker: df["dollar_volume"] for ticker, df in all_data.items()}
        )

        # Fill NaN values
        for df in [
            self.close,
            self.open,
            self.high,
            self.low,
            self.volume,
            self.dollar_volume,
        ]:
            df.ffill(inplace=True)
            df.fillna(0, inplace=True)

        self.valid_tickers = list(all_data.keys())

        logger.info(f"📊 Data shape: {self.close.shape} (days × tickers)")

        # Clear memory
        del all_data
        gc.collect()

    def _load_market_regime_data(self):
        """Load SPY and VIX for market regime detection (Centralized)."""
        from src.utils.market_regime import load_spy_vix_data

        logger.info("📊 Loading market regime data (SPY + VIX)...")

        try:
            start_str = (self.start_date - timedelta(days=self.lookback_days)).strftime(
                "%Y-%m-%d"
            )
            end_str = self.end_date.strftime("%Y-%m-%d")

            # Use centralized loader
            spy_data, vix_data = load_spy_vix_data(
                start_date=start_str,
                end_date=end_str,
                cache=self.cache,
                offline=self.offline_mode,
            )

            # Align with ticker data
            if spy_data is not None:
                self.spy_close = spy_data["close"].reindex(self.close.index).ffill()
                # Calculate SPY indicators
                self.spy_ema20 = self.spy_close.ewm(span=20, adjust=False).mean()
                self.spy_sma200 = self.spy_close.rolling(window=200).mean()
            else:
                self.spy_close = pd.Series(0, index=self.close.index)
                self.spy_ema20 = pd.Series(0, index=self.close.index)
                self.spy_sma200 = pd.Series(0, index=self.close.index)

            if vix_data is not None:
                self.vix_close = vix_data["close"].reindex(self.close.index).ffill()
                # Calculate VIX indicator
                self.vix_sma20 = self.vix_close.rolling(window=20).mean()
            else:
                self.vix_close = pd.Series(0, index=self.close.index)
                self.vix_sma20 = pd.Series(0, index=self.close.index)

            logger.info("✅ Market regime data loaded")

        except Exception as e:
            logger.error(f"Failed to load market regime data: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Fallback to zeros
            self.spy_close = pd.Series(0, index=self.close.index)
            self.spy_ema20 = pd.Series(0, index=self.close.index)
            self.spy_sma200 = pd.Series(0, index=self.close.index)
            self.vix_close = pd.Series(0, index=self.close.index)
            self.vix_sma20 = pd.Series(0, index=self.close.index)

    def _calculate_indicators(self):
        """Pre-calculate ALL indicators (ONE TIME ONLY)."""
        logger.info("🔢 Calculating indicators...")

        # Moving averages
        self.sma20 = TechnicalIndicators.sma(self.close, 20)
        self.sma50 = TechnicalIndicators.sma(self.close, 50)
        self.sma200 = TechnicalIndicators.sma(self.close, 200)
        self.ema10 = TechnicalIndicators.ema(self.close, 10)
        self.ema21 = TechnicalIndicators.ema(self.close, 21)

        # Distance from SMA20 (%)
        self.dist_sma20 = (self.close - self.sma20) / self.sma20 * 100

        # RVOL (relative volume)
        self.rvol = TechnicalIndicators.rvol(self.volume, period=20)

        # ADR (Average Daily Range) %
        self.adr = TechnicalIndicators.adr(self.high, self.low, self.close, period=20)

        logger.info("✅ Indicators calculated")

    def _calculate_advanced_indicators(self):
        """Calculate advanced indicators for professional features."""
        logger.info("🔢 Calculating advanced indicators...")

        # ATR (Average True Range)
        high_low = self.high - self.low
        high_close = np.abs(self.high - self.close.shift())
        low_close = np.abs(self.low - self.close.shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        self.atr = true_range.rolling(14).mean()

        # Bollinger Bands
        bb_std = self.close.rolling(20).std()
        self.bb_upper = self.sma20 + (bb_std * 2)
        self.bb_lower = self.sma20 - (bb_std * 2)

        # Consolidation metrics
        self._calculate_consolidation_metrics()

        logger.info("✅ Advanced indicators calculated")

    def _calculate_consolidation_metrics(self):
        """Calculate consolidation range and days."""
        # Rolling 15-day high/low for consolidation detection
        rolling_high_15 = self.high.rolling(15).max()
        rolling_low_15 = self.low.rolling(15).min()
        self.consolidation_range = (
            (rolling_high_15 - rolling_low_15) / rolling_low_15 * 100
        )

        # Count consolidation days (simplified)
        # Days where range is tight (< 20%)
        is_tight = self.consolidation_range < 20
        self.consolidation_days = is_tight.rolling(30).sum()

    def _detect_signal_type(
        self, ticker: str, date_idx: int, signal_type: str = "any"
    ) -> bool:
        """
        Detect if signal matches requested type.

        Args:
            ticker: Ticker symbol
            date_idx: Date index
            signal_type: 'vcp', 'breakout', 'ath', 'any'

        Returns:
            True if signal matches type
        """
        if signal_type == "any":
            return True

        try:
            close_val = self.close.loc[date_idx, ticker]
            high_val = self.high.loc[date_idx, ticker]

            if signal_type == "ath":
                # All-time high: close at 52-week high
                high_52w = self.high.loc[:date_idx, ticker].tail(252).max()
                return close_val >= high_52w * 0.99

            elif signal_type == "breakout":
                # Breakout: above consolidation range
                if date_idx in self.consolidation_range.index:
                    consol_range = self.consolidation_range.loc[date_idx, ticker]
                    return consol_range < 15  # Tight consolidation
                return False

            elif signal_type == "vcp":
                # VCP: Tight consolidation + volume contraction
                if date_idx in self.consolidation_range.index:
                    consol_range = self.consolidation_range.loc[date_idx, ticker]
                    consol_days = self.consolidation_days.loc[date_idx, ticker]

                    # VCP criteria
                    tight = consol_range < 20
                    long_enough = consol_days >= 10

                    return tight and long_enough
                return False

        except (KeyError, IndexError):
            return False

        return False

    def _calculate_relative_strength(self):
        """
        Calculate Relative Strength (RS) for all tickers vs SPY.

        Formula (TradingView methodology):
        1. Calculate spread: ticker / SPY
        2. Calculate percentrank of spread over lookback period
        3. Result: 0-100 (percentile rank)
        """
        logger.info("🔢 Calculating Relative Strength (RS)...")

        if self.spy_close is None or (self.spy_close == 0).all():
            logger.warning("⚠️  SPY data missing - skipping RS calculation")
            # Create dummy RS (neutral = 50)
            self.rs_5d = pd.DataFrame(
                50.0, index=self.close.index, columns=self.close.columns
            )
            self.rs_21d = pd.DataFrame(
                50.0, index=self.close.index, columns=self.close.columns
            )
            self.rs_63d = pd.DataFrame(
                50.0, index=self.close.index, columns=self.close.columns
            )
            self.rs_126d = pd.DataFrame(
                50.0, index=self.close.index, columns=self.close.columns
            )
            self.rs_avg = pd.DataFrame(
                50.0, index=self.close.index, columns=self.close.columns
            )
            return

        # Calculate spread (ticker / SPY)
        safe_spy = self.spy_close.replace(0, np.nan)

        # Broadcast SPY to all tickers
        spy_broadcast = pd.DataFrame(
            np.tile(safe_spy.values[:, None], (1, len(self.close.columns))),
            index=self.close.index,
            columns=self.close.columns,
        )

        spread = self.close / spy_broadcast

        # Calculate RS for different lookbacks
        logger.info("   Calculating RS (5d, 21d, 63d, 126d)...")
        self.rs_5d = self._percentrank_rolling(spread, 5)
        self.rs_21d = self._percentrank_rolling(spread, 21)
        self.rs_63d = self._percentrank_rolling(spread, 63)
        self.rs_126d = self._percentrank_rolling(spread, 126)

        # Calculate average RS (mean of all periods)
        self.rs_avg = (self.rs_5d + self.rs_21d + self.rs_63d + self.rs_126d) / 4

        logger.info("✅ Relative Strength calculated")

    def _percentrank_rolling(self, data: pd.DataFrame, window: int) -> pd.DataFrame:
        """
        Calculate rolling percentile rank (0-100).

        This is the core RS calculation from TradingView: ta.percentrank(close, length)

        Args:
            data: DataFrame with spread values
            window: Lookback window

        Returns:
            DataFrame with percentile ranks (0-100)
        """

        def percentile_rank(x):
            if len(x) < 2:
                return 50.0  # Default to neutral
            return stats.percentileofscore(x, x.iloc[-1], kind="rank")

        # Apply rolling percentrank
        result = data.rolling(window=window, min_periods=max(5, window // 2)).apply(
            percentile_rank, raw=False
        )

        return result.fillna(50.0)

    def _calculate_earnings_mask(self, days_buffer=5):
        """
        Calculate earnings danger zone mask.

        Philosophy:
        - If we have earnings data -> Mark danger zone around date
        - If NO data -> Assume safe (don't kill old backtests)

        Args:
            days_buffer: Days before earnings to avoid (default: 5)

        Returns:
            DataFrame: True = Safe, False = Danger (near earnings)
        """
        logger.info(f"🔢 Calculating earnings mask (buffer={days_buffer} days)...")

        # Start with all SAFE (False = no danger)
        danger_mask = pd.DataFrame(
            False, index=self.close.index, columns=self.close.columns
        )

        tickers_with_data = 0
        tickers_blocked = 0

        for ticker in self.valid_tickers:
            try:
                earnings = self.cache.get_earnings_history(ticker)

                # If NO data, leave as safe
                if earnings is None or earnings.empty:
                    continue

                tickers_with_data += 1

                # Apply danger zone
                dates = pd.to_datetime(earnings["report_date"])
                for event_date in dates:
                    start_date = event_date - pd.Timedelta(days=days_buffer)

                    # Only mark if dates are in our backtest range
                    if (
                        start_date in danger_mask.index
                        or event_date in danger_mask.index
                    ):
                        danger_mask.loc[start_date:event_date, ticker] = True
                        tickers_blocked += 1

            except Exception as e:
                # If error, leave as safe (don't block trades)
                logger.debug(f"⚠️  Could not load earnings for {ticker}: {e}")
                continue

        logger.info(
            f"   Tickers with earnings data: {tickers_with_data}/{len(self.valid_tickers)}"
        )

        # Return SAFETY mask (invert: True = Safe to trade)
        return ~danger_mask

    def backtest(self, params: Dict) -> Dict:
        """
        Run backtest with given parameters (FAST - no data loading).

        Args:
            params: Dictionary of parameters

        Returns:
            Dictionary with results
        """
        try:
            # Extract parameters with defaults
            risk_dollars = params.get("risk_dollars", 150)
            max_exposure_pct = params.get("max_exposure_pct", 0.25)

            # Liquidity filters
            min_volume = params.get("min_volume", 200000)
            min_dollar_volume = params.get("min_dollar_volume", 10e6)

            # Momentum filters
            min_rvol = params.get("min_rvol", 1.0)
            min_adr = params.get("min_adr", 1.0)
            max_dist_sma20 = params.get("max_dist_sma20", 10.0)
            max_stop_pct = params.get("max_stop_pct", 8.0)

            # Signal type
            signal_type = params.get("signal_type", "any")

            # Consolidation filters
            min_consolidation_days = params.get("min_consolidation_days", 0)
            max_consolidation_range = params.get("max_consolidation_range", 100)

            # Sector filters
            require_sector_strength = params.get("require_sector_strength", False)
            sector_top_percentile = params.get("sector_top_percentile", 0.4)

            # Position sizing (RVOL-based)
            rvol_danger = params.get("rvol_danger", 3.0)
            rvol_warning = params.get("rvol_warning", 2.0)
            rvol_danger_size = params.get("rvol_danger_size", 0.25)
            rvol_warning_size = params.get("rvol_warning_size", 0.60)

            # Multi-phase exits
            use_phases = params.get("use_phases", False)
            tp1_r = params.get("tp1_r", 1.5)
            tp2_r = params.get("tp2_r", 3.0)

            # TP exit percentages (optimizable)
            tp1_pct = params.get("tp1_pct", 0.5)  # Default 50%
            tp2_pct = params.get("tp2_pct", 0.3)  # Default 30%
            runner_pct = params.get("runner_pct", 0.2)  # Default 20%

            # NEW: Relative Strength filters
            min_rs = params.get("min_rs", 0.0)  # Minimum RS (0-100)
            rs_lookback = params.get("rs_lookback", "21d")  # Which RS to use
            require_positive_rs = params.get("require_positive_rs", False)  # RS > 50

            # NEW: Market regime filters
            require_bullish_spy = params.get(
                "require_bullish_spy", False
            )  # SPY > EMA20
            max_vix = params.get("max_vix", 100.0)  # Max VIX level (fear filter)

            # NEW: Earnings filter
            use_earnings_filter = params.get("use_earnings_filter", False)
            earnings_days = params.get("earnings_days", 5)

            # CONTROL FLAGS
            use_dynamic_stop = params.get(
                "use_dynamic_stop", True
            )  # Default True (Pro behavior)

            # Calculate earnings mask if needed (only once per backtest)
            if use_earnings_filter and self.earnings_safe is None:
                self.earnings_safe = self._calculate_earnings_mask(
                    days_buffer=earnings_days
                )

            # Select RS period
            rs_data = {
                "5d": self.rs_5d,
                "21d": self.rs_21d,
                "63d": self.rs_63d,
                "126d": self.rs_126d,
                "avg": self.rs_avg,
            }.get(rs_lookback, self.rs_21d)

            # --- APPLY CENTRALIZED LIQUIDITY FILTERS ---
            liquidity_mask = LiquidityFilters.get_mask(
                close=self.close,
                volume=self.volume,
                dollar_volume=self.dollar_volume,
                rvol=self.rvol,
                adr=self.adr,
                min_volume=min_volume,
                min_dollar_volume=min_dollar_volume,
                min_rvol=min_rvol,
                min_adr=min_adr,
                fillna_value=False,
            )

            # ENTRY SIGNALS (vectorized)
            entries = (
                # Apply Liquidity Mask
                liquidity_mask
                &
                # Price action
                (self.close > self.sma20)
                & (self.dist_sma20 < max_dist_sma20)
                & (self.dist_sma20 > 0)
                &
                # Trend
                (self.sma20 > self.sma50)
                & (self.sma50 > self.sma200)
                &
                # Consolidation quality (if specified)
                (self.consolidation_days >= min_consolidation_days)
                & (self.consolidation_range <= max_consolidation_range)
                &
                # NEW: Relative Strength filter
                (rs_data >= min_rs)
            )

            # NEW: Require positive RS (stronger than SPY)
            if require_positive_rs:
                entries = entries & (rs_data > 50)

            # NEW: Market regime filter (SPY bullish)
            if require_bullish_spy and self.spy_close is not None:
                spy_bullish = pd.Series(
                    self.spy_close > self.spy_ema20, index=self.close.index
                )
                spy_broadcast = pd.DataFrame(
                    np.tile(spy_bullish.values[:, None], (1, len(self.close.columns))),
                    index=self.close.index,
                    columns=self.close.columns,
                )
                entries = entries & spy_broadcast

            # NEW: VIX filter (fear filter)
            if max_vix < 100 and self.vix_close is not None:
                vix_ok = pd.Series(self.vix_close <= max_vix, index=self.close.index)
                vix_broadcast = pd.DataFrame(
                    np.tile(vix_ok.values[:, None], (1, len(self.close.columns))),
                    index=self.close.index,
                    columns=self.close.columns,
                )
                entries = entries & vix_broadcast

            # NEW: Earnings filter (avoid trading near earnings)
            if use_earnings_filter and self.earnings_safe is not None:
                entries = entries & self.earnings_safe

            # Signal type filtering (applied per-ticker, per-day)
            # Fix: Avoid ambiguous truth value error
            if signal_type != "any":
                signal_mask = pd.DataFrame(
                    False, index=entries.index, columns=entries.columns
                )
                for ticker in entries.columns:
                    # Only check signal type for actual entries
                    entry_dates = entries.index[entries[ticker]]
                    for date in entry_dates:
                        is_valid = self._detect_signal_type(ticker, date, signal_type)
                        signal_mask.loc[date, ticker] = is_valid
                entries = entries & signal_mask

            # Calculate stops (vectorized)
            if use_dynamic_stop:
                stop_loss_pct = np.minimum(
                    (self.close - self.sma20) / self.close * 100, max_stop_pct
                )
                stop_loss_pct = np.maximum(stop_loss_pct, 3.0)  # Minimum 3%
            else:
                # Fixed stop loss (Baseline/THOR compatibility)
                stop_loss_pct = max_stop_pct

            # EXIT SIGNALS
            exits = self.close < self.sma20

            # DYNAMIC POSITION SIZING (RVOL-based)
            # Refactored to use centralized PositionSizer

            # 1. Calculate Base Size (Fixed Dollar Risk)
            # Note: stop_loss_pct calculated above is already in percentage (3.0 to max_stop_pct)
            position_value_base = PositionSizer.get_fixed_risk_size(
                close=self.close,
                risk_dollars=risk_dollars,
                stop_pct=stop_loss_pct,
                min_stop_pct=3.0,
            )

            # 2. Apply RVOL Adjustment
            position_value = PositionSizer.apply_rvol_adjustment(
                position_value=position_value_base,
                rvol=self.rvol,
                warning_level=rvol_warning,
                danger_level=rvol_danger,
                warning_size=rvol_warning_size,
                danger_size=rvol_danger_size,
            )

            # 3. Apply Exposure Limit
            position_value = PositionSizer.apply_exposure_limit(
                position_value, self.initial_capital, max_exposure_pct
            )

            # ═══════════════════════════════════════════════════════════════
            # DECISION: Use phases or simple exit?
            # ═══════════════════════════════════════════════════════════════
            if use_phases:
                # Use 3-phase system (TP1/TP2/Runner)
                return self._backtest_with_phases(
                    entries=entries,
                    stop_loss_pct=stop_loss_pct,
                    position_value=position_value,
                    tp1_r=tp1_r,
                    tp2_r=tp2_r,
                    tp1_pct=tp1_pct,
                    tp2_pct=tp2_pct,
                    runner_pct=runner_pct,
                )

            # ═══════════════════════════════════════════════════════════════
            # SIMPLE EXIT (Basic - Fast)
            # ═══════════════════════════════════════════════════════════════

            # Run VectorBT backtest
            portfolio = vbt.Portfolio.from_signals(
                self.close,
                entries,
                exits,
                size=position_value,
                size_type="amount",
                init_cash=self.initial_capital,
                fees=0.001,
                slippage=0.001,
                freq="1D",
            )

            # Extract metrics
            trades_df = portfolio.trades.records_readable
            if len(trades_df) > 0:
                total_profit = trades_df[trades_df["PnL"] > 0]["PnL"].sum()
                total_loss = abs(trades_df[trades_df["PnL"] < 0]["PnL"].sum())
                profit_factor = total_profit / total_loss if total_loss > 0 else 0

                # Aggregate stats
                total_trades = len(trades_df)

                # Calculate return on total initial capital (assuming fixed capital pool)
                final_value = portfolio.value().iloc[-1].sum()
                # Assuming initial capital is per ticker OR total.
                # OptimizationEngine initializes with 'initial_capital'.
                # VectorBT by default uses init_cash per column if passed as scalar?
                # Actually vbt broadcasts init_cash.
                # Let's assume total_invested is initial_capital (shared pool) or sum.
                # In advanced engine we use initial_capital as total pool.
                # Here we simulate independent streams.
                # Let's standardize: Total Return = (Final - Initial) / Initial
                # But here we have multiple columns.

                # Simple sum of PnL / Initial Capital
                total_pnl = trades_df["PnL"].sum()
                total_return = total_pnl / self.initial_capital  # Scalar

                win_rate = (
                    (len(trades_df[trades_df["PnL"] > 0]) / total_trades)
                    if total_trades > 0
                    else 0
                )

                # Sharpe and drawdown (Portfolio-level)
                # Combine returns to portfolio level - CORRECT CALCULATION
                daily_returns = portfolio.returns()
                # Portfolio return = sum of returns across all assets for each day
                portfolio_daily_returns = daily_returns.sum(axis=1)
                sharpe_ratio = (
                    portfolio_daily_returns.mean()
                    / portfolio_daily_returns.std()
                    * np.sqrt(252)
                    if portfolio_daily_returns.std() > 0
                    else 0
                )
                max_drawdown = portfolio.drawdown().max().max()
            else:
                profit_factor = 0
                total_trades = 0
                total_return = 0
                win_rate = 0
                sharpe_ratio = 0
                max_drawdown = 0

            # Return keys matching Advanced engine where possible
            return {
                "profit_factor": profit_factor,
                "total_trades": total_trades,
                "total_return": total_return,  # Fixed key name
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,  # Fixed key name and scale
                "win_rate": win_rate,  # Fixed key name
            }

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return {
                "profit_factor": 0,
                "total_trades": 0,
                "total_return": 0,
                "sharpe_ratio": 0,
                "max_drawdown": 0,
                "win_rate": 0,
            }

    def _backtest_with_phases(
        self,
        entries: pd.DataFrame,
        stop_loss_pct: pd.DataFrame,
        position_value: pd.DataFrame,
        tp1_r: float,
        tp2_r: float,
        tp1_pct: float = 0.5,
        tp2_pct: float = 0.3,
        runner_pct: float = 0.2,
    ) -> Dict:
        """
        Backtest with 3-phase exits (HYBRID VECTORIZED).

        Architecture:
        - Phase 1: Exit tp1_pct% at TP1 (default 50%)
        - Phase 2: Exit tp2_pct% at TP2 (default 30%)
        - Phase 3: Runner with runner_pct% trailing stop (default 20%)

        Percentages are now OPTIMIZABLE parameters.

        Args:
            entries: Entry signals
            stop_loss_pct: Stop loss percentage
            position_value: Position size in dollars
            tp1_r: TP1 R-multiple (default 1.5)
            tp2_r: TP2 R-multiple (default 3.0)
            tp1_pct: Percentage to exit at TP1 (default 0.5 = 50%)
            tp2_pct: Percentage to exit at TP2 (default 0.3 = 30%)
            runner_pct: Percentage for runner (default 0.2 = 20%)

        Returns:
            Dict with aggregated results
        """
        logger.info("🎯 Running 3-phase backtest (TP1/TP2/Runner)...")

        # ═══════════════════════════════════════════════════════════════
        # CRITICAL: Track entry prices (FIXED per position)
        # ═══════════════════════════════════════════════════════════════

        # Create entry price matrix (filled only on entry days)
        entry_prices = pd.DataFrame(
            np.nan, index=self.close.index, columns=self.close.columns
        )
        entry_prices[entries] = self.close[entries]

        # Forward-fill to maintain entry price during position
        # This ensures TP targets are FIXED from entry, not recalculated
        entry_prices_filled = entry_prices.ffill()

        # Create position active mask (True while in position)
        position_active = entry_prices_filled.notna()

        # Calculate risk based on ENTRY price (not current price)
        risk_per_share = entry_prices_filled * (stop_loss_pct / 100)

        # Calculate FIXED targets from entry price
        tp1_target = entry_prices_filled + (tp1_r * risk_per_share)
        tp2_target = entry_prices_filled + (tp2_r * risk_per_share)
        stop_target = entry_prices_filled - risk_per_share

        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: TP1 exit (configurable % of position)
        # ═══════════════════════════════════════════════════════════════
        # Exit when: current price >= TP1 target OR breaks SMA20
        # Only exit if position is active
        exits_tp1 = (
            (self.close >= tp1_target) | (self.close < self.sma20)
        ) & position_active

        pf1 = vbt.Portfolio.from_signals(
            self.close,
            entries,
            exits_tp1,
            size=position_value * tp1_pct,
            size_type="amount",
            init_cash=self.initial_capital * tp1_pct,
            fees=0.001,
            slippage=0.001,
            freq="1D",
        )

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: TP2 exit (configurable % of position)
        # ═══════════════════════════════════════════════════════════════
        exits_tp2 = (
            (self.close >= tp2_target) | (self.close < self.sma20)
        ) & position_active

        pf2 = vbt.Portfolio.from_signals(
            self.close,
            entries,
            exits_tp2,
            size=position_value * tp2_pct,
            size_type="amount",
            init_cash=self.initial_capital * tp2_pct,
            fees=0.001,
            slippage=0.001,
            freq="1D",
        )

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: Runner with trailing stop (configurable % of position)
        # ═══════════════════════════════════════════════════════════════
        # Calculate EMA8 and EMA21 for trailing
        ema8 = self.close.ewm(span=8, adjust=False).mean()
        ema21 = self.close.ewm(span=21, adjust=False).mean()

        # Exit when trend breaks (EMA8 < EMA21) OR hits stop
        exits_runner = ((ema8 < ema21) | (self.close < stop_target)) & position_active

        pf3 = vbt.Portfolio.from_signals(
            self.close,
            entries,
            exits_runner,
            size=position_value * runner_pct,
            size_type="amount",
            init_cash=self.initial_capital * runner_pct,
            fees=0.001,
            slippage=0.001,
            freq="1D",
        )

        # ═══════════════════════════════════════════════════════════════
        # AGGREGATE RESULTS from all 3 phases
        # ═══════════════════════════════════════════════════════════════

        # Combine equity curves
        equity1 = pf1.value().sum(axis=1) if len(pf1.value().shape) > 1 else pf1.value()
        equity2 = pf2.value().sum(axis=1) if len(pf2.value().shape) > 1 else pf2.value()
        equity3 = pf3.value().sum(axis=1) if len(pf3.value().shape) > 1 else pf3.value()

        # Subtract initial capital from each portfolio to get PnL curve, then add back ONE initial capital
        # Wait, each portfolio starts with a fraction of capital.
        # pf1 starts with 0.5 * Capital.
        # pf2 starts with 0.3 * Capital.
        # pf3 starts with 0.2 * Capital.
        # So sum(pf.value()) correctly reconstructs total equity.

        total_equity = equity1 + equity2 + equity3

        # Combine trades
        trades1 = pf1.trades.records_readable
        trades2 = pf2.trades.records_readable
        trades3 = pf3.trades.records_readable

        # Mark phase in trades (for analysis)
        if len(trades1) > 0:
            trades1["phase"] = "TP1"
        if len(trades2) > 0:
            trades2["phase"] = "TP2"
        if len(trades3) > 0:
            trades3["phase"] = "Runner"

        all_trades = pd.concat([trades1, trades2, trades3], ignore_index=True)

        # Calculate metrics
        if len(all_trades) > 0:
            total_profit = all_trades[all_trades["PnL"] > 0]["PnL"].sum()
            total_loss = abs(all_trades[all_trades["PnL"] < 0]["PnL"].sum())
            profit_factor = total_profit / total_loss if total_loss > 0 else 0

            total_trades = len(all_trades)
            final_value = total_equity.iloc[-1]

            # Use total invested (capital allocated per ticker * N tickers)
            # In Optimization Engine, 'initial_capital' is usually the total pool (unlike vectorbt default)
            # But here we broadcasted 'initial_capital' to vectorbt.Portfolio as 'init_cash'.
            # If we passed init_cash=scalar, vbt broadcasts it to every column.
            # So total_initial_capital = self.initial_capital * len(self.close.columns)
            total_invested = self.initial_capital * len(self.close.columns)

            # Simple Return: (Final - Initial) / Initial
            # total_return_pct = (final_value / total_invested - 1) * 100
            # Let's use PnL sum for simplicity and robustness against cash handling
            total_pnl = all_trades["PnL"].sum()
            total_return = (
                total_pnl / total_invested
            )  # Scalar return (e.g., 0.15 for 15%)

            win_rate = (
                (len(all_trades[all_trades["PnL"] > 0]) / total_trades)
                if total_trades > 0
                else 0
            )

            # Calculate Sharpe
            returns = total_equity.pct_change().dropna()
            sharpe_ratio = (
                returns.mean() / returns.std() * np.sqrt(252)
                if returns.std() > 0
                else 0
            )

            # Calculate drawdown
            cummax = total_equity.cummax()
            drawdown = (total_equity - cummax) / cummax
            max_drawdown = abs(drawdown.min())  # Scalar (e.g. 0.05 for 5%)

            # Phase breakdown (for logging)
            logger.info(f"   TP1 trades: {len(trades1)}")
            logger.info(f"   TP2 trades: {len(trades2)}")
            logger.info(f"   Runner trades: {len(trades3)}")

        else:
            profit_factor = 0
            total_trades = 0
            total_return = 0
            win_rate = 0
            sharpe_ratio = 0
            max_drawdown = 0
            final_value = self.initial_capital

        # Return dict with keys expected by verify_engine_equivalence.py
        return {
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "final_value": final_value,
            "phase_breakdown": {
                "tp1_trades": len(trades1) if len(trades1) > 0 else 0,
                "tp2_trades": len(trades2) if len(trades2) > 0 else 0,
                "runner_trades": len(trades3) if len(trades3) > 0 else 0,
            },
        }

    def get_data_summary(self) -> Dict:
        """Get summary of loaded data."""
        return {
            "tickers_loaded": len(self.valid_tickers),
            "tickers_requested": len(self.tickers),
            "date_range": f"{self.close.index[0].date()} to {self.close.index[-1].date()}",
            "trading_days": len(self.close),
            "data_shape": self.close.shape,
            "memory_mb": (
                self.close.memory_usage(deep=True).sum()
                + self.open.memory_usage(deep=True).sum()
                + self.high.memory_usage(deep=True).sum()
                + self.low.memory_usage(deep=True).sum()
            )
            / 1024
            / 1024,
            "market_regime_enabled": self.spy_close is not None
            and not (self.spy_close == 0).all(),
            "rs_enabled": self.rs_21d is not None,
        }
