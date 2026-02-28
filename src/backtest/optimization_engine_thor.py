#!/usr/bin/env python3
"""
⚠️  DEPRECATED - DO NOT USE FOR PRODUCTION ⚠️
===============================================

This engine (THOR/Divo) is DEPRECATED as of 2025-02-11.

REASON FOR DEPRECATION:
The two-engine workflow (THOR for research, Advanced for production) has been
proven to produce parameter sets that COLLAPSE when moved to production.
This is due to fundamental mismatches:
- THOR: Simple entry, no costs, no regime/sector filters, simple sizing (~503 trades)
- Advanced: Liquidity/sector/regime filters, earnings buffer, realistic costs,
           adaptive sizing, survivorship handling (~138 trades)

MIGRATION PATH:
Use src.backtest.vectorbt_engine_advanced.AdvancedVectorBTEngine instead.
It is now the SINGLE "engine of record" that fully reflects production reality.

The Advanced engine includes:
- Full production rule fidelity (costs, slippage, liquidity limits)
- Survivorship handling and regime/sector filters
- Adaptive position sizing
- 3-phase research gate (Discovery → Validation → Productionization)
- Robustness metrics (PBO, CSCV, Walk-Forward, bootstrap percentiles)
- Stress testing suite

For validation harness and quality gates, see:
- src.validation.research_gate
- src.validation.stress_testing
- src.validation.robustness_metrics

Author: DEPRECATED - Migrate to Advanced Engine
"""

import pandas as pd
import numpy as np
import vectorbt as vbt
import gc
import warnings
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import sys
from pathlib import Path

# Setup path to allow importing from src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.data.ticker_cache import TickerCache
from src.indicators.technical import TechnicalIndicators
from src.filters.liquidity import LiquidityFilters
from src.risk.position_sizing import PositionSizer

logger = logging.getLogger(__name__)

# Emit deprecation warning at module load time
warnings.warn(
    "OptimizationEngineTHOR is DEPRECATED. "
    "Use AdvancedVectorBTEngine from vectorbt_engine_advanced instead. "
    "The two-engine workflow causes parameter collapse in production. "
    "See module docstring for migration details.",
    DeprecationWarning,
    stacklevel=2,
)


class OptimizationEngineTHOR:
    """
    BUGATTI THOR: The ultimate W16 engine.
    Memory-optimized, structural liquidity filters, and high-precision entry logic.
    """

    def __init__(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        lookback_days: int = 365,
        offline_mode: bool = True,
        use_float32: bool = True,
        chunk_size: int = 100,
    ):
        logger.info("⚡🔨 BUGATTI THOR (W16) igniting...")
        logger.info(f"📅 Period: {start_date} to {end_date}")
        logger.info(f"🎯 Tickers: {len(tickers)}")

        self.tickers = tickers
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.lookback_days = lookback_days
        self.offline_mode = offline_mode
        self.use_float32 = use_float32
        self.chunk_size = chunk_size

        self.cache = TickerCache()
        self.dtype = np.float32 if use_float32 else np.float64

        # Core data (SIEMPRE cargado)
        self.close = None
        self.open = None
        self.high = None
        self.low = None
        self.volume = None

        # Lazy indicators (None hasta que se necesiten)
        self._sma20 = None
        self._sma50 = None
        self._sma200 = None
        self._ema8 = None
        self._ema21 = None
        self._dist_sma20 = None
        self._rvol = None
        self._adr = None
        self._atr = None

        self._consolidation_range = None
        self._consolidation_days = None

        # Volume structural (lazy)
        self._vol_sma20 = None

        # Market regime (lazy)
        self._spy_close = None
        self._spy_ema20 = None
        self._spy_sma50 = None
        self._vix_close = None

        # Relative Strength (lazy)
        self._rs_21d = None

        self.valid_tickers = []

        # Load data
        self._load_data_chunked()

        logger.info(f"✅ THOR ready: {len(self.valid_tickers)} tickers")
        logger.info(
            f"💾 RAM mode: {'Float32 (50% saving)' if use_float32 else 'Float64'}"
        )

    def _load_data_chunked(self):
        """Cargar datos en chunks para evitar RAM spike."""
        extended_start = self.start_date - timedelta(days=self.lookback_days)

        logger.info(f"📥 Loading data in chunks of {self.chunk_size}...")

        all_close = []
        all_open = []
        all_high = []
        all_low = []
        all_volume = []
        valid_tickers = []

        for i in range(0, len(self.tickers), self.chunk_size):
            chunk_tickers = self.tickers[i : i + self.chunk_size]
            logger.info(
                f"   Chunk {i // self.chunk_size + 1}/{(len(self.tickers) - 1) // self.chunk_size + 1}"
            )

            chunk_data = {}

            for ticker in chunk_tickers:
                try:
                    df = self.cache.get_ohlcv(
                        ticker,
                        start_date=extended_start.strftime("%Y-%m-%d"),
                        end_date=self.end_date.strftime("%Y-%m-%d"),
                        offline=self.offline_mode,
                    )

                    if df is not None and len(df) >= 100:
                        df = df.reset_index()
                        # Fix: index name might be 'Date' or 'date' after reset_index
                        index_col = df.columns[0]  # First column is always the index
                        df.rename(columns={index_col: "date"}, inplace=True)
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date")
                        df.columns = [col.lower() for col in df.columns]

                        # Convert to float32 inmediatamente
                        if self.use_float32:
                            for col in ["open", "high", "low", "close", "volume"]:
                                if col in df.columns:
                                    df[col] = df[col].astype(self.dtype)

                        chunk_data[ticker] = df
                        valid_tickers.append(ticker)

                except Exception:
                    continue

            if chunk_data:
                chunk_close = pd.DataFrame(
                    {t: d["close"] for t, d in chunk_data.items()}
                )
                chunk_open = pd.DataFrame({t: d["open"] for t, d in chunk_data.items()})
                chunk_high = pd.DataFrame({t: d["high"] for t, d in chunk_data.items()})
                chunk_low = pd.DataFrame({t: d["low"] for t, d in chunk_data.items()})
                chunk_volume = pd.DataFrame(
                    {t: d["volume"] for t, d in chunk_data.items()}
                )

                all_close.append(chunk_close)
                all_open.append(chunk_open)
                all_high.append(chunk_high)
                all_low.append(chunk_low)
                all_volume.append(chunk_volume)

            del chunk_data
            gc.collect()

        if all_close:
            self.close = pd.concat(all_close, axis=1).astype(self.dtype)
            self.open = pd.concat(all_open, axis=1).astype(self.dtype)
            self.high = pd.concat(all_high, axis=1).astype(self.dtype)
            self.low = pd.concat(all_low, axis=1).astype(self.dtype)
            self.volume = pd.concat(all_volume, axis=1).astype(self.dtype)

            # Fill NaN
            for df in [self.close, self.open, self.high, self.low, self.volume]:
                df.ffill(inplace=True)
                df.fillna(0, inplace=True)

            self.valid_tickers = valid_tickers

            logger.info(f"✅ Loaded {len(self.valid_tickers)} tickers")
            logger.info(f"📊 Shape: {self.close.shape}")

            mem_mb = (
                (
                    self.close.memory_usage(deep=True).sum()
                    + self.open.memory_usage(deep=True).sum()
                    + self.high.memory_usage(deep=True).sum()
                    + self.low.memory_usage(deep=True).sum()
                    + self.volume.memory_usage(deep=True).sum()
                )
                / 1024
                / 1024
            )
            logger.info(f"💾 Core data memory: {mem_mb:.1f} MB")
        else:
            raise ValueError("No data loaded!")

        del all_close, all_open, all_high, all_low, all_volume
        gc.collect()

    # ========================================================================
    # LAZY PROPERTIES - Solo calcular cuando se accede
    # ========================================================================

    @property
    def sma20(self):
        if self._sma20 is None:
            logger.debug("   💤 Calculating SMA20...")
            self._sma20 = self.close.rolling(20).mean().astype(self.dtype)
        return self._sma20

    @property
    def sma50(self):
        if self._sma50 is None:
            logger.debug("   💤 Calculating SMA50...")
            self._sma50 = self.close.rolling(50).mean().astype(self.dtype)
        return self._sma50

    @property
    def sma200(self):
        if self._sma200 is None:
            logger.debug("   💤 Calculating SMA200...")
            self._sma200 = self.close.rolling(200).mean().astype(self.dtype)
        return self._sma200

    @property
    def ema8(self):
        if self._ema8 is None:
            logger.debug("   💤 Calculating EMA8...")
            self._ema8 = self.close.ewm(span=8, adjust=False).mean().astype(self.dtype)
        return self._ema8

    @property
    def ema21(self):
        if self._ema21 is None:
            logger.debug("   💤 Calculating EMA21...")
            self._ema21 = (
                self.close.ewm(span=21, adjust=False).mean().astype(self.dtype)
            )
        return self._ema21

    @property
    def dist_sma20(self):
        if self._dist_sma20 is None:
            logger.debug("   💤 Calculating distance to SMA20...")
            self._dist_sma20 = ((self.close - self.sma20) / self.sma20 * 100).astype(
                self.dtype
            )
        return self._dist_sma20

    @property
    def vol_sma20(self):
        if self._vol_sma20 is None:
            logger.debug("   💤 Calculating Volume SMA20...")
            self._vol_sma20 = self.volume.rolling(20).mean().astype(self.dtype)
        return self._vol_sma20

    @property
    def rvol(self):
        if self._rvol is None:
            logger.debug("   💤 Calculating RVOL...")
            raw_rvol = TechnicalIndicators.rvol(self.volume, period=20)
            # CONVERGENCE FIX: Apply same sanitization as Advanced engine
            # Force RVOL = 1.0 where avg_volume <= 500 (to match Advanced behavior)
            avg_volume_20 = self.volume.rolling(window=20, min_periods=1).mean()
            valid_vol_mask = avg_volume_20 > 500
            self._rvol = (
                raw_rvol.where(valid_vol_mask, 1.0).fillna(1.0).astype(self.dtype)
            )
        return self._rvol

    @property
    def adr(self):
        if self._adr is None:
            logger.debug("   💤 Calculating ADR (20-day Rolling Mean)...")
            # CHANGED: Now using the rolling mean (ADR) instead of single-day range
            # to match the Advanced engine logic as requested.
            self._adr = TechnicalIndicators.adr(
                self.high, self.low, self.close, period=20
            ).astype(self.dtype)
        return self._adr

    @property
    def atr(self):
        if self._atr is None:
            logger.debug("   💤 Calculating ATR...")
            # FIXED: Correcto cálculo de ATR
            hl = self.high - self.low
            hc = (self.high - self.close.shift()).abs()
            lc = (self.low - self.close.shift()).abs()

            # True range es el máximo de los 3
            tr = (
                pd.DataFrame(
                    {
                        "hl": hl.values.flatten(),
                        "hc": hc.values.flatten(),
                        "lc": lc.values.flatten(),
                    }
                )
                .max(axis=1)
                .values.reshape(hl.shape)
            )

            tr = pd.DataFrame(tr, index=self.close.index, columns=self.close.columns)
            self._atr = tr.rolling(14).mean().astype(self.dtype)
        return self._atr

    @property
    def consolidation_range(self):
        if self._consolidation_range is None:
            logger.debug("   💤 Calculating consolidation range...")
            high_20 = self.high.rolling(20).max()
            low_20 = self.low.rolling(20).min()
            self._consolidation_range = ((high_20 - low_20) / low_20 * 100).astype(
                self.dtype
            )
        return self._consolidation_range

    @property
    def consolidation_days(self):
        if self._consolidation_days is None:
            logger.debug("   💤 Calculating consolidation days...")
            # Contar días dentro de BB
            bb_period = 20
            bb_std = 2
            sma = self.close.rolling(bb_period).mean()
            std = self.close.rolling(bb_period).std()
            bb_upper = sma + (std * bb_std)
            bb_lower = sma - (std * bb_std)

            inside_bb = (self.close >= bb_lower) & (self.close <= bb_upper)
            # Contar días consecutivos
            self._consolidation_days = inside_bb.rolling(20).sum().astype(self.dtype)

            del bb_upper, bb_lower, sma, std, inside_bb
            gc.collect()
        return self._consolidation_days

    # Market regime (lazy)
    @property
    def spy_close(self):
        if self._spy_close is None:
            self._load_market_regime()
        return self._spy_close

    @property
    def spy_ema20(self):
        if self._spy_ema20 is None:
            if self.spy_close is not None:
                self._spy_ema20 = (
                    self.spy_close.ewm(span=20, adjust=False).mean().astype(self.dtype)
                )
        return self._spy_ema20

    @property
    def spy_sma50(self):
        if self._spy_sma50 is None:
            if self.spy_close is not None:
                self._spy_sma50 = self.spy_close.rolling(50).mean().astype(self.dtype)
        return self._spy_sma50

    @property
    def vix_close(self):
        if self._vix_close is None:
            self._load_market_regime()
        return self._vix_close

    def _load_market_regime(self):
        """Lazy load SPY and VIX using centralized loader"""
        from src.utils.market_regime import load_spy_vix_data

        logger.debug("   💤 Loading Market Regime Data (SPY/VIX)...")

        extended_start = self.start_date - timedelta(days=self.lookback_days)

        spy_df, vix_df = load_spy_vix_data(
            start_date=extended_start.strftime("%Y-%m-%d"),
            end_date=self.end_date.strftime("%Y-%m-%d"),
            cache=self.cache,
        )

        # Align to close index
        if spy_df is not None:
            # Reindex matches index, ffill propagates last value
            self._spy_close = (
                spy_df["close"].reindex(self.close.index).ffill().astype(self.dtype)
            )
        else:
            self._spy_close = pd.Series(0, index=self.close.index, dtype=self.dtype)

        if vix_df is not None:
            self._vix_close = (
                vix_df["close"].reindex(self.close.index).ffill().astype(self.dtype)
            )
        else:
            self._vix_close = pd.Series(0, index=self.close.index, dtype=self.dtype)

    @property
    def rs_21d(self):
        """Lazy calculation de Relative Strength vs SPY"""
        if self._rs_21d is None:
            logger.debug("   💤 Calculating RS 21d...")
            stock_ret = self.close.pct_change(21)
            spy_ret = self.spy_close.pct_change(21)
            # Fix: usar .sub() con axis=0 para broadcast correcto
            self._rs_21d = stock_ret.sub(spy_ret, axis=0).astype(self.dtype)
        return self._rs_21d

    def clear_indicator_cache(self):
        """
        Limpiar indicators para liberar RAM.
        Llamar después de varios trials si la RAM crece mucho.
        """
        self._sma20 = None
        self._sma50 = None
        self._sma200 = None
        self._ema8 = None
        self._ema21 = None
        self._dist_sma20 = None
        self._vol_sma20 = None
        self._rvol = None
        self._adr = None
        self._atr = None
        self._consolidation_range = None
        self._consolidation_days = None
        self._spy_close = None
        self._spy_ema20 = None
        self._vix_close = None
        self._rs_21d = None
        gc.collect()
        logger.debug("   🧹 Indicator cache cleared")

    # ========================================================================
    # BACKTEST ENGINE
    # ========================================================================

    def backtest(self, params: Dict) -> Dict:
        """
        Backtest optimizado con 3-phase exits como el Chiron.
        THOR V2: Estructura Refinada + Liquidez Estructural.
        """
        try:
            # ============================================================
            # EXTRACT PARAMS
            # ============================================================

            # Signal & Entry Logic
            signal_type = params.get("signal_type", "any")

            # Liquidity Filters
            min_rvol = params.get("min_rvol", 1.5)
            min_adr = params.get("min_adr", 1.5)
            min_volume = params.get("min_volume", 200000)
            min_dollar_volume = params.get("min_dollar_volume", 5e6)

            # Quality Filters
            max_dist_sma20 = params.get("max_dist_sma20", 15.0)
            max_consolidation_range = params.get("max_consolidation_range", 15.0)
            min_consolidation_days = params.get("min_consolidation_days", 10)

            # Position Sizing
            risk_dollars = params.get("risk_dollars", 150)
            max_stop_pct = params.get("max_stop_pct", 0.07)
            max_exposure_pct = params.get("max_exposure_pct", 0.25)

            # Exit Targets
            tp1_r = params.get("tp1_r", 1.5)
            tp2_r = params.get("tp2_r", 3.0)

            # TP exit percentages (optimizable)
            tp1_pct = params.get("tp1_pct", 0.5)  # Default 50%
            tp2_pct = params.get("tp2_pct", 0.3)  # Default 30%
            runner_pct = params.get("runner_pct", 0.2)  # Default 20%

            # Market Regime
            use_phases = params.get("use_phases", True)
            require_bullish_spy = params.get("require_bullish_spy", False)
            require_spy_above_sma50 = params.get("require_spy_above_sma50", False)
            max_vix = params.get("max_vix", 40.0)
            require_positive_rs = params.get("require_positive_rs", False)
            require_sma_trend = params.get("require_sma_trend", False)

            # RVOL-based position sizing
            rvol_danger = params.get("rvol_danger", 3.0)
            rvol_warning = params.get("rvol_warning", 2.0)
            rvol_danger_size = params.get("rvol_danger_size", 0.30)
            rvol_warning_size = params.get("rvol_warning_size", 0.65)

            # Convert percentage values (>1) to decimal
            if rvol_danger_size > 1.0:
                rvol_danger_size = rvol_danger_size / 100.0
            if rvol_warning_size > 1.0:
                rvol_warning_size = rvol_warning_size / 100.0

            # ============================================================
            # STEP 1: LIQUIDITY FILTERS (SIEMPRE aplicar)
            # ============================================================

            # 🔥 THOR: Usar vol_sma20 para liquidez estructural (anti-trap)
            avg_dollar_volume = (
                (self.close * self.vol_sma20).fillna(0).astype(self.dtype)
            )

            # Use centralized LiquidityFilters
            liquidity_filters = LiquidityFilters.get_mask(
                rvol=self.rvol,
                adr=self.adr,
                avg_volume=self.vol_sma20,
                dollar_volume=avg_dollar_volume,
                min_rvol=min_rvol,
                min_adr=min_adr,
                min_volume=min_volume,
                min_dollar_volume=min_dollar_volume,
                fillna_value=False,
            )

            # ============================================================
            # STEP 2: TREND & QUALITY FILTERS
            # ============================================================

            if require_sma_trend:
                # Modo STRICT: Requiere trend + distancia controlada
                trend_filters = (
                    (self.close > self.sma20)
                    & (self.close > self.sma50)
                    & (self.dist_sma20 <= max_dist_sma20)
                )
            else:
                # Modo PERMISSIVE: Solo controlar distancia (evita sobreextendidos)
                trend_filters = self.dist_sma20 <= max_dist_sma20

            # Combinar liquidity + trend
            base_filters = liquidity_filters & trend_filters

            # ============================================================
            # STEP 3: MARKET REGIME FILTERS
            # ============================================================

            if require_bullish_spy:
                base_filters &= (self.spy_close > self.spy_ema20).values[:, None]

            if require_spy_above_sma50:
                base_filters &= (self.spy_close > self.spy_sma50).values[:, None]

            # VIX filter (solo si require_sma_trend=True, sino es muy restrictivo)
            if require_sma_trend:
                base_filters &= self.vix_close <= max_vix

            # Relative Strength
            if require_positive_rs:
                base_filters &= self.rs_21d > 0

            # ============================================================
            # STEP 4: CONSOLIDATION QUALITY (Aplicar según signal type)
            # ============================================================

            # Calcular consolidation quality
            consolidation_quality = (
                self.consolidation_range <= max_consolidation_range
            ) & (self.consolidation_days >= min_consolidation_days)

            # ============================================================
            # STEP 5: SIGNAL-SPECIFIC ENTRY LOGIC
            # ============================================================

            if signal_type == "vcp":
                # VCP: Requiere consolidation + breakout
                entries = (
                    base_filters
                    & consolidation_quality
                    & (self.close > self.high.shift().rolling(20).max())
                )

            elif signal_type == "breakout":
                # Breakout: Requiere breakout y PREFERENCIA por consolidation
                entries = (
                    base_filters
                    & consolidation_quality
                    & (self.close > self.high.shift().rolling(20).max())
                )

            else:  # 'any'
                # Any: Aplicar consolidation quality para evitar basura
                entries = base_filters & consolidation_quality

            # ============================================================
            # POSITION SIZING - Fixed Dollar Risk con Exposure Control
            # ============================================================

            # 1. Calcular base position value ($)
            # Refactored to use centralized PositionSizer
            position_value_base = PositionSizer.get_fixed_risk_size(
                close=self.close,
                risk_dollars=risk_dollars,
                stop_pct=max_stop_pct * 100 if max_stop_pct < 1.0 else max_stop_pct,
                min_stop_pct=3.0,
            ).astype(self.dtype)

            # 2. Aplicar ajustes por RVOL (size reduction)
            position_value = PositionSizer.apply_rvol_adjustment(
                position_value=position_value_base,
                rvol=self.rvol,
                warning_level=rvol_warning,
                danger_level=rvol_danger,
                warning_size=rvol_warning_size,
                danger_size=rvol_danger_size,
            ).astype(self.dtype)

            # 3. Aplicar límite de exposición por ticker
            position_value = PositionSizer.apply_exposure_limit(
                position_value, self.initial_capital, max_exposure_pct
            ).astype(self.dtype)

            # ============================================================
            # VALIDACION DE PRECIOS (evita NaN/inf/<=0)
            # ============================================================

            valid_close = self.close.replace([np.inf, -np.inf], np.nan).ffill().bfill()
            valid_prices_mask = (valid_close > 0) & valid_close.notna()
            entries = entries & valid_prices_mask

            # ============================================================
            # EXITS (3-PHASE LOGIC)
            # ============================================================

            if not use_phases:
                # Simple exit: below SMA20
                exits = valid_close < self.sma20

                portfolio = vbt.Portfolio.from_signals(
                    valid_close,
                    entries,
                    exits,
                    size=position_value,
                    size_type="amount",
                    init_cash=self.initial_capital,
                    fees=0.001,
                    slippage=0.001,
                    freq="1D",
                )

                trades_df = portfolio.trades.records_readable

                if len(trades_df) > 0:
                    total_profit = trades_df[trades_df["PnL"] > 0]["PnL"].sum()
                    total_loss = abs(trades_df[trades_df["PnL"] < 0]["PnL"].sum())
                    profit_factor = total_profit / total_loss if total_loss > 0 else 0

                    total_trades = len(trades_df)
                    final_value = portfolio.value().iloc[-1]
                    if isinstance(final_value, pd.Series):
                        final_value = final_value.sum()

                    total_invested = self.initial_capital * len(self.close.columns)
                    total_return_pct = (final_value / total_invested - 1) * 100

                    win_rate_pct = (
                        len(trades_df[trades_df["PnL"] > 0]) / total_trades * 100
                    )

                    returns = portfolio.returns()
                    if isinstance(returns, pd.DataFrame):
                        returns = returns.stack().dropna()
                    else:
                        returns = returns.dropna()
                    sharpe_ratio = (
                        returns.mean() / returns.std() * np.sqrt(252)
                        if returns.std() > 0
                        else 0
                    )

                    equity = portfolio.value()
                    if isinstance(equity, pd.DataFrame):
                        equity = equity.sum(axis=1)
                    cummax = equity.cummax()
                    drawdown = (equity - cummax) / cummax
                    max_drawdown_pct = abs(drawdown.min()) * 100

                else:
                    profit_factor = 0
                    total_trades = 0
                    total_return_pct = 0
                    sharpe_ratio = 0
                    max_drawdown_pct = 0
                    win_rate_pct = 0
                    final_value = self.initial_capital

                result = {
                    "profit_factor": profit_factor,
                    "total_trades": total_trades,
                    "total_return_pct": total_return_pct,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown_pct": max_drawdown_pct,
                    "win_rate_pct": win_rate_pct,
                    "final_value": final_value,
                }

            else:
                # 3-PHASE EXITS - Simulación día-a-día (fix del bug crítico)
                # La lógica anterior usaba ffill() que mantenía entry_price indefinidamente
                # y position_active nunca se reseteaba, generando trades fantasmas.
                stop_pct_decimal = (
                    max_stop_pct / 100.0 if max_stop_pct > 1.0 else max_stop_pct
                )

                # Convertir a arrays numpy para simulación eficiente
                close_arr = valid_close.values.astype(np.float64)
                entries_arr = entries.values.astype(bool)
                position_value_arr = position_value.values.astype(np.float64)

                n_days, n_tickers = close_arr.shape

                # Estado del portafolio
                cash = float(self.initial_capital)
                equity_curve = np.zeros(n_days, dtype=np.float64)

                # Estado de posiciones (por ticker) - similar a Numba core
                pos_active = np.zeros(n_tickers, dtype=bool)
                pos_shares = np.zeros(n_tickers, dtype=np.float64)
                pos_original_shares = np.zeros(n_tickers, dtype=np.float64)
                pos_entry_price = np.zeros(n_tickers, dtype=np.float64)
                pos_stop_price = np.zeros(n_tickers, dtype=np.float64)
                pos_tp1_price = np.zeros(n_tickers, dtype=np.float64)
                pos_tp2_price = np.zeros(n_tickers, dtype=np.float64)
                pos_stop_dist = np.zeros(n_tickers, dtype=np.float64)

                # Flags de fase
                pos_tp1_done = np.zeros(n_tickers, dtype=bool)
                pos_tp2_done = np.zeros(n_tickers, dtype=bool)

                # Registro de trades
                trades_log = []

                # Arrays de indicadores para exits
                ema8_arr = self.ema8.values.astype(np.float64)
                ema21_arr = self.ema21.values.astype(np.float64)

                # BUCLE PRINCIPAL (Día a Día)
                for t in range(n_days):
                    # 1. Valorar Portafolio al cierre de hoy
                    current_equity = cash
                    for i in range(n_tickers):
                        if pos_active[i]:
                            current_price = close_arr[t, i]
                            if np.isnan(current_price) and t > 0:
                                current_price = close_arr[t - 1, i]
                            if not np.isnan(current_price):
                                current_equity += pos_shares[i] * current_price

                    equity_curve[t] = current_equity

                    # Saltar último día
                    if t == n_days - 1:
                        break

                    # 2. Procesar SALIDAS (Prioridad: TP1 > TP2 > STOP > RUNNER)
                    for i in range(n_tickers):
                        if not pos_active[i]:
                            continue

                        curr_high = close_arr[t, i]  # Usar close como proxy de high
                        curr_low = close_arr[t, i]  # Usar close como proxy de low
                        curr_close = close_arr[t, i]

                        if np.isnan(curr_close):
                            continue

                        exit_signal = False
                        exit_type = -1
                        exit_shares = 0.0
                        exit_price = 0.0

                        # --- A) TAKE PROFIT 1 ---
                        if not pos_tp1_done[i] and curr_high >= pos_tp1_price[i]:
                            exit_signal = True
                            exit_type = 1
                            exit_shares = np.floor(pos_original_shares[i] * tp1_pct)
                            exit_price = pos_tp1_price[i]

                        # --- B) TAKE PROFIT 2 ---
                        elif not pos_tp2_done[i] and curr_high >= pos_tp2_price[i]:
                            exit_signal = True
                            exit_type = 2
                            if pos_tp1_done[i]:
                                remaining_pct = 1.0 - tp1_pct
                                if remaining_pct > 0:
                                    shares_pct = tp2_pct / remaining_pct
                                    exit_shares = np.floor(pos_shares[i] * shares_pct)
                                else:
                                    exit_shares = pos_shares[i]
                            else:
                                exit_shares = np.floor(pos_original_shares[i] * tp2_pct)
                            exit_price = pos_tp2_price[i]

                        # --- C) STOP LOSS ---
                        elif curr_low <= pos_stop_price[i]:
                            exit_signal = True
                            exit_type = 0
                            exit_shares = pos_shares[i]
                            exit_price = pos_stop_price[i]

                        # --- D) RUNNER EXIT (EMA8 < EMA21) ---
                        elif pos_tp1_done[i] and pos_tp2_done[i] and pos_shares[i] > 0:
                            ema8_val = ema8_arr[t, i]
                            ema21_val = ema21_arr[t, i]
                            if not np.isnan(ema8_val) and not np.isnan(ema21_val):
                                if ema8_val < ema21_val:
                                    exit_signal = True
                                    exit_type = 3
                                    exit_shares = pos_shares[i]
                                    exit_price = curr_close

                        # --- EJECUTAR SALIDA ---
                        if exit_signal and exit_shares > 0:
                            exit_shares = min(exit_shares, pos_shares[i])
                            pnl = (exit_price - pos_entry_price[i]) * exit_shares
                            cash += exit_price * exit_shares
                            pos_shares[i] -= exit_shares

                            trades_log.append(
                                {
                                    "day": t,
                                    "ticker_idx": i,
                                    "exit_type": exit_type,
                                    "exit_price": exit_price,
                                    "shares": exit_shares,
                                    "pnl": pnl,
                                    "entry_price": pos_entry_price[i],
                                }
                            )

                            # Actualizar flags
                            if exit_type == 0:  # STOP total
                                pos_active[i] = False
                                pos_shares[i] = 0
                                pos_tp1_done[i] = False
                                pos_tp2_done[i] = False
                            elif exit_type == 1:
                                pos_tp1_done[i] = True
                            elif exit_type == 2:
                                pos_tp2_done[i] = True
                            elif exit_type == 3:  # RUNNER
                                pos_active[i] = False
                                pos_shares[i] = 0
                                pos_tp1_done[i] = False
                                pos_tp2_done[i] = False

                            # Limpieza residual
                            if pos_shares[i] < 1:
                                pos_active[i] = False
                                pos_shares[i] = 0
                                pos_tp1_done[i] = False
                                pos_tp2_done[i] = False

                    # 3. Procesar ENTRADAS
                    for i in range(n_tickers):
                        if pos_active[i]:
                            continue  # Ya hay posición activa

                        if entries_arr[t, i]:
                            curr_close = close_arr[t, i]

                            if np.isnan(curr_close) or curr_close <= 0:
                                continue

                            # Calcular tamaño de posición
                            stop_dist = curr_close * stop_pct_decimal
                            if stop_dist <= 0:
                                continue

                            pos_value = position_value_arr[t, i]
                            if pos_value <= 0:
                                continue

                            shares = np.floor(pos_value / curr_close)
                            if shares <= 0:
                                continue

                            cost = shares * curr_close

                            if cash >= cost:
                                # Ejecutar entrada
                                cash -= cost
                                pos_active[i] = True
                                pos_shares[i] = shares
                                pos_original_shares[i] = shares
                                pos_entry_price[i] = curr_close
                                pos_stop_dist[i] = stop_dist

                                # Definir niveles
                                pos_stop_price[i] = curr_close - stop_dist
                                pos_tp1_price[i] = curr_close + (stop_dist * tp1_r)
                                pos_tp2_price[i] = curr_close + (stop_dist * tp2_r)

                                # Reset flags
                                pos_tp1_done[i] = False
                                pos_tp2_done[i] = False

                # Convertir trades a DataFrame
                trades_df = pd.DataFrame(trades_log) if trades_log else pd.DataFrame()

                # Calcular métricas
                total_equity = pd.Series(equity_curve, index=valid_close.index)

                if len(trades_df) > 0:
                    total_profit = trades_df[trades_df["pnl"] > 0]["pnl"].sum()
                    total_loss = abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
                    profit_factor = total_profit / total_loss if total_loss > 0 else 0

                    # Contar entradas únicas
                    unique_entries = (
                        trades_df.groupby(["day", "ticker_idx"]).size().shape[0]
                    )
                    total_trades = unique_entries

                    final_value = total_equity.iloc[-1]
                    total_invested = self.initial_capital
                    total_return_pct = (final_value / total_invested - 1) * 100

                    win_rate_pct = (
                        len(trades_df[trades_df["pnl"] > 0]) / len(trades_df) * 100
                    )

                    returns = total_equity.pct_change().dropna()
                    sharpe_ratio = (
                        returns.mean() / returns.std() * np.sqrt(252)
                        if returns.std() > 0
                        else 0
                    )

                    cummax = total_equity.cummax()
                    drawdown = (total_equity - cummax) / cummax
                    max_drawdown_pct = abs(drawdown.min()) * 100

                    # Breakdown por fase
                    tp1_trades = len(trades_df[trades_df["exit_type"] == 1])
                    tp2_trades = len(trades_df[trades_df["exit_type"] == 2])
                    runner_trades = len(trades_df[trades_df["exit_type"] == 3])
                    stop_trades = len(trades_df[trades_df["exit_type"] == 0])
                else:
                    profit_factor = 0
                    total_trades = 0
                    total_return_pct = 0
                    sharpe_ratio = 0
                    max_drawdown_pct = 0
                    win_rate_pct = 0
                    final_value = self.initial_capital
                    tp1_trades = tp2_trades = runner_trades = stop_trades = 0

                result = {
                    "profit_factor": profit_factor,
                    "total_trades": total_trades,
                    "all_exits": len(trades_df),
                    "unique_entries": total_trades,
                    "total_return_pct": total_return_pct,
                    "sharpe_ratio": sharpe_ratio,
                    "max_drawdown_pct": max_drawdown_pct,
                    "win_rate_pct": win_rate_pct,
                    "final_value": final_value,
                    "phase_breakdown": {
                        "tp1_trades": tp1_trades,
                        "tp2_trades": tp2_trades,
                        "runner_trades": runner_trades,
                        "stop_trades": stop_trades,
                    },
                }

                # Cleanup
                del trades_df, trades_log, total_equity

            # Cleanup
            del entries, position_value
            gc.collect()

            return result

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            return {
                "profit_factor": 0,
                "total_trades": 0,
                "total_return_pct": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "win_rate_pct": 0,
                "final_value": self.initial_capital,
            }

    def get_data_summary(self) -> Dict:
        """Summary de datos cargados"""
        return {
            "engine": "BUGATTI DIVO",
            "tickers_loaded": len(self.valid_tickers),
            "date_range": f"{self.close.index[0].date()} to {self.close.index[-1].date()}",
            "trading_days": len(self.close),
            "data_shape": self.close.shape,
            "memory_mb": (
                self.close.memory_usage(deep=True).sum()
                + self.open.memory_usage(deep=True).sum()
                + self.high.memory_usage(deep=True).sum()
                + self.low.memory_usage(deep=True).sum()
                + self.volume.memory_usage(deep=True).sum()
            )
            / 1024
            / 1024,
            "dtype": str(self.dtype),
            "lazy_indicators": True,
        }


# ============================================================================
# OPTUNA WRAPPER CON GC INTELIGENTE
# ============================================================================


def create_memory_safe_objective(engine, metric="sharpe", clear_cache_every=20):
    """
    Wrapper que limpia cache cada N trials para evitar RAM creep.
    """
    trial_count = [0]

    def objective(trial):
        trial_count[0] += 1

        params = {
            "signal_type": trial.suggest_categorical(
                "signal_type", ["any", "breakout", "vcp"]
            ),
            "min_rvol": trial.suggest_categorical("min_rvol", [1.5, 2.0, 2.5]),
            "min_adr": trial.suggest_categorical("min_adr", [1.5, 2.0, 2.5]),
            "risk_dollars": trial.suggest_categorical("risk_dollars", [150, 200, 250]),
            "max_dist_sma20": trial.suggest_categorical(
                "max_dist_sma20", [10.0, 12.5, 15.0]
            ),
            "tp1_r": trial.suggest_categorical("tp1_r", [1.25, 1.5, 1.75, 2.0]),
            "tp2_r": trial.suggest_categorical("tp2_r", [3.0, 3.5, 4.0]),
            "use_phases": True,
            "require_bullish_spy": False,
            "max_vix": 40.0,
        }

        result = engine.backtest(params)

        # Limpieza periódica
        if trial_count[0] % clear_cache_every == 0:
            logger.info(f"🧹 Clearing cache (trial {trial_count[0]})")
            engine.clear_indicator_cache()
            gc.collect()

        # Penalizar drawdown excesivo
        sharpe = result.get("sharpe_ratio", -999)
        max_dd = abs(result.get("max_drawdown_pct", 100))

        if max_dd > 30:
            sharpe *= 0.5

        # CRITICAL FIX: Require minimum 30 trades for statistical significance
        if result.get("total_trades", 0) < 30:
            return -999

        return sharpe if metric == "sharpe" else result.get("profit_factor", 0)

    return objective


if __name__ == "__main__":
    # Quick test
    logger.info("⚡🔨 BUGATTI THOR - Benchmarking W16 Engine")

    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]

    engine = OptimizationEngineTHOR(
        tickers=tickers,
        start_date="2023-01-01",
        end_date="2023-12-31",
        use_float32=True,
        chunk_size=50,
    )

    summary = engine.get_data_summary()
    print(f"\n{'=' * 60}")
    print(f"Engine: BUGATTI THOR (W16)")
    print(f"Tickers: {summary['tickers_loaded']}")
    print(f"Period: {summary['date_range']}")
    print(f"Memory: {summary['memory_mb']:.1f} MB")
    print(f"Dtype: {summary['dtype']}")
    print(f"{'=' * 60}")

    params = {
        "signal_type": "any",
        "min_rvol": 2.0,
        "min_adr": 2.0,
        "risk_dollars": 150,
        "min_dollar_volume": 5e6,
        "use_phases": True,
    }

    stats = engine.backtest(params)
    print(f"\nTest Backtest (THOR Logic):")
    print(f"  Sharpe: {stats['sharpe_ratio']:.2f}")
    print(f"  Trades: {stats['total_trades']}")
    print(f"  Return: {stats['total_return_pct']:.2f}%")
    print(f"  Max DD: {stats['max_drawdown_pct']:.2f}%")

    engine.clear_indicator_cache()
    print(f"\n✅ THOR is roaring! ⚡🔨")
