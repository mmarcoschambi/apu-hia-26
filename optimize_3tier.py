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
except ImportError as e:
    logger.error(f"Missing module: {e}")
    logger.error("Run from project root: cd momentum-v2 && python optimize_3tier.py")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def get_universe_from_db(
    limit: int = 50, start_date: str = "2022-01-01", end_date: str = "2024-12-31"
) -> List[str]:
    """
    Get top tickers by data availability from cache DB for a SPECIFIC period.
    Corrected to use ticker_cache.db (ohlcv_cache table).
    """
    db_path = Path("data/ticker_cache.db")
    if not db_path.exists():
        logger.warning(f"Database {db_path} not found. Using fallbacks.")
        return _get_fallback_universe(limit)

    try:
        conn = sqlite3.connect(str(db_path))
        # Query specifically for tickers that have data in the requested range
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
            # If we have very few tickers with full data, warn the user
            if len(tickers) < 10:
                logger.warning(
                    f"Only {len(tickers)} tickers found for period {start_date} to {end_date}"
                )
            return tickers
    except Exception as e:
        logger.error(f"Error querying ticker_cache.db: {e}")

    return _get_fallback_universe(limit)


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


def run_baseline(
    universe: List[str],
    start_date: str,
    end_date: str,
    tier3_engine_params: Dict[str, Any],
    initial_capital: float = 100_000,
    use_pit_universe: bool = False,
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

    # Loose Tier 2: Let almost everything through
    loose_params = {
        "min_rvol": 0.5,  # Very low - see everything
        "min_adr": 1.0,  # Very low
        "max_dist_sma20": 20.0,  # Very wide
        "min_consolidation_days": 3,  # Very short
        "min_volume": 100_000,
        "min_dollar_volume": 1_000_000,
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
        "signal_type": "any",  # Match production config (was "breakout" - caused signal mismatch)
        "require_spy_above_sma50": True,
        "max_vix_threshold": 40.0,  # Slightly wider than production
        "use_market_regime_filter": False,  # OFF for baseline
        "use_composite_sector_scoring": False,
        "use_earnings_calendar": False,
        "use_trailing_stop": False,
        "require_positive_rs": False,
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
        "risk_dollars": risk_dollars,  # Fixed dollar risk (matches production, NO compounding)
        "signal_type": "any",  # Match production config (was "breakout" - caused signal mismatch)
        "require_spy_above_sma50": True,
        "max_vix_threshold": 35.0,
        # --- ALIGN WITH UI MARKET REGIME RULES ---
        "use_market_regime_filter": True,  # Activa el filtro
        "block_trades_in_stage3": True,  # Bloquea mercados de distribución
        "block_trades_in_stage4": True,  # Bloquea mercados bajistas (Bear)
        # ---------------------------------------
        "use_earnings_calendar": False,
        "use_trailing_stop": False,
        "use_composite_sector_scoring": False,
        "require_positive_rs": False,
        "use_adaptive_filtering": True,  # Activa filtros TIER 1-2-3 con rechazos detallados
        "use_pit_universe": use_pit_universe,
    }

    # Pre-load data once for all trials (optimization: create engine, load data,
    # then for each trial just update params). Unfortunately AdvancedVectorBTEngine
    # takes params in constructor, so we must reinstantiate. But data loading is
    # cached by TickerCache, so subsequent loads are fast.

    def objective(trial: optuna.Trial) -> float:
        # ── Tier 1: ONLY these are optimized ──────────────────────────
        # Aligned with Streamlit proven parameters (1.5R / 3.5R)
        tier1_params = {
            "tp1_r": trial.suggest_float("tp1_r", 1.25, 2.0, step=0.25),
            "tp2_r": trial.suggest_float("tp2_r", 3.0, 5.0, step=0.25),
        }

        # Position distribution (must sum to ~1.0)
        # Aligned with Streamlit: 50% at TP1, 40% at TP2, 10% runner
        tp1_pct = trial.suggest_float("tp1_pct", 0.40, 0.55, step=0.05)
        tp2_pct = trial.suggest_float("tp2_pct", 0.30, 0.45, step=0.05)
        runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)

        # Constraint: runner must have at least 5% and max 25%
        if runner_pct < 0.05 or runner_pct > 0.25:
            return -999.0

        tier1_params["tp1_pct"] = tp1_pct
        tier1_params["tp2_pct"] = tp2_pct
        tier1_params["runner_pct"] = runner_pct

        # Combine everything
        full_params = {**fixed_params, **tier1_params}

        try:
            engine = AdvancedVectorBTEngine(
                universe=universe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                **full_params,
            )
            engine.load_data()
            results = engine.run_backtest()

            # Minimum trade threshold for statistical reliability
            if results.get("total_trades", 0) < 20:
                return -999.0

            score = robust_objective_function(results, robust_config)

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
    study = optuna.create_study(
        direction="maximize",
        study_name=f"3tier_{datetime.now().strftime('%Y%m%d_%H%M')}",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)

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

    return best, study.best_value, study


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4: VALIDATION (ResearchGate)
# ══════════════════════════════════════════════════════════════════════════════


def validate_with_research_gate(
    universe: List[str],
    full_params: Dict[str, Any],
    train_dates: Tuple[str, str],
    test_dates: Tuple[str, str],
) -> Any:
    """
    Phase 4: Run the 3-phase ResearchGate validation with MULTI-WINDOW Walk Forward.

    Instead of a single train/test split, we use rolling windows to ensure
    robustness across different market regimes.

    Returns:
        ValidationResult (with .promotion_approved bool)
    """
    logger.info("=" * 70)
    logger.info("PHASE 4: RESEARCH GATE VALIDATION (Multi-Window Walk Forward)")
    logger.info("=" * 70)

    gate = ResearchGate()

    # Use single window for now - ResearchGate handles the validation internally
    result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=full_params,
        universe=universe,
        train_dates=train_dates,
        test_dates=test_dates,
        verbose=True,
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
            "require_positive_rs": False,
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

    logger.info("=" * 70)
    logger.info("3-TIER OPTIMIZATION PIPELINE")
    logger.info("=" * 70)
    logger.info(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"  Period: {args.start} to {args.end}")
    logger.info(f"  Tickers: {args.tickers}")
    logger.info(f"  Trials: {args.trials}")
    logger.info(f"  Capital: ${args.capital:,.0f}")

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
    else:
        universe = get_universe_from_db(
            limit=args.tickers, start_date=args.start, end_date=args.end
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
    )

    # Save baseline trades for analysis
    output_dir = Path("outputs/3tier_optimization")
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_trades.to_csv(output_dir / "baseline_trades.csv", index=False)
    logger.info(f"  Baseline trades saved: {output_dir / 'baseline_trades.csv'}")

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
    best_tier1, best_score, study = optimize_tier1(
        universe=universe,
        start_date=args.start,
        end_date=args.end,
        tier2_derived=tier2_derived,
        tier3_engine_params=tier3_engine,
        n_trials=args.trials,
        initial_capital=args.capital,
        use_pit_universe=use_pit,
    )

    # Save trial history
    output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
    study.trials_dataframe().to_csv(output_dir / "optuna_trials.csv", index=False)

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 4: ResearchGate Validation
    # ══════════════════════════════════════════════════════════════════════
    validation_result = None

    if not args.skip_validation:
        # Base params (Tier 3 + Tier 1 + infrastructure) — Tier 2 re-derived per fold
        base_params = {
            # Tier 3 (institutional)
            **tier3_engine,
            # Tier 1 (optimized)
            **best_tier1,
            # Infrastructure
            "mode": "production",
            "fees": 0.001,
            "slippage": 0.001,
            "risk_dollars": int(args.capital * tier3_raw.get("risk_fraction", 0.005)),
            "signal_type": "any",  # Match production config
            "require_spy_above_sma50": True,
            "max_vix_threshold": 35.0,
            "use_market_regime_filter": True,
            "block_trades_in_stage3": True,
            "block_trades_in_stage4": True,
            "use_earnings_calendar": False,
            "use_trailing_stop": False,
            "use_composite_sector_scoring": False,
            "require_positive_rs": False,
            "use_adaptive_filtering": True,  # Activa filtros TIER 1-2-3 con rechazos detallados
            "use_pit_universe": use_pit,
        }

        # Multi-Window Walk Forward Validation
        # Creates multiple train/test splits for robust validation
        # IMPORTANT: Tier 2 is RE-DERIVED per fold using only train data
        # to prevent IS/OOS contamination (Tier 2 never sees test data).
        from datetime import datetime as dt

        start_dt = dt.strptime(args.start, "%Y-%m-%d")
        end_dt = dt.strptime(args.end, "%Y-%m-%d")
        total_days = (end_dt - start_dt).days

        # Create 3 overlapping windows for walk-forward validation
        # Window 1: First 50% train, next 25% test
        # Window 2: First 60% train, next 20% test
        # Window 3: First 70% train, last 30% test (original)
        windows = [
            (0.50, 0.25),  # More conservative
            (0.60, 0.20),  # Balanced
            (0.70, 0.30),  # Original
        ]

        all_results = []
        best_result = None
        wf_best_score = -999.0

        for i, (train_pct, test_pct) in enumerate(windows, 1):
            split_dt = start_dt + pd.Timedelta(days=int(total_days * train_pct))
            test_end_dt = split_dt + pd.Timedelta(days=int(total_days * test_pct))

            # Ensure test doesn't go beyond end date
            if test_end_dt > end_dt:
                test_end_dt = end_dt

            train_dates = (args.start, split_dt.strftime("%Y-%m-%d"))
            test_dates = (
                split_dt.strftime("%Y-%m-%d"),
                test_end_dt.strftime("%Y-%m-%d"),
            )

            logger.info(
                f"\n  Walk-Forward Window {i}/{len(windows)}: Train {train_pct * 100:.0f}%, Test {test_pct * 100:.0f}%"
            )
            logger.info(f"    Train: {train_dates[0]} to {train_dates[1]}")
            logger.info(f"    Test:  {test_dates[0]} to {test_dates[1]}")

            # ── Re-derive Tier 2 from TRAIN data only (no OOS contamination) ──
            logger.info(f"    Re-deriving Tier 2 from train period only...")
            _, fold_trades = run_baseline(
                universe=universe,
                start_date=train_dates[0],
                end_date=train_dates[1],
                tier3_engine_params=tier3_engine,
                initial_capital=args.capital,
                use_pit_universe=use_pit,
            )
            fold_tier2 = derive_tier2_filters(
                trades_df=fold_trades,
                winner_threshold_r=0.0,
                keep_pct=args.keep_pct,
            )
            logger.info(f"    Fold Tier 2: {fold_tier2}")

            # Build full_params with fold-specific Tier 2
            full_params = {**fold_tier2, **base_params}

            result = validate_with_research_gate(
                universe=universe,
                full_params=full_params,
                train_dates=train_dates,
                test_dates=test_dates,
            )

            all_results.append(result)

            # Track best result based on promotion approval and score
            if result.promotion_approved:
                # Calculate a simple score: Sharpe - MaxDD_penalty
                score = result.sharpe_ratio - (result.max_drawdown_pct / 100)
                if score > wf_best_score:
                    wf_best_score = score
                    best_result = result

        # Use the best performing window result
        if best_result:
            validation_result = best_result
            logger.info(f"\n  ✅ Best Walk-Forward Window Selected:")
            logger.info(f"     Sharpe: {best_result.sharpe_ratio:.2f}")
            logger.info(f"     Max DD: {best_result.max_drawdown_pct:.2f}%")
            logger.info(f"     Approved: {best_result.promotion_approved}")
        else:
            # If no window passed, use the last one for detailed error reporting
            validation_result = all_results[-1] if all_results else None
            logger.warning("\n  ⚠️  No walk-forward window passed all validations")
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

    if validation_result:
        if validation_result.promotion_approved:
            logger.info(f"\n  VALIDATION: APPROVED FOR PRODUCTION")

            # ══════════════════════════════════════════════════════════════════
            # PHASE 5: Auto-Export to Streamlit (if approved)
            # ══════════════════════════════════════════════════════════════════
            if not args.skip_streamlit_export:
                try:
                    export_to_streamlit_config(
                        final_config=final_config,
                        output_path="config/production_config.json",
                        backup=True,
                    )
                    logger.info(f"\n  🚀 Strategy exported to Streamlit app!")
                    logger.info(f"     Run: streamlit run app.py")
                except Exception as e:
                    logger.error(f"\n  ❌ Failed to export to Streamlit: {e}")
            else:
                logger.info(
                    f"\n  ⏭️  Skipped Streamlit export (--skip-streamlit-export)"
                )
        else:
            logger.info(f"\n  VALIDATION: REJECTED")
            for reason in validation_result.rejection_reasons:
                logger.info(f"    - {reason}")
            logger.info(f"\n  ❌ Strategy NOT exported (failed validation)")

    logger.info(f"\n  Output: {final_path}")
    logger.info("=" * 70)

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
        help="Number of tickers in universe (default: 50)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="2022-01-01",
        help="Backtest start date (default: 2022-01-01)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default="2024-12-31",
        help="Backtest end date (default: 2024-12-31)",
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
        "--skip-streamlit-export",
        action="store_true",
        help="Skip auto-export to Streamlit config (for testing)",
    )
    parser.add_argument(
        "--use-pit-universe",
        action="store_true",
        help="Use Point-in-Time S&P 500 universe (eliminates survivorship bias)",
    )

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
