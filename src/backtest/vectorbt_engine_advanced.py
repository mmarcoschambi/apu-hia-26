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

# import vectorbt as vbt  # Lazy load
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
from src.utils.sector_rotation import (
    SectorRotationAnalyzer,
    integrate_sector_filter_in_backtest,
    SECTOR_MAP,
)
from src.utils.rvol_context_v2 import integrate_with_unified_position_size
from src.utils.market_regime import MarketRegimeClassifier, load_spy_vix_data
from src.utils.adaptive_filter_engine import AdaptiveFilterEngine
from src.indicators.technical import TechnicalIndicators
from src.filters.liquidity import LiquidityFilters
from src.risk.position_sizing import PositionSizer
from src.backtest.numba_core import simulate_fast_core  # NEW: Numba Core
from config.defaults import filter_blacklisted_tickers  # Ticker blacklist


# ============================================================================
# MEMORY OPTIMIZATION: Helper function to convert and release DataFrames
# ============================================================================
def prepare_numba_arrays(engine, release_dataframes: bool = False) -> Dict:
    """
    Convierte DataFrames a arrays numpy.
    MEMORY OPTIMIZED: Creates float32 arrays to reduce memory usage by 50%.

    Args:
        engine: The backtest engine with DataFrames
        release_dataframes: If True, delete DataFrames after conversion (saves memory but
                           prevents multi-chunk processing). Default False for multi-chunk support.

    Returns:
        Dict con todos los arrays necesarios para el núcleo Numba
    """
    logger.info("🔄 Converting DataFrames to NumPy arrays (float32 optimization)...")

    arrays = {}

    # Core price arrays (mantener estos, se necesitan para simulate_with_partial_exits)
    # OPTIMIZATION: Use float32 to reduce memory usage by 50%
    arrays["close"] = engine.close.values.astype(np.float32)
    arrays["high"] = (
        engine.high.values.astype(np.float32)
        if hasattr(engine, "high") and engine.high is not None
        else arrays["close"]
    )
    arrays["low"] = (
        engine.low.values.astype(np.float32)
        if hasattr(engine, "low") and engine.low is not None
        else arrays["close"]
    )
    arrays["volume"] = (
        engine.volume.values.astype(np.float32)
        if hasattr(engine, "volume") and engine.volume is not None
        else np.ones_like(arrays["close"])
    )

    # Indicators arrays (ya calculados en load_data)
    # OPTIMIZATION: Use float32
    arrays["sma_20"] = (
        engine.sma_20.values.astype(np.float32)
        if hasattr(engine, "sma_20") and engine.sma_20 is not None
        else np.zeros_like(arrays["close"])
    )

    # Calculate ATR inline to avoid calling engine method if close was deleted
    if hasattr(engine, "high") and hasattr(engine, "low") and hasattr(engine, "close"):
        high_low = engine.high - engine.low
        high_close = np.abs(engine.high - engine.close.shift())
        low_close = np.abs(engine.low - engine.close.shift())
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        atr_df = tr.rolling(14).mean()
        arrays["atr"] = atr_df.values.astype(np.float32)
    else:
        arrays["atr"] = np.zeros_like(arrays["close"])

    arrays["rvol"] = (
        engine.rvol.values.astype(np.float32)
        if hasattr(engine, "rvol") and engine.rvol is not None
        else np.ones_like(arrays["close"])
    )
    arrays["avg_volume_20"] = (
        engine.avg_volume_20.values.astype(np.float32)
        if hasattr(engine, "avg_volume_20") and engine.avg_volume_20 is not None
        else np.ones_like(arrays["close"])
    )

    # EMA arrays for exits
    # OPTIMIZATION: Use float32
    arrays["ema_10"] = (
        engine.ema_10.values.astype(np.float32)
        if hasattr(engine, "ema_10") and engine.ema_10 is not None
        else np.zeros_like(arrays["close"])
    )
    arrays["ema_8"] = (
        engine.ema_8.values.astype(np.float32)
        if hasattr(engine, "ema_8") and engine.ema_8 is not None
        else np.zeros_like(arrays["close"])
    )
    arrays["ema_21"] = (
        engine.ema_21.values.astype(np.float32)
        if hasattr(engine, "ema_21") and engine.ema_21 is not None
        else np.zeros_like(arrays["close"])
    )

    # ============================================
    # ENTRY QUALITY SCORE v2 - RS Rank + 52wk Proximity
    # Score = 0.70 * RS_rank_daily + 0.30 * proximity_52wk_high
    #
    # RS_rank_daily: percentil cross-sectional del RS de 60 dias
    #   → responde "¿quién es el rey del momentum HOY?"
    #   → 1.0 = mejor RS relativo, 0.0 = peor
    #
    # proximity_52wk_high: close / max(close, 252 dias)
    #   → responde "¿quién tiene menos resistencia arriba?"
    #   → 1.0 = en el máximo, 0.5 = a 50% de distancia
    #
    # Pesos optimizables por Optuna: score_rs_weight, score_proximity_weight
    # ============================================
    try:
        close_arr = arrays["close"]
        n_rows, n_cols = close_arr.shape

        close_df = engine.close.ffill()

        # --- COMPONENTE 1: RS Rank del dia (cross-sectional percentile) ---
        # Usar el RS ya calculado en el engine (performance 60d) si existe
        # Si no, calcularlo directamente desde close
        rs_lookback = getattr(engine, "rs_lookback_days", 60)
        rs_raw = close_df.pct_change(rs_lookback)  # retorno 60 dias
        # Rank cross-sectional: cada dia, rankear todos los tickers
        # pct=True -> percentil 0.0 a 1.0, ascending=True -> mayor RS = 1.0
        score_rs = rs_raw.rank(axis=1, pct=True, ascending=True)
        score_rs = score_rs.ffill().fillna(0.5)  # neutral si no hay dato

        # --- COMPONENTE 2: Proximidad a máximo de 52 semanas ---
        # close / rolling_max_252 -> 1.0 = en ATH, menor = más lejos
        max_52wk = close_df.rolling(window=252, min_periods=50).max()
        proximity_52wk = (close_df / max_52wk.replace(0, np.nan)).clip(0.0, 1.0)
        proximity_52wk = proximity_52wk.ffill().fillna(0.5)

        # --- PONDERACION ---
        rs_w = getattr(engine, "score_rs_weight", 0.70)
        prox_w = getattr(engine, "score_proximity_weight", 0.30)
        # Asegurar que suman 1.0
        total_w = rs_w + prox_w
        if total_w > 0:
            rs_w = rs_w / total_w
            prox_w = prox_w / total_w

        entry_score_df = rs_w * score_rs + prox_w * proximity_52wk
        entry_score = entry_score_df.values.astype(np.float32)
        entry_score = np.nan_to_num(entry_score, nan=0.5)

        # Recortar a shape correcto
        if entry_score.shape != (n_rows, n_cols):
            padded = np.full((n_rows, n_cols), 0.5, dtype=np.float32)
            r = min(entry_score.shape[0], n_rows)
            c = min(entry_score.shape[1], n_cols)
            padded[:r, :c] = entry_score[:r, :c]
            entry_score = padded

        # ============================================
        # PATTERN BONUS - Add bonus for detected patterns
        # Pattern bonus is ADDITIVE: preserves timing semantics
        # ============================================
        if (
            hasattr(engine, "pattern_confidence_matrix")
            and engine.pattern_confidence_matrix is not None
        ):
            try:
                conf_df = engine.pattern_confidence_matrix

                # Get the dates and tickers from engine.close
                close_df = engine.close

                # Reindex pattern matrix to match close matrix
                common_dates = close_df.index.intersection(conf_df.index)
                common_tickers = [t for t in close_df.columns if t in conf_df.columns]

                if len(common_dates) > 0 and len(common_tickers) > 0:
                    # Extract pattern confidence for common dates/tickers
                    pattern_conf = conf_df.loc[common_dates, common_tickers]

                    # Align with close array (handle potential index mismatches)
                    pattern_arr = pattern_conf.values.astype(np.float32)

                    # Handle shape mismatch (may need to pad or trim)
                    target_shape = close_arr.shape
                    if pattern_arr.shape != target_shape:
                        # Pad with zeros if needed
                        padded = np.zeros(target_shape, dtype=np.float32)
                        min_rows = min(pattern_arr.shape[0], target_shape[0])
                        min_cols = min(pattern_arr.shape[1], target_shape[1])
                        padded[:min_rows, :min_cols] = pattern_arr[:min_rows, :min_cols]
                        pattern_arr = padded

                    # Calculate pattern bonus based on confidence thresholds
                    bonus_high = getattr(engine, "pattern_bonus_high", 0.30)
                    bonus_med = getattr(engine, "pattern_bonus_med", 0.20)
                    bonus_low = getattr(engine, "pattern_bonus_low", 0.10)

                    pattern_bonus = np.where(
                        pattern_arr >= 0.7,
                        bonus_high,
                        np.where(
                            pattern_arr >= 0.5,
                            bonus_med,
                            np.where(pattern_arr >= 0.3, bonus_low, 0.0),
                        ),
                    )

                    # Add bonus to base entry_score
                    entry_score = np.clip(entry_score + pattern_bonus, 0.0, 1.0)

                    # Log pattern bonus stats
                    bonus_applied = (pattern_bonus > 0).sum()
                    total_entries = pattern_arr.size
                    logger.info(
                        f"   🎯 Pattern bonus applied: {bonus_applied}/{total_entries} "
                        f"({bonus_applied / total_entries * 100:.1f}%) entries with pattern"
                    )
            except Exception as e:
                logger.warning(f"⚠️  Could not apply pattern bonus: {e}")

        arrays["entry_score"] = entry_score

        logger.info(
            f"   📊 Entry score calculated: mean={entry_score.mean():.3f}, std={entry_score.std():.3f}"
        )
    except Exception as e:
        logger.warning(
            f"   ⚠️ Could not calculate entry_score: {e}. Using uniform score."
        )
        arrays["entry_score"] = np.ones_like(arrays["close"], dtype=np.float32)

    # Market data arrays
    # OPTIMIZATION: Use float32
    if (
        hasattr(engine, "spy_close")
        and engine.spy_close is not None
        and isinstance(engine.spy_close, pd.Series)
    ):
        arrays["spy_close"] = engine.spy_close.values.astype(np.float32)
        arrays["vix_close"] = (
            engine.vix_close.values.astype(np.float32)
            if hasattr(engine, "vix_close") and engine.vix_close is not None
            else np.zeros(len(arrays["close"]), dtype=np.float32)
        )
    else:
        arrays["spy_close"] = np.zeros(len(arrays["close"]), dtype=np.float32)
        arrays["vix_close"] = np.zeros(len(arrays["close"]), dtype=np.float32)

    # Calculate memory usage
    total_bytes = sum(arr.nbytes for arr in arrays.values())
    logger.info(f"   ✅ Arrays prepared: {total_bytes / (1024**2):.1f} MB total")

    # Log shapes for debugging
    logger.info(
        f"   📊 Array shapes: close={arrays['close'].shape}, high={arrays['high'].shape}"
    )

    # OPTIONAL: Release DataFrames after converting to arrays
    # Only do this for single-chunk mode to save memory
    # For multi-chunk mode, we need to keep DataFrames
    if release_dataframes:
        logger.info("   🧹 Releasing DataFrames to free memory...")
        attrs_to_delete = [
            "close",
            "high",
            "low",
            "volume",
            "sma_20",
            "rvol",
            "avg_volume_20",
            "ema_10",
            "ema_8",
            "ema_21",
            "spy_close",
            "vix_close",
        ]
        for attr in attrs_to_delete:
            if hasattr(engine, attr):
                try:
                    delattr(engine, attr)
                except:
                    pass

        # Force garbage collection to free memory immediately
        gc.collect()
        logger.info("   🧹 Memory cleanup complete - DataFrames released")

    return arrays


logger = logging.getLogger(__name__)


def get_dynamic_thresholds(
    current_vix: float,
    base_min_rvol: float = 0.91,
    base_min_adr: float = 1.97,
    base_max_dist_sma20: float = 8.94,
    base_max_stop_pct: float = 8.0,
    base_min_dollar_volume: float = 20_000_000,
    base_min_consolidation_days: int = 5,
) -> Dict[str, float]:
    """
    Ajusta umbrales según volatilidad del mercado (VIX).
    DYNAMIC: Usa validated params como base y aplica multiplicadores por régimen.

    Defaults sincronizados con config/production_config.json (optimizado 2026-02-19)

    Args:
        current_vix: Valor actual del VIX
        base_*: Parámetros base de validated params (usados en NEUTRAL regime)

    Returns:
        Diccionario con umbrales ajustados por régimen
    """
    if current_vix < 20:  # Mercado tranquilo/bullish
        return {
            "regime_name": "BULL",
            "min_rvol": base_min_rvol * 1.0,  # Relax (same as base)
            "min_adr": base_min_adr * 1.0,  # Relax (same as base)
            "max_dist_sma20": base_max_dist_sma20 * 1.15,  # Allow +15% extension
            "max_stop_pct": base_max_stop_pct * 1.08,  # Allow +8% wider stops
            "min_dollar_volume": base_min_dollar_volume * 0.67,  # Relax liquidity -33%
            "min_consolidation_days": max(
                5, int(base_min_consolidation_days * 0.6)
            ),  # Shorter consolidation
            "strict_sector": False,
        }
    elif current_vix < 30:  # Mercado normal - USE BASE PARAMS
        return {
            "regime_name": "NEUTRAL",
            "min_rvol": base_min_rvol,
            "min_adr": base_min_adr,
            "max_dist_sma20": base_max_dist_sma20,
            "max_stop_pct": base_max_stop_pct,
            "min_dollar_volume": base_min_dollar_volume,
            "min_consolidation_days": base_min_consolidation_days,
            "strict_sector": False,
        }
    else:  # Mercado volátil/bear - TIGHTEN
        return {
            "regime_name": "BEAR",
            "min_rvol": base_min_rvol * 1.2,  # +20% más estricto
            "min_adr": base_min_adr * 1.6,  # +60% más estricto
            "max_dist_sma20": base_max_dist_sma20 * 0.71,  # -29% menos extensión
            "max_stop_pct": base_max_stop_pct * 0.92,  # -8% stops más ajustados
            "min_dollar_volume": base_min_dollar_volume
            * 1.67,  # +67% más liquidez requerida
            "min_consolidation_days": int(
                base_min_consolidation_days * 1.2
            ),  # +20% más consolidación
            "strict_sector": True,
        }


@lru_cache(maxsize=256)
def should_trade_long(
    spy_price: float,
    spy_sma50: float,
    vix_value: float,
    max_vix_threshold: float = 35.0,
) -> bool:
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
    RISK_PER_TRADE = (
        risk_per_trade  # Dólares Fijos. Puede ser sobrescrito por parametro.
    )

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

    def __init__(
        self,
        universe: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        risk_pct: float = 0.005,
        risk_dollars: Optional[float] = None,  # NEW: Fixed dollar risk
        max_exposure_pct: float = 0.35,  # INCREASED: 35% (was 25%) to reduce zero_shares rejections
        # Filter parameters (sincronizados con production_config.json)
        max_dist_sma20: float = 8.94,  # OPTIMIZED: 8.94%
        # RVOL filters
        min_rvol: float = 0.91,  # OPTIMIZED: 0.91x
        rvol_danger: float = 3.0,  # VALIDATED: Danger zone
        rvol_warning: float = 2.0,  # VALIDATED: Warning zone
        rvol_danger_size: int = 30,  # VALIDATED: 30%
        rvol_warning_size: int = 65,  # VALIDATED: 65%
        # ADR filters
        min_adr: float = 1.97,  # OPTIMIZED: 1.97%
        adr_high: float = 6.0,
        adr_med: float = 5.0,
        # Target Multiples (VALIDATED)
        tp1_r: float = 1.25,
        tp2_r: float = 3.0,
        # Volume filters (sincronizados con production_config.json)
        min_volume: int = 100000,  # Min daily volume (100k shares)
        min_dollar_volume: float = 20000000,  # OPTIMIZED: $20M
        max_stop_pct: float = 8.0,  # OPTIMIZED: 8.0%
        earnings_days: int = 5,
        earnings_cushion: float = 10.0,
        use_earnings_calendar: bool = False,  # VALIDATED: Disabled
        offline_mode: bool = True,
        # Sector rotation parameters (NEW)
        use_composite_sector_scoring: bool = False,  # Use Top 40% methodology
        sector_top_percentile: float = 0.40,  # Top 40% of sectors
        require_positive_rs: bool = False,  # CONVERGENCE: False by default (was True)
        # Market regime parameters (NEW)
        use_market_regime_filter: bool = False,  # Enable market context filter
        block_trades_in_stage3: bool = True,  # Block longs in distribution
        block_trades_in_stage4: bool = False,  # RELAXED: Allow longs in Stage 4 oversold
        adjust_risk_by_regime: bool = True,  # Adjust position size by market stage
        use_dynamic_thresholds: bool = False,  # Use VIX-based dynamic thresholds
        max_vix_threshold: float = 35.0,  # PROFESSIONAL: VIX > 35 = NO trades (was 30)
        require_spy_above_sma50: bool = True,  # PROFESSIONAL: SPY > SMA50 required
        min_consolidation_days: int = 10,  # PROFESSIONAL: VCP quality (was 5)
        use_adaptive_filtering: bool = False,  # NEW: Use AdaptiveFilterEngine with tiered filtering
        # Survivorship bias protection (NEW)
        min_pre_history_days: int = 200,  # Min trading days required before start_date (200 ≈ 1 year)
        use_pit_universe: bool = True,  # Point-in-time S&P 500 membership filter (eliminates survivorship bias)
        # NEW: RS IBD-style parameters
        use_rs_percentile: bool = False,  # Use IBD-style RS ranking (0-100 percentile)
        min_rs_percentile: float = 80.0,  # Minimum RS percentile (80 = Top 20%)
        rs_lookback_days: int = 60,  # Lookback for RS calculation (60 = 3 months)
        # NEW: SMA50/ATR Extension filter
        use_sma50_atr_filter: bool = False,  # Filter overextended stocks
        max_sma50_atr_extension: float = 2.0,  # Max ATR extension from SMA50
        # NEW: Trailing Stop parameters
        use_trailing_stop: bool = True,  # ENABLED: Move to breakeven after TP1 hit
        be_trailing_threshold: float = 1.5,  # Move stop to BE when +1.5R (after TP1)
        # NEW: ATR-based Stop System
        use_atr_stop: bool = False,  # Use ATR-based stops instead of fixed %
        atr_stop_multiplier: float = 1.5,  # ATR multiplier for initial stop (1.5-2.0)
        atr_trailing_multiplier: float = 2.5,  # ATR multiplier for trailing (2.0-3.0)
        # NEW: Signal type for convergence with THOR
        signal_type: str = "breakout",  # 'breakout' (close > 20d high) or 'any' (close > SMA20)
        # NEW: Operation Mode
        mode: str = "production",  # 'production' (Pct Risk) or 'convergence' (Fixed $ Risk like THOR)
        # NEW: Entry Quality Score weights (optimizable)
        score_vwap_weight: float = 0.4,  # Weight for VWAP proximity (0.0-1.0)
        score_volume_weight: float = 0.4,  # Weight for volume strength (0.0-1.0)
        score_ema_weight: float = 0.2,  # Weight for EMA10 trend (0.0-1.0)
        # NEW: Pattern Detection Integration (Tier 2)
        use_pattern_filter: bool = False,  # Filter entries without pattern (start False)
        min_pattern_confidence: float = 0.5,  # Minimum confidence for filter
        pattern_bonus_high: float = 0.30,  # Bonus for confidence >= 0.7
        pattern_bonus_med: float = 0.20,  # Bonus for confidence >= 0.5
        pattern_bonus_low: float = 0.10,  # Bonus for confidence >= 0.3
        allowed_patterns: Optional[List[str]] = None,  # None = all patterns allowed
        pattern_cache_path: str = "data/pattern_matrix.pkl",  # Path to precomputed patterns
        **kwargs,
    ):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date) if end_date else pd.Timestamp.now()
        self.initial_capital = initial_capital
        self.mode = mode

        # Configure Risk based on Mode
        if self.mode == "convergence":
            # CONVERGENCE MODE: Mimic THOR exactly
            # 1. Fixed Dollar Risk ($150)
            self.risk_dollars = 150.0
            self.use_fixed_dollar_risk = True
            self.risk_pct = 0.0  # Irrelevant but set for safety

            logger.info("=" * 60)
            logger.info("🔬 MODE: CONVERGENCE (Validating logic vs THOR)")
            logger.info("   • Risk: FIXED DOLLAR ($150)")
            logger.info("   • Compounding: DISABLED")
            logger.info("   • Goal: Match THOR signals and exits")
            logger.info("=" * 60)

        else:
            # PRODUCTION MODE: Real trading simulation
            # Check if fixed dollar risk is provided
            if risk_dollars is not None and risk_dollars > 0:
                # Fixed Dollar Risk Mode
                self.risk_dollars = risk_dollars
                self.use_fixed_dollar_risk = True
                self.risk_pct = 0.0  # Not used in fixed dollar mode

                logger.info("=" * 60)
                logger.info("🚀 MODE: PRODUCTION (Fixed Dollar Risk)")
                logger.info(f"   • Risk: FIXED DOLLAR (${self.risk_dollars:.0f})")
                logger.info("   • Compounding: DISABLED")
                logger.info("=" * 60)
            else:
                # Percentage Risk (Compounding)
                self.risk_pct = risk_pct
                self.use_fixed_dollar_risk = False
                self.risk_dollars = None  # Disable fixed risk

                logger.info("=" * 60)
                logger.info("🚀 MODE: PRODUCTION (Percentage Risk)")
                logger.info(f"   • Risk: PERCENTAGE ({self.risk_pct * 100:.1f}%)")
                logger.info("   • Compounding: ENABLED")
                logger.info("=" * 60)

        # Store original risk_dollars parameter for market regime adjustments
        self.base_risk_dollars = self.risk_dollars if self.risk_dollars else 500.0

        # Store Target Multiples
        self.tp1_r = tp1_r
        self.tp2_r = tp2_r

        # TP exit percentages (VALIDATED)
        self.tp1_pct = kwargs.get("tp1_pct", 0.33)  # VALIDATED: 33%
        self.tp2_pct = kwargs.get("tp2_pct", 0.33)  # VALIDATED: 33%
        self.runner_pct = kwargs.get("runner_pct", 0.34)  # VALIDATED: 34%

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

        # ATR-based Stop System
        self.use_atr_stop = use_atr_stop
        self.atr_stop_multiplier = atr_stop_multiplier
        self.atr_trailing_multiplier = atr_trailing_multiplier

        # Signal type
        self.signal_type = signal_type

        # Entry Quality Score weights
        self.score_vwap_weight = score_vwap_weight
        self.score_volume_weight = score_volume_weight
        self.score_ema_weight = score_ema_weight

        # Pattern Detection Integration
        self.use_pattern_filter = use_pattern_filter
        self.min_pattern_confidence = min_pattern_confidence
        self.pattern_bonus_high = pattern_bonus_high
        self.pattern_bonus_med = pattern_bonus_med
        self.pattern_bonus_low = pattern_bonus_low
        self.allowed_patterns = allowed_patterns
        self.pattern_cache_path = pattern_cache_path
        self.pattern_confidence_matrix: Optional[pd.DataFrame] = None
        self.pattern_type_matrix: Optional[pd.DataFrame] = None

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
        self.earnings_cushion = int(
            earnings_cushion
        )  # Post-earnings buffer in trading days
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
        self.min_pre_history_days = min_pre_history_days  # Survivorship bias protection
        self.use_pit_universe = (
            use_pit_universe  # Point-in-time S&P 500 membership (survivorship bias)
        )
        self.tradeable_mask = None  # Built in load_data() if use_pit_universe=True
        self.require_positive_rs = require_positive_rs

        # NEW: RS IBD-style parameters
        self.use_rs_percentile = use_rs_percentile
        self.min_rs_percentile = min_rs_percentile
        self.rs_lookback_days = rs_lookback_days

        # NEW: SMA50/ATR Extension filter
        self.use_sma50_atr_filter = use_sma50_atr_filter
        self.max_sma50_atr_extension = max_sma50_atr_extension
        self.min_consolidation_days = min_consolidation_days
        self.use_adaptive_filtering = (
            use_adaptive_filtering  # NEW: Adaptive filter engine flag
        )
        self.require_positive_rs = (
            require_positive_rs  # NEW: Require RS > 0 to eliminate weak stocks
        )

        # Initialize AdaptiveFilterEngine (will be reconfigured if use_adaptive_filtering=True)
        self.filter_engine = None
        self.rejection_stats_tier = {}  # Store rejection stats from vectorized filtering
        self.rejection_details_df = None  # Store detailed rejection reasons

        self.cache = TickerCache()
        self.data_provider = MarketDataProvider()  # For earnings data
        self.data: Dict[str, pd.DataFrame] = {}

        logger.info(f"🚀 Advanced VectorBT Engine initialized")
        logger.info(f"📅 Period: {start_date} to {end_date}")
        logger.info(f"🎯 Universe: {len(universe)} tickers")
        logger.info(
            f"🎛️  Liquidity: vol≥{min_volume / 1000:.0f}k, $vol≥${min_dollar_volume / 1e6:.0f}M, ADR≥{min_adr}%, RVOL≥{min_rvol}x"
        )
        logger.info(
            f"🎛️  Position Size: RVOL Danger≥{rvol_danger}x→{rvol_danger_size}%, Warning≥{rvol_warning}x→{rvol_warning_size}%"
        )
        if self.use_rs_percentile:
            logger.info(
                f"📊 IBD-Style RS: RS≥{self.min_rs_percentile}%, Lookback={self.rs_lookback_days}d"
            )
        if self.use_sma50_atr_filter:
            logger.info(
                f"📏 SMA50/ATR: Max extension={self.max_sma50_atr_extension}x ATR"
            )

        # Initialize market regime classifier if enabled
        if self.use_market_regime_filter:
            logger.info("=" * 60)
            logger.info("🌍 MARKET REGIME FILTER ENABLED")
            logger.info("=" * 60)
            try:
                spy_data, vix_data = load_spy_vix_data(
                    self.start_date.strftime("%Y-%m-%d"),
                    self.end_date.strftime("%Y-%m-%d"),
                    cache=self.data_provider,
                )
                self.market_regime_classifier = MarketRegimeClassifier(
                    spy_data, vix_data
                )
                logger.info("   ✅ Market regime classifier initialized")
                logger.info(f"   🚫 Block Stage 3: {self.block_trades_in_stage3}")
                logger.info(f"   🚫 Block Stage 4: {self.block_trades_in_stage4}")
                logger.info(
                    f"   📊 Adjust risk by regime: {self.adjust_risk_by_regime}"
                )
            except Exception as e:
                logger.error(
                    f"   ❌ Failed to initialize market regime classifier: {e}"
                )
                logger.warning("   ⚠️  Continuing without market regime filter")
                self.use_market_regime_filter = False

    def _load_pattern_cache(self) -> None:
        """
        Load precomputed pattern cache and build aligned matrices.
        Called from run_backtest() before prepare_numba_arrays.
        """
        import pickle
        from pathlib import Path

        cache_path = Path(self.pattern_cache_path)
        if not cache_path.exists():
            logger.warning(f"⚠️  Pattern cache not found: {cache_path}")
            return

        try:
            with open(cache_path, "rb") as f:
                matrix_data = pickle.load(f)

            if isinstance(matrix_data, dict) and "confidence" in matrix_data:
                conf_df = matrix_data["confidence"]
                pt_df = matrix_data.get("pattern_type")
            else:
                logger.warning(f"⚠️  Pattern cache format unexpected")
                return

            # Filter to relevant date range
            conf_df = conf_df.loc[conf_df.index >= self.start_date]
            conf_df = conf_df.loc[conf_df.index <= self.end_date]

            # Filter to universe tickers
            available_tickers = [t for t in self.universe if t in conf_df.columns]
            if len(available_tickers) < len(self.universe):
                missing = set(self.universe) - set(available_tickers)
                logger.warning(
                    f"⚠️  {len(missing)} tickers not in pattern cache: {list(missing)[:5]}..."
                )

            conf_df = conf_df[available_tickers]
            if pt_df is not None:
                pt_df = pt_df[available_tickers]

            self.pattern_confidence_matrix = conf_df
            self.pattern_type_matrix = pt_df

            # Stats
            total_entries = conf_df.size
            patterns_found = (conf_df > 0).sum().sum()
            detection_rate = (
                patterns_found / total_entries * 100 if total_entries > 0 else 0
            )

            logger.info(
                f"✅ Pattern cache loaded: {len(available_tickers)} tickers, "
                f"{len(conf_df)} dates, {patterns_found} patterns ({detection_rate:.1f}% detection)"
            )

            # Log pattern type distribution
            if pt_df is not None:
                type_counts = {}
                for col in pt_df.columns:
                    counts = pt_df[col].value_counts()
                    for pt, cnt in counts.items():
                        if pt != "NONE":
                            type_counts[pt] = type_counts.get(pt, 0) + cnt
                if type_counts:
                    logger.info(
                        f"   📊 Pattern distribution: {dict(sorted(type_counts.items(), key=lambda x: -x[1])[:5])}"
                    )

        except Exception as e:
            logger.warning(f"⚠️  Failed to load pattern cache: {e}")

    def load_data(self) -> pd.DataFrame:
        """Load OHLCV data for all tickers with 1 year lookback for valid signals"""
        # Apply ticker blacklist
        original_count = len(self.universe)
        self.universe = filter_blacklisted_tickers(self.universe)
        filtered_count = original_count - len(self.universe)
        if filtered_count > 0:
            logger.info(
                f"🚫 Filtered {filtered_count} blacklisted tickers from universe"
            )

        # Add 365 days lookback for ATH/VCP calculation
        fetch_start_date = self.start_date - pd.Timedelta(days=365)

        logger.info(
            f"📥 Loading data from {fetch_start_date.date()} (buffer) to {self.end_date.date()}..."
        )
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

        logger.info(
            f"🛡️  Survivorship bias protection: PIT mask will determine eligibility quarterly"
        )

        # Use ThreadPoolExecutor for parallel data fetching
        # Reduced max_workers from 10 to 4 to avoid SQLite lock contention
        def fetch_ticker(ticker):
            try:
                df = self.cache.get_ohlcv(
                    ticker,
                    fetch_start_date.strftime("%Y-%m-%d"),
                    self.end_date.strftime("%Y-%m-%d"),
                    offline=self.offline_mode,
                )

                if df is not None and len(df) >= min_required_days:
                    # Basic preprocessing
                    df = df.reset_index()
                    # Fix: handle both 'Date' and 'date' index names
                    index_col = df.columns[0]
                    df.rename(columns={index_col: "date"}, inplace=True)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")

                    # NOTE: Pre-history filtering removed - PIT mask handles eligibility
                    # The PointInTimeUniverse will determine tradeable status quarterly
                    # based on data availability at each rebalance date

                    # Track incomplete data
                    partial = None
                    if len(df) < expected_days * 0.8:
                        partial = f"{ticker} ({len(df)}/{expected_days} days)"

                    return ticker, df, None, partial
                else:
                    reason = (
                        "None returned"
                        if df is None
                        else f"len={len(df)} < min={min_required_days}"
                    )
                    return ticker, None, reason, None
            except Exception as e:
                return ticker, None, f"Exception: {str(e)}", None

        logger.info(f"⚡ Fetching data for {len(self.universe)} tickers in parallel...")

        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_ticker = {
                executor.submit(fetch_ticker, t): t for t in self.universe
            }

            for i, future in enumerate(as_completed(future_to_ticker)):
                if (i + 1) % 100 == 0:
                    logger.info(f"   {i + 1}/{len(self.universe)}...")

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
            logger.info(
                f"ℹ️  {len(partial_data)} tickers with partial data (gaps in history)"
            )

        if len(all_data) == 0:
            raise ValueError(
                f"No data available for period {self.start_date.date()} to {self.end_date.date()}"
            )

        # Update universe to only include loaded tickers
        # DETERMINISM FIX: sort alphabetically so column order is always identical
        # regardless of thread completion order in ThreadPoolExecutor
        self.universe = sorted(all_data.keys())
        all_data = {t: all_data[t] for t in self.universe}

        # Build DataFrames
        close_data = {t: df["Close"] for t, df in all_data.items()}
        high_data = {t: df["High"] for t, df in all_data.items()}
        low_data = {t: df["Low"] for t, df in all_data.items()}
        volume_data = {t: df["Volume"] for t, df in all_data.items()}

        self.close = pd.DataFrame(close_data).ffill()
        self.high = pd.DataFrame(high_data).ffill()
        self.low = pd.DataFrame(low_data).ffill()
        self.volume = pd.DataFrame(volume_data).fillna(
            0
        )  # Volume should be 0 if missing

        # ============================================
        # MEMORY OPTIMIZATION: Convert to float32 (50% memory reduction)
        # ============================================

        # Convert all core DataFrames to float32 for 50% memory reduction
        self.close = self.close.astype(np.float32)
        self.high = self.high.astype(np.float32)
        self.low = self.low.astype(np.float32)
        self.volume = self.volume.astype(np.float32)

        # Log memory usage for core DataFrames
        core_mem_mb = (
            self.close.memory_usage(deep=True).sum()
            + self.high.memory_usage(deep=True).sum()
            + self.low.memory_usage(deep=True).sum()
            + self.volume.memory_usage(deep=True).sum()
        ) / (1024**2)
        logger.info(
            f"Memory: {core_mem_mb:.1f} MB for {len(self.close.columns)} tickers (core DataFrames)"
        )
        # ============================================

        # ============================================
        # POINT-IN-TIME UNIVERSE: Survivorship bias protection
        # ============================================
        if self.use_pit_universe:
            from src.data.pit_universe import PointInTimeUniverse

            logger.info(
                "🛡️  Building Point-in-Time tradeable mask (survivorship bias protection)..."
            )
            pit = PointInTimeUniverse()
            self.tradeable_mask = pit.build_tradeable_mask(
                self.close.index,
                list(self.close.columns),
                close_df=self.close,  # enables data-availability mask for non-S&P tickers
            )

            # NaN out price data for dates where ticker was NOT in the index.
            # This prevents:
            #   1. Indicators (SMA, RS) from computing on pre-IPO/post-delist phantom data
            #   2. ffill() from propagating the last price forever after delisting
            # We apply AFTER ffill so legitimate intra-membership gaps are filled,
            # but pre-membership and post-membership data is removed.
            non_tradeable = ~self.tradeable_mask
            nan32 = np.float32(np.nan)
            self.close[non_tradeable] = nan32
            self.high[non_tradeable] = nan32
            self.low[non_tradeable] = nan32
            self.volume[non_tradeable] = np.float32(0)  # 0 volume, not NaN

            masked_out_pct = (
                non_tradeable.sum().sum()
                / (self.tradeable_mask.shape[0] * self.tradeable_mask.shape[1])
                * 100
            )
            logger.info(
                f"   🛡️  Masked out {non_tradeable.sum().sum():,} cells ({masked_out_pct:.1f}%) "
                f"as non-tradeable (pre-IPO, post-delist, not in S&P 500)"
            )
        # ============================================

        # Initialize precomputed metrics from cache
        sma20_data = {}
        sma50_data = {}
        adr_pct_data = {}

        # Check how many tickers have precomputed data
        cache_available_count = 0

        for t, df in all_data.items():
            if "sma20" in df.columns and not df["sma20"].isna().all():
                sma20_data[t] = df["sma20"]
                cache_available_count += 1
            if "sma50" in df.columns and not df["sma50"].isna().all():
                sma50_data[t] = df["sma50"]
            if "adr_pct_20" in df.columns and not df["adr_pct_20"].isna().all():
                adr_pct_data[t] = df["adr_pct_20"]

        # Build SMAs from precomputed data
        self.sma_20 = (
            pd.DataFrame(sma20_data)
            if sma20_data
            else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        )
        self.sma_50 = (
            pd.DataFrame(sma50_data)
            if sma50_data
            else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        )
        self.adr_pct = (
            pd.DataFrame(adr_pct_data)
            if adr_pct_data
            else pd.DataFrame(0, index=self.close.index, columns=self.close.columns)
        )

        # ALIGNMENT FIX: Ensure all have same shape as Close to prevent ValueError
        self.sma_20 = self.sma_20.reindex(
            index=self.close.index, columns=self.close.columns
        )
        self.sma_50 = self.sma_50.reindex(
            index=self.close.index, columns=self.close.columns
        )
        self.adr_pct = self.adr_pct.reindex(
            index=self.close.index, columns=self.close.columns
        )

        # Log cache utilization
        if cache_available_count > 0:
            logger.info(
                f"   ✅ Using precomputed metrics for {cache_available_count}/{len(all_data)} tickers from SQLite cache"
            )
        else:
            logger.warning(
                "   ⚠️ No precomputed metrics found in cache, will calculate on the fly"
            )

        # Extract context columns (ADR, RVOL, trend, etc.)
        # Calculate context metrics on the fly if missing (crucial fix for missing cache data)
        self.avg_volume_20 = pd.DataFrame(
            index=self.close.index, columns=self.close.columns
        )
        self.trend_aligned = pd.DataFrame(
            index=self.close.index, columns=self.close.columns
        )
        self.dollar_volume = pd.DataFrame(
            index=self.close.index, columns=self.close.columns
        )

        for t, df in all_data.items():
            # ADR already loaded from cache if available, calculate if missing
            if t not in adr_pct_data:
                if "adr_pct_14" in df.columns:
                    self.adr_pct[t] = df["adr_pct_14"]
                else:
                    high_low_pct = ((df["High"] - df["Low"]) / df["Low"]) * 100
                    self.adr_pct[t] = high_low_pct.rolling(20).mean()

            # 2. Avg Volume (20 days)
            if "avg_volume_20" in df.columns:
                self.avg_volume_20[t] = df["avg_volume_20"]
            else:
                self.avg_volume_20[t] = df["Volume"].rolling(20).mean()

            # 3. Dollar Volume
            if "dollar_volume" in df.columns:
                self.dollar_volume[t] = df["dollar_volume"]
            else:
                self.dollar_volume[t] = df["Close"] * df["Volume"]

            # 4. Trend Alignment (Simple: Close > SMA50 > SMA200)
            if "trend_aligned" in df.columns:
                self.trend_aligned[t] = df["trend_aligned"]
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
        cache_hit_rate = (self.sma_20 != 0).sum().sum() / (
            self.sma_20.shape[0] * self.sma_20.shape[1]
        )

        if cache_hit_rate < 0.1:
            logger.info(
                "   ⚠️ Precomputed metrics not available, calculating on the fly..."
            )
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
            daily_range_pct = (self.high - self.low) / self.close * 100
            self.adr_pct = daily_range_pct.rolling(20, min_periods=1).mean()
            logger.info(
                f"   ✅ ADR calculated - Mean: {self.adr_pct.mean().mean():.2f}%, Max: {self.adr_pct.max().max():.2f}%"
            )

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

        # 3. Consolidation days (días dentro de Bollinger Bands) - CONVERGENCE FIX: Match THOR logic
        bb_period = 20
        bb_std = 2
        sma = self.close.rolling(bb_period).mean()
        std = self.close.rolling(bb_period).std()
        bb_upper = sma + (std * bb_std)
        bb_lower = sma - (std * bb_std)

        inside_bb = (self.close >= bb_lower) & (self.close <= bb_upper)
        # Contar días dentro de BB (no consecutivos, es suma simple)
        self.consolidation_days = inside_bb.rolling(20).sum().fillna(0)

        # Also calculate consolidation_range for consistency with THOR
        high_20 = self.high.rolling(20).max()
        low_20 = self.low.rolling(20).min()
        self.consolidation_range = ((high_20 - low_20) / low_20 * 100).fillna(0)

        # Clean up to save memory
        import gc

        del bb_upper, bb_lower, sma, std, inside_bb, high_20, low_20
        gc.collect()

        # 3. Market Regime Data (SPY & VIX)
        try:
            logger.info("   Loading SPY and VIX data for Market Regime...")

            # Use centralized loader
            spy_data, vix_data = load_spy_vix_data(
                start_date=(self.start_date - pd.Timedelta(days=365)).strftime(
                    "%Y-%m-%d"
                ),
                end_date=self.end_date.strftime("%Y-%m-%d"),
                cache=self.cache,
            )

            # Assign to internal variables
            if spy_data is not None and not spy_data.empty:
                # Reindex SPY data to match close index
                self.spy_close = spy_data["close"].reindex(self.close.index).ffill()

                # We need the full dataframe for the classifier (High/Low/Close)
                # Reindex all columns
                spy_aligned = spy_data.reindex(self.close.index).ffill()
            else:
                self.spy_close = pd.Series(0, index=self.close.index)
                spy_aligned = pd.DataFrame(
                    {
                        "close": self.spy_close,
                        "high": self.spy_close,
                        "low": self.spy_close,
                    }
                )

            if vix_data is not None and not vix_data.empty:
                self.vix_close = vix_data["close"].reindex(self.close.index).ffill()
                vix_aligned = vix_data.reindex(self.close.index).ffill()
            else:
                self.vix_close = pd.Series(0, index=self.close.index)
                vix_aligned = pd.DataFrame({"close": self.vix_close})

            # Initialize classifier
            self.market_regime_classifier = MarketRegimeClassifier(
                spy_data=spy_aligned, vix_data=vix_aligned
            )

            # Calculate Indicators for SPY (using classifier logic internally)
            # But kept here for legacy access if needed
            self.spy_ema20 = self.spy_close.ewm(span=20, adjust=False).mean()
            self.spy_sma200 = self.spy_close.rolling(window=200).mean()
            self.spy_sma50 = self.spy_close.rolling(window=50).mean()

            # Calculate Market Regime
            self.market_is_bullish = (self.spy_close > self.spy_sma200) & (
                self.vix_close < 20
            )
            self.market_is_safe = (self.spy_close > self.spy_ema20) & (
                self.vix_close < 20
            )

            logger.info(f"   ✅ Market Data Loaded & Aligned")

        except Exception as e:
            logger.warning(f"⚠️ Failed to load market data (SPY/VIX): {e}")
            import traceback

            logger.warning(traceback.format_exc())
            # Initialize with default safe values
            self.market_is_safe = pd.Series(True, index=self.close.index)
            self.spy_close = pd.Series(0, index=self.close.index)
            self.vix_close = pd.Series(0, index=self.close.index)
            # CRITICAL FIX: Initialize spy_sma50 to prevent hasattr() failures
            self.spy_sma50 = pd.Series(np.nan, index=self.close.index)
            logger.warning(
                "   ⚠️  spy_sma50 initialized as NaN - SPY > SMA50 filter will block all trades"
            )

        actual_start = self.close.index.min().date()
        actual_end = self.close.index.max().date()

        logger.info(f"✅ Loaded: {len(self.close.columns)} tickers")

        if len(failed) > 0:
            logger.info(f"🛡️  Filtered out {len(failed)} tickers (insufficient data)")

        logger.info(
            f"   Date range: {actual_start} to {actual_end} ({len(self.close)} days)"
        )

        if actual_start > self.start_date.date() or actual_end < self.end_date.date():
            logger.warning(
                f"⚠️  Actual range differs from requested: {self.start_date.date()} to {self.end_date.date()}"
            )

        # TRUNCATE data to requested date range (BUG FIX)
        # This ensures backtest runs exactly from start_date to end_date
        if actual_start < self.start_date.date():
            logger.info(
                f"   🔧 Truncating data to start_date: {self.start_date.date()}"
            )
            self.close = self.close.loc[self.start_date :]
            self.high = (
                self.high.loc[self.start_date :]
                if hasattr(self, "high") and self.high is not None
                else None
            )
            self.low = (
                self.low.loc[self.start_date :]
                if hasattr(self, "low") and self.low is not None
                else None
            )
            self.open = (
                self.open.loc[self.start_date :]
                if hasattr(self, "open") and self.open is not None
                else None
            )
            self.volume = (
                self.volume.loc[self.start_date :]
                if hasattr(self, "volume") and self.volume is not None
                else None
            )
            # Truncate indicators
            for attr in [
                "sma_20",
                "sma_50",
                "sma_200",
                "ema_8",
                "ema_21",
                "adr",
                "adr_pct",
                "avg_volume_20",
                "dollar_volume",
                "rolling_dollar_vol_20",
                "rvol",
                "dist_sma20_pct",
                "consolidation_days",
                "high_20",
                "low_20",
            ]:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    df = getattr(self, attr)
                    if isinstance(df, pd.DataFrame):
                        setattr(self, attr, df.loc[self.start_date :])

        # ============================================
        # MEMORY OPTIMIZATION: Convert remaining DataFrames to float32
        # ============================================
        if hasattr(self, "sma_20") and isinstance(self.sma_20, pd.DataFrame):
            self.sma_20 = self.sma_20.astype(np.float32)
        if hasattr(self, "sma_50") and isinstance(self.sma_50, pd.DataFrame):
            self.sma_50 = self.sma_50.astype(np.float32)
        if hasattr(self, "adr_pct") and isinstance(self.adr_pct, pd.DataFrame):
            self.adr_pct = self.adr_pct.astype(np.float32)
        if hasattr(self, "avg_volume_20") and isinstance(
            self.avg_volume_20, pd.DataFrame
        ):
            self.avg_volume_20 = self.avg_volume_20.astype(np.float32)
        if hasattr(self, "dollar_volume") and isinstance(
            self.dollar_volume, pd.DataFrame
        ):
            self.dollar_volume = self.dollar_volume.astype(np.float32)
        if hasattr(self, "ema_8") and isinstance(self.ema_8, pd.DataFrame):
            self.ema_8 = self.ema_8.astype(np.float32)
        if hasattr(self, "ema_21") and isinstance(self.ema_21, pd.DataFrame):
            self.ema_21 = self.ema_21.astype(np.float32)
        if hasattr(self, "dist_sma20_pct") and isinstance(
            self.dist_sma20_pct, pd.DataFrame
        ):
            self.dist_sma20_pct = self.dist_sma20_pct.astype(np.float32)
        if hasattr(self, "rvol") and isinstance(self.rvol, pd.DataFrame):
            self.rvol = self.rvol.astype(np.float32)
        if hasattr(self, "consolidation_days") and isinstance(
            self.consolidation_days, pd.DataFrame
        ):
            self.consolidation_days = self.consolidation_days.astype(np.float32)
        if hasattr(self, "spy_close") and isinstance(self.spy_close, pd.Series):
            self.spy_close = self.spy_close.astype(np.float32)
        if hasattr(self, "vix_close") and isinstance(self.vix_close, pd.Series):
            self.vix_close = self.vix_close.astype(np.float32)

        # Log total memory usage
        total_mem_mb = 0
        for attr in [
            "close",
            "high",
            "low",
            "volume",
            "sma_20",
            "sma_50",
            "adr_pct",
            "avg_volume_20",
            "dollar_volume",
            "ema_8",
            "ema_21",
            "dist_sma20_pct",
            "rvol",
            "consolidation_days",
        ]:
            if hasattr(self, attr):
                df = getattr(self, attr)
                if isinstance(df, pd.DataFrame):
                    total_mem_mb += df.memory_usage(deep=True).sum() / (1024**2)

        logger.info(f"Memory: ~{total_mem_mb:.1f} MB total after float32 conversion")
        # ============================================

        return self.close

    def _build_trade_dict(
        self,
        ticker,
        pos,
        exit_date,
        exit_price,
        pnl,
        exit_phase,
        hit_target=False,
        was_stopped_out=True,
        r_multiple=0.0,
        outcome_category="",
        hold_time_days=0,
    ):
        """
        Helper function to build trade dictionary with all fields.
        OPTIMIZATION: Avoids code duplication across exit scenarios.
        """
        shares = pos["shares"]
        risk_per_share = pos.get("risk_per_share", 1.0)

        return {
            "ticker": ticker,
            "entry_date": pos["entry_date"],
            "exit_date": exit_date,
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "shares": shares,
            "pnl": pnl,
            "exit_phase": exit_phase,
            "entry_signal": pos.get("entry_signal_type", "UNKNOWN"),
            "initial_shares": pos.get("original_shares", shares),
            "R_inicial": pos.get("adjusted_risk_dollars", 0),
            "adr_valor": pos["entry_price"] * (pos.get("context_adr", 0) / 100.0),
            "reason": exit_phase,
            "r_multiple": r_multiple
            if r_multiple > 0
            else pnl / (shares * risk_per_share)
            if risk_per_share > 0
            else 0,
            "outcome_category": outcome_category
            or (
                "BIG_WIN"
                if pnl > shares * 3 * risk_per_share
                else (
                    "WIN"
                    if pnl > 0
                    else (
                        "SMALL_LOSS"
                        if pnl > -shares * 0.5 * risk_per_share
                        else "BIG_LOSS"
                    )
                )
            ),
            "was_stopped_out": was_stopped_out,
            "hit_target": hit_target,
            "hold_time_category": (
                "SCALP"
                if hold_time_days < 3
                else (
                    "SWING"
                    if hold_time_days < 10
                    else ("POSITION" if hold_time_days < 30 else "LONG")
                )
            ),
            "context_adr": pos.get("context_adr", 0),
            "context_rvol": pos.get("context_rvol", 0),
            "context_trend": pos.get("context_trend", "N/A"),
            "context_vol": pos.get("context_vol", 0),
            "context_dollar_vol": pos.get("context_dollar_vol", 0),
            "dist_sma20_pct": pos.get("dist_sma20_pct", 0),
            "consolidation_days": pos.get("consolidation_days", 0),
            "sector": pos.get("sector", "UNKNOWN"),
            "sector_strength": pos.get("sector_strength", 0),
            "time_since_earnings": pos.get("time_since_earnings", -1),
            "spx_vs_voltrig": pos.get("spx_vs_voltrig", False),
            "spy_at_entry": pos.get("spy_at_entry", 0.0),
            "vix_at_entry": pos.get("vix_at_entry", 0.0),
            "spy_ema20_at_entry": pos.get("spy_ema20_at_entry", 0.0),
            "base_risk_dollars": pos.get("base_risk_dollars", 0),
            "adjusted_risk_dollars": pos.get("adjusted_risk_dollars", 0),
            "risk_reduction_factor": pos.get("risk_reduction_factor", 1.0),
            "size_multipliers_applied": pos.get("size_multipliers_applied", ""),
            "rvol_classification": pos.get("rvol_classification", "UNKNOWN"),
            "price_vs_sma20": pos.get("price_vs_sma20", 0),
            "price_vs_sma50": pos.get("price_vs_sma50", 0),
            "volume_at_entry": pos.get("volume_at_entry", 0),
            "avg_volume_20d": pos.get("avg_volume_20d", 0),
            "atr_at_entry": pos.get("atr_at_entry", 0),
            "atr_pct_price": pos.get("atr_pct_price", 0),
            "volatility_regime": pos.get("volatility_regime", "UNKNOWN"),
            "consolidation_quality": pos.get("consolidation_quality", "B"),
            "is_vcp_pattern": pos.get("is_vcp_pattern", False),
            "days_to_next_earnings": pos.get("days_to_next_earnings", -1),
            "earnings_risk_level": pos.get("earnings_risk_level", "UNKNOWN"),
            "vix_regime": pos.get("vix_regime", "UNKNOWN"),
            "spy_above_ema20": pos.get("spy_above_ema20", False),
            "entry_score": pos.get("entry_score", 0.5),
        }

    def simulate_with_partial_exits(
        self,
        entries: pd.DataFrame,
        close: pd.DataFrame,
        atr: pd.DataFrame,
        avwap: pd.DataFrame,
        signal_types: pd.DataFrame = None,
        numba_arrays: Dict = None,
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Simulación acelerada con Numba.
        Reemplaza la lógica lenta basada en loops por código máquina compilado JIT.

        Args:
            numba_arrays: Dict opcional con arrays numpy pre-calculados para optimizar memoria
        """
        logger.info("⚡ Ejecutando simulación ultra-rápida (Numba Core)...")

        # 1. Preparar Arrays de Numpy (float64 para precisión)
        # MEMORY OPTIMIZATION: Use pre-calculated arrays if available
        # FIX: Keep as float32 to save 50% memory, Numba handles conversion internally
        if numba_arrays is not None:
            logger.info(
                "   🚀 Using pre-calculated NumPy arrays (memory optimized - float32)"
            )
            close_arr = numba_arrays["close"].astype(np.float32)
            high_arr = numba_arrays["high"].astype(np.float32)
            low_arr = numba_arrays["low"].astype(np.float32)
            # Open not in numba_arrays, use close as fallback
            open_arr = close_arr
            # NEW: Volume and RVOL from numba_arrays
            volume_arr = numba_arrays.get("volume", np.zeros_like(close_arr)).astype(
                np.float32
            )
            rvol_arr = numba_arrays.get("rvol", np.zeros_like(close_arr)).astype(
                np.float32
            )
            entry_score_arr = numba_arrays.get(
                "entry_score", np.ones_like(close_arr)
            ).astype(np.float32)
        else:
            # Fallback: Convert from DataFrames (legacy mode)
            logger.info("   🐌 Converting from DataFrames (legacy mode - float32)")
            close_arr = close.ffill().values.astype(np.float32)
            high_arr = (
                self.high.ffill().values.astype(np.float32)
                if hasattr(self, "high") and self.high is not None
                else close_arr
            )
            low_arr = (
                self.low.ffill().values.astype(np.float32)
                if hasattr(self, "low") and self.low is not None
                else close_arr
            )

            # NEW: Volume and RVOL from self attributes
            volume_arr = (
                self.volume.fillna(0).values.astype(np.float32)
                if hasattr(self, "volume") and self.volume is not None
                else np.zeros_like(close_arr)
            )
            rvol_arr = (
                self.rvol.fillna(0).values.astype(np.float32)
                if hasattr(self, "rvol") and self.rvol is not None
                else np.zeros_like(close_arr)
            )
            # Entry score array for trade quality prioritization
            entry_score_arr = np.ones_like(close_arr, dtype=np.float32)

            # Open es opcional pero recomendado para gaps
            if hasattr(self, "open"):
                open_arr = self.open.ffill().values.astype(np.float32)
            else:
                open_arr = close_arr  # Fallback si no hay open

        entries_arr = entries.fillna(False).values.astype(bool)
        atr_arr = atr.fillna(0).values.astype(np.float32)

        # NUEVO: Preparar arrays para lógica de runner exit adaptativa
        # Convertir indicadores a arrays de numpy para Numba
        # MEMORY OPTIMIZATION: Use pre-calculated arrays if available
        if numba_arrays is not None:
            sma20_arr = numba_arrays.get("sma_20", np.zeros_like(close_arr)).astype(
                np.float32
            )
            ema10_arr = numba_arrays.get("ema_10", np.zeros_like(close_arr)).astype(
                np.float32
            )
            ema8_arr = numba_arrays.get("ema_8", np.zeros_like(close_arr)).astype(
                np.float32
            )
            ema21_arr = numba_arrays.get("ema_21", np.zeros_like(close_arr)).astype(
                np.float32
            )
        else:
            # Fallback: Use DataFrames (legacy mode)
            sma20_arr = (
                self.sma_20.values.astype(np.float32)
                if hasattr(self, "sma_20") and self.sma_20 is not None
                else np.zeros_like(close_arr)
            )
            ema10_arr = (
                self.ema_10.values.astype(np.float32)
                if hasattr(self, "ema_10") and self.ema_10 is not None
                else np.zeros_like(close_arr)
            )
            ema8_arr = (
                self.ema_8.values.astype(np.float32)
                if hasattr(self, "ema_8") and self.ema_8 is not None
                else np.zeros_like(close_arr)
            )
            ema21_arr = (
                self.ema_21.values.astype(np.float32)
                if hasattr(self, "ema_21") and self.ema_21 is not None
                else np.zeros_like(close_arr)
            )

        adr_arr = (
            self.adr_pct.values.astype(np.float32)
            if hasattr(self, "adr_pct") and self.adr_pct is not None
            else np.zeros_like(close_arr)
        )

        # Arrays de mercado (SPY)
        spy_close_arr = (
            self.spy_close.values.astype(np.float32)
            if hasattr(self, "spy_close") and isinstance(self.spy_close, pd.Series)
            else np.zeros(close_arr.shape[0], dtype=np.float32)
        )
        spy_sma50_arr = (
            self.spy_sma50.values.astype(np.float32)
            if hasattr(self, "spy_sma50") and isinstance(self.spy_sma50, pd.Series)
            else np.zeros(close_arr.shape[0], dtype=np.float32)
        )

        # Validar dimensiones
        if close_arr.shape != entries_arr.shape:
            raise ValueError(
                f"Shape mismatch: Close {close_arr.shape} vs Entries {entries_arr.shape}"
            )

        # 2. Ejecutar Numba Core
        # Parámetros de riesgo
        # CRITICAL FIX: Convertir risk_dollars a risk_pct para compatibilidad con V6_PRO
        if (
            self.use_fixed_dollar_risk
            and hasattr(self, "risk_dollars")
            and self.risk_dollars > 0
        ):
            # Calcular risk_pct equivalente basado en capital inicial
            # risk_dollars = equity * risk_pct => risk_pct = risk_dollars / equity
            risk_pct_per_trade = self.risk_dollars / self.initial_capital
            logger.info(
                f"   💰 Numba Core usando FIXED DOLLAR RISK: ${self.risk_dollars} → risk_pct={risk_pct_per_trade:.4f}"
            )
        else:
            risk_pct_per_trade = self.risk_pct  # Ej: 0.01 (1%)
            logger.info(
                f"   💰 Numba Core usando DYNAMIC RISK: {risk_pct_per_trade * 100:.2f}%"
            )

        max_exposure_pct = self.max_exposure_pct  # Ej: 0.25 (25%)
        be_threshold_r = 1.0  # Mover a BE al 1R (si trailing stop activo)

        # NUEVO: Parámetros de salida parcial (optimizables)
        tp1_pct = getattr(self, "tp1_pct", 0.5)  # Default 50%
        tp2_pct = getattr(self, "tp2_pct", 0.3)  # Default 30%
        runner_pct = getattr(self, "runner_pct", 0.2)  # Default 20%
        # CRITICAL FIX: max_stop_pct se mantiene en decimal (0.03 = 3%) para consistencia
        max_stop_pct = getattr(self, "max_stop_pct", 0.03)  # Decimal: 0.03 = 3%

        # DEBUG: Log all critical parameters
        logger.info(f"🔧 NUMBA CORE PARAMETERS:")
        logger.info(f"   Initial Capital: ${self.initial_capital:,.2f}")
        logger.info(
            f"   Risk per Trade: ${self.risk_dollars if self.use_fixed_dollar_risk else (self.initial_capital * self.risk_pct):,.2f}"
        )
        logger.info(f"   Use Fixed Risk: {self.use_fixed_dollar_risk}")
        logger.info(f"   TP1/TP2 Targets: {self.tp1_r}R / {self.tp2_r}R")
        logger.info(
            f"   TP Distribution: {tp1_pct * 100:.0f}% / {tp2_pct * 100:.0f}% / {runner_pct * 100:.0f}%"
        )
        logger.info(
            f"   Max Stop %%: {max_stop_pct * 100:.1f}% (decimal: {max_stop_pct})"
        )
        logger.info(f"   Trailing Stop: {self.use_trailing_stop}")
        logger.info(f"   ATR Stop Mode: {self.use_atr_stop}")
        if self.use_atr_stop:
            logger.info(f"   ATR Stop Multiplier: {self.atr_stop_multiplier}x")
            logger.info(f"   ATR Trailing Multiplier: {self.atr_trailing_multiplier}x")
        logger.info(f"   Total Entries Signals: {entries_arr.sum()}")

        start_time = datetime.now()

        equity_curve_arr, trades_log = simulate_fast_core(
            close_arr=close_arr,
            high_arr=high_arr,
            low_arr=low_arr,
            open_arr=open_arr,
            volume_arr=volume_arr,
            entries_arr=entries_arr,
            atr_arr=atr_arr,
            sma20_arr=sma20_arr,
            ema10_arr=ema10_arr,
            ema8_arr=ema8_arr,
            ema21_arr=ema21_arr,
            adr_arr=adr_arr,
            rvol_arr=rvol_arr,
            entry_score_arr=entry_score_arr,
            spy_close_arr=spy_close_arr,
            spy_sma50_arr=spy_sma50_arr,
            initial_capital=self.initial_capital,
            tp1_r=self.tp1_r,
            tp2_r=self.tp2_r,
            tp1_pct=tp1_pct,
            tp2_pct=tp2_pct,
            runner_pct=runner_pct,
            risk_pct_per_trade=risk_pct_per_trade,
            max_exposure_pct=max_exposure_pct,
            be_threshold_r=be_threshold_r,
            use_trailing_stop=self.use_trailing_stop,
            max_stop_pct=max_stop_pct,
            risk_dollars=self.risk_dollars if self.use_fixed_dollar_risk else 0.0,
            use_fixed_dollar_risk=self.use_fixed_dollar_risk,
            use_atr_stop=self.use_atr_stop,
            atr_stop_multiplier=self.atr_stop_multiplier,
            atr_trailing_multiplier=self.atr_trailing_multiplier,
        )

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"🚀 Numba Simulation Time: {duration:.4f}s")

        # DEBUG: Reportar estadísticas de entradas y trades
        total_entries = entries_arr.sum()
        total_trades = len(trades_log)
        conversion_rate = (
            (total_trades / total_entries * 100) if total_entries > 0 else 0
        )

        logger.info(f"📊 Numba Core Results:")
        logger.info(f"   Entry signals found: {total_entries}")
        logger.info(f"   Trades executed: {total_trades}")
        logger.info(f"   Conversion rate: {conversion_rate:.1f}%")
        logger.info(f"   Final equity: ${equity_curve_arr[-1]:,.2f}")

        if total_entries > 0 and total_trades == 0:
            logger.error(
                f"   ❌ CRITICAL: {total_entries} entry signals but 0 trades executed!"
            )
            logger.error(
                f"   Check: max_stop_pct={max_stop_pct}, risk_dollars={self.risk_dollars}"
            )
            logger.error(
                f"   Common causes: Stop distance too small, insufficient cash, or position sizing bug"
            )
        elif conversion_rate < 5:
            logger.warning(
                f"   ⚠️ Low conversion rate ({conversion_rate:.1f}%) - Check parameters"
            )
            logger.warning(
                f"   May indicate: Restrictive filters, large stop distances, or insufficient capital"
            )

        # Show exit type distribution if we have trades
        if len(trades_log) > 0:
            exit_types = trades_log[:, 2]  # Column 2 is exit_type_code
            stop_count = np.sum(exit_types == 0)
            tp1_count = np.sum(exit_types == 1)
            tp2_count = np.sum(exit_types == 2)
            runner_count = np.sum(exit_types == 3)
            logger.info(
                f"   Exit distribution: STOP={stop_count}, TP1={tp1_count}, TP2={tp2_count}, RUNNER={runner_count}"
            )

        # 3. Reconstruir Objetos Pandas
        equity_curve = pd.Series(equity_curve_arr, index=close.index)

        if len(trades_log) > 0:
            # Columnas: [dia_salida, ticker_idx, tipo_salida, precio_salida, shares, pnl, dia_entrada, riesgo_inicial, rvol, adr, vol, entry_score, stop_loss, tp1_target, tp2_target]
            trades_df = pd.DataFrame(
                trades_log,
                columns=[
                    "day_idx",
                    "col_idx",
                    "exit_type_code",
                    "exit_price",
                    "shares",
                    "pnl",
                    "entry_day_idx",
                    "initial_risk",
                    "context_rvol",
                    "context_adr",
                    "context_volume",
                    "entry_score",
                    "stop_loss",
                    "tp1_target",
                    "tp2_target",
                ],
            )

            # Mapear índices a fechas y símbolos
            trades_df["exit_date"] = close.index[trades_df["day_idx"].astype(int)]

            # NUEVO: Mapear fecha de entrada real
            trades_df["entry_date"] = close.index[
                trades_df["entry_day_idx"].astype(int)
            ]

            trades_df["symbol"] = close.columns[trades_df["col_idx"].astype(int)]

            # Mapear códigos de salida
            exit_map = {0: "STOP", 1: "TP1", 2: "TP2", 3: "RUNNER"}
            trades_df["exit_phase"] = trades_df["exit_type_code"].map(exit_map)

            # Asignar riesgo monetario para cálculo de R
            trades_df["monetary_risk"] = trades_df["initial_risk"]
            trades_df["adjusted_risk_dollars"] = trades_df["initial_risk"]
            trades_df["base_risk_dollars"] = trades_df["initial_risk"]

            # Asignar Contexto para UI (Volumen y ADR)
            # NOTA: VectorBT espera context_vol en unidades (no millones), la UI lo formateará
            trades_df["context_vol"] = trades_df["context_volume"]

            # Recuperar datos de entrada (aproximados post-simulación para reporte)
            # Esto es un compromiso: Para velocidad extrema en Numba, no devolvemos el log completo de entrada
            # Lo reconstruimos aquí vectorizadamente si es necesario, o aceptamos info parcial.

            # Para el dashboard, necesitamos entry_price y entry_date.
            # Como Numba solo devuelve la salida, buscaremos la entrada correspondiente hacia atrás.
            # OPTIMIZACIÓN: Hacer esto vectorizado también sería ideal, pero por ahora lo haremos simple.

            # Enriquecer DataFrame
            trades_df["return_pct"] = (
                trades_df["pnl"] / (trades_df["shares"] * trades_df["exit_price"])
            ) * 100  # Aprox
            # Fix return pct calc: pnl / (shares * entry_price) -> entry = exit - (pnl/shares)
            trades_df["entry_price"] = trades_df["exit_price"] - (
                trades_df["pnl"] / trades_df["shares"]
            )

            # Ahora sí podemos calcular dollar volume usando entry_price
            trades_df["context_dollar_vol"] = (
                trades_df["context_volume"] * trades_df["entry_price"]
            )  # Aprox

            trades_df["return_pct"] = (
                trades_df["pnl"] / (trades_df["shares"] * trades_df["entry_price"])
            ) * 100

            # Rellenar columnas faltantes para compatibilidad con Dashboard
            trades_df["signal_type"] = "MOMENTUM"  # Genérico por ahora

            # Enriquecer con dist_sma20_pct para derive_tier2_filters.py
            if hasattr(self, "dist_sma20_pct") and isinstance(
                self.dist_sma20_pct, pd.DataFrame
            ):
                dist_vals = []
                for _, row in trades_df.iterrows():
                    try:
                        entry_date = row["entry_date"]
                        sym = row["symbol"]
                        if (
                            entry_date in self.dist_sma20_pct.index
                            and sym in self.dist_sma20_pct.columns
                        ):
                            dist_vals.append(
                                float(self.dist_sma20_pct.loc[entry_date, sym])
                            )
                        else:
                            dist_vals.append(np.nan)
                    except Exception:
                        dist_vals.append(np.nan)
                trades_df["dist_sma20_pct"] = dist_vals

            # ═══════════════════════════════════════════════════════════════
            # AGREGAR RS PERCENTILE Y POSITION SIZING DETAILS
            # ═══════════════════════════════════════════════════════════════

            # -- RS Percentile at Entry --
            if self.use_rs_percentile and hasattr(self, "close"):
                rs_percentile = self.calculate_rs_percentile(
                    lookback_days=self.rs_lookback_days
                )
                rs_vals = []
                for _, row in trades_df.iterrows():
                    try:
                        entry_date = row["entry_date"]
                        sym = row["symbol"]
                        if (
                            entry_date in rs_percentile.index
                            and sym in rs_percentile.columns
                        ):
                            rs_vals.append(float(rs_percentile.loc[entry_date, sym]))
                        else:
                            rs_vals.append(np.nan)
                    except Exception:
                        rs_vals.append(np.nan)
                trades_df["rs_percentile"] = rs_vals

            # ═══════════════════════════════════════════════════════════════
            # PATTERN INFO at Entry
            # ═══════════════════════════════════════════════════════════════
            if self.pattern_confidence_matrix is not None and len(trades_df) > 0:
                pattern_conf = self.pattern_confidence_matrix
                pattern_types = (
                    self.pattern_type_matrix
                    if self.pattern_type_matrix is not None
                    else None
                )

                pattern_confidences = []
                pattern_types_list = []

                for _, row in trades_df.iterrows():
                    try:
                        entry_date = row["entry_date"]
                        sym = row["symbol"]

                        if (
                            entry_date in pattern_conf.index
                            and sym in pattern_conf.columns
                        ):
                            conf = float(pattern_conf.loc[entry_date, sym])
                        else:
                            conf = 0.0

                        pattern_confidences.append(conf)

                        # Pattern type
                        if pattern_types is not None:
                            if (
                                entry_date in pattern_types.index
                                and sym in pattern_types.columns
                            ):
                                ptype = str(pattern_types.loc[entry_date, sym])
                            else:
                                ptype = "NONE"
                            pattern_types_list.append(ptype)
                        else:
                            pattern_types_list.append("NONE")

                    except Exception:
                        pattern_confidences.append(0.0)
                        pattern_types_list.append("NONE")

                trades_df["pattern_confidence"] = pattern_confidences
                trades_df["pattern_type"] = pattern_types_list

                # Calculate pattern_bonus applied (same logic as in entry_score)
                bonus_high = getattr(self, "pattern_bonus_high", 0.30)
                bonus_med = getattr(self, "pattern_bonus_med", 0.20)
                bonus_low = getattr(self, "pattern_bonus_low", 0.10)

                def calc_pattern_bonus(conf):
                    if conf >= 0.7:
                        return bonus_high
                    elif conf >= 0.5:
                        return bonus_med
                    elif conf >= 0.3:
                        return bonus_low
                    return 0.0

                trades_df["pattern_bonus"] = trades_df["pattern_confidence"].apply(
                    calc_pattern_bonus
                )

                logger.info(
                    f"   🎯 Pattern info added to trades: {len(trades_df)} trades"
                )
                logger.info(
                    f"      Trades with pattern (conf > 0): {(trades_df['pattern_confidence'] > 0).sum()}"
                )
                logger.info(
                    f"      Pattern distribution: {trades_df['pattern_type'].value_counts().head(5).to_dict()}"
                )

            # -- Position Sizing Details --
            # stop_distance = entry_price - stop_price
            trades_df["stop_distance"] = trades_df["initial_risk"] / trades_df["shares"]
            trades_df["stop_distance_pct"] = (
                trades_df["stop_distance"] / trades_df["entry_price"]
            ) * 100
            trades_df["risk_per_share"] = trades_df["stop_distance"]

            # -- VWAP Score Components (for Entry Quality analysis) --
            if hasattr(self, "close") and hasattr(self, "volume"):
                vwap_scores = []
                vol_scores = []
                ema_scores = []
                for _, row in trades_df.iterrows():
                    try:
                        entry_date = row["entry_date"]
                        sym = row["symbol"]
                        entry_price = row["entry_price"]
                        rvol = row["context_rvol"]

                        # Volume Score
                        vol_score = np.clip((rvol - 0.5) / 1.5, 0.0, 1.0)
                        vol_scores.append(vol_score)

                        # EMA10 Score (price > EMA10?)
                        ema_score = (
                            1.0
                            if hasattr(self, "ema_10")
                            and entry_date in self.ema_10.index
                            and sym in self.ema_10.columns
                            and entry_price > self.ema_10.loc[entry_date, sym]
                            else 0.0
                        )
                        ema_scores.append(ema_score)

                        # VWAP Score placeholder (requires MVWAP/AVWAP calculation)
                        vwap_scores.append(np.nan)
                    except Exception:
                        vwap_scores.append(np.nan)
                        vol_scores.append(np.nan)
                        ema_scores.append(np.nan)

                trades_df["score_volume"] = vol_scores
                trades_df["score_ema10"] = ema_scores

            # -- R-Multiple --
            trades_df["r_multiple"] = trades_df["pnl"] / trades_df["initial_risk"]

            # -- Win/Loss Category --
            trades_df["outcome"] = trades_df["pnl"].apply(
                lambda x: "WIN" if x > 0 else ("LOSS" if x < 0 else "BE")
            )

            # -- Big Win/Big Loss flags --
            trades_df["is_big_win"] = trades_df["r_multiple"] >= 2.0
            trades_df["is_big_loss"] = trades_df["r_multiple"] <= -1.0

        else:
            trades_df = pd.DataFrame(
                columns=[
                    "symbol",
                    "entry_date",
                    "exit_date",
                    "pnl",
                    "return_pct",
                    "exit_phase",
                ]
            )

        return equity_curve, trades_df

    def _calculate_earnings_mask(self) -> pd.DataFrame:
        """
        Calculate earnings danger zone mask.

        Returns a boolean DataFrame (same shape as self.close) where:
            True  = Safe to trade
            False = Within danger zone of an earnings report

        Danger zone = [event_date - earnings_days_bdays, event_date + earnings_cushion_bdays]
        Uses BUSINESS DAYS (not calendar days) so weekends don't consume the buffer.

        Fail-safe: if no data or errors, assumes safe (does not block trades).
        """
        pre_buffer_bdays = self.earnings_days  # trading days BEFORE earnings
        post_buffer_bdays = self.earnings_cushion  # trading days AFTER earnings

        # Start with all safe (no danger)
        danger_mask = pd.DataFrame(
            False, index=self.close.index, columns=self.close.columns
        )

        tickers_with_data = 0
        events_applied = 0

        for ticker in self.close.columns:
            try:
                earnings = self.cache.get_earnings_history(ticker)
                if earnings is None or earnings.empty:
                    continue

                tickers_with_data += 1
                dates = pd.to_datetime(earnings["report_date"])

                for event_date in dates:
                    # Business day offsets: skip weekends
                    start_danger = event_date - pd.offsets.BDay(pre_buffer_bdays)
                    end_danger = event_date + pd.offsets.BDay(post_buffer_bdays)

                    # Only apply if danger zone overlaps our backtest range
                    if (
                        start_danger <= self.close.index[-1]
                        and end_danger >= self.close.index[0]
                    ):
                        danger_mask.loc[start_danger:end_danger, ticker] = True
                        events_applied += 1

            except Exception as e:
                logger.debug(f"Could not load earnings for {ticker}: {e}")
                continue

        logger.info(
            f"   Earnings filter: {tickers_with_data}/{len(self.close.columns)} tickers with data"
        )
        logger.info(
            f"   Events applied: {events_applied} | "
            f"Buffer: {pre_buffer_bdays} bdays before, {post_buffer_bdays} bdays after"
        )
        total_blocked = danger_mask.sum().sum()
        logger.info(f"   Ticker-days in danger zone: {total_blocked}")

        # Invert: True = safe, False = danger
        return ~danger_mask

    def calculate_atr(self, period: int = 14) -> pd.DataFrame:
        """Calculate Average True Range vectorized - OPTIMIZED"""
        high_low = self.high - self.low
        high_close = np.abs(self.high - self.close.shift())
        low_close = np.abs(self.low - self.close.shift())

        # Fully vectorized - use np.maximum for element-wise max
        tr = np.maximum(high_low, np.maximum(high_close, low_close))

        # Rolling mean on the entire DataFrame at once
        atr = (
            pd.DataFrame(tr, index=self.high.index, columns=self.high.columns)
            .rolling(period)
            .mean()
        )

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
        logger.info(
            f"📈 Calculating RS Percentile (IBD-style, {lookback_days}d lookback)..."
        )

        # Calculate performance for each ticker
        performance = self.close.pct_change(lookback_days)

        # Calculate percentile rank across all tickers for each day
        # RS = percentile of performance vs all stocks that day
        rs_percentile = performance.rank(axis=1, pct=True) * 100

        logger.info(
            f"   ✅ RS Percentile calculated (mean: {rs_percentile.mean().mean():.1f})"
        )

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

        logger.info(
            f"   ✅ Extension calculated (mean: {extension.mean().mean():.2f}x ATR)"
        )

        return extension

    def run_backtest(self) -> Dict:
        """Execute backtest with partial exits"""
        logger.info("🎯 Starting advanced backtest with partial exits...")

        # Load data
        self.load_data()

        if len(self.close.columns) == 0:
            return self._empty_results()

        # Ensure all dataframes are aligned (identical columns and order)
        common_columns = self.close.columns
        self.high = self.high[common_columns]
        self.low = self.low[common_columns]
        self.volume = self.volume[common_columns]
        if hasattr(self, "adr_pct"):
            self.adr_pct = self.adr_pct[common_columns]
        if hasattr(self, "avg_volume_20"):
            self.avg_volume_20 = self.avg_volume_20[common_columns]

        # Calculate entry signals using built-in logic
        logger.info("🔍 Calculating entry signals...")

        # =====================================================================
        # BASELINE MODE: Use THOR-compatible logic when all filters are OFF
        # =====================================================================
        # Detect if we're in baseline mode (all advanced filters OFF)
        # OR if we are explicitly in CONVERGENCE mode (which forces THOR logic)
        is_baseline_mode = (
            not self.use_dynamic_thresholds
            and not self.use_adaptive_filtering
            and not self.require_spy_above_sma50
            and not self.use_market_regime_filter
            and not self.require_positive_rs
            and not self.use_rs_percentile
            and not self.use_sma50_atr_filter
        ) or self.mode == "convergence"

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
            dist_sma20_pct = (self.close - safe_sma20) / safe_sma20 * 100

            # Consolidation days (THOR: count days inside BB)
            bb_std = self.close.rolling(20).std()
            bb_upper = safe_sma20 + (bb_std * 2)
            bb_lower = safe_sma20 - (bb_std * 2)
            inside_bb = (self.close >= bb_lower) & (self.close <= bb_upper)
            consolidation_days = inside_bb.rolling(20).sum()

            # Consolidation range (THOR: max range / low * 100)
            consolidation_range = self.consolidation_range

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
                min_dollar_volume=5e6,
            )

            # Quality: dist_sma20 <= max_dist_sma20
            quality = dist_sma20_pct <= self.max_dist_sma20

            # Consolidation: BOTH range AND days (THOR logic)
            consolidation = (
                (consolidation_days >= self.min_consolidation_days)
                & (consolidation_range <= 15.0)  # THOR default max_consolidation_range
            )

            # Breakout signal (THOR: close > 20d high)
            breakout_signal = self.close > self.high.shift().rolling(20).max()

            # Combine: THOR baseline = liquidity & quality & consolidation & breakout
            entries = liquidity & quality & consolidation & breakout_signal

            logger.info(f"   📊 THOR-baseline entries: {entries.sum().sum()}")
            logger.info(f"      Liquidity passed: {liquidity.sum().sum()}")
            logger.info(f"      Quality passed: {quality.sum().sum()}")
            logger.info(f"      Consolidation passed: {consolidation.sum().sum()}")
            logger.info(f"      Breakout passed: {breakout_signal.sum().sum()}")

        else:
            # ADVANCED MODE: Use original Advanced logic with all filters
            # CRITICAL FIX: Apply liquidity filters upfront (like V6_PRO) for consistency
            safe_sma20 = self.sma_20.fillna(0)

            # Base entry: Close > SMA20 (signal generation only)
            # NOTE: All quality filters (RVOL, ADR, dist_sma20, consolidation)
            # are handled by the Adaptive Filter Engine to avoid double-filtering
            base_entry = self.close > safe_sma20

            # Add breakout requirement if signal_type='breakout'
            if self.signal_type == "breakout":
                breakout_signal = self.close > self.high.shift().rolling(20).max()
                entries = base_entry & breakout_signal
                logger.info(
                    f"   🎯 Using BREAKOUT signal (close > 20d high) for THOR convergence"
                )
            else:
                entries = base_entry
                logger.info(f"   🎯 Using TREND signal (close > SMA20)")

            logger.info(
                f"   📊 ADVANCED MODE entries (before Adaptive Filter): {entries.sum().sum()}"
            )
            logger.info(f"      Base entry passed: {base_entry.sum().sum()}")
            if self.signal_type == "breakout":
                logger.info(f"      Breakout passed: {breakout_signal.sum().sum()}")

        # Signal types: Mark all as BREAKOUT for now
        signal_types = pd.DataFrame(
            index=self.close.index, columns=self.close.columns, dtype=object
        )
        signal_types[entries] = "BREAKOUT"

        # =====================================================================
        # EARNINGS CALENDAR FILTER (applied before any mode-specific logic)
        # =====================================================================
        if self.use_earnings_calendar:
            logger.info(
                f"📅 Applying earnings calendar filter (buffer={self.earnings_days} days)..."
            )
            entries_before = entries.sum().sum()
            earnings_safe = self._calculate_earnings_mask()
            entries = entries & earnings_safe
            entries_after = entries.sum().sum()
            blocked = entries_before - entries_after
            logger.info(f"   ❌ Entries blocked by earnings proximity: {blocked}")
            logger.info(f"   ✅ Entries after earnings filter: {entries_after}")
            # Update signal_types to reflect removed entries
            signal_types[~entries] = None

        # =====================================================================
        # POINT-IN-TIME UNIVERSE FILTER (block trades on non-member dates)
        # =====================================================================
        if self.use_pit_universe and self.tradeable_mask is not None:
            entries_before = entries.sum().sum()
            # Reindex mask to match entries shape (handles column/index mismatches)
            pit_mask = self.tradeable_mask.reindex(
                index=entries.index, columns=entries.columns, fill_value=False
            )
            entries = entries & pit_mask
            entries_after = entries.sum().sum()
            blocked = entries_before - entries_after
            logger.info(
                f"🛡️  PIT Universe filter: blocked {blocked} entries on non-member dates "
                f"({entries_after} remaining)"
            )
            signal_types[~entries] = None

        # =====================================================================
        # PATTERN FILTER (optional - filter entries without pattern)
        # =====================================================================
        if self.use_pattern_filter and self.pattern_confidence_matrix is not None:
            entries_before = entries.sum().sum()

            # Build pattern mask from confidence matrix
            pattern_conf = self.pattern_confidence_matrix

            # Reindex to match entries
            pattern_conf_aligned = pattern_conf.reindex(
                index=entries.index, columns=entries.columns, fill_value=0.0
            )

            # Apply minimum confidence threshold
            pattern_mask = pattern_conf_aligned >= self.min_pattern_confidence

            # Apply filter
            entries = entries & pattern_mask

            entries_after = entries.sum().sum()
            blocked = entries_before - entries_after
            logger.info(
                f"🎯 Pattern filter: blocked {blocked} entries without pattern "
                f"(conf < {self.min_pattern_confidence}), {entries_after} remaining"
            )
            signal_types[~entries] = None

        # =====================================================================
        # BASELINE MODE: Use NUMBA CORE directly (same as Advanced mode)
        # =====================================================================
        # FIX: The old baseline mode used VectorBT from_signals with a broken
        # 3-phase approach (entry_price.ffill() + entries.cumsum() > 0) that
        # generated phantom trades. Now both modes use the Numba core which
        # has proper day-by-day position tracking.
        # =====================================================================
        if is_baseline_mode:
            logger.info(
                "   ⚡ BASELINE MODE: Using Numba Core (same engine as Advanced)"
            )

            # Calculate ATR for Numba core
            atr = self.calculate_atr(14)

            # AVWAP (not used by Numba core but required by function signature)
            typical_price = (self.high + self.low + self.close) / 3
            pv = typical_price * self.volume
            cum_pv = pv.cumsum()
            cum_vol = self.volume.cumsum()
            avwap = cum_pv / cum_vol

            # Run via Numba core (same path as Advanced mode)
            total_days = len(self.close)
            chunk_size_days = 500

            if total_days <= chunk_size_days:
                equity_curve, trades_df = self._run_single_backtest_chunk(
                    entries, atr, avwap, signal_types
                )
            else:
                n_chunks = int(np.ceil(total_days / chunk_size_days))
                logger.info(
                    f"📊 Multi-chunk mode: {total_days} days -> {n_chunks} chunks"
                )
                equity_curve, trades_df = self._run_multi_chunk_backtest(
                    entries, atr, avwap, signal_types, n_chunks
                )

            # Calculate metrics (same as Advanced mode)
            if len(equity_curve) == 0:
                return self._empty_results()

            total_return = (
                equity_curve.iloc[-1] - self.initial_capital
            ) / self.initial_capital
            returns = equity_curve.pct_change().dropna()
            sharpe = (
                returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
                if len(returns) > 0
                else 0
            )

            cum_max = equity_curve.cummax()
            drawdown = (equity_curve - cum_max) / cum_max
            max_dd = drawdown.min()

            unique_entries = entries.sum().sum()
            all_exits_count = len(trades_df)
            winners = len(trades_df[trades_df["pnl"] > 0]) if len(trades_df) > 0 else 0
            win_rate = winners / all_exits_count if all_exits_count > 0 else 0

            total_profit = (
                trades_df[trades_df["pnl"] > 0]["pnl"].sum()
                if len(trades_df) > 0
                else 0
            )
            total_loss = (
                abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
                if len(trades_df) > 0
                else 0
            )
            profit_factor = total_profit / total_loss if total_loss > 0 else 0

            logger.info(
                f"   📊 BASELINE trades: {int(unique_entries)} entries -> {all_exits_count} exits"
            )
            logger.info(
                f"   Return: {total_return * 100:.2f}%, Sharpe: {sharpe:.2f}, Max DD: {max_dd * 100:.2f}%"
            )

            return {
                "total_return": total_return,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "total_trades": int(unique_entries),
                "all_exits": int(all_exits_count),
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "equity_curve": equity_curve,
                "final_value": equity_curve.iloc[-1]
                if len(equity_curve) > 0
                else self.initial_capital,
                "trades": trades_df,
                "trades_df": trades_df,
            }

        # ═══════════════════════════════════════════════════════════════
        # ADVANCED MODE: Continue with manual simulation
        # ═══════════════════════════════════════════════════════════════
        if self.use_dynamic_thresholds and hasattr(self, "vix_close"):
            logger.info("📊 Aplicando umbrales dinámicos basados en VIX...")

            # Calcular SMA50 de SPY si no existe
            if not hasattr(self, "spy_sma50"):
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
                        base_min_consolidation_days=self.min_consolidation_days,
                    )
                    dynamic_thresholds.loc[date, "min_rvol"] = thresholds["min_rvol"]
                    dynamic_thresholds.loc[date, "min_adr"] = thresholds["min_adr"]
                    dynamic_thresholds.loc[date, "max_dist_sma20"] = thresholds[
                        "max_dist_sma20"
                    ]
                    dynamic_thresholds.loc[date, "max_stop_pct"] = thresholds[
                        "max_stop_pct"
                    ]
                except:
                    # Fallback to defaults if VIX data is missing
                    dynamic_thresholds.loc[date, "min_rvol"] = self.min_rvol
                    dynamic_thresholds.loc[date, "min_adr"] = self.min_adr
                    dynamic_thresholds.loc[date, "max_dist_sma20"] = self.max_dist_sma20
                    dynamic_thresholds.loc[date, "max_stop_pct"] = (
                        self.max_stop_pct * 100
                    )

            # Usar thresholds dinámicos en lugar de estáticos
            self.min_rvol_dynamic = dynamic_thresholds["min_rvol"]
            self.min_adr_dynamic = dynamic_thresholds["min_adr"]
            self.max_dist_sma20_dynamic = dynamic_thresholds["max_dist_sma20"]
            self.max_stop_pct_dynamic = dynamic_thresholds["max_stop_pct"] / 100.0

            # Sample dynamic thresholds for logging
            if len(dynamic_thresholds) > 0:
                sample_date = dynamic_thresholds.index[0]
                sample_vix = float(self.vix_close.loc[sample_date])
                logger.info(
                    f"   📊 Ejemplo ({sample_date.date()}): VIX={sample_vix:.1f}, "
                    f"min_rvol={dynamic_thresholds.loc[sample_date, 'min_rvol']:.1f}, "
                    f"min_adr={dynamic_thresholds.loc[sample_date, 'min_adr']:.1f}, "
                    f"max_dist={dynamic_thresholds.loc[sample_date, 'max_dist_sma20']:.1f}%"
                )
        else:
            # Use static thresholds
            self.min_rvol_dynamic = self.min_rvol
            self.min_adr_dynamic = self.min_adr
            self.max_dist_sma20_dynamic = self.max_dist_sma20
            self.max_stop_pct_dynamic = self.max_stop_pct

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
            logger.info(
                "🔧 Applying Adaptive Filter Engine (TIER 1-2-3) - OPTIMIZADO..."
            )

            # Initialize filter engine
            self.filter_engine = AdaptiveFilterEngine(
                use_dynamic=True, logger_obj=logger
            )

            total_entries_pre_filter = entries.sum().sum()
            self.rejection_stats_tier = {"TIER1": 0, "TIER2": 0, "TIER3": 0}
            rejected_details = []

            # ┌─────────────────────────────────────────────────────────────────┐
            # TIER 1: MARKET SAFETY FILTER (Vectorizado - 60x más rápido)
            # └─────────────────────────────────────────────────────────────────┘
            # FIX: Iterate over unique dates to prevent indexing errors
            for date in tqdm(
                entries.index.unique(),
                desc="   ⚡ Applying Adaptive Filter",
                unit="day",
            ):
                if date in self.vix_close.index and date in self.spy_close.index:
                    # Robust scalar extraction handling duplicates
                    vix_series = self.vix_close.loc[date]
                    vix_val = (
                        float(vix_series.iloc[0])
                        if isinstance(vix_series, pd.Series)
                        else float(vix_series)
                    )

                    spy_series = self.spy_close.loc[date]
                    spy_price = (
                        float(spy_series.iloc[0])
                        if isinstance(spy_series, pd.Series)
                        else float(spy_series)
                    )

                    # Calculate SPY SMA50 if needed
                    if not hasattr(self, "spy_sma50"):
                        self.spy_sma50 = self.spy_close.rolling(window=50).mean()

                    spy_sma50_res = self.spy_sma50.loc[date]
                    if isinstance(spy_sma50_res, pd.Series):
                        spy_sma50_val = (
                            float(spy_sma50_res.iloc[0])
                            if not pd.isna(spy_sma50_res.iloc[0])
                            else None
                        )
                    else:
                        spy_sma50_val = (
                            float(spy_sma50_res) if not pd.isna(spy_sma50_res) else None
                        )

                    spy_trend_strength = (
                        (spy_price - spy_sma50_val) / spy_sma50_val
                        if spy_sma50_val is not None and spy_sma50_val > 0
                        else 0
                    )

                    # TIER 1: Market Safety Filter (SPY > SMA50, VIX < 35)
                    # Get current entries for this date to count actual rejections
                    current_date_entries = entries.loc[date]
                    entries_before_count = current_date_entries.sum()

                    # Skip warm-up period if SMA50 is not available
                    if spy_sma50_val is None:
                        entries.loc[date, :] = False
                        # FIX: Only count actual entries, not all tickers
                        self.rejection_stats_tier["TIER1"] += int(entries_before_count)
                        if entries_before_count > 0:
                            rejected_details.append(
                                (
                                    date,
                                    "TIER1",
                                    "TIER1_WarmUp",
                                    "ALL",
                                    int(entries_before_count),
                                )
                            )
                        continue

                    should_trade = should_trade_long(
                        spy_price, spy_sma50_val, vix_val, self.max_vix_threshold
                    )
                    if not should_trade:
                        entries.loc[date, :] = False
                        # FIX: Only count actual entries, not all tickers
                        self.rejection_stats_tier["TIER1"] += int(entries_before_count)
                        if entries_before_count > 0:
                            rejected_details.append(
                                (
                                    date,
                                    "TIER1",
                                    "TIER1_MarketSafety",
                                    "ALL",
                                    int(entries_before_count),
                                )
                            )
                            logger.debug(
                                f"   🚫 {date.date()}: Market Safety Filter - Blocked {int(entries_before_count)} entries (SPY={spy_price:.2f}, SMA50={spy_sma50_val:.2f}, VIX={vix_val:.2f})"
                            )
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
                            avg_vol_arr = get_vals(
                                self.avg_volume_20, date, entries.columns
                            )

                            if hasattr(self, "adr_pct"):
                                adr_arr = get_vals(self.adr_pct, date, entries.columns)
                            else:
                                adr_arr = np.array([5.0] * len(entries.columns))

                            if hasattr(self, "dollar_volume"):
                                dollar_vol_arr = get_vals(
                                    self.dollar_volume, date, entries.columns
                                )
                            else:
                                dollar_vol_arr = price_arr * volume_arr

                            # Get VIX-based thresholds using validated params as base
                            thresholds = get_dynamic_thresholds(
                                vix_val,
                                base_min_rvol=self.min_rvol,
                                base_min_adr=self.min_adr,
                                base_max_dist_sma20=self.max_dist_sma20,
                                base_max_stop_pct=self.max_stop_pct,
                                base_min_dollar_volume=self.min_dollar_volume,
                                base_min_consolidation_days=self.min_consolidation_days,
                            )
                            rvol_threshold = thresholds["min_rvol"]
                            adr_threshold = thresholds["min_adr"]
                            dist_threshold = thresholds["max_dist_sma20"]
                            dollar_vol_threshold = thresholds["min_dollar_volume"]

                            # Safe casting and handling of NaN/None/Zero
                            try:
                                volume_arr = np.array(volume_arr, dtype=float)
                                avg_vol_arr = np.array(avg_vol_arr, dtype=float)
                                price_arr = np.array(price_arr, dtype=float)
                                sma20_arr = np.array(sma20_arr, dtype=float)
                                adr_arr = np.array(adr_arr, dtype=float)

                                # Handle cases where original data was invalid (force fail if data missing)
                                invalid_data_mask = (
                                    np.isnan(avg_vol_arr)
                                    | (avg_vol_arr <= 0)
                                    | np.isnan(sma20_arr)
                                    | (sma20_arr <= 0)
                                )

                                # Only process valid data
                                valid_mask = ~invalid_data_mask
                                avg_vol_safe = np.where(valid_mask, avg_vol_arr, 1.0)
                                sma20_safe = np.where(valid_mask, sma20_arr, 1.0)

                                # Calculate RVOL array (vectorized) - only for valid data
                                rvol_arr = np.zeros_like(volume_arr, dtype=float)
                                rvol_arr[valid_mask] = (
                                    volume_arr[valid_mask] / avg_vol_safe[valid_mask]
                                )

                                # Vectorized comparisons
                                tier2_fail_rvol = (
                                    rvol_arr < rvol_threshold
                                ) | invalid_data_mask
                                tier2_fail_adr = (adr_arr < adr_threshold) | np.isnan(
                                    adr_arr
                                )
                                tier2_fail_dist = (
                                    (price_arr - sma20_safe) / sma20_safe * 100
                                    > dist_threshold
                                ) | invalid_data_mask

                            except Exception as e_conv:
                                logger.warning(
                                    f"   ⚠️ Error converting data for TIER 2: {e_conv}"
                                )
                                # Fallback to prevent crash, assuming all fail if conversion fails
                                rvol_arr = np.zeros_like(volume_arr)
                                tier2_fail_rvol = np.ones_like(volume_arr, dtype=bool)
                                tier2_fail_adr = np.ones_like(volume_arr, dtype=bool)
                                tier2_fail_dist = np.ones_like(volume_arr, dtype=bool)

                            # TIER 2: Combine failures
                            tier2_fail_mask = (
                                tier2_fail_rvol | tier2_fail_adr | tier2_fail_dist
                            )

                            # FIX: Only apply filter to tickers with actual entries
                            current_date_entries = entries.loc[date].values
                            entries_idx = np.where(current_date_entries)[0]

                            if len(entries_idx) > 0:
                                # Only count failures for tickers that had entries
                                tier2_fail_entries_mask = tier2_fail_mask[entries_idx]
                                tier2_rejected_count = tier2_fail_entries_mask.sum()

                                if tier2_rejected_count > 0:
                                    self.rejection_stats_tier["TIER2"] += int(
                                        tier2_rejected_count
                                    )
                                    for idx in entries_idx[tier2_fail_entries_mask]:
                                        ticker = entries.columns[idx]
                                        if tier2_fail_rvol[idx]:
                                            reason = f"TIER2_LowRVOL_Regime{thresholds['regime_name']}_{rvol_arr[idx]:.1f}x"
                                        elif tier2_fail_adr[idx]:
                                            reason = f"TIER2_LowADR_Regime{thresholds['regime_name']}_{adr_arr[idx]:.1f}%"
                                        else:
                                            reason = f"TIER2_Overextended_Regime{thresholds['regime_name']}_{(price_arr[idx] - sma20_arr[idx]) / sma20_arr[idx] * 100:.1f}%"
                                        rejected_details.append(
                                            (date, "TIER2", reason, ticker, 1)
                                        )
                                    # Only block entries that were actually active
                                    entries.loc[
                                        date,
                                        entries.columns[
                                            tier2_fail_mask & current_date_entries
                                        ],
                                    ] = False

                        except Exception as e:
                            logger.warning(f"   ⚠️ Error applying TIER 2 filters: {e}")

                        # ┌─────────────────────────────────────────────────────────────────┐
                        # TIER 3: OPTIONAL FILTERS (Configurables - Vectorizado)
                        # └─────────────────────────────────────────────────────────────────┘
                        # Only process TIER 3 for entries that passed TIER 1 and TIER 2
                        if (
                            len(entries.columns) > 0
                        ):  # Only process if there are entries left
                            try:
                                # Get consolidation days and sector RS (vectorized if available)
                                # FIX: Use self.consolidation_days DataFrame instead of non-existent method
                                if (
                                    hasattr(self, "consolidation_days")
                                    and not self.consolidation_days.empty
                                    and date in self.consolidation_days.index
                                ):
                                    consolidation_arr = get_vals(
                                        self.consolidation_days, date, entries.columns
                                    ).astype(float)
                                else:
                                    consolidation_arr = np.array(
                                        [float(self.min_consolidation_days)]
                                        * len(entries.columns)
                                    )

                                # Sector RS - default to 0 if not available
                                sector_rs_arr = np.array([0.0] * len(entries.columns))

                                # Get regime for consolidation and sector requirements
                                thresholds = get_dynamic_thresholds(vix_val)
                                consolidation_threshold = thresholds.get(
                                    "min_consolidation_days",
                                    self.min_consolidation_days,
                                )
                                require_sector_strong = thresholds.get(
                                    "strict_sector", False
                                )

                                # Vectorized comparisons
                                tier3_fail_consol = (
                                    consolidation_arr < consolidation_threshold
                                )
                                tier3_fail_sector = require_sector_strong & (
                                    sector_rs_arr < 0
                                )
                                tier3_fail_mask = tier3_fail_consol | tier3_fail_sector

                                # FIX: Only apply filter to tickers with actual entries
                                current_date_entries_t3 = entries.loc[date].values
                                entries_idx_t3 = np.where(current_date_entries_t3)[0]

                                if len(entries_idx_t3) > 0:
                                    tier3_fail_entries_mask = tier3_fail_mask[
                                        entries_idx_t3
                                    ]
                                    tier3_rejected_count = tier3_fail_entries_mask.sum()

                                    if tier3_rejected_count > 0:
                                        self.rejection_stats_tier["TIER3"] += int(
                                            tier3_rejected_count
                                        )
                                        for idx in entries_idx_t3[
                                            tier3_fail_entries_mask
                                        ]:
                                            ticker = entries.columns[idx]
                                            if tier3_fail_consol[idx]:
                                                reason = f"TIER3_ShortConsolidation_{consolidation_arr[idx]}d_Req{consolidation_threshold}d"
                                            else:
                                                reason = "TIER3_WeakSector"
                                            rejected_details.append(
                                                (date, "TIER3", reason, ticker, 1)
                                            )
                                        entries.loc[
                                            date,
                                            entries.columns[
                                                tier3_fail_mask
                                                & current_date_entries_t3
                                            ],
                                        ] = False

                            except Exception as e:
                                logger.warning(
                                    f"   ⚠️ Error applying TIER 3 filters: {e}"
                                )

            # Log summary statistics
            total_entries_post_filter = entries.sum().sum()
            rejected_entries = total_entries_pre_filter - total_entries_post_filter

            logger.info(
                f"   📊 Entries antes de Adaptive Filter: {total_entries_pre_filter}"
            )
            logger.info(f"   ❌ Entries rechazadas por TIER:")
            logger.info(
                f"      TIER 1 (Market Safety): {self.rejection_stats_tier['TIER1']}"
            )
            logger.info(
                f"      TIER 2 (Dynamic Quality): {self.rejection_stats_tier['TIER2']}"
            )
            logger.info(
                f"      TIER 3 (Optional): {self.rejection_stats_tier['TIER3']}"
            )
            logger.info(f"   ✅ Entries finales: {total_entries_post_filter}")

            # Save rejection details for Streamlit dashboard
            if rejected_details:
                # Convert to DataFrame for display
                rejection_df = pd.DataFrame(
                    rejected_details,
                    columns=["date", "tier", "reason", "ticker", "count"],
                )
                self.rejection_details_df = rejection_df

                # Save to CSV for detailed analysis
                rejection_df.to_csv(
                    "outputs/backtests/adaptive_filter_rejections_detailed.csv",
                    index=False,
                )

            # Print summary
            print("\n" + "=" * 70)
            print("📊 ADAPTIVE FILTER ENGINE - RESUMEN (OPTIMIZADO)")
            print("=" * 70)
            print(
                f"  Total de Rechazos: {total_entries_pre_filter - total_entries_post_filter}"
            )
            print(f"  • TIER 1 (Market Safety): {self.rejection_stats_tier['TIER1']}")
            print(f"  • TIER 2 (Dynamic Quality): {self.rejection_stats_tier['TIER2']}")
            print(f"  TIER 3 (Optional): {self.rejection_stats_tier['TIER3']}")
            print("=" * 70)
        elif is_baseline_mode:
            # BASELINE MODE: Skip all additional filtering (already applied in entry logic)
            logger.info("   ⚡ Skipping additional filters (baseline mode)")
        else:
            # FALLBACK: Use legacy sequential filtering
            logger.info("⚠️ Using legacy sequential filtering")

            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTRO DE RIESGO 0: HARD FLOOR (Precio < SMA20)
            # ═══════════════════════════════════════════════════════════════
            logger.info(
                "🔍 Aplicando filtro HARD FLOOR: Precio >= SMA20 (Trend Alignment)..."
            )

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
            logger.info(
                f"🔍 Aplicando filtro de sobreextensión (dist_sma20_pct > threshold)..."
            )

            if self.use_dynamic_thresholds and hasattr(self, "max_dist_sma20_dynamic"):
                overextended_mask = pd.DataFrame(
                    False,
                    index=self.dist_sma20_pct.index,
                    columns=self.dist_sma20_pct.columns,
                )
                for date in self.dist_sma20_pct.index:
                    if date in self.max_dist_sma20_dynamic.index:
                        threshold = self.max_dist_sma20_dynamic.loc[date]
                        overextended_mask.loc[date] = (
                            self.dist_sma20_pct.loc[date] > threshold
                        )
            else:
                overextended_mask = self.dist_sma20_pct > self.max_dist_sma20

            total_entries_before = entries.sum().sum()
            rejected_entries = (entries & overextended_mask).sum().sum()
            entries = entries & ~overextended_mask

            total_entries_after = entries.sum().sum()

            logger.info(f"   📊 Entries antes del filtro: {total_entries_before}")
            logger.info(
                f"   ❌ Entries rechazadas (>7% sobre SMA20): {rejected_entries}"
            )
            logger.info(f"   ✅ Entries finales: {total_entries_after}")

            if rejected_entries > 0:
                rejection_pct = (
                    (rejected_entries / total_entries_before * 100)
                    if total_entries_before > 0
                    else 0
                )
                logger.info(f"   📉 Tasa de rechazo: {rejection_pct:.1f}%")

            # ═══════════════════════════════════════════════════════════════
            # 🛡️ FILTRO DE LIQUIDEZ: RVOL Mínimo, ADR Mínimo, Volumen Mínimo
            # ═══════════════════════════════════════════════════════════════
            if self.use_dynamic_thresholds and hasattr(self, "min_rvol_dynamic"):
                logger.info(
                    "🔍 Aplicando filtros de liquidez con UMBRALES DINÁMICOS..."
                )

                low_rvol_mask = pd.DataFrame(
                    False, index=self.rvol.index, columns=self.rvol.columns
                )
                low_adr_mask = pd.DataFrame(
                    False, index=self.adr_pct.index, columns=self.adr_pct.columns
                )

                for date in self.rvol.index:
                    if date in self.min_rvol_dynamic.index:
                        rvol_threshold = self.min_rvol_dynamic.loc[date]
                        adr_threshold = self.min_adr_dynamic.loc[date]
                        low_rvol_mask.loc[date] = self.rvol.loc[date] < rvol_threshold
                        low_adr_mask.loc[date] = self.adr_pct.loc[date] < adr_threshold
            else:
                logger.info(
                    f"🔍 Aplicando filtros de liquidez estáticos (RVOL≥{self.min_rvol}x, ADR≥{self.min_adr}%)..."
                )

                low_rvol_mask = self.rvol < self.min_rvol
                low_adr_mask = self.adr_pct < self.min_adr

            low_volume_mask = self.volume < self.min_volume
            low_dollar_volume_mask = self.dollar_volume < self.min_dollar_volume

            total_entries_pre_liquidity = entries.sum().sum()
            rejected_low_rvol = (entries & low_rvol_mask).sum().sum()
            rejected_low_adr = (entries & low_adr_mask).sum().sum()
            rejected_low_volume = (entries & low_volume_mask).sum().sum()
            rejected_low_dollar_volume = (entries & low_dollar_volume_mask).sum().sum()

            entries = (
                entries
                & ~low_rvol_mask
                & ~low_adr_mask
                & ~low_volume_mask
                & ~low_dollar_volume_mask
            )

            total_entries_post_liquidity = entries.sum().sum()

            logger.info(
                f"   📊 Entries antes de filtros de liquidez: {total_entries_pre_liquidity}"
            )
            logger.info(
                f"   ❌ Rechazadas por RVOL<{self.min_rvol}x: {rejected_low_rvol}"
            )
            logger.info(f"   ❌ Rechazadas por ADR<{self.min_adr}%: {rejected_low_adr}")
            logger.info(
                f"   ❌ Rechazadas por Vol<{self.min_volume / 1000:.0f}k: {rejected_low_volume}"
            )
            logger.info(
                f"   ❌ Rechazadas por $Vol<${self.min_dollar_volume / 1e6:.0f}M: {rejected_low_dollar_volume}"
            )
            logger.info(f"   ✅ Entries finales: {total_entries_post_liquidity}")

            # ═══════════════════════════════════════════════════════════════
            # 🌍 FILTRO DE RÉGIMEN DE MERCADO (Market Context)
            # ═══════════════════════════════════════════════════════════════
            if (
                self.use_market_regime_filter
                and self.market_regime_classifier is not None
            ):
                logger.info("🌍 Aplicando filtro de régimen de mercado...")

                market_stages = {}
                blocked_entries = 0
                total_entries_pre_regime = entries.sum().sum()

                blocked_mask = pd.DataFrame(
                    False, index=entries.index, columns=entries.columns
                )

                for date in entries.index:
                    context = self.market_regime_classifier.get_market_context(date)
                    market_stages[date] = context

                    should_block = False
                    if (
                        self.block_trades_in_stage4
                        and context["market_stage"] == "STAGE_4"
                    ):
                        should_block = True
                    elif (
                        self.block_trades_in_stage3
                        and context["market_stage"] == "STAGE_3"
                    ):
                        should_block = True

                    if should_block:
                        blocked_mask.loc[date, :] = True
                        blocked_entries += entries.loc[date, :].sum()

                    if self.adjust_risk_by_regime:
                        risk_mult = context["risk_multiplier"]
                        if not hasattr(self, "regime_risk_multipliers"):
                            self.regime_risk_multipliers = {}
                        self.regime_risk_multipliers[date] = risk_mult

                total_entries_post_regime = entries.sum().sum()

                logger.info(
                    f"   📊 Entries antes de filtro de régimen: {total_entries_pre_regime}"
                )
                logger.info(f"   ❌ Entries bloqueadas por régimen: {blocked_entries}")
                logger.info(f"   ✅ Entries finales: {total_entries_post_regime}")

                if self.adjust_risk_by_regime:
                    logger.info(f"   📊 Risk adjustment by regime: ENABLED")

                # Count stages
                stage_counts = {}
                for context in market_stages.values():
                    stage = context["market_stage"]
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
        self.voltrig_warning = (self.rvol >= self.rvol_warning) & (
            self.rvol < self.rvol_danger
        )
        self.voltrig_safe = self.rvol < self.rvol_warning

        # Contar entries por categoría
        danger_entries = (entries & self.voltrig_danger).sum().sum()
        warning_entries = (entries & self.voltrig_warning).sum().sum()
        safe_entries = (entries & self.voltrig_safe).sum().sum()

        logger.info(
            f"   ☔ Danger (RVOL>={self.rvol_danger}x): {danger_entries} entries → Size {int(self.rvol_danger_size * 100)}%"
        )
        logger.info(
            f"   ⚠️  Warning (RVOL>={self.rvol_warning}x): {warning_entries} entries → Size {int(self.rvol_warning_size * 100)}%"
        )
        logger.info(
            f"   ✅ Safe (RVOL<{self.rvol_warning}x): {safe_entries} entries → Size 100%"
        )

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

        logger.info(
            f"   🔥 High ADR (>{self.adr_high}%): {high_adr_entries} entries → Size 25%"
        )
        logger.info(
            f"   ⚠️  Med ADR (>{self.adr_med}%): {med_adr_entries} entries → Size 33%"
        )

        # ═══════════════════════════════════════════════════════════════
        # 📊 FILTRO 5: IBD-Style RS Percentile (Ranking vs Market)
        # ═══════════════════════════════════════════════════════════════
        if self.use_rs_percentile:
            logger.info(
                f"📊 Aplicando filtro RS Percentile (IBD-style, RS≥{self.min_rs_percentile})..."
            )

            # Calculate RS percentile (0-100)
            rs_percentile = self.calculate_rs_percentile(
                lookback_days=self.rs_lookback_days
            )

            # Filter: Only entries with RS >= threshold
            low_rs_mask = rs_percentile < self.min_rs_percentile

            total_entries_pre_rs = entries.sum().sum()
            entries = entries & ~low_rs_mask
            total_entries_post_rs = entries.sum().sum()

            rejected_low_rs = total_entries_pre_rs - total_entries_post_rs

            logger.info(
                f"   📊 Entries antes del filtro RS Percentile: {total_entries_pre_rs}"
            )
            logger.info(
                f"   ❌ Rechazadas por RS<{self.min_rs_percentile}: {rejected_low_rs}"
            )
            logger.info(f"   ✅ Entries finales: {total_entries_post_rs}")

        # ═══════════════════════════════════════════════════════════════
        # 📏 FILTRO 6: SMA50/ATR Extension (Avoid Overextended)
        # ═══════════════════════════════════════════════════════════════
        if self.use_sma50_atr_filter:
            logger.info(
                f"📏 Aplicando filtro SMA50/ATR Extension (max {self.max_sma50_atr_extension}x ATR)..."
            )

            # Calculate extension from SMA50 in terms of ATR
            sma50_atr_extension = self.calculate_sma50_atr_extension(
                atr_mult=self.max_sma50_atr_extension
            )

            # Filter: Only entries where extension < threshold
            overextended_mask = sma50_atr_extension > self.max_sma50_atr_extension

            total_entries_pre_extension = entries.sum().sum()
            entries = entries & ~overextended_mask
            total_entries_post_extension = entries.sum().sum()

            rejected_overextended = (
                total_entries_pre_extension - total_entries_post_extension
            )

            logger.info(
                f"   📊 Entries antes del filtro Extension: {total_entries_pre_extension}"
            )
            logger.info(
                f"   ❌ Rechazadas por extensión>{self.max_sma50_atr_extension}x ATR: {rejected_overextended}"
            )
            logger.info(f"   ✅ Entries finales: {total_entries_post_extension}")

        # ═══════════════════════════════════════════════════════════════

        # Calculate ATR
        atr = self.calculate_atr(14)

        # =====================================================================
        # MEMORY OPTIMIZATION: Chunking for multi-year backtests
        # =====================================================================
        # Auto-detect if we need chunking based on date range
        total_days = len(self.close)
        # MEMORY FIX: Reduced from 750 to 500 (~2 years) for better memory management
        # For 8+ year backtests, this prevents OOM kills by processing in smaller chunks
        chunk_size_days = 500  # ~2 years of trading data per chunk

        if total_days <= chunk_size_days:
            # SINGLE-CHUNK MODE: Small enough to run in one pass
            logger.info(
                f"📊 Single-chunk mode: {total_days} days (≤ {chunk_size_days})"
            )
            equity_curve, trades_df = self._run_single_backtest_chunk(
                entries, atr, avwap, signal_types
            )
        else:
            # MULTI-CHUNK MODE: Large dataset, process in chunks to save memory
            n_chunks = int(np.ceil(total_days / chunk_size_days))
            logger.info(
                f"📊 Multi-chunk mode: {total_days} days → {n_chunks} chunks of ~{chunk_size_days} days"
            )
            equity_curve, trades_df = self._run_multi_chunk_backtest(
                entries, atr, avwap, signal_types, n_chunks
            )

        # 🛡️ SAFETY CHECK: Verificar si hay resultados antes de calcular métricas
        if len(equity_curve) == 0:
            logger.error(
                "❌ CRITICAL: Empty equity curve - simulation failed completely"
            )
            raise ValueError(
                "Backtest simulation failed to generate equity curve. "
                "This usually indicates a data loading error or crash in the simulation engine. "
                "Check logs above for errors during data loading or simulation (e.g. no price data found for selected range)."
            )

        # Calculate metrics
        total_return = (
            equity_curve.iloc[-1] - self.initial_capital
        ) / self.initial_capital
        returns = equity_curve.pct_change().dropna()
        sharpe = (
            returns.mean() / (returns.std() + 1e-10) * np.sqrt(252)
            if len(returns) > 0
            else 0
        )

        cum_max = equity_curve.cummax()
        drawdown = (equity_curve - cum_max) / cum_max
        max_dd = drawdown.min()

        # Calculate MAR Ratio and Calmar Ratio
        days_trading = len(equity_curve)
        years_trading = days_trading / 252  # 252 trading days per year
        annualized_return = (
            (equity_curve.iloc[-1] / self.initial_capital) ** (1 / years_trading) - 1
            if years_trading > 0 and total_return > -1
            else 0
        )

        # MAR Ratio = Annualized Return / Max Drawdown
        # Calmar Ratio = Annualized Return / Absolute Max Drawdown
        mar_ratio = (
            annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0
        )
        calmar_ratio = (
            annualized_return / abs(max_dd) if max_dd < 0 and max_dd != -1 else 0
        )

        # DEBUG: Check entries count (optional - comment out if not needed)
        # logger.info(f"🔍 DEBUG entries shape: {entries.shape}")
        # logger.info(f"🔍 DEBUG entries.sum().sum(): {entries.sum().sum()}")
        # logger.info(f"🔍 DEBUG entries True count: {(entries == True).sum().sum()}")
        # logger.info(f"🔍 DEBUG entries dtypes: {entries.dtypes}")
        # logger.info(f"🔍 DEBUG entries any NaN: {entries.isna().sum().sum()}")

        # CONVERGENCE FIX: Count unique entries (not all partial exits)
        # Each entry generates 3 exits (TP1, TP2, Runner), so unique_entries = total_exits / 3
        all_exits_count = len(trades_df)
        unique_entries = entries.sum().sum()  # Count actual entry signals

        # For win rate and profit factor, use all exits (more statistically significant)
        winners = len(trades_df[trades_df["pnl"] > 0]) if len(trades_df) > 0 else 0
        win_rate = winners / all_exits_count if all_exits_count > 0 else 0

        # Calculate Profit Factor
        total_profit = (
            trades_df[trades_df["pnl"] > 0]["pnl"].sum() if len(trades_df) > 0 else 0
        )
        total_loss = (
            abs(trades_df[trades_df["pnl"] < 0]["pnl"].sum())
            if len(trades_df) > 0
            else 0
        )
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        results = {
            "total_return": total_return,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "annualized_return": annualized_return,
            "mar_ratio": mar_ratio,
            "calmar_ratio": calmar_ratio,
            "total_trades": int(unique_entries),  # For convergence with THOR
            "all_exits": int(all_exits_count),  # Total including partial exits
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "equity_curve": equity_curve,
            "trades": trades_df,
            "trades_df": trades_df,  # Add alias for compatibility
        }

        logger.info(f"✅ Backtest complete!")
        logger.info(f"   Return: {total_return * 100:.2f}%")
        logger.info(f"   Annualized Return: {annualized_return * 100:.2f}%")
        logger.info(f"   Sharpe: {sharpe:.2f}")
        logger.info(f"   Max DD: {max_dd * 100:.2f}%")
        logger.info(f"   MAR Ratio: {mar_ratio:.2f}")
        logger.info(f"   Calmar Ratio: {calmar_ratio:.2f}")
        logger.info(f"   Win Rate: {win_rate * 100:.1f}%")
        logger.info(
            f"   Trades: {int(unique_entries)} entries → {int(all_exits_count)} total exits (including partial)"
        )

        return results

    def get_position_size_by_regime(
        self, date: pd.Timestamp, base_risk_dollars: float
    ) -> float:
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
            "STAGE_1": 1.0,  # Bull market: 100% del riesgo base
            "STAGE_2": 0.75,  # Consolidation: 75% del riesgo base
            "STAGE_3": 0.25,  # Distribution: 25% del riesgo base
            "STAGE_4": 0.0,  # Bear market: NO operar
        }

        multiplier = position_multipliers.get(market_regime, 0.5)
        return base_risk_dollars * multiplier

    def _empty_results(self):
        # Create empty trades DataFrame with expected columns for compatibility
        empty_trades = pd.DataFrame(
            columns=[
                "symbol",
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "shares",
                "pnl",
                "return_pct",
                "exit_phase",
            ]
        )
        return {
            "total_return": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "equity_curve": pd.Series(),
            "trades": empty_trades,
            "trades_df": empty_trades,
        }

    def get_rejection_stats(self) -> Dict[str, int]:
        """
        Get combined rejection statistics from all filter sources.

        Returns:
            Dictionary with rejection reasons and counts (both aggregated and detailed)
        """
        combined_stats = {}

        # Add tier stats from vectorized filtering (aggregated)
        if hasattr(self, "rejection_stats_tier") and self.rejection_stats_tier:
            combined_stats.update(
                {
                    "TIER1_MarketSafety": self.rejection_stats_tier.get("TIER1", 0),
                    "TIER2_DynamicQuality": self.rejection_stats_tier.get("TIER2", 0),
                    "TIER3_Optional": self.rejection_stats_tier.get("TIER3", 0),
                }
            )

        # Add stats from AdaptiveFilterEngine (if used)
        if hasattr(self, "filter_engine") and self.filter_engine is not None:
            filter_stats = self.filter_engine.get_rejection_stats()
            if filter_stats:
                combined_stats.update(filter_stats)

        # Add detailed rejection reasons from rejection_details_df
        if (
            hasattr(self, "rejection_details_df")
            and self.rejection_details_df is not None
        ):
            if not self.rejection_details_df.empty:
                # Group by reason and sum counts
                reason_counts = self.rejection_details_df.groupby("reason")[
                    "count"
                ].sum()
                for reason, count in reason_counts.items():
                    combined_stats[reason] = int(count)

        return combined_stats

    def _run_single_backtest_chunk(
        self,
        entries: pd.DataFrame,
        atr: pd.DataFrame,
        avwap: pd.DataFrame,
        signal_types: pd.DataFrame,
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Execute backtest on a single chunk of data.
        MEMORY OPTIMIZED: Converts to NumPy arrays before simulation.

        Returns:
            Tuple of (equity_curve, trades_df)
        """
        logger.info("🔄 Running single-chunk backtest with Numba Core...")

        # Load pattern cache if enabled
        if (
            getattr(self, "use_pattern_filter", False)
            or getattr(self, "pattern_bonus_high", 0) > 0
        ):
            self._load_pattern_cache()

        # Prepare NumPy arrays (memory optimized)
        numba_arrays = prepare_numba_arrays(self)

        # Run simulation
        equity_curve, trades_df = self.simulate_with_partial_exits(
            entries=entries,
            close=self.close
            if hasattr(self, "close")
            else pd.DataFrame(numba_arrays["close"]),
            atr=atr,
            avwap=avwap,
            signal_types=signal_types,
            numba_arrays=numba_arrays,
        )

        # Cleanup arrays after simulation
        del numba_arrays
        gc.collect()

        return equity_curve, trades_df

    def _run_multi_chunk_backtest(
        self,
        entries: pd.DataFrame,
        atr: pd.DataFrame,
        avwap: pd.DataFrame,
        signal_types: pd.DataFrame,
        n_chunks: int,
    ) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Execute backtest in multiple chunks to avoid memory issues.
        MEMORY OPTIMIZED: Processes data in yearly chunks with state transfer.

        For multi-year backtests (5-10+ years), this prevents OOM kills by:
        1. Processing 1-2 years at a time
        2. Transferring final equity to next chunk as initial capital
        3. Force-closing positions at chunk boundaries (simplification)
        4. Releasing memory between chunks

        Args:
            entries: Full DataFrame of entry signals
            atr: Full DataFrame of ATR values
            avwap: Full DataFrame of AVWAP values
            signal_types: Full DataFrame of signal types
            n_chunks: Number of chunks to split data into

        Returns:
            Tuple of (combined_equity_curve, combined_trades_df)
        """
        logger.info(f"🔄 Running multi-chunk backtest: {n_chunks} chunks...")

        # Calculate chunk boundaries
        total_days = len(self.close)
        chunk_size = int(np.ceil(total_days / n_chunks))

        all_equity_curves = []
        all_trades = []
        current_capital = self.initial_capital

        # Store original DataFrames (we'll slice them per chunk)
        original_close = self.close.copy()
        original_high = self.high.copy() if hasattr(self, "high") else None
        original_low = self.low.copy() if hasattr(self, "low") else None
        original_volume = self.volume.copy() if hasattr(self, "volume") else None

        for chunk_idx in range(n_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, total_days)

            logger.info(
                f"   📦 Chunk {chunk_idx + 1}/{n_chunks}: days {start_idx}-{end_idx} "
                f"(capital: ${current_capital:,.0f})"
            )

            # Slice data for this chunk
            chunk_dates = original_close.index[start_idx:end_idx]

            # Temporarily replace engine DataFrames with chunk slices
            self.close = original_close.iloc[start_idx:end_idx]
            if original_high is not None:
                self.high = original_high.iloc[start_idx:end_idx]
            if original_low is not None:
                self.low = original_low.iloc[start_idx:end_idx]
            if original_volume is not None:
                self.volume = original_volume.iloc[start_idx:end_idx]

            # Slice entries and indicators
            chunk_entries = entries.iloc[start_idx:end_idx]
            chunk_atr = atr.iloc[start_idx:end_idx]
            chunk_avwap = avwap.iloc[start_idx:end_idx]
            chunk_signal_types = (
                signal_types.iloc[start_idx:end_idx]
                if signal_types is not None
                else None
            )

            # Slice all other indicators that may be used
            indicator_attrs = [
                "sma_20",
                "sma_50",
                "adr_pct",
                "rvol",
                "avg_volume_20",
                "ema_8",
                "ema_21",
                "ema_10",
                "dist_sma20_pct",
                "dollar_volume",
                "consolidation_days",
            ]
            original_indicators = {}
            for attr in indicator_attrs:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    original_df = getattr(self, attr)
                    if (
                        isinstance(original_df, pd.DataFrame)
                        and len(original_df) == total_days
                    ):
                        original_indicators[attr] = original_df
                        setattr(self, attr, original_df.iloc[start_idx:end_idx])

            # Slice market data (SPY/VIX) - these are Series, not DataFrames
            market_attrs = [
                "spy_close",
                "vix_close",
                "spy_sma50",
                "spy_ema20",
                "spy_sma200",
            ]
            original_market = {}
            for attr in market_attrs:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    original_series = getattr(self, attr)
                    if (
                        isinstance(original_series, pd.Series)
                        and len(original_series) >= end_idx
                    ):
                        original_market[attr] = original_series
                        setattr(self, attr, original_series.iloc[start_idx:end_idx])

            # Update initial capital for this chunk
            original_initial_capital = self.initial_capital
            self.initial_capital = current_capital

            # Run single chunk simulation
            try:
                chunk_equity, chunk_trades = self._run_single_backtest_chunk(
                    chunk_entries, chunk_atr, chunk_avwap, chunk_signal_types
                )

                # Store results
                all_equity_curves.append(chunk_equity)
                if len(chunk_trades) > 0:
                    all_trades.append(chunk_trades)

                # Update capital for next chunk (use final equity)
                if len(chunk_equity) > 0:
                    current_capital = chunk_equity.iloc[-1]
                    logger.info(
                        f"   ✅ Chunk {chunk_idx + 1} complete: "
                        f"{len(chunk_trades)} trades, final equity ${current_capital:,.0f}"
                    )

            except Exception as e:
                logger.error(f"   ❌ Chunk {chunk_idx + 1} failed: {e}")
                # Continue with current capital
                import traceback

                logger.error(traceback.format_exc())

            # Restore original initial capital
            self.initial_capital = original_initial_capital

            # Restore original indicators
            for attr, original_df in original_indicators.items():
                setattr(self, attr, original_df)

            # Restore original market data
            for attr, original_series in original_market.items():
                setattr(self, attr, original_series)

            # Force garbage collection between chunks
            gc.collect()

        # Restore original DataFrames
        self.close = original_close
        if original_high is not None:
            self.high = original_high
        if original_low is not None:
            self.low = original_low
        if original_volume is not None:
            self.volume = original_volume

        # Combine results
        if all_equity_curves:
            # Concatenate equity curves (they should have unique indices)
            combined_equity = pd.concat(all_equity_curves)
            # Handle any duplicate indices by keeping last value
            combined_equity = combined_equity[
                ~combined_equity.index.duplicated(keep="last")
            ]
        else:
            combined_equity = pd.Series(dtype=float)

        if all_trades:
            combined_trades = pd.concat(all_trades, ignore_index=True)
        else:
            # Ensure empty DataFrame has expected columns for compatibility
            combined_trades = pd.DataFrame(
                columns=[
                    "symbol",
                    "entry_date",
                    "exit_date",
                    "entry_price",
                    "exit_price",
                    "shares",
                    "pnl",
                    "return_pct",
                    "exit_phase",
                    "exit_type_code",
                    "day_idx",
                    "entry_day_idx",
                    "col_idx",
                    "entry_signal",
                    "context_adr",
                    "context_rvol",
                    "context_volume",
                    "context_sma20",
                    "risk_per_share",
                    "stop_loss",
                    "tp1_target",
                    "tp2_target",
                    "initial_risk",
                    "monetary_risk",
                    "adjusted_risk_dollars",
                    "base_risk_dollars",
                ]
            )

        logger.info(
            f"✅ Multi-chunk backtest complete: {len(combined_trades)} total trades"
        )

        return combined_equity, combined_trades

    def cleanup(self):
        """Libera memoria del engine después del backtest."""
        import gc

        # Close cache connection
        if hasattr(self, "cache"):
            try:
                self.cache.close()
            except:
                pass

        # Clear large DataFrames
        attrs_to_clear = [
            "close",
            "high",
            "low",
            "open",
            "volume",
            "sma_20",
            "sma_50",
            "adr_pct",
            "rvol",
            "dist_sma20_pct",
            "avg_volume_20",
            "trend_aligned",
            "dollar_volume",
            "spy_data",
            "market_regime_classifier",
        ]

        for attr in attrs_to_clear:
            if hasattr(self, attr):
                try:
                    df = getattr(self, attr)
                    if hasattr(df, "values"):
                        del df
                    setattr(self, attr, None)
                except:
                    pass

        # Force garbage collection
        gc.collect()

        logger.info("🧹 Engine memory cleaned up")
