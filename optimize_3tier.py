#!/usr/bin/env python3
"""
OPTIMIZE 3-TIER - Unified Pipeline (Correct Implementation)
============================================================

3-phase sequential pipeline that respects the tier hierarchy:

  Tier 3 (Risk Management) -> FIXED institutional parameters (NEVER optimized)
  Tier 2 (Quality Filters)  -> DERIVED statistically from baseline data
  Tier 1 (Strategy Params)  -> OPTIMIZED via Optuna with robust objective

Pipeline:
  Phase 1: Baseline Run    - Loose filters to collect raw trade universe
  Phase 2: Tier 2 Derivation - Statistical analysis of winners vs losers
  Phase 3: Tier 1 Optimization - Optuna tunes exits/sizing with Tier 2+3 fixed
  Phase 4: ResearchGate Validation - 3-phase promotion gate
  Phase 5: Auto-Export to Streamlit - If approved, update production_config.json

Key design decisions:
  - Uses AdvancedVectorBTEngine ONLY (THOR is deprecated)
  - Tier 3 loaded from config/tier3_risk_management.py (institutional, never touched)
  - Tier 2 derived from the SAME engine that will use them (no cross-engine contamination)
  - Robust objective function (not raw Sharpe) for optimization
  - ResearchGate validation as final gate before any params are promoted

Usage:
    python optimize_3tier.py --trials 100 --tickers 50
    python optimize_3tier.py --trials 200 --tickers 80 --start 2022-01-01 --end 2024-12-31
    python optimize_3tier.py --trials 50 --skip-validation  # Dev mode

References:
    - config/tier3_risk_management.py (Tier 3 source of truth)
    - src/validation/research_gate.py (Promotion gate)
    - src/validation/robustness_metrics.py (Objective function)
    - MIGRATION_THOR_TO_ADVANCED.md (Architecture rationale)
"""

import argparse
import json
import sys
import logging
import sqlite3
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
import pandas as pd
import optuna

# ──────────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("optimize_3tier.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Imports (fail fast if missing)
# ──────────────────────────────────────────────────────────────────────────────

try:
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    from src.validation.research_gate import ResearchGate, ValidationThresholds
    from src.validation.robustness_metrics import (
        robust_objective_function,
        RobustObjectiveConfig,
    )
    from src.data.cache_manager import CacheManager
    from config.tier3_risk_management import get_tier3_config, validate_tier3_params
    from config.defaults import get_tier2_defaults, reload_config
    from src.config.pattern_configs import get_pattern_config, list_patterns
    from src.screeners import ScreenerRegistry
    from src.data.market_data import MarketDataProvider
except ImportError as e:
    logger.error(f"Missing module: {e}")
    logger.error("Run from project root: cd momentum-v2 && python optimize_3tier.py")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Numba Warmup — pre-compila simulate_fast_core antes del primer trial
# Sin esto el primer trial tarda 15-60s extra en compilar JIT
# ──────────────────────────────────────────────────────────────────────────────
def _warmup_numba() -> None:
    """Pre-compile Numba JIT function with minimal dummy arrays."""
    try:
        n, m = 12, 2  # 12 dias, 2 tickers — minimo para que no falle el rolling(14)
        dummy2d = np.zeros((n, m), dtype=np.float32)
        entries = np.zeros((n, m), dtype=np.bool_)
        dummy1d = np.zeros(n, dtype=np.float32)
        simulate_fast_core(
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,  # close/high/low/open/volume
            entries,  # entries
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,  # atr/sma20/ema10/ema8/ema21
            dummy2d,
            dummy2d,
            dummy2d,  # adr/rvol/entry_score
            dummy1d,
            dummy1d,  # spy_close/spy_sma50
            100_000.0,  # initial_capital
            1.5,
            3.0,  # tp1_r, tp2_r
            0.5,
            0.3,
            0.2,  # tp1_pct, tp2_pct, runner_pct
            0.01,
            0.5,  # risk_pct_per_trade, be_threshold_r
            0.5,  # max_exposure_pct  (NEW param order)
            True,  # use_trailing_stop
            0.08,  # max_stop_pct
            500.0,  # risk_dollars
            True,  # use_fixed_dollar_risk
            True,  # use_atr_stop
            1.5,  # atr_stop_multiplier
            1.0,  # atr_trailing_multiplier
        )
        logger.info("Numba warmup complete (JIT compiled)")
    except Exception as e:
        logger.debug(f"Numba warmup skipped: {e}")  # silently continue


_warmup_numba()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def get_universe_from_db(
    limit: int = 50, start_date: str = "2021-01-01", end_date: str = "2025-12-31"
) -> List[str]:
    """
    Get top tickers by data availability from cache DB for a SPECIFIC period.
    Corrected to use ticker_cache.db (ohlcv_cache table).
    """
    db_path = Path("data/ticker_cache.db")
    if not db_path.exists():
        logger.warning(f"Database {db_path} not found. Using fallbacks.")
        return _get_fallback_universe(limit)

    # Intentar DuckDB primero (20x mas rapido para queries analiticos sobre SQLite)
    try:
        import duckdb

        conn = duckdb.connect()
        conn.execute(f"ATTACH '{db_path}' AS src (TYPE SQLITE, READ_ONLY TRUE)")
        query = """
            SELECT ticker, COUNT(*) as cnt
            FROM src.ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT ?
        """
        df = conn.execute(query, [start_date, end_date, limit]).fetchdf()
        conn.close()
        if not df.empty:
            tickers = df["ticker"].tolist()
            if len(tickers) < 10:
                logger.warning(
                    f"Only {len(tickers)} tickers found for period {start_date} to {end_date}"
                )
            logger.debug(f"Universe loaded via DuckDB: {len(tickers)} tickers")
            return tickers
    except ImportError:
        logger.debug("DuckDB not installed, falling back to SQLite")
    except Exception as e:
        logger.debug(f"DuckDB query failed ({e}), falling back to SQLite")

    # Fallback: SQLite estandar
    try:
        conn = sqlite3.connect(str(db_path))
        query = """
            SELECT ticker, COUNT(*) as cnt
            FROM ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(start_date, end_date, limit))
        conn.close()
        if not df.empty:
            tickers = df["ticker"].tolist()
            if len(tickers) < 10:
                logger.warning(
                    f"Only {len(tickers)} tickers found for period {start_date} to {end_date}"
                )
            return tickers
    except Exception as e:
        logger.error(f"Error querying ticker_cache.db: {e}")

    return _get_fallback_universe(limit)


def apply_screener_to_universe(
    universe: List[str],
    screener_name: str,
    start_date: str,
    end_date: str,
) -> List[str]:
    """Filter universe using an explicit screener before optimization.

    FASE 1 FIX: Explicit asset state management per ticker iteration.
    Each ticker gets its own isolated state dict that is destroyed at the
    end of the iteration. Screener instances are already stateless (new
    instance per ScreenerRegistry.get() call), but this adds defensive
    isolation for any future screener that might hold state.
    """
    from dataclasses import dataclass, field

    @dataclass
    class AssetState:
        """Transient state for a single ticker during screening."""

        ticker: str
        df: Optional[pd.DataFrame] = None
        result: Optional[Any] = None
        error: Optional[str] = None
        passed: bool = False

    logger.info(
        f"  Applying screener '{screener_name}' to universe of {len(universe)} tickers..."
    )

    try:
        screener = ScreenerRegistry.get(screener_name)
    except Exception as e:
        logger.warning(f"  Screener not available: {e}. Using raw universe.")
        return universe

    market_data = MarketDataProvider()
    screened: List[str] = []
    estado_activos: Dict[str, AssetState] = {}

    for ticker in universe:
        state = AssetState(ticker=ticker)
        try:
            state.df = market_data.get_daily_data(
                ticker,
                start=(pd.Timestamp(start_date) - pd.Timedelta(days=300)).strftime(
                    "%Y-%m-%d"
                ),
                end=end_date,
            )
            if state.df is None or state.df.empty or len(state.df) < 100:
                continue

            state.result = screener.scan(ticker, state.df)
            state.passed = state.result.passed
            if state.passed:
                screened.append(ticker)
        except Exception as e:
            state.error = str(e)
            continue
        finally:
            estado_activos[ticker] = state
            del state

    logger.info(f"  Screener results: {len(screened)}/{len(universe)} passed")
    return screened or universe


def _get_fallback_universe(limit: int) -> List[str]:
    """Top 50 most liquid S&P 500 tickers as fallback."""
    fallback_universe = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "NVDA",
        "TSLA",
        "META",
        "AMZN",
        "NFLX",
        "AMD",
        "CRM",
        "AVGO",
        "ORCL",
        "CSCO",
        "ADBE",
        "INTC",
        "TXN",
        "QCOM",
        "AMAT",
        "MU",
        "ADI",
        "NOW",
        "PANW",
        "PLTR",
        "SNOW",
        "CRWD",
        "DDOG",
        "NET",
        "ZS",
        "OKTA",
        "FTNT",
        "JPM",
        "BAC",
        "WFC",
        "C",
        "MS",
        "GS",
        "BLK",
        "SCHW",
        "AXP",
        "USB",
        "V",
        "MA",
        "PYPL",
        "SQ",
        "COIN",
        "SOFI",
        "AFRM",
        "UPST",
        "HOOD",
        "NU",
    ]
    return fallback_universe[:limit]


def normalize_engine_results(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize AdvancedVectorBTEngine output to standard _pct format.

    The engine returns decimals (total_return=0.15, win_rate=0.65, max_drawdown=-0.05).
    This function adds _pct aliases for downstream code that expects percentage format.

    NOTE: As of the research_gate.py patch (Feb 2026), ResearchGate._extract_metrics()
    now handles both formats natively, so this normalization is mainly for
    local convenience (e.g., logging with total_return_pct).

    This function adds the _pct aliases WITHOUT modifying originals,
    ensuring compatibility with both robust_objective_function (uses originals)
    and code that expects _pct keys.
    """
    normalized = dict(results)

    # total_return -> total_return_pct
    if "total_return" in normalized and "total_return_pct" not in normalized:
        normalized["total_return_pct"] = normalized["total_return"] * 100

    # win_rate -> win_rate_pct
    if "win_rate" in normalized and "win_rate_pct" not in normalized:
        normalized["win_rate_pct"] = normalized["win_rate"] * 100

    # max_drawdown -> max_drawdown_pct (engine returns negative decimal)
    if "max_drawdown" in normalized and "max_drawdown_pct" not in normalized:
        normalized["max_drawdown_pct"] = abs(normalized["max_drawdown"]) * 100

    return normalized


def build_tier3_engine_params(tier3_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert tier3_risk_management.py config to AdvancedVectorBTEngine kwargs.

    The tier3 config stores decimals (rvol_danger_size=0.30 meaning 30%)
    but AdvancedVectorBTEngine expects integers (rvol_danger_size=30)
    because it divides by 100 internally.

    Similarly max_stop_pct_hard is stored as 0.08 (8%) but engine expects 8.0.
    """
    engine_params = {}

    # Direct pass-through (no conversion needed)
    for key in [
        "rvol_danger",
        "rvol_warning",
        "adr_high",
        "adr_med",
        "max_exposure_pct",
        "earnings_days",
        "risk_fraction",  # Added: Need this to calculate risk_dollars dynamically
    ]:
        if key in tier3_raw:
            engine_params[key] = tier3_raw[key]

    # Size params: config stores decimal (0.30 = 30%), engine expects int (30)
    for key in ["rvol_danger_size", "rvol_warning_size"]:
        if key in tier3_raw:
            val = tier3_raw[key]
            engine_params[key] = int(val * 100) if val <= 1.0 else int(val)

    # max_stop_pct: config stores 0.08 (8%), engine expects 8.0
    if "max_stop_pct_hard" in tier3_raw:
        val = tier3_raw["max_stop_pct_hard"]
        engine_params["max_stop_pct"] = val * 100 if val < 1.0 else val

    return engine_params


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1: BASELINE RUN
# ══════════════════════════════════════════════════════════════════════════════


def _compute_universe_volume_thresholds(
    universe: List[str],
    start_date: str,
    end_date: str,
    volume_percentile: float = 5.0,
    dollar_volume_percentile: float = 5.0,
) -> Tuple[int, float]:
    """
    FASE 2: Compute universe-aware volume thresholds from actual data.

    Instead of hardcoded absolutes (min_volume=100k, min_dollar_volume=1M),
    calculate percentiles from the universe's median daily volume distribution.
    This scales thresholds to the actual liquidity profile:
      - Large-cap universe → higher thresholds (natural)
      - Small-cap universe → lower thresholds (avoids rejecting everything)

    Args:
        universe: List of tickers
        start_date: Backtest start
        end_date: Backtest end
        volume_percentile: Percentile cutoff for min_volume (default p5)
        dollar_volume_percentile: Percentile cutoff for min_dollar_volume (default p5)

    Returns:
        (min_volume, min_dollar_volume) — sane defaults if data unavailable
    """
    FLOOR_VOLUME = 50_000
    FLOOR_DOLLAR_VOLUME = 500_000
    CEILING_VOLUME = 5_000_000
    CEILING_DOLLAR_VOLUME = 50_000_000

    try:
        market_data = MarketDataProvider()
        volumes = []
        dollar_volumes = []

        for ticker in universe[:30]:  # Sample first 30 for efficiency
            try:
                df = market_data.get_daily_data(ticker, start=start_date, end=end_date)
                if df is None or df.empty or len(df) < 30:
                    continue
                median_vol = float(df["Volume"].median())
                median_price = float(df["Close"].median())
                median_dv = median_vol * median_price
                volumes.append(median_vol)
                dollar_volumes.append(median_dv)
            except Exception:
                continue

        if len(volumes) >= 5:
            min_vol = int(np.percentile(volumes, volume_percentile))
            min_dv = float(np.percentile(dollar_volumes, dollar_volume_percentile))
            min_vol = max(FLOOR_VOLUME, min(CEILING_VOLUME, min_vol))
            min_dv = max(FLOOR_DOLLAR_VOLUME, min(CEILING_DOLLAR_VOLUME, min_dv))
            logger.info(
                f"  Universe volume thresholds (p{volume_percentile:.0f}): "
                f"min_volume={min_vol:,.0f}, min_dollar_volume=${min_dv:,.0f}"
            )
            return min_vol, min_dv
    except Exception as e:
        logger.warning(
            f"  Could not compute universe volume thresholds ({e}), using defaults"
        )

    logger.info(
        f"  Using default volume thresholds: "
        f"min_volume={FLOOR_VOLUME:,.0f}, min_dollar_volume=${FLOOR_DOLLAR_VOLUME:,.0f}"
    )
    return FLOOR_VOLUME, FLOOR_DOLLAR_VOLUME


def run_baseline(
    universe: List[str],
    start_date: str,
    end_date: str,
    tier3_engine_params: Dict[str, Any],
    initial_capital: float = 100_000,
    use_pit_universe: bool = False,
    signal_type: str = "breakout",  # tipo de patron para etiquetado correcto en trades
    screener_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Phase 1: Run backtest with LOOSE filters to capture the full trade universe.

    We need to see both winners AND losers to derive meaningful Tier 2 cutoffs.
    If we start with strict filters, we introduce selection bias.

    Returns:
        (backtest_results, trades_df) - Raw results from the permissive run
    """
    logger.info("=" * 70)
    logger.info("PHASE 1: BASELINE RUN (Loose Filters)")
    logger.info("=" * 70)

    # Calculate risk_dollars from RISK_FRACTION (Tier 3)
    risk_fraction = tier3_engine_params.get("risk_fraction", 0.005)
    risk_dollars = int(initial_capital * risk_fraction)

    logger.info(f"  Initial Capital: ${initial_capital:,.0f}")
    logger.info(f"  Risk Fraction (Tier 3): {risk_fraction * 100:.2f}%")
    logger.info(f"  Risk per Trade: ${risk_dollars:,.0f}")

    # FASE 2 FIX: Compute universe-aware volume thresholds instead of
    # hardcoded absolutes. min_volume and min_dollar_volume scale with
    # the actual liquidity distribution of the universe.
    # Large-cap universes naturally have higher dollar volume; small-cap
    # universes need lower thresholds to avoid rejecting everything.
    min_volume, min_dollar_volume = _compute_universe_volume_thresholds(
        universe, start_date, end_date
    )

    # Loose Tier 2: Let almost everything through
    loose_params = {
        "min_rvol": 0.5,  # Very low - see everything
        "min_adr": 1.0,  # Very low
        "max_dist_sma20": 20.0,  # Very wide
        "min_consolidation_days": 3,  # Very short
        "min_volume": min_volume,
        "min_dollar_volume": min_dollar_volume,
        # Strategy defaults (not critical, just need trades)
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34,
        # Production mode with costs
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "risk_dollars": risk_dollars,  # Fixed dollar risk (matches production, NO compounding)
        # Market filters (keep basic ones on for realistic signals)
        "signal_type": signal_type,  # Usar el patron real para etiquetado correcto de trades
        "require_spy_above_sma50": True,
        "max_vix_threshold": 28.0,  # Slightly wider than production
        "use_market_regime_filter": False,  # OFF for baseline
        "use_composite_sector_scoring": False,
        "use_earnings_calendar": False,
        "use_trailing_stop": False,
        "require_positive_rs": False,  # OFF for baseline (loose filters)
        "use_rs_percentile": False,  # OFF for baseline (loose filters)
        "use_adaptive_filtering": False,  # OFF for baseline (loose filters)
        "use_pit_universe": use_pit_universe,
    }

    # Merge with Tier 3 risk params
    full_params = {**loose_params, **tier3_engine_params}

    logger.info(f"  Universe: {len(universe)} tickers")
    logger.info(f"  Period: {start_date} to {end_date}")
    logger.info(
        f"  Filters: LOOSE (min_rvol={loose_params['min_rvol']}, "
        f"min_adr={loose_params['min_adr']}, "
        f"max_dist_sma20={loose_params['max_dist_sma20']})"
    )

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        **full_params,
    )
    engine.load_data()
    results = engine.run_backtest()
    results = normalize_engine_results(results)

    trades_df = results.get("trades_df", pd.DataFrame())

    logger.info(f"  Total entries: {results.get('total_trades', 0)}")
    logger.info(f"  Total exits (incl. partial): {len(trades_df)}")
    logger.info(f"  Return: {results.get('total_return_pct', 0):.2f}%")

    if len(trades_df) < 30:
        logger.warning(
            f"  WARNING: Only {len(trades_df)} trades. "
            "Consider expanding universe or date range for reliable Tier 2 derivation."
        )

    return results, trades_df


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 2: TIER 2 DERIVATION
# ══════════════════════════════════════════════════════════════════════════════


def derive_tier2_filters(
    trades_df: pd.DataFrame,
    winner_threshold_r: float = 0.0,
    keep_pct: float = 95,  # Changed from 90 to 95 for looser filters (p5 of winners)
) -> Dict[str, Any]:
    """
    Phase 2: Statistically derive Tier 2 quality filters from baseline trades.

    Logic:
    1. Separate winners (pnl > 0) from losers
    2. For each filter dimension (rvol, adr, dist_sma20):
       - Find the percentile cutoff that KEEPS `keep_pct`% of winners
       - This eliminates the weakest trades while preserving the majority of edge
    3. Validate derived values are reasonable

    Args:
        trades_df: Trades from Phase 1 baseline run
        winner_threshold_r: Min PnL to count as winner (0 = breakeven+)
        keep_pct: Percentage of winners to keep (80 = keep 80%, cut 20%)

    Returns:
        Dict with derived filter values ready for engine consumption
    """
    logger.info("=" * 70)
    logger.info("PHASE 2: TIER 2 DERIVATION (Statistical Filter Analysis)")
    logger.info("=" * 70)

    if len(trades_df) == 0:
        logger.error("  No trades to analyze! Cannot derive Tier 2 filters.")
        return _default_tier2()

    # Separate winners and losers
    winners = trades_df[trades_df["pnl"] > winner_threshold_r]
    losers = trades_df[trades_df["pnl"] <= 0]

    logger.info(f"  Total exits: {len(trades_df)}")
    logger.info(
        f"  Winners (pnl > {winner_threshold_r}): {len(winners)} "
        f"({len(winners) / len(trades_df) * 100:.1f}%)"
    )
    logger.info(f"  Losers: {len(losers)} ({len(losers) / len(trades_df) * 100:.1f}%)")

    if len(winners) < 10:
        logger.warning("  Too few winners for reliable derivation. Using defaults.")
        return _default_tier2()

    # The cutoff percentile: keep_pct=80 means p20 (keep top 80%)
    cut_percentile = 100 - keep_pct

    derived = {}

    # ── RVOL ─────────────────────────────────────────────────────────────
    if "context_rvol" in trades_df.columns:
        valid_rvol = winners["context_rvol"].dropna()
        if len(valid_rvol) > 5:
            derived_rvol = round(float(np.percentile(valid_rvol, cut_percentile)), 2)

            # Log estadísticas completas
            rvol_stats = {
                "p10": round(float(np.percentile(valid_rvol, 10)), 2),
                "median": round(float(np.percentile(valid_rvol, 50)), 2),
                "p90": round(float(np.percentile(valid_rvol, 90)), 2),
                "max": round(float(valid_rvol.max()), 2),
            }

            # Sanity bounds: never below 0.5 or above 4.0 (lowered min for more trades)
            clamped = derived_rvol < 0.5 or derived_rvol > 4.0
            derived["min_rvol"] = max(0.5, min(4.0, derived_rvol))

            loser_median_rvol = (
                losers["context_rvol"].dropna().median() if len(losers) > 0 else 0
            )
            logger.info(f"  min_rvol: {derived['min_rvol']}")
            logger.info(
                f"    📊 RVOL Stats (winners): p10={rvol_stats['p10']}, median={rvol_stats['median']}, p90={rvol_stats['p90']}, max={rvol_stats['max']}"
            )
            logger.info(f"    🎯 Derived raw (p{cut_percentile}): {derived_rvol:.2f}")
            if clamped:
                logger.warning(
                    f"    ⚠️  CLAMPED to bounds [0.5, 4.0] → final: {derived['min_rvol']}"
                )
            logger.info(f"    📉 Loser median: {loser_median_rvol:.2f}")
        else:
            derived["min_rvol"] = 1.5
            logger.info(
                f"  min_rvol: {derived['min_rvol']} (insufficient data, using default)"
            )
    else:
        derived["min_rvol"] = 1.5
        logger.info(
            f"  min_rvol: {derived['min_rvol']} (column missing, using default)"
        )

    # ── ADR ───────────────────────────────────────────────────────────────
    if "context_adr" in trades_df.columns:
        valid_adr = winners["context_adr"].dropna()
        if len(valid_adr) > 5:
            derived_adr = round(float(np.percentile(valid_adr, cut_percentile)), 2)

            # Log estadísticas completas
            adr_stats = {
                "p10": round(float(np.percentile(valid_adr, 10)), 2),
                "median": round(float(np.percentile(valid_adr, 50)), 2),
                "p90": round(float(np.percentile(valid_adr, 90)), 2),
                "max": round(float(valid_adr.max()), 2),
            }

            # Sanity bounds: never below 0.5 or above 8.0 (lowered min for more trades)
            clamped = derived_adr < 0.5 or derived_adr > 8.0
            derived["min_adr"] = max(0.5, min(8.0, derived_adr))

            loser_median_adr = (
                losers["context_adr"].dropna().median() if len(losers) > 0 else 0
            )
            logger.info(f"  min_adr: {derived['min_adr']}")
            logger.info(
                f"    📊 ADR Stats (winners): p10={adr_stats['p10']}%, median={adr_stats['median']}%, p90={adr_stats['p90']}%, max={adr_stats['max']}%"
            )
            logger.info(f"    🎯 Derived raw (p{cut_percentile}): {derived_adr:.2f}%")
            if clamped:
                logger.warning(
                    f"    ⚠️  CLAMPED to bounds [0.5, 8.0] → final: {derived['min_adr']}"
                )
            logger.info(f"    📉 Loser median: {loser_median_adr:.2f}%")
        else:
            derived["min_adr"] = 2.0
            logger.info(
                f"  min_adr: {derived['min_adr']} (insufficient data, using default)"
            )
    else:
        derived["min_adr"] = 2.0
        logger.info(f"  min_adr: {derived['min_adr']} (column missing, using default)")

    # ── Distance to SMA20 ────────────────────────────────────────────────
    if "dist_sma20_pct" in trades_df.columns:
        valid_dist = winners["dist_sma20_pct"].dropna()
        if len(valid_dist) > 5:
            # For max_dist: use upper percentile (we want to cap outliers)
            derived_dist = round(
                float(np.percentile(valid_dist, 95)), 2
            )  # Changed from 90 to 95

            # Log estadísticas completas
            dist_stats = {
                "p10": round(float(np.percentile(valid_dist, 10)), 2),
                "median": round(float(np.percentile(valid_dist, 50)), 2),
                "p90": round(float(np.percentile(valid_dist, 90)), 2),
                "max": round(float(valid_dist.max()), 2),
            }

            # Sanity bounds: never below 3.0 or above 20.0 (increased max for more trades)
            clamped = derived_dist < 3.0 or derived_dist > 20.0
            derived["max_dist_sma20"] = max(3.0, min(20.0, derived_dist))

            loser_median_dist = (
                losers["dist_sma20_pct"].dropna().median() if len(losers) > 0 else 0
            )
            logger.info(f"  max_dist_sma20: {derived['max_dist_sma20']}")
            logger.info(
                f"    📊 Dist SMA20 Stats (winners): p10={dist_stats['p10']}%, median={dist_stats['median']}%, p90={dist_stats['p90']}%, max={dist_stats['max']}%"
            )
            logger.info(f"    🎯 Derived raw (p95): {derived_dist:.2f}%")
            if clamped:
                logger.warning(
                    f"    ⚠️  CLAMPED to bounds [3.0, 20.0] → final: {derived['max_dist_sma20']}"
                )
            logger.info(f"    📉 Loser median: {loser_median_dist:.2f}%")
        else:
            derived["max_dist_sma20"] = 7.0
            logger.info(
                f"  max_dist_sma20: {derived['max_dist_sma20']} (insufficient data, using default)"
            )
    else:
        derived["max_dist_sma20"] = 7.0
        logger.info(
            f"  max_dist_sma20: {derived['max_dist_sma20']} (column missing, using default)"
        )

    # ── Dollar Volume ─────────────────────────────────────────────────────
    if "context_dollar_vol" in trades_df.columns:
        valid_dv = winners["context_dollar_vol"].dropna()
        if len(valid_dv) > 5:
            derived_dv = float(np.percentile(valid_dv, cut_percentile))

            # Log estadísticas completas para detectar sesgo
            dv_stats = {
                "p10": float(np.percentile(valid_dv, 10)),
                "p25": float(np.percentile(valid_dv, 25)),
                "median": float(np.percentile(valid_dv, 50)),
                "p75": float(np.percentile(valid_dv, 75)),
                "p90": float(np.percentile(valid_dv, 90)),
                "max": float(valid_dv.max()),
                "derived_raw": derived_dv,
            }

            # Apply floor only (no ceiling - use raw derived value)
            clamped = False
            if derived_dv < 1_000_000:
                clamped = True
                clamp_reason = "FLOOR (1M)"
            else:
                clamp_reason = "none"

            derived["min_dollar_volume"] = max(1_000_000, derived_dv)

            # Log detallado
            logger.info(f"  min_dollar_volume: {derived['min_dollar_volume']:,.0f}")
            logger.info(f"    📊 Dollar Volume Stats (winners):")
            logger.info(
                f"       p10=${dv_stats['p10'] / 1e6:.1f}M, p25=${dv_stats['p25'] / 1e6:.1f}M, "
                f"median=${dv_stats['median'] / 1e6:.1f}M, p75=${dv_stats['p75'] / 1e6:.1f}M, "
                f"p90=${dv_stats['p90'] / 1e6:.1f}M, max=${dv_stats['max'] / 1e6:.1f}M"
            )
            logger.info(
                f"    🎯 Derived raw (p{cut_percentile}): ${derived_dv / 1e6:.2f}M"
            )
            if clamped:
                logger.warning(
                    f"    ⚠️  CLAMPED by {clamp_reason} → final: ${derived['min_dollar_volume'] / 1e6:.0f}M"
                )
            else:
                logger.info(f"    ✅ No clamping needed")
        else:
            derived["min_dollar_volume"] = 5_000_000
            logger.info(
                f"  min_dollar_volume: {derived['min_dollar_volume']:,.0f} (insufficient data)"
            )
    else:
        derived["min_dollar_volume"] = 5_000_000
        logger.info(
            f"  min_dollar_volume: {derived['min_dollar_volume']:,.0f} (column missing)"
        )

    # ── Static Tier 2 values (not derived) ────────────────────────────────
    derived["min_consolidation_days"] = 5  # Lowered from 10 for more trades
    derived["min_volume"] = 100_000  # Lowered from 300k for more trades

    # ── RS Percentile (IBD-style) - Static values ──────────────────────
    derived["require_positive_rs"] = True  # Activate RS filter
    derived["use_rs_percentile"] = True  # Use IBD-style RS ranking
    derived["min_rs_percentile"] = 70.0  # Top 30% of market
    derived["rs_lookback_days"] = 60  # 3 months lookback

    # ── Pattern Detection (NOT in tier2_derived - comes from engine defaults or Optuna tier1) ───────
    # Pattern params are NOT derived from data - they are optimized by Optuna or use engine defaults
    # We only set the cache path here (not optimizable)
    derived["use_pattern_filter"] = (
        False  # Start without hard filter (comes from engine default)
    )
    derived["min_pattern_confidence"] = 0.5  # (comes from engine default)
    # NOTE: pattern_bonus_high/med/low are NOT set here - they come from:
    #   - Optuna (tier1_params) if optimizing
    #   - Engine defaults if not optimizing
    derived["pattern_cache_path"] = "data/pattern_matrix.pkl"

    # ── Summary of derived values with clamping status ────────────────────
    logger.info(f"\n  ═══════════════════════════════════════════════════════════")
    logger.info(f"  DERIVED TIER 2 FILTERS SUMMARY:")
    logger.info(f"  ═══════════════════════════════════════════════════════════")
    for k, v in derived.items():
        if k == "min_dollar_volume":
            logger.info(f"    {k}: ${v / 1e6:.1f}M")
        else:
            logger.info(f"    {k}: {v}")

    # Store raw derived values (before clamping) for JSON export
    derived["_raw_derived"] = {
        "rvol_raw": locals().get("derived_rvol", None),
        "adr_raw": locals().get("derived_adr", None),
        "dist_sma20_raw": locals().get("derived_dist", None),
        "dollar_volume_raw": locals().get("derived_dv", None),
    }

    # Store stats for JSON export
    if "dv_stats" in locals():
        derived["_dollar_volume_stats"] = dv_stats
    if "rvol_stats" in locals():
        derived["_rvol_stats"] = rvol_stats
    if "adr_stats" in locals():
        derived["_adr_stats"] = adr_stats
    if "dist_stats" in locals():
        derived["_dist_sma20_stats"] = dist_stats

    return derived


def _default_tier2() -> Dict[str, Any]:
    """Use centralized defaults from config/defaults.py (synchronized with production_config.json)."""
    defaults = get_tier2_defaults()
    return {
        "min_rvol": defaults.get("min_rvol", 0.91),
        "min_adr": defaults.get("min_adr", 1.97),
        "max_dist_sma20": defaults.get("max_dist_sma20", 8.94),
        "min_dollar_volume": defaults.get("min_dollar_volume", 20_000_000),
        "min_consolidation_days": defaults.get("min_consolidation_days", 5),
        "min_volume": defaults.get("min_volume", 100_000),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3: TIER 1 OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════


def optimize_tier1(
    universe: List[str],
    start_date: str,
    end_date: str,
    tier2_derived: Dict[str, Any],
    tier3_engine_params: Dict[str, Any],
    n_trials: int = 100,
    initial_capital: float = 100_000,
    use_pit_universe: bool = False,
    optim_seed: Optional[int] = None,
    warmstart_params: Optional[Dict[str, Any]] = None,
    pattern_config: Optional[Dict[str, Any]] = None,
    # PERF Item 3: paralelizacion Optuna con n_jobs workers.
    # Thread-safety confirmada: cada trial usa clone_with_params (instancia propia).
    # DataFrames del template son read-only; _ml_pool_buffer tiene lock.
    # n_jobs=1 -> secuencial (default conservador, identico comportamiento anterior)
    # n_jobs=2 -> recomendado en produccion (12 CPUs disponibles, deja margen)
    # n_jobs=4 -> agresivo, OK si RAM lo permite (cada clone ~igual mem que template)
    # NOTA: show_progress_bar se desactiva con n_jobs>1 (tqdm no es thread-safe)
    n_jobs: int = 1,
) -> Tuple[Dict[str, Any], float, optuna.Study]:
    """
    Phase 3: Optimize ONLY Tier 1 strategy parameters via Optuna.

    Tier 2 (derived in Phase 2) and Tier 3 (institutional) are FIXED.
    Only exit parameters and sizing are varied.

    This is the correct approach because:
    - Risk management (Tier 3) comes from institutional expertise, not curve fitting
    - Quality filters (Tier 2) are derived from data distribution, not optimized
    - Only execution parameters (Tier 1) should be tuned

    Returns:
        (best_params, best_score, study)
    """
    logger.info("=" * 70)
    logger.info("PHASE 3: TIER 1 OPTIMIZATION (Strategy Params Only)")
    logger.info("=" * 70)
    logger.info(f"  Trials: {n_trials}")
    logger.info(f"  Tier 2 (FIXED): {json.dumps(tier2_derived, indent=2, default=str)}")
    logger.info(
        f"  Tier 3 (FIXED): {json.dumps(tier3_engine_params, indent=2, default=str)}"
    )

    robust_config = RobustObjectiveConfig(
        p5_weight=1.0,
        p10_weight=0.5,
        p50_weight=0.2,
        sharpe_weight=0.3,
        sortino_weight=0.3,
        calmar_weight=0.2,
        max_dd_penalty=2.0,
        dd_duration_penalty=1.0,
        loss_prob_penalty=1.5,
    )

    # Calculate risk_dollars from RISK_FRACTION (Tier 3)
    # This makes risk scale with capital automatically
    risk_fraction = tier3_engine_params.get("risk_fraction", 0.005)
    risk_dollars = int(initial_capital * risk_fraction)

    logger.info(f"\n  RISK CALCULATION:")
    logger.info(f"    Initial Capital: ${initial_capital:,.0f}")
    logger.info(f"    Risk Fraction (Tier 3): {risk_fraction * 100:.2f}%")
    logger.info(f"    Risk per Trade: ${risk_dollars:,.0f}")

    # Fixed params that combine Tier 2 + Tier 3 + infrastructure
    fixed_params = {
        # Tier 2 (derived)
        **tier2_derived,
        # Tier 3 (institutional)
        **tier3_engine_params,
        # Infrastructure (always fixed)
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "risk_dollars": risk_dollars,
        "use_earnings_calendar": False,
        "use_trailing_stop": False,
        "use_composite_sector_scoring": False,
        "use_pit_universe": use_pit_universe,
        "log_rejections": False,  # PERF: skip CSV writes durante optimizacion
        # Extra params del patron (signal_type, regime flags, adaptive filtering)
        # El plugin define estos segun el comportamiento optimo de cada patron.
        # Para breakout (default): adaptive=True, regime=True
        # Para VCP/PP/FB: adaptive=False, regime=False (optimizacion in-sample sin bloqueos)
        **(
            pattern_config["extra_fixed_params"]
            if pattern_config
            else {
                "signal_type": "any",
                "require_spy_above_sma50": True,
                "max_vix_threshold": 25.0,
                "use_market_regime_filter": True,
                "block_trades_in_stage3": True,
                "block_trades_in_stage4": True,
                "use_adaptive_filtering": True,
            }
        ),
    }

    # =========================================================
    # PRE-LOAD ENGINE TEMPLATE (data shared across all trials)
    # Saves ~1.5s per trial (no SQLite re-reads, no indicator recalc)
    # =========================================================
    logger.info(
        "  Pre-loading engine template (data + indicators, shared across trials)..."
    )
    import time as _time

    _t0 = _time.time()
    _template_params = {
        **fixed_params,
        "tp1_r": 1.75,
        "tp2_r": 3.0,
        "tp1_pct": 0.5,
        "tp2_pct": 0.3,
        "runner_pct": 0.2,
        "score_rs_weight": 0.7,
        "score_proximity_weight": 0.3,
        "pattern_bonus_high": 0.0,
        "pattern_bonus_med": 0.0,
        "pattern_bonus_low": 0.0,
    }
    _template_engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        **_template_params,
    )
    _template_engine.load_data()
    logger.info(
        f"  Engine template loaded in {_time.time() - _t0:.2f}s — data will be reused each trial"
    )

    # PERF Item 2: Pre-calcular componentes crudos de entry_score (una sola vez)
    # score_rs_weight / score_proximity_weight varian por trial, pero los
    # componentes normalizados (RS multi-TF y proximidad 52wk) son constantes.
    try:
        _rs_component = _template_engine._compute_rs_scores()
        _prox_component = _template_engine._compute_proximity_scores()
        # Cachear en template para inspeccion posterior si se necesita
        _template_engine._rs_score_component = _rs_component
        _template_engine._proximity_score_component = _prox_component
        _precompute_score = True
        logger.info(
            "  Entry score components pre-computed (RS + proximity) — skipped per-trial"
        )
    except Exception as _e_pre:
        _precompute_score = False
        logger.warning(f"  Could not pre-compute entry score components: {_e_pre}")

    # ML TRAINING POOL: accumulate trades from promising trials
    _ML_POOL_PATH = __import__("pathlib").Path(
        "outputs/3tier_optimization/ml_training_pool.csv"
    )
    _ML_POOL_MIN_SHARPE = 0.50  # only save trades from trials with Sharpe > this
    _ML_POOL_MIN_TRADES = 30  # and at least this many trades
    _ml_pool_lock = __import__("threading").Lock()
    _ml_pool_buffer = []  # PERF: acumular en memoria, escribir 1 vez al final

    def objective(trial: optuna.Trial) -> float:
        # PATTERN PLUGIN DISPATCH
        # Si se paso un pattern_config, usar su espacio Optuna.
        # Esto permite que cada patron defina sus propios params
        # sin modificar este script base.
        if pattern_config and "optuna_space" in pattern_config:
            _trial_params = pattern_config["optuna_space"](trial, fixed_params)
            if _trial_params is None:
                return -999.0
            tier1_params = _trial_params
            full_params = {**fixed_params, **tier1_params}
        else:
            # BREAKOUT DEFAULT SPACE (cuando no hay plugin)
            tier1_params = {
                "tp1_r": trial.suggest_float("tp1_r", 1.25, 2.5, step=0.25),
                "tp2_r": trial.suggest_float("tp2_r", 2.0, 4.5, step=0.25),
            }

            # Position distribution (must sum to ~1.0)
            # Aligned with Streamlit: 50% at TP1, 40% at TP2, 10% runner
            tp1_pct = trial.suggest_float(
                "tp1_pct", 0.35000000000000003, 0.60, step=0.05
            )
            tp2_pct = trial.suggest_float("tp2_pct", 0.2, 0.55, step=0.05)
            runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)

            # Constraint: runner must have at least 5% and max 25%
            if runner_pct < 0.05 or runner_pct > 0.25:
                return -999.0

            # Constraint: tp2 must be meaningfully higher than tp1 (min 0.5R separation)
            # Prevents degenerate solutions where tp1=tp2
            if tier1_params["tp2_r"] - tier1_params["tp1_r"] < 0.5:
                return -999.0

            tier1_params["tp1_pct"] = tp1_pct
            tier1_params["tp2_pct"] = tp2_pct
            tier1_params["runner_pct"] = runner_pct

            # Entry Quality Score v2: RS rank + 52wk proximity
            # Optuna decide la proporcion optima entre las dos señales
            score_rs_weight = trial.suggest_float(
                "score_rs_weight", 0.30000000000000004, 1.0, step=0.1
            )
            score_proximity_weight = round(1.0 - score_rs_weight, 2)
            tier1_params["score_rs_weight"] = score_rs_weight
            tier1_params["score_proximity_weight"] = score_proximity_weight

            # PATTERN BONUS: fijado en 0.0 para diagnostico
            # El bonus distorsiona el entry score (High score WR < Med score WR)
            # Una vez confirmado si aporta valor se re-activa
            tier1_params["pattern_bonus_high"] = 0.0
            tier1_params["pattern_bonus_med"] = 0.0
            tier1_params["pattern_bonus_low"] = 0.0

            # Combine everything
            full_params = {**fixed_params, **tier1_params}

        try:
            # PERF Item 1: clone_with_params evita re-instanciar el engine y
            # re-inyectar ~30 attrs por trial. DataFrames se comparten por ref.
            try:
                engine = _template_engine.clone_with_params(**full_params)
            except NameError:
                # Fallback si no hay template (no deberia ocurrir en flujo normal)
                engine = AdvancedVectorBTEngine(
                    universe=universe,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    **full_params,
                )
                engine.load_data()

            # PERF Item 2: inyectar entry_score pre-computado para este trial
            # (score_rs_weight + score_proximity_weight varian, componentes no)
            if _precompute_score:
                _rs_w = full_params.get("score_rs_weight", 0.70)
                _prox_w = full_params.get("score_proximity_weight", 0.30)
                _total_w = _rs_w + _prox_w
                if _total_w > 0:
                    _rs_w /= _total_w
                    _prox_w /= _total_w
                import numpy as _np_obj

                engine._entry_score_precomputed = (
                    _rs_w * _rs_component + _prox_w * _prox_component
                ).astype(_np_obj.float32)

            results = engine.run_backtest()

            # Minimum trade threshold for statistical reliability
            if results.get("total_trades", 0) < 20:
                return -999.0

            score = robust_objective_function(results, robust_config)

            # ML TRAINING DATA: save trades from promising trials
            _trial_sharpe = results.get("sharpe_ratio", 0)
            _trial_trades_df = results.get("trades_df", None)
            if (
                _trial_sharpe >= _ML_POOL_MIN_SHARPE
                and _trial_trades_df is not None
                and len(_trial_trades_df) >= _ML_POOL_MIN_TRADES
            ):
                try:
                    _trial_trades_df = _trial_trades_df.copy()
                    _trial_trades_df["_trial"] = trial.number
                    _trial_trades_df["_trial_sharpe"] = round(_trial_sharpe, 3)
                    with _ml_pool_lock:
                        _ml_pool_buffer.append(
                            _trial_trades_df
                        )  # PERF: solo append, sin I/O
                except Exception as _pe:
                    pass  # non-critical

            # Store useful attrs for analysis
            trial.set_user_attr("total_return", results.get("total_return", 0) * 100)
            trial.set_user_attr("sharpe", results.get("sharpe_ratio", 0))
            trial.set_user_attr("max_dd", results.get("max_drawdown", 0) * 100)
            trial.set_user_attr("win_rate", results.get("win_rate", 0) * 100)
            trial.set_user_attr("trades", results.get("total_trades", 0))
            trial.set_user_attr("profit_factor", results.get("profit_factor", 0))

            return score

        except Exception as e:
            logger.error(f"  Trial {trial.number} failed: {e}")
            return -999.0

    # Run optimization
    # optim_seed=None → exploracion libre (default, para optimizar)
    # optim_seed=42   → determinista (para reproducir o comparar runs)
    study = optuna.create_study(
        direction="maximize",
        study_name=f"3tier_{datetime.now().strftime('%Y%m%d_%H%M')}",
        sampler=optuna.samplers.TPESampler(
            seed=optim_seed,
            n_startup_trials=15,  # PERF: 50->15 (espacio ~6 dims, no necesita mas)
            n_ei_candidates=24,  # PERF: 48->24 (suficiente para 6 dims)
            multivariate=True,  # PERF: captura correlaciones entre params (tp1_r<->tp1_pct)
            consider_endpoints=True,  # Samplea valores extremos del rango
        ),
    )

    # Warmstart: enqueue known-good params as first trial
    # Esto le da a Optuna un punto de partida fuerte en lugar de empezar ciego
    if warmstart_params is not None:
        ws = {
            k: v
            for k, v in warmstart_params.items()
            if k in ["tp1_r", "tp2_r", "tp1_pct", "tp2_pct", "score_rs_weight"]
        }
        if ws:
            study.enqueue_trial(ws)
            logger.info(f"  Warmstart enqueued: {ws}")

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Columnas estándar para el ML pool (todas las corridas deben tener estas)
    _STANDARD_COLS = [
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
        "exit_date",
        "entry_date",
        "symbol",
        "exit_phase",
        "monetary_risk",
        "adjusted_risk_dollars",
        "base_risk_dollars",
        "context_vol",
        "return_pct",
        "entry_price",
        "context_dollar_vol",
        "signal_type",
        "dist_sma20_pct",
        "rs_percentile",
        "stop_distance",
        "stop_distance_pct",
        "risk_per_share",
        "r_multiple",
        "outcome",
        "is_big_win",
        "is_big_loss",
        "_trial",
        "_trial_sharpe",
    ]

    # PERF: flush ML pool buffer al salir (atexit como safety net si se interrumpe)
    _ml_pool_flushed = False

    def _flush_ml_pool() -> None:
        """Persist ML training pool once; idempotent (safe for atexit + explicit flush)."""
        nonlocal _ml_pool_flushed
        if _ml_pool_flushed:
            return

        with _ml_pool_lock:
            if not _ml_pool_buffer:
                _ml_pool_flushed = True
                return
            _buffer = list(_ml_pool_buffer)
            _ml_pool_buffer.clear()
            _ml_pool_flushed = True

        try:
            combined = pd.concat(_buffer, ignore_index=True)
            # Normalizar: solo mantener columnas estándar, ignorar extras
            existing_cols = [c for c in _STANDARD_COLS if c in combined.columns]
            combined = combined[existing_cols]
            _write_header = not _ML_POOL_PATH.exists()
            combined.to_csv(_ML_POOL_PATH, mode="a", header=_write_header, index=False)
            logger.info(
                f"  ML pool: saved {len(combined)} rows ({len(existing_cols)} cols) from {len(_buffer)} trials -> {_ML_POOL_PATH}"
            )
        except Exception as _pe:
            logger.debug(f"ML pool flush failed (non-critical): {_pe}")

    import atexit as _atexit

    _atexit.register(_flush_ml_pool)

    # PERF Item 3: n_jobs controla workers paralelos de Optuna.
    # Con n_jobs>1 se desactiva show_progress_bar (tqdm no es thread-safe).
    study.optimize(
        objective,
        n_trials=n_trials,
        n_jobs=n_jobs,
        show_progress_bar=(n_jobs == 1),
    )

    # Flush inmediato tras optimize (el atexit es solo backup si se interrumpe)
    _flush_ml_pool()

    best = study.best_params
    # Add derived runner_pct
    best["runner_pct"] = round(
        1.0 - best.get("tp1_pct", 0.33) - best.get("tp2_pct", 0.33), 2
    )

    logger.info(f"\n  BEST TIER 1 PARAMETERS (Score: {study.best_value:.2f}):")
    for k, v in best.items():
        logger.info(f"    {k}: {v}")

    # Show best trial metrics
    bt = study.best_trial
    logger.info(f"\n  BEST TRIAL METRICS:")
    logger.info(f"    Return: {bt.user_attrs.get('total_return', 0):.2f}%")
    logger.info(f"    Sharpe: {bt.user_attrs.get('sharpe', 0):.2f}")
    logger.info(f"    Max DD: {bt.user_attrs.get('max_dd', 0):.2f}%")
    logger.info(f"    Win Rate: {bt.user_attrs.get('win_rate', 0):.1f}%")
    logger.info(f"    Trades: {bt.user_attrs.get('trades', 0)}")
    logger.info(f"    PF: {bt.user_attrs.get('profit_factor', 0):.2f}")

    return best, study.best_value, study, _template_engine


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4: VALIDATION (ResearchGate)
# ══════════════════════════════════════════════════════════════════════════════


def validate_with_research_gate(
    universe: List[str],
    full_params: Dict[str, Any],
    train_dates: Tuple[str, str],
    test_dates: Tuple[str, str],
    template_engine=None,
) -> Any:
    """
    Phase 4: Run the 3-phase ResearchGate validation with MULTI-WINDOW Walk Forward.

    template_engine: si se pasa, todos los engines internos (train, test, CSCV x20,
    stress x3) heredan sus DataFrames sin llamar load_data(). Elimina 24 de 25
    load_data() en Phase 4.
    """
    logger.info("=" * 70)
    logger.info("PHASE 4: RESEARCH GATE VALIDATION (Multi-Window Walk Forward)")
    if template_engine is not None:
        logger.info("  PERF: template_engine provided - skipping 24 load_data() calls")
    logger.info("=" * 70)

    gate = ResearchGate()

    result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=full_params,
        universe=universe,
        train_dates=train_dates,
        test_dates=test_dates,
        verbose=True,
        template_engine=template_engine,
    )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 5: AUTO-EXPORT TO STREAMLIT
# ══════════════════════════════════════════════════════════════════════════════


def export_to_streamlit_config(
    final_config: Dict[str, Any],
    output_path: str = "config/production_config.json",
    backup: bool = True,
) -> None:
    """
    Export optimized parameters to Streamlit production config.

    This function converts the 3-tier optimization output into the format
    expected by the Streamlit app (config/production_config.json).

    Args:
        final_config: Output from run_pipeline()
        output_path: Path to production config file
        backup: If True, backup existing config before overwriting
    """
    from pathlib import Path
    import shutil

    logger.info("=" * 70)
    logger.info("PHASE 5: AUTO-EXPORT TO STREAMLIT")
    logger.info("=" * 70)

    output_file = Path(output_path)

    # Backup existing config
    if backup and output_file.exists():
        backup_path = output_file.with_suffix(".json.bak")
        shutil.copy2(output_file, backup_path)
        logger.info(f"  ✅ Backed up existing config to: {backup_path}")

    # Load existing config to preserve history
    existing_config = {}
    if output_file.exists():
        with open(output_file, "r") as f:
            existing_config = json.load(f)

    # Extract parameters
    tier1 = final_config["tier1_strategy"]
    tier2 = final_config["tier2_filters"]
    tier3 = final_config["tier3_risk"]
    validation = final_config.get("validation", {})
    optimization = final_config.get("optimization", {})

    # Calculate risk_dollars from RISK_FRACTION (consistent with optimization)
    initial_capital = final_config.get("period", {}).get("initial_capital", 100000)
    risk_fraction = tier3.get("risk_fraction", 0.005)
    risk_dollars = int(initial_capital * risk_fraction)

    # Build new config in Streamlit format
    streamlit_config = {
        "_schema_version": "2.0",
        "_description": "Auto-exported from 3-Tier Optimization Pipeline",
        "_last_updated": final_config["timestamp"],
        "_optimization_method": "3Tier_AdvancedVectorBT",
        "system": {
            "name": "Bugatti Trading System",
            "version": "3.0",
            "mode": "production",
            "tier_system_enabled": True,
        },
        "=== TIER 1: STRATEGY (Optimized via Optuna) ===": {},
        "tier1_strategy": {
            "tp1_r": tier1["tp1_r"],
            "tp2_r": tier1["tp2_r"],
            "tp1_pct": tier1["tp1_pct"],
            "tp2_pct": tier1["tp2_pct"],
            "runner_pct": tier1["runner_pct"],
            "max_stop_pct": tier3.get("max_stop_pct_hard", 0.08),
            "risk_dollars": risk_dollars,  # Calculated from RISK_FRACTION
            "use_phases": True,
            "signal_type": "any",
            "_optimized_with": f"3-Tier Pipeline (AdvancedVectorBT, {final_config['universe_size']} tickers)",
            "_trials": optimization.get("trials", 0),
            "_robust_score": optimization.get("best_score", 0),
            "_sharpe_validation": validation.get("sharpe_ratio", 0),
        },
        "=== TIER 2: FILTERS (Statistically Derived) ===": {},
        "tier2_filters": {
            "min_rvol": tier2["min_rvol"],
            "min_adr": tier2["min_adr"],
            "max_dist_sma20": tier2["max_dist_sma20"],
            "min_consolidation_days": tier2.get("min_consolidation_days", 10),
            "min_volume": tier2.get("min_volume", 300000),
            "min_dollar_volume": tier2.get("min_dollar_volume", 20000000),
            "max_consolidation_range": 15.0,
            "require_sector_strength": False,
            "sector_top_percentile": 0.4,
            "require_positive_rs": tier2.get("require_positive_rs", True),
            "use_rs_percentile": tier2.get("use_rs_percentile", True),
            "min_rs_percentile": tier2.get("min_rs_percentile", 70.0),
            "rs_lookback_days": tier2.get("rs_lookback_days", 60),
            "_source": f"Derived from baseline trades (keep_pct filter applied)",
            "_baseline_trades": optimization.get("baseline_trades", 0),
        },
        "=== TIER 3: RISK MANAGEMENT (Fixed Institutional) ===": {},
        "tier3_risk": {
            "rvol_danger": tier3["rvol_danger"],
            "rvol_warning": tier3["rvol_warning"],
            "rvol_danger_size": tier3["rvol_danger_size"],
            "rvol_warning_size": tier3["rvol_warning_size"],
            "adr_high": tier3["adr_high"],
            "adr_med": tier3["adr_med"],
            "adr_high_size": tier3.get("adr_high_size", 0.75),
            "adr_med_size": tier3.get("adr_med_size", 0.85),
            "max_exposure_pct": tier3["max_exposure_pct"],
            "max_position_pct": tier3.get("max_position_pct", 0.25),
            "earnings_days": tier3.get("earnings_days", 5),
            "earnings_cushion": tier3.get("earnings_cushion", 2),
            "max_stop_pct_hard": tier3.get("max_stop_pct_hard", 0.08),
            "risk_fraction": tier3.get("risk_fraction", 0.005),
            "compounding_enabled": tier3.get("compounding_enabled", False),
            "_source": "config/tier3_risk_management.py (Institutional Standards)",
        },
        "=== MARKET REGIME ===": {},
        "market_regime": {
            "require_spy_above_sma50": True,
            "max_vix": 35.0,
            "use_market_regime_filter": True,
            "block_trades_in_stage3": True,
            "block_trades_in_stage4": True,
            "use_dynamic_thresholds": False,
        },
        "=== PERFORMANCE TARGETS ===": {},
        "performance": {
            "target_sharpe": 0.8,
            "target_win_rate": 45.0,
            "max_acceptable_drawdown": 25.0,
            "validation_max_degradation_pct": 20.0,
            "sharpe_ratio": validation.get("sharpe_ratio", 0),
            "total_trades": optimization.get("best_trial_metrics", {}).get("trades", 0),
            "win_rate_pct": optimization.get("best_trial_metrics", {}).get(
                "win_rate", 0
            ),
            "total_return_pct": optimization.get("best_trial_metrics", {}).get(
                "total_return", 0
            ),
            "max_drawdown_pct": validation.get("max_drawdown_pct", 0),
            "pbo_score": validation.get("pbo_score", 0),
            "bootstrap_p5": validation.get("bootstrap_p5", 0),
            "bootstrap_p10": validation.get("bootstrap_p10", 0),
        },
        "=== UI DEFAULTS (Override these for Streamlit) ===": {},
        "ui_defaults": existing_config.get(
            "ui_defaults",
            {
                "initial_capital": 100000,
                "risk_type": "fixed_dollar",
                "default_universe_size": 50,
                "lookback_days": 365,
            },
        ),
        "=== OPTIMIZATION HISTORY ===": {},
        "optimization_history": existing_config.get("optimization_history", []),
    }

    # Add current run to history
    history_entry = {
        "date": final_config["timestamp"][:10],
        "method": "3Tier_AdvancedVectorBT",
        "trials": optimization.get("trials", 0),
        "sharpe": optimization.get("best_trial_metrics", {}).get("sharpe", 0),
        "win_rate": optimization.get("best_trial_metrics", {}).get("win_rate", 0),
        "trades": optimization.get("best_trial_metrics", {}).get("trades", 0),
        "pbo_score": validation.get("pbo_score", 0),
        "approved": validation.get("approved", False),
        "notes": f"{final_config['universe_size']} tickers, {final_config['period']['start']} to {final_config['period']['end']}",
    }
    streamlit_config["optimization_history"].append(history_entry)

    # Save to file
    with open(output_file, "w") as f:
        json.dump(streamlit_config, f, indent=2, default=str)

    logger.info(f"  ✅ Exported to: {output_file}")
    logger.info(f"  📊 Strategy ready for Streamlit app testing")
    logger.info("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# MASTER PIPELINE
# ══════════════════════════════════════════════════════════════════════════════


def run_pipeline(args) -> Dict[str, Any]:
    """Execute the full 3-tier optimization pipeline."""

    # ================================================================
    # HOLDOUT SET GUARD: 2025-H2 is sacred -- never optimize on it
    # ================================================================
    _HOLDOUT_START = "2025-07-01"
    if str(args.end) > _HOLDOUT_START:
        logger.warning("=" * 70)
        logger.warning(
            "  DATA SNOOPING GUARD: end_date %s exceeds holdout boundary", args.end
        )
        logger.warning(
            "  2025-H2 reserved as sacred OOS holdout. Capping to %s", _HOLDOUT_START
        )
        logger.warning("=" * 70)
        args.end = _HOLDOUT_START

    # Cargar config del patron a optimizar
    signal_type = getattr(args, "signal_type", "breakout")
    pcfg = get_pattern_config(signal_type)
    config_output = getattr(args, "output", pcfg["config_output"])
    # Si el output no fue sobreescrito por el usuario, usar el del plugin
    if config_output == "config/production_config.json" and signal_type != "breakout":
        config_output = pcfg["config_output"]

    logger.info("=" * 70)
    logger.info("3-TIER OPTIMIZATION PIPELINE")
    logger.info("=" * 70)
    logger.info(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"  Signal type: {signal_type} -- {pcfg['description']}")
    logger.info(f"  Config output: {config_output}")
    logger.info(f"  Period: {args.start} to {args.end}")
    logger.info(f"  Tickers: {args.tickers}")
    logger.info(f"  Trials: {args.trials}")
    logger.info(f"  Capital: ${args.capital:,.0f}")

    screener_name = getattr(args, "screener", None)

    # ── Load Tier 3 (Institutional Risk) ──────────────────────────────────
    validate_tier3_params()
    tier3_raw = get_tier3_config()
    tier3_engine = build_tier3_engine_params(tier3_raw)

    logger.info(f"\n  TIER 3 (Institutional - FIXED):")
    logger.info(
        f"    rvol_danger/warning: {tier3_raw['rvol_danger']}/{tier3_raw['rvol_warning']}"
    )
    logger.info(f"    max_exposure: {tier3_raw['max_exposure_pct'] * 100:.0f}%")
    logger.info(f"    max_stop_hard: {tier3_raw.get('max_stop_pct_hard', 'N/A')}")

    # ── Get Universe ──────────────────────────────────────────────────────
    use_pit = getattr(args, "use_pit_universe", False)
    if use_pit:
        from src.data.pit_universe import PointInTimeUniverse

        pit = PointInTimeUniverse()
        universe = pit.get_superset(args.start, args.end)
        logger.info(
            f"\n  Universe (PIT): {len(universe)} tickers (survivorship-bias-free superset)"
        )
        logger.info(f"    First 10: {universe[:10]}")
    elif getattr(args, "ticker_file", None):
        # Load curated universe from file
        from pathlib import Path as _Path

        _tf = _Path(args.ticker_file)
        if not _tf.exists():
            raise FileNotFoundError(f"ticker-file not found: {args.ticker_file}")
        with open(_tf) as _f:
            universe = [
                t.strip() for t in _f.readlines() if t.strip() and not t.startswith("#")
            ]
        logger.info(
            f"\n  Universe (curated file): {len(universe)} tickers from {args.ticker_file}"
        )
    else:
        universe = get_universe_from_db(
            limit=args.tickers, start_date=args.start, end_date=args.end
        )

    if screener_name:
        universe = apply_screener_to_universe(
            universe=universe,
            screener_name=screener_name,
            start_date=args.start,
            end_date=args.end,
        )
    logger.info(f"\n  Universe: {len(universe)} tickers ({', '.join(universe[:5])}...)")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1: Baseline
    # ══════════════════════════════════════════════════════════════════════
    baseline_results, baseline_trades = run_baseline(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        tier3_engine_params=tier3_engine,
        initial_capital=args.capital,
        use_pit_universe=use_pit,
        signal_type=signal_type,  # propagar --signal-type al engine para etiquetado
        screener_name=screener_name,
    )

    # Save baseline trades for analysis
    output_dir = Path("outputs/3tier_optimization")
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_trades.to_csv(output_dir / "baseline_trades.csv", index=False)
    logger.info(f"  Baseline trades saved: {output_dir / 'baseline_trades.csv'}")
    # Guardar tambien con nombre por patron para ML multi-patron
    pattern_trades_path = output_dir / f"baseline_trades_{signal_type}.csv"
    baseline_trades.to_csv(pattern_trades_path, index=False)
    logger.info(f"  Pattern baseline saved: {pattern_trades_path}")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: Derive Tier 2
    # ══════════════════════════════════════════════════════════════════════
    tier2_derived = derive_tier2_filters(
        trades_df=baseline_trades,
        winner_threshold_r=0.0,
        keep_pct=args.keep_pct,
    )

    # Save derived Tier 2
    tier2_path = output_dir / "tier2_derived.json"
    with open(tier2_path, "w") as f:
        json.dump(tier2_derived, f, indent=2, default=str)
    logger.info(f"  Tier 2 filters saved: {tier2_path}")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3: Optimize Tier 1
    # ══════════════════════════════════════════════════════════════════════
    # Load warmstart: para breakout usa production_config.json,
    # para otros patrones intenta cargar su propio config primero.
    warmstart = None
    _ws_path = Path(pcfg["config_output"])
    if not _ws_path.exists() and signal_type != "breakout":
        _ws_path = None  # no warmstart si el config del patron no existe aun
    elif signal_type == "breakout":
        _ws_path = Path("config/production_config.json")
    prod_config_path = _ws_path
    if prod_config_path and prod_config_path.exists():
        try:
            with open(prod_config_path) as f:
                prod = json.load(f)
            # Extract Tier 1 params from production config
            t1 = prod.get("tier1_strategy", prod.get("strategy", {}))
            if t1:
                warmstart = {
                    "tp1_r": t1.get("tp1_r", 1.5),
                    "tp2_r": t1.get("tp2_r", 3.0),
                    "tp1_pct": t1.get("tp1_pct", 0.5),
                    "tp2_pct": t1.get("tp2_pct", 0.35),
                    "score_rs_weight": t1.get("score_rs_weight", 0.7),
                }
                logger.info(
                    f"  Warmstart loaded from production_config.json: {warmstart}"
                )
        except Exception as e:
            logger.warning(f"  Could not load warmstart from production config: {e}")

    best_tier1, best_score, study, _template_engine = optimize_tier1(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        tier2_derived=tier2_derived,
        tier3_engine_params=tier3_engine,
        n_trials=args.trials,
        initial_capital=args.capital,
        use_pit_universe=use_pit,
        optim_seed=getattr(args, "seed", None),
        pattern_config=pcfg,
        warmstart_params=warmstart,
        n_jobs=getattr(args, "jobs", 1),  # PERF Item 3
    )

    # Save trial history
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    study.trials_dataframe().to_csv(output_dir / "optuna_trials.csv", index=False)

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 4: ResearchGate Validation
    # ══════════════════════════════════════════════════════════════════════
    validation_result = None
    promoted_tier1 = None
    best_is_score = best_score

    if not args.skip_validation:
        # Get top 10 trials to find the most robust one (OOS-first selection)
        trials_df = study.trials_dataframe()
        top_trials = (
            trials_df[trials_df["state"] == "COMPLETE"]
            .sort_values("value", ascending=False)
            .head(10)
        )

        logger.info(f"  Validating top {len(top_trials)} trials to find robust candidate...")

        # Walk-forward windows: fechas ABSOLUTAS para evitar validar en 2022
        absolute_windows = [
            ("2019-01-01", "2021-06-01", "2021-06-01", "2022-06-01"),
            ("2019-01-01", "2023-01-01", "2023-01-01", "2024-01-01"),
            ("2019-01-01", "2023-07-01", "2023-07-01", "2025-12-31"),
        ]
        min_windows_required = 1

        for idx, (_, row) in enumerate(top_trials.iterrows()):
            # Reconstruct trial params
            trial_params = {
                k.replace("params_", ""): v
                for k, v in row.items()
                if k.startswith("params_")
            }
            # Add derived runner_pct
            trial_params["runner_pct"] = round(
                1.0 - trial_params.get("tp1_pct", 0.33) - trial_params.get("tp2_pct", 0.33), 2
            )
            
            trial_num = row.get("number", "N/A")
            trial_value = row.get("value", 0)
            
            logger.info(f"\n  [Trial {trial_num}] Testing candidate {idx+1}/{len(top_trials)} (IS Score: {trial_value:.2f})")

            # Base params (Tier 3 + Trial Tier 1 + infrastructure)
            base_params = {
                **tier3_engine,
                **trial_params,
                "mode": "production",
                "fees": 0.001,
                "slippage": 0.001,
                "risk_dollars": int(args.capital * tier3_raw.get("risk_fraction", 0.005)),
                "signal_type": signal_type,
                "require_spy_above_sma50": True,
                "max_vix_threshold": 25.0,
                "use_market_regime_filter": True,
                "block_trades_in_stage3": True,
                "block_trades_in_stage4": True,
                "use_earnings_calendar": False,
                "use_trailing_stop": False,
                "use_composite_sector_scoring": False,
                "require_positive_rs": tier2_derived.get("require_positive_rs", True),
                "use_rs_percentile": tier2_derived.get("use_rs_percentile", True),
                "min_rs_percentile": tier2_derived.get("min_rs_percentile", 70.0),
                "rs_lookback_days": tier2_derived.get("rs_lookback_days", 60),
                "pattern_bonus_high": trial_params.get("pattern_bonus_high", 0.0),
                "pattern_bonus_med": trial_params.get("pattern_bonus_med", 0.0),
                "pattern_bonus_low": trial_params.get("pattern_bonus_low", 0.0),
                "use_pattern_filter": tier2_derived.get("use_pattern_filter", False),
                "min_pattern_confidence": tier2_derived.get("min_pattern_confidence", 0.5),
                "pattern_cache_path": tier2_derived.get("pattern_cache_path", "data/pattern_matrix.pkl"),
                "use_adaptive_filtering": True,
                "use_pit_universe": use_pit,
            }

            all_results = []
            best_fold_result = None
            wf_best_score = -999.0
            windows_passed = 0

            for i, (train_s, train_e, test_s, test_e) in enumerate(absolute_windows, 1):
                train_dates = (train_s, train_e)
                test_dates = (test_s, test_e)

                logger.info(f"    Fold {i}/{len(absolute_windows)}: Train {train_s} / Test {test_s}")

                # Re-derive Tier 2 from TRAIN data only
                _, fold_trades = run_baseline(
                    universe=universe,
                    start_date=train_dates[0],
                    end_date=train_dates[1],
                    tier3_engine_params=tier3_engine,
                    initial_capital=args.capital,
                    use_pit_universe=use_pit,
                    signal_type=signal_type,
                )
                fold_tier2 = derive_tier2_filters(
                    trades_df=fold_trades,
                    winner_threshold_r=0.0,
                    keep_pct=args.keep_pct,
                )

                full_params = {**fold_tier2, **base_params}

                result = validate_with_research_gate(
                    universe=universe,
                    full_params=full_params,
                    train_dates=train_dates,
                    test_dates=test_dates,
                    template_engine=_template_engine,
                )
                all_results.append(result)

                if result.promotion_approved:
                    windows_passed += 1
                    score = result.sharpe_ratio - (result.max_drawdown_pct / 100)
                    if score > wf_best_score:
                        wf_best_score = score
                        best_fold_result = result
                    logger.info(f"      ✅ Fold {i} PASS")
                else:
                    logger.info(f"      ❌ Fold {i} FAIL ({', '.join(result.rejection_reasons[:2])})")

            if windows_passed >= min_windows_required:
                validation_result = best_fold_result
                promoted_tier1 = trial_params
                best_is_score = trial_value
                logger.info(f"  🏆 [Trial {trial_num}] PROMOTED: Passed {windows_passed} windows.")
                break
            else:
                logger.warning(f"  ⚠️  [Trial {trial_num}] REJECTED: Only {windows_passed} windows passed.")

        if promoted_tier1:
            best_tier1 = promoted_tier1
            best_score = best_is_score
        else:
            validation_result = all_results[-1] if all_results else None
            logger.error("  ❌ PIPELINE FAILED: None of the top 10 trials passed Walk-Forward validation.")
    else:
        logger.info("\n  SKIPPING ResearchGate validation (--skip-validation)")


    # ══════════════════════════════════════════════════════════════════════
    # FINAL OUTPUT
    # ══════════════════════════════════════════════════════════════════════
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE COMPLETE - FINAL REPORT")
    logger.info("=" * 70)

    final_config = {
        "timestamp": datetime.now().isoformat(),
        "pipeline": "optimize_3tier",
        "period": {
            "start": args.start,
            "end": args.end,
            "initial_capital": args.capital,
        },
        "universe_size": len(universe),
        "tier3_risk": tier3_raw,
        "tier2_filters": tier2_derived,
        "tier1_strategy": best_tier1,
        "optimization": {
            "trials": args.trials,
            "best_score": best_score,
            "best_trial_metrics": {
                k: v for k, v in study.best_trial.user_attrs.items()
            },
        },
    }

    if validation_result:
        final_config["validation"] = {
            "approved": validation_result.promotion_approved,
            "discovery_passed": validation_result.discovery_passed,
            "validation_passed": validation_result.validation_passed,
            "production_passed": validation_result.productionization_passed,
            "pbo_score": validation_result.pbo_score,
            "sharpe_ratio": validation_result.sharpe_ratio,
            "bootstrap_p5": validation_result.bootstrap_p5,
            "bootstrap_p10": validation_result.bootstrap_p10,
            "max_drawdown_pct": validation_result.max_drawdown_pct,
            "rejection_reasons": validation_result.rejection_reasons,
        }

    # Save final config
    final_path = output_dir / "FINAL_CONFIG.json"
    with open(final_path, "w") as f:
        json.dump(final_config, f, indent=2, default=str)

    # For non-production patterns (vcp, pocket_pivot, flat_base),
    # also copy directly to their config_output path.
    # This keeps config/ in sync after every run.
    _cfg_out = Path(config_output)
    if _cfg_out != Path("config/production_config.json"):
        _cfg_out.parent.mkdir(parents=True, exist_ok=True)
        import shutil as _shutil

        _shutil.copy2(final_path, _cfg_out)
        logger.info(f"  Pattern config saved to: {_cfg_out}")

    # Print summary
    logger.info(f"\n  TIER 3 (Risk - Fixed):")
    logger.info(f"    rvol_danger: {tier3_raw['rvol_danger']}x")
    logger.info(f"    rvol_warning: {tier3_raw['rvol_warning']}x")
    logger.info(f"    max_exposure: {tier3_raw['max_exposure_pct'] * 100:.0f}%")

    logger.info(f"\n  TIER 2 (Quality - Derived from {len(baseline_trades)} trades):")
    for k, v in tier2_derived.items():
        logger.info(f"    {k}: {v}")

    logger.info(f"\n  TIER 1 (Strategy - Optimized, score={best_score:.2f}):")
    for k, v in best_tier1.items():
        logger.info(f"    {k}: {v}")

    # ═══════════════════════════════════════════════════════════════════════
    # REJECTIONS BY TIER (from best trial)
    # ═══════════════════════════════════════════════════════════════════════
    # Re-run best params to get rejection stats
    try:
        # fixed_params lives inside optimize_tier1() -- reconstruct minimal version here
        _rj_base = {
            **tier3_engine,
            **tier2_derived,
            "signal_type": signal_type,
            "mode": "production",
            "fees": 0.001,
            "slippage": 0.001,
            "risk_dollars": int(args.capital * tier3_raw.get("risk_fraction", 0.005)),
            "use_market_regime_filter": True,
            "require_spy_above_sma50": True,
            "max_vix_threshold": 25.0,
            "use_adaptive_filtering": True,
            "use_earnings_calendar": False,
            "use_trailing_stop": False,
        }
        full_best_params = {**_rj_base, **best_tier1}
        rejection_engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            **full_best_params,
        )
        rejection_engine.load_data()
        rejection_engine.run_backtest()

        rejection_stats = getattr(rejection_engine, "rejection_stats_tier", {})
        if rejection_stats:
            tier1_rejections = rejection_stats.get("TIER1", 0)
            tier2_rejections = rejection_stats.get("TIER2", 0)
            tier3_rejections = rejection_stats.get("TIER3", 0)
            total_rejections = tier1_rejections + tier2_rejections + tier3_rejections

            logger.info(f"\n  REJECTIONS BY TIER (Best Trial):")
            logger.info(f"    Tier 1 (Market Safety): {tier1_rejections:,}")
            logger.info(f"    Tier 2 (Quality Filter): {tier2_rejections:,}")
            logger.info(f"    Tier 3 (Optional): {tier3_rejections:,}")
            logger.info(f"    Total Rejections: {total_rejections:,}")
    except Exception as e:
        logger.warning(f"  Could not get rejection stats: {e}")

    if validation_result:
        if validation_result.promotion_approved:
            logger.info(f"\n  VALIDATION: APPROVED FOR PRODUCTION")

            # ══════════════════════════════════════════════════════════════════
            # ================================================================
            # PHASE 5: GOLDEN CONFIG GUARD + AUTO-EXPORT
            # ================================================================
            # _new_sharpe  = walk-forward Sharpe from ResearchGate validation
            # _golden_sharpe = WF Sharpe stamped by the PREVIOUS approved pipeline run
            #   (stored as _oos_sharpe in production_config.json)
            # Rule: new run must beat golden by >=5% to overwrite.
            # Use --force-export to bypass (e.g. after fixing a code bug).
            # ================================================================
            import json as _json

            # Golden path: usar el config del signal_type activo (benchmark por estrategia)
            # Cada estrategia compite contra su propio golden, no contra un global.
            _signal_golden_path = Path(
                pcfg.get("config_output", "config/production_config.json")
            )
            _golden_path = (
                _signal_golden_path
                if _signal_golden_path.exists()
                else Path("config/production_config.json")
            )
            _new_sharpe = getattr(validation_result, "sharpe_ratio", 0.0)
            _new_dd = getattr(validation_result, "max_drawdown_pct", 999.0)
            _golden_sharpe = 0.0
            _golden_date = "none"
            _should_export = True
            _reason = "no golden config found"
            _margin = 0.05  # must improve by >=5%

            if _golden_path.exists():
                try:
                    _golden = _json.load(open(_golden_path))
                    # _oos_sharpe: stamped by this pipeline on the previous approved run
                    # Fallback: _sharpe_validation (legacy field from pattern configs)
                    # Fallback: performance.sharpe_ratio (legacy field)
                    _golden_sharpe = _golden.get(
                        "_oos_sharpe",
                        _golden.get(
                            "_sharpe_validation",
                            _golden.get("performance", {}).get("sharpe_ratio", 0.0),
                        ),
                    )
                    _golden_date = _golden.get(
                        "_oos_stamped",
                        _golden.get(
                            "_last_updated", _golden.get("timestamp", "unknown")
                        ),
                    )
                except Exception as _ge:
                    logger.warning(f"  Could not read golden config: {_ge}")
            logger.info(
                f"  Golden file    : {_golden_path.name}  (signal: {signal_type})"
            )

            # --force-export bypasses the guard
            if getattr(args, "force_export", False):
                _should_export = True
                _reason = f"--force-export flag set by user (golden={_golden_sharpe:.3f} bypassed)"
            elif _golden_sharpe > 0 and _new_sharpe < _golden_sharpe * (1 + _margin):
                _should_export = False
                _gdate = (
                    _golden_date[:10]
                    if len(str(_golden_date)) >= 10
                    else str(_golden_date)
                )
                _reason = (
                    f"WF Sharpe {_new_sharpe:.3f} does not improve golden "
                    f"{_golden_sharpe:.3f} by >{_margin * 100:.0f}% "
                    f"(need >= {_golden_sharpe * (1 + _margin):.3f}, golden from {_gdate})"
                )
            else:
                _gdate = (
                    _golden_date[:10]
                    if len(str(_golden_date)) >= 10
                    else str(_golden_date)
                )
                _reason = (
                    f"WF Sharpe {_new_sharpe:.3f} beats golden "
                    f"{_golden_sharpe:.3f} (golden from {_gdate})"
                )

            logger.info("=" * 60)
            logger.info("  GOLDEN CONFIG GUARD")
            logger.info("=" * 60)
            logger.info(
                f"  New  WF Sharpe : {_new_sharpe:.4f}  (MaxDD: {_new_dd:.1f}%)"
            )
            logger.info(f"  Golden file    : {_golden_path.name}")
            logger.info(f"  Golden Sharpe  : {_golden_sharpe:.4f}")
            logger.info(f"  Required margin: +{_margin * 100:.0f}%")
            logger.info(
                f"  Decision       : {'EXPORT' if _should_export else 'PRESERVE GOLDEN'}"
            )
            logger.info(f"  Reason         : {_reason}")
            logger.info("=" * 60)

            if not args.skip_streamlit_export:
                if _should_export:
                    try:
                        export_to_streamlit_config(
                            final_config=final_config,
                            output_path=args.output,
                            backup=True,
                        )
                        # Stamp the WF Sharpe into production_config for next run comparison
                        try:
                            _pc = _json.load(open(args.output))
                            _pc["_oos_sharpe"] = round(_new_sharpe, 4)
                            _pc["_oos_max_dd"] = round(_new_dd, 2)
                            _pc["_oos_stamped"] = datetime.now().isoformat()
                            with open(args.output, "w") as _pf:
                                _json.dump(_pc, _pf, indent=2, default=str)
                            logger.info(
                                f"  _oos_sharpe={_new_sharpe:.4f} stamped in {args.output}"
                            )
                        except Exception as _se:
                            logger.warning(f"  Could not stamp _oos_sharpe: {_se}")
                        logger.info(f"  Exported to: {args.output}")
                        logger.info(f"  Run: streamlit run app.py")
                    except Exception as e:
                        logger.error(f"  Export failed: {e}")
                else:
                    logger.warning(f"  production_config.json NOT overwritten.")
                    logger.info(
                        f"  New config: outputs/3tier_optimization/FINAL_CONFIG.json"
                    )
                    logger.info(
                        f"  To force-export: python optimize_3tier.py --force-export"
                    )
            else:
                logger.info(f"  Skipped export (--skip-streamlit-export)")
            logger.info(f"\n  VALIDATION: REJECTED")
            for reason in validation_result.rejection_reasons:
                logger.info(f"    - {reason}")
            logger.info(f"\n  ❌ Strategy NOT exported (failed validation)")

    logger.info(f"\n  Output: {final_path}")
    logger.info("=" * 70)

    # ============================================================
    # AUTO-EXPAND RANGES: detectar params en limite y expandir
    # ============================================================
    try:
        import subprocess, sys

        expand_result = subprocess.run(
            [sys.executable, "auto_expand_ranges.py"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        if expand_result.stdout:
            for line in expand_result.stdout.strip().split("\n"):
                logger.info(line)
        if expand_result.returncode != 0 and expand_result.stderr:
            logger.warning(f"auto_expand_ranges: {expand_result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"No se pudo ejecutar auto_expand_ranges: {e}")

    return final_config


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="3-Tier Optimization Pipeline (Unified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python optimize_3tier.py --trials 100 --tickers 50
  python optimize_3tier.py --trials 200 --tickers 80 --start 2022-01-01 --end 2024-12-31
  python optimize_3tier.py --trials 50 --skip-validation   # Dev/quick mode
  python optimize_3tier.py --keep-pct 75                   # Stricter Tier 2 filters
        """,
    )

    parser.add_argument(
        "--trials",
        type=int,
        default=100,
        help="Number of Optuna trials for Tier 1 optimization (default: 100)",
    )
    parser.add_argument(
        "--tickers",
        type=int,
        default=50,
        help="Number of tickers in universe (default: 50). Ignored if --ticker-file is set.",
    )
    parser.add_argument(
        "--ticker-file",
        type=str,
        default=None,
        help="Path to file with one ticker per line (e.g. config/universe_sp500_curated.txt). "
        "Overrides --tickers. Use for curated live-trading universe.",
    )
    parser.add_argument(
        "--screener",
        type=str,
        default=None,
        help="Optional screener name to filter the universe before optimization.",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2021-01-01",
        help="Backtest start date (default: 2021-01-01). HOLDOUT: never use 2025-07-01 to 2025-12-31 for optimization.",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2025-06-30",
        help="Backtest end date. Default capped at 2025-06-30 to preserve 2025-H2 as sacred holdout.",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000,
        help="Initial capital (default: 100000)",
    )
    parser.add_argument(
        "--keep-pct",
        type=float,
        default=95,
        help="Percent of winners to keep when deriving Tier 2 (default: 95)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip ResearchGate validation (for quick dev runs)",
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        default=False,
        help="Bypass golden guard and force-export. Use after fixing a bug that depressed performance.",
    )
    parser.add_argument(
        "--skip-streamlit-export",
        action="store_true",
        help="Skip auto-export to Streamlit config (for testing)",
    )
    parser.add_argument(
        "--use-pit-universe",
        action="store_true",
        help="Use Point-in-Time S&P 500 universe (eliminates survivorship bias)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="config/production_config.json",
        help="Output path for Streamlit config (default: config/production_config.json)",
    )
    parser.add_argument(
        "--signal-type",
        type=str,
        default="breakout",
        help="Pattern to optimize: breakout | vcp | pocket_pivot | flat_base. "
        "Each has its own config output and Optuna search space. "
        "Run with --list-patterns to see all available options.",
    )
    parser.add_argument(
        "--list-patterns",
        action="store_true",
        help="List all available signal types and exit.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for Optuna (default: None = non-deterministic exploration). "
        "Set e.g. --seed 42 to reproduce a specific run exactly.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Numero de workers paralelos para Optuna (default: 1 = secuencial). "
        "Recomendado: --jobs 2. Con n>1 se desactiva la barra de progreso. "
        "Thread-safety garantizada via clone_with_params (Item 1).",
    )
    parser.add_argument(
        "--no-warmstart",
        action="store_true",
        help="Skip loading production_config.json as warmstart for Optuna.",
    )

    args = parser.parse_args()
    if getattr(args, "list_patterns", False):
        print(list_patterns())
        return
    # Normalizar signal_type (guion a guion bajo)
    args.signal_type = getattr(args, "signal_type", "breakout").replace("-", "_")
    run_pipeline(args)


if __name__ == "__main__":
    main()
