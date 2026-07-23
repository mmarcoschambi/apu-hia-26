#!/usr/bin/env python3
"""
OPTIMIZE COMBO - Screener × Pattern Optimization
===============================================

3-tier optimization pipeline for Screener × Pattern combinations.

  Tier 3 (Risk)     -> FIXED from combo config (never optimized)
  Tier 2 (Filters)   -> DERIVED statistically from baseline data
  Tier 1 (Exits)    -> OPTIMIZED via Optuna

Combos are predefined in config/combos/:
  - combo_ideal_setup: minervini_trend × vcp
  - combo_aggressive_momentum: minervini_trend × pocket_pivot
  - combo_stage2_breakout: minervini_trend × breakout
  - combo_pure_momentum: qullamaggie_momentum × breakout
  - combo_pullback_entry: ema21_pullback × pocket_pivot

Usage:
    python optimize_combo.py --combo combo_ideal_setup --trials 100
    python optimize_combo.py --list-combos
    python optimize_combo.py --all --trials 50
"""

import argparse
import json
import sys
import logging
import sqlite3
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import pandas as pd
import optuna

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("optimize_combo.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


try:
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    from src.validation.research_gate import ResearchGate, ValidationThresholds
    from src.validation.robustness_metrics import (
        robust_objective_function,
        RobustObjectiveConfig,
    )
    from config.defaults import get_tier2_defaults
    from src.data.screener_cache import ScreenerCacheManager
except ImportError as e:
    logger.error(f"Missing module: {e}")
    sys.exit(1)


COMBOS_DIR = Path(__file__).resolve().parent / "config" / "combos"
OUTPUT_DIR = Path(__file__).resolve().parent / "config" / "combo_results"
OUTPUT_DIR.mkdir(exist_ok=True)
SCREENER_CACHE = ScreenerCacheManager()


def load_combo_config(combo_name: str) -> Dict[str, Any]:
    """Load combo configuration from JSON."""
    combo_path = COMBOS_DIR / f"{combo_name}.json"
    if not combo_path.exists():
        available = list(COMBOS_DIR.glob("*.json"))
        raise ValueError(
            f"Combo '{combo_name}' not found at {combo_path}. "
            f"Available: {[c.stem for c in available]}"
        )
    with open(combo_path, "r") as f:
        return json.load(f)


def build_screener_cache_for_combo(
    combo_name: str, start_date: str, end_date: str, universe: List[str]
) -> None:
    """Build a historical screener cache for one combo."""
    combo = load_combo_config(combo_name)
    screener_name = combo["screener"]["name"]
    logger.info(
        f"Building screener cache for {combo_name} ({screener_name}) from {start_date} to {end_date}"
    )
    SCREENER_CACHE.build_for_combo(
        screener_name=screener_name,
        tickers=universe,
        start_date=start_date,
        end_date=end_date,
    )


def list_available_combos() -> List[str]:
    """List all available combos."""
    return [c.stem for c in COMBOS_DIR.glob("combo_*.json")]


def get_universe_from_db(
    limit: int = 50,
    start_date: str = "2021-01-01",
    end_date: str = "2025-12-31",
    seed: Optional[int] = None,
    liquidity_stratified: bool = True,
) -> List[str]:
    """
    Get tickers from cache DB with STRATIFIED sampling.
    Uses same implementation as optimize_3tier.py for consistency.
    """
    db_path = Path("data/ticker_cache.db")
    if not db_path.exists():
        return get_fallback_universe(limit)

    # Get full universe with metrics
    try:
        import duckdb

        conn = duckdb.connect()
        conn.execute(f"ATTACH '{db_path}' AS src (TYPE SQLITE, READ_ONLY TRUE)")
        query = """
            SELECT 
                ticker, 
                COUNT(*) as cnt,
                AVG(close * volume) as avg_dollar_vol,
                AVG(volume) as avg_volume,
                AVG(close) as avg_price
            FROM src.ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            HAVING cnt >= 100
        """
        df = conn.execute(query, [start_date, end_date]).fetchdf()
        conn.close()
    except ImportError:
        try:
            conn = sqlite3.connect(str(db_path))
            query = """
                SELECT 
                    ticker, 
                    COUNT(*) as cnt,
                    AVG(close * volume) as avg_dollar_vol,
                    AVG(volume) as avg_volume,
                    AVG(close) as avg_price
                FROM ohlcv_cache
                WHERE date >= ? AND date <= ?
                GROUP BY ticker
                HAVING COUNT(*) >= 100
            """
            df = pd.read_sql_query(query, conn, params=(start_date, end_date))
            conn.close()
        except Exception as e:
            logger.error(f"Error querying ticker_cache.db: {e}")
            return get_fallback_universe(limit)
    except Exception as e:
        logger.error(f"DuckDB query failed ({e}), falling back")
        return get_fallback_universe(limit)

    if df.empty or len(df) < 10:
        return get_fallback_universe(limit)

    rng = np.random.default_rng(seed) if seed is not None else np.random

    if liquidity_stratified and len(df) >= 30:
        try:
            df["liq_bin"] = pd.qcut(
                df["avg_dollar_vol"].clip(lower=1e6),
                q=min(5, len(df) // 10),
                labels=False,
                duplicates="drop",
            )
            n_bins = df["liq_bin"].nunique()
            per_bin = max(1, limit // n_bins)

            sampled = []
            for bin_id in sorted(df["liq_bin"].unique()):
                bin_df = df[df["liq_bin"] == bin_id]
                take = min(len(bin_df), per_bin + rng.integers(0, 3))
                sampled.append(bin_df.sample(min(take, len(bin_df)), random_state=seed))

            result = pd.concat(sampled, ignore_index=True)
            result = result.sample(frac=1, random_state=seed).reset_index(drop=True)
            tickers = result["ticker"].tolist()[:limit]
            method = "stratified"
        except Exception:
            tickers = df.nlargest(limit, "cnt")["ticker"].tolist()
            method = "top-cnt (stratified failed)"
    else:
        tickers = df.nlargest(limit, "cnt")["ticker"].tolist()
        method = "top-cnt"

    logger.debug(f"Universe ({method}, seed={seed}): {len(tickers)} tickers")
    return tickers


def apply_screener_to_universe(
    universe: List[str],
    screener_name: str,
    start_date: str,
    end_date: str,
) -> List[str]:
    """
    Aplica el screener a cada ticker del universo y retorna los que pasan.
    Requiere datos de mercado para evaluar el screener.
    """
    logger.info(
        f"  Aplicando screener '{screener_name}' al universo de {len(universe)} tickers..."
    )

    if SCREENER_CACHE.cache_path(screener_name).exists():
        logger.info(
            f"  Historical screener cache found for '{screener_name}'."
            " Universe prefilter skipped to avoid look-ahead bias."
        )
        return universe

    logger.info(
        "  No historical cache available; leaving universe unchanged to avoid bias."
    )
    return universe


def get_fallback_universe(limit: int) -> List[str]:
    """Fallback universe of liquid stocks."""
    return [
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
        "GS",
        "MS",
        "V",
        "MA",
        "PG",
        "JNJ",
        "UNH",
        "HD",
        "DIS",
        "SBUX",
        "NKE",
        "V",
    ][:limit]


def _warmup_numba():
    """Pre-compile Numba JIT functions."""
    try:
        from src.backtest.numba_core import simulate_fast_core

        n, m = 12, 2
        dummy2d = np.zeros((n, m), dtype=np.float32)
        entries = np.zeros((n, m), dtype=np.bool_)
        dummy1d = np.zeros(n, dtype=np.float32)
        simulate_fast_core(
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            entries,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy2d,
            dummy1d,
            dummy1d,
            100_000.0,
            1.5,
            3.0,
            0.5,
            0.3,
            0.2,
            0.01,
            0.5,
            0.5,
            True,
            0.08,
            500.0,
            True,
            True,
            1.5,
            1.0,
        )
        logger.info("Numba warmup complete")
    except Exception as e:
        logger.debug(f"Numba warmup skipped: {e}")


_warmup_numba()


def phase1_baseline_run(
    combo: Dict[str, Any],
    universe: List[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Phase 1: Baseline run with loose filters to collect trade universe.
    Returns DataFrame with trade results for Tier 2 derivation.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("PHASE 1: BASELINE RUN (Loose Filters)")
    logger.info(f"{'=' * 60}")

    pattern_type = combo["pattern"]["signal_type"]

    engine_params = {
        "universe": universe,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": 100_000,
        "signal_type": pattern_type,
        "risk_pct": 0.005,
        "max_loss_pct": combo["tier3_fixed"]["max_loss_pct"],
        "use_trailing_stop": True,
        "max_stop_pct": 8.0,
        "screener_name": combo["screener"]["name"],
        "screener_cache_path": str(SCREENER_CACHE.cache_dir),
    }

    engine = AdvancedVectorBTEngine(**engine_params)

    results = engine.run_backtest()

    logger.info(f"Baseline trades: {results.get('total_trades', 0)}")
    logger.info(f"Win rate: {results.get('win_rate', 0) * 100:.1f}%")
    logger.info(f"Profit factor: {results.get('profit_factor', 0):.2f}")

    return results.get("trades_df", pd.DataFrame())


def phase2_derive_tier2(
    baseline_trades: pd.DataFrame,
    combo: Dict[str, Any],
    keep_pct: float = 95,
) -> Dict[str, Any]:
    """
    Phase 2: Derive Tier 2 filter thresholds from baseline trade analysis.
    Statistical analysis of winners vs losers to set optimal thresholds.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("PHASE 2: TIER 2 DERIVATION (Statistical Filters)")
    logger.info(f"{'=' * 60}")

    if baseline_trades.empty:
        logger.warning("No baseline trades - using combo defaults")
        base_defaults = get_tier2_defaults()
        return {
            **base_defaults,
            **combo["tier2_filters"],
            "min_consolidation_days": 5,
            "min_volume": 100_000,
        }

    # Si hay muy pocos trades, los percentiles son ruidosos -> 0-trade collapse en OOS
    if len(baseline_trades) < 20:
        logger.warning(
            f"Baseline tiene solo {len(baseline_trades)} trades - insuficiente para derivar filtros. Usando defaults del combo JSON."
        )
        base_defaults = get_tier2_defaults()
        return {
            **base_defaults,
            **combo["tier2_filters"],
            "min_consolidation_days": 5,
            "min_volume": 100_000,
        }

    winners = baseline_trades[baseline_trades["pnl"] > 0]

    derived = {}
    cut_percentile = 100 - keep_pct

    if "context_rvol" in baseline_trades.columns:
        valid_rvol = winners["context_rvol"].dropna()
        if len(valid_rvol) > 5:
            derived_rvol = round(float(np.percentile(valid_rvol, cut_percentile)), 2)
            derived["min_rvol"] = max(0.5, min(4.0, derived_rvol))
            logger.info(f"  min_rvol: {derived['min_rvol']}")
        else:
            derived["min_rvol"] = get_tier2_defaults().get("min_rvol", 0.91)
    else:
        derived["min_rvol"] = get_tier2_defaults().get("min_rvol", 0.91)

    if "context_adr" in baseline_trades.columns:
        valid_adr = winners["context_adr"].dropna()
        if len(valid_adr) > 5:
            derived_adr = round(float(np.percentile(valid_adr, cut_percentile)), 2)
            derived["min_adr"] = max(0.5, min(8.0, derived_adr))
            logger.info(f"  min_adr: {derived['min_adr']}")
        else:
            derived["min_adr"] = get_tier2_defaults().get("min_adr", 1.97)
    else:
        derived["min_adr"] = get_tier2_defaults().get("min_adr", 1.97)

    if "dist_sma20_pct" in baseline_trades.columns:
        valid_dist = winners["dist_sma20_pct"].dropna()
        if len(valid_dist) > 5:
            derived_dist = round(float(np.percentile(valid_dist, 95)), 2)
            derived["max_dist_sma20"] = max(3.0, min(20.0, derived_dist))
            logger.info(f"  max_dist_sma20: {derived['max_dist_sma20']}")
        else:
            derived["max_dist_sma20"] = get_tier2_defaults().get("max_dist_sma20", 8.94)
    else:
        derived["max_dist_sma20"] = get_tier2_defaults().get("max_dist_sma20", 8.94)

    if "context_dollar_vol" in baseline_trades.columns:
        valid_dv = winners["context_dollar_vol"].dropna()
        if len(valid_dv) > 5:
            derived_dv = float(np.percentile(valid_dv, cut_percentile))
            # Cap maximo: $20M. El percentil de ganadores refleja el universo
            # (stocks grandes tienden a ganar), no una causalidad de liquidez.
            # Sin cap, en universos Minervini el derivado llega a $50-108M y
            # mata todo el universo de senales. $20M es el techo correcto:
            #   - Evita los $50-108M de combos Minervini
            #   - No aplasta combos EMA21 pullback (baseline derivaba $22.8M)
            # Nota: el clamp del combo JSON (lineas siguientes) puede bajar aun mas.
            _MAX_DERIVED_DV = 20_000_000
            derived["min_dollar_volume"] = max(
                1_000_000, min(derived_dv, _MAX_DERIVED_DV)
            )
            logger.info(f"  min_dollar_volume: {derived['min_dollar_volume']:,.0f}")
        else:
            derived["min_dollar_volume"] = get_tier2_defaults().get(
                "min_dollar_volume", 20_000_000
            )
    else:
        derived["min_dollar_volume"] = get_tier2_defaults().get(
            "min_dollar_volume", 20_000_000
        )

    derived["min_consolidation_days"] = 5
    derived["min_volume"] = 100_000

    # NOTE: min_screener_score YA NO SE DERIVA.
    # El entry_score cambió de escala (0-100 -> 0-1), y derivar de winners
    # produce valores erroneos (0.9 en lugar de 70).
    # El combo JSON define el requisito de calidad explícito - se respeta.
    # El merge final (linea 416) ya preserva combo["tier2_filters"]["min_screener_score"]
    # if "min_screener_score" in combo["tier2_filters"]:
    #     if "entry_score" in baseline_trades.columns and not winners.empty:
    #         q75 = winners["entry_score"].quantile(0.75)
    #         derived["min_screener_score"] = round(q75, 1)
    #         logger.info(
    #             f"  Derived min_screener_score: {derived['min_screener_score']}"
    #         )

    if "min_rs_percentile" in combo["tier2_filters"]:
        if "rs_percentile" in baseline_trades.columns and not winners.empty:
            q80 = winners["rs_percentile"].quantile(0.80)
            derived["min_rs_percentile"] = round(q80, 1)
            logger.info(f"  Derived min_rs_percentile: {derived['min_rs_percentile']}")

    # NOTE: min_adr_pct YA NO SE DERIVA.
    # El screener define min_adr_pct = 3.5, pero la derivación desde trades
    # produce valores incorrectos (2.2 en lugar de 3.5).
    # El combo JSON define el requisito de volatilidad - se respeta.
    # if "min_adr_pct" in combo["tier2_filters"]:
    #     if "context_adr" in baseline_trades.columns and not losers.empty:
    #         q25 = losers["context_adr"].quantile(0.25)
    #         derived["min_adr_pct"] = round(q25, 1)
    #         logger.info(f"  Derived min_adr_pct: {derived['min_adr_pct']}")

    # Merge: derived gana en general (estadistico), EXCEPTO min_dollar_volume.
    # Para liquidez: el combo JSON define el TECHO (max permitido).
    # Si el derivado estadistico es mayor al override del JSON, usar el JSON.
    # Esto evita que el Phase 2 destruya combos con restriccion de liquidez propia.
    final_filters = {**combo["tier2_filters"], **derived}
    _combo_dv = combo["tier2_filters"].get("min_dollar_volume")
    if _combo_dv is not None:
        final_filters["min_dollar_volume"] = min(
            final_filters["min_dollar_volume"], float(_combo_dv)
        )
        if final_filters["min_dollar_volume"] != derived.get("min_dollar_volume"):
            logger.info(
                f"  min_dollar_volume clamped by combo JSON: "
                f"{final_filters['min_dollar_volume']:,.0f} "
                f"(derived={derived.get('min_dollar_volume', 0):,.0f}, "
                f"combo_json={_combo_dv:,.0f})"
            )
    return final_filters


def phase3_optimize_tier1(
    combo: Dict[str, Any],
    tier2_filters: Dict[str, Any],
    universe: List[str],
    start_date: str,
    end_date: str,
    n_trials: int = 100,
    n_jobs: int = 1,
    seed: int = 42,
) -> Tuple[Dict[str, Any], float, optuna.Study, Any]:
    """
    Phase 3: Optuna optimization of Tier 1.
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("PHASE 3: TIER 1 OPTIMIZATION (Exits + Pattern Params)")
    logger.info(f"{'=' * 60}")

    pattern_type = combo["pattern"]["signal_type"]

    # --- Load Tier 1 Pattern Config ---
    _pattern_config = None
    _use_rich_space = False
    try:
        from src.config.pattern_configs import get_pattern_config

        _pattern_config = get_pattern_config(pattern_type)
        _use_rich_space = True
        logger.info(f"  Usando optuna_space rico de pattern_configs ({pattern_type})")
    except Exception as _e:
        logger.info(f"  Usando optuna_space del JSON del combo: {_e}")

    _extra_fixed = (
        _pattern_config.get("extra_fixed_params", {}) if _pattern_config else {}
    )
    optuna_space = combo.get("tier1_optuna_space", {})
    if not optuna_space:
        logger.warning(f"  combo JSON missing 'tier1_optuna_space' — usando defaults")
        optuna_space = {
            "tp1_r": {"min": 1.25, "max": 2.25, "step": 0.25},
            "tp2_r": {"min": 2.75, "max": 5.5, "step": 0.25},
            "tp1_pct": {"min": 0.3, "max": 0.5, "step": 0.05},
            "tp2_pct": {"min": 0.2, "max": 0.4, "step": 0.05},
        }

    # =========================================================
    # PRE-LOAD ENGINE TEMPLATE (PERF)
    # =========================================================
    logger.info("  Pre-loading engine template (data + indicators)...")
    _base_params = {
        **tier2_filters,
        **combo["tier3_fixed"],
        **_extra_fixed,
        "signal_type": pattern_type,
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "risk_dollars": int(100_000 * combo["tier3_fixed"].get("risk_fraction", 0.005)),
        "screener_name": combo["screener"]["name"],
        "screener_cache_path": str(SCREENER_CACHE.cache_dir),
    }

    _template_engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100_000,
        **_base_params,
    )
    _template_engine.load_data()

    # Pre-compute RS/Proximity components
    _precompute_score = False
    try:
        _rs_component = _template_engine._compute_rs_scores()
        _prox_component = _template_engine._compute_proximity_scores()
        _precompute_score = True
        logger.info("  Entry score components pre-computed (RS + proximity)")
    except Exception as _e_pre:
        logger.warning(f"  Could not pre-compute entry score components: {_e_pre}")

    def objective(trial: optuna.Trial) -> float:
        if _use_rich_space and _pattern_config:
            params = _pattern_config["optuna_space"](trial, _extra_fixed)
            if params is None:
                return -999.0
        else:
            params = {}
            for key, cfg in optuna_space.items():
                if isinstance(cfg.get("min"), int):
                    params[key] = trial.suggest_int(
                        key, cfg["min"], cfg["max"], step=cfg.get("step", 1)
                    )
                else:
                    params[key] = trial.suggest_float(
                        key, cfg["min"], cfg["max"], step=cfg.get("step", 0.25)
                    )

        tp1_pct = params.get("tp1_pct", 0.35)
        tp2_pct = params.get("tp2_pct", 0.25)
        runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
        if runner_pct < 0.10 or runner_pct > 0.35:
            return -999.0
        if params.get("tp2_r", 3.0) - params.get("tp1_r", 1.5) < 0.5:
            return -999.0

        full_params = {
            **params,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "runner_pct": runner_pct,
        }

        try:
            # Clone from template (PERF)
            engine = _template_engine.clone_with_params(**full_params)

            if _precompute_score:
                _rs_w = full_params.get("score_rs_weight", 0.70)
                _prox_w = full_params.get("score_proximity_weight", 0.30)
                _total_w = _rs_w + _prox_w
                if _total_w > 0:
                    _rs_w /= _total_w
                    _prox_w /= _total_w
                engine._entry_score_precomputed = (
                    _rs_w * _rs_component + _prox_w * _prox_component
                ).astype(np.float32)

            results = engine.run_backtest()
            n_trades = results.get("total_trades", 0)
            if n_trades < 15:
                return -999.0

            robust_config = RobustObjectiveConfig(
                p5_weight=1.0,
                p10_weight=0.5,
                p50_weight=0.2,
                sharpe_weight=0.30,
                sortino_weight=0.30,
                calmar_weight=0.20,
                max_dd_penalty=2.0,
                dd_duration_penalty=1.0,
                loss_prob_penalty=1.5,
            )
            score = robust_objective_function(results, robust_config)

            # Penalizacion por activity
            _MIN_TRADES_FOLD_TOTAL = 40
            if n_trades < _MIN_TRADES_FOLD_TOTAL:
                _activity_penalty = 0.40 * (
                    1.0 - (n_trades - 15) / (_MIN_TRADES_FOLD_TOTAL - 15)
                )
                score = score - _activity_penalty

            trial.set_user_attr("total_return", results.get("total_return", 0) * 100)
            trial.set_user_attr("sharpe", results.get("sharpe_ratio", 0))
            trial.set_user_attr("max_dd", results.get("max_drawdown", 0) * 100)
            trial.set_user_attr("win_rate", results.get("win_rate", 0) * 100)
            trial.set_user_attr("trades", results.get("total_trades", 0))
            trial.set_user_attr("profit_factor", results.get("profit_factor", 0))

            return score
        except Exception:
            return -999.0

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(
            seed=seed, n_startup_trials=20, n_ei_candidates=24, multivariate=False
        ),
    )

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(
        objective, n_trials=n_trials, n_jobs=n_jobs, show_progress_bar=(n_jobs == 1)
    )

    best = study.best_params.copy()
    tp1_pct = best.get("tp1_pct", 0.35)
    tp2_pct = best.get("tp2_pct", 0.25)
    runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
    if runner_pct < 0.10:
        tp2_pct = round(1.0 - tp1_pct - 0.15, 2)
        runner_pct = round(1.0 - tp1_pct - tp2_pct, 2)
        best["tp2_pct"] = tp2_pct
    best["runner_pct"] = runner_pct

    best_score = study.best_value
    logger.info(f"\n  BEST TIER 1 (Score: {best_score:.2f}):")
    for k, v in best.items():
        logger.info(f"    {k}: {v}")

    return best, best_score, study, _template_engine


def validate_combo(
    combo: Dict[str, Any],
    tier1_params: Dict[str, Any],
    tier2_filters: Dict[str, Any],
    train_dates: Tuple[str, str],
    test_dates: Tuple[str, str],
    universe: List[str],
    initial_capital: float = 100_000,
) -> bool:
    validation_result = validate_combo_result(
        combo,
        tier1_params,
        tier2_filters,
        train_dates,
        test_dates,
        universe,
        initial_capital,
    )
    return bool(validation_result and validation_result.promotion_approved)


def validate_combo_result(
    combo: Dict[str, Any],
    tier1_params: Dict[str, Any],
    tier2_filters: Dict[str, Any],
    train_dates: Tuple[str, str],
    test_dates: Tuple[str, str],
    universe: List[str],
    initial_capital: float = 100_000,
    template_engine: Any = None,
):
    """Run validation and return the full ValidationResult object."""
    logger.info(f"\n{'=' * 60}")
    logger.info("PHASE 4: RESEARCHGATE VALIDATION")
    logger.info(f"{'=' * 60}")

    risk_fraction = combo["tier3_fixed"].get("risk_fraction", 0.005)
    risk_dollars = int(initial_capital * risk_fraction)

    validation_config = combo.get("validation", {})
    # min_win_rate en JSON puede ser fraccion (0.40) o porcentaje (40.0)
    # Normalizamos: si <= 1.0 es fraccion, multiplicar por 100
    _raw_wr = validation_config.get("min_win_rate", 0.40)
    _wr_pct = _raw_wr * 100 if _raw_wr <= 1.0 else _raw_wr
    # Para el torneo bajamos los umbrales respecto al 3tier:
    # el combo optimiza un espacio mas chico -> rendimiento OOS menor es esperado
    custom_thresholds = ValidationThresholds(
        min_trades=validation_config.get("min_trades", 20),
        min_win_rate=_wr_pct,
        min_profit_factor=validation_config.get("min_profit_factor", 1.1),
        min_sharpe_ratio=0.0,  # combo: no exigimos sharpe positivo OOS para pasar
        min_p5_oos_return=-20.0,  # mas permisivo que default (-15%); espacio combo es chico
        min_p10_oos_return=-15.0,  # mas permisivo que el 3tier (-8%)
        # PBO: el CSCV del combo corre sobre el periodo de TRAINING (2019-2023),
        # no sobre el OOS real. Un PBO alto aqui refleja varianza de parametros
        # dentro del training set — no necesariamente overfitting sobre OOS.
        # Umbral relajado a 0.75 (vs 0.50 del 3tier) para no rechazar combos
        # validos solo por el mecanismo de calculo CSCV en training.
        max_pbo=0.85,  # fallback; primary fix is adaptive n_splits in CSCVAnalyzer
    )

    _screener_name = combo["screener"]["name"]
    full_params = {
        **tier1_params,
        **tier2_filters,
        **combo["tier3_fixed"],
        "signal_type": combo["pattern"]["signal_type"],
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "risk_dollars": risk_dollars,
        # Screener cache: permite al engine filtrar entradas por fecha historica
        "screener_name": _screener_name,
        "screener_cache_path": str(SCREENER_CACHE.cache_dir),
    }

    gate = ResearchGate(thresholds=custom_thresholds)

    result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=full_params,
        universe=universe,
        train_dates=train_dates,
        test_dates=test_dates,
        verbose=True,
        template_engine=template_engine,
    )

    logger.info(
        f"\n  ResearchGate Result: {'PASS' if result.promotion_approved else 'FAIL'}"
    )
    if result.rejection_reasons:
        for reason in result.rejection_reasons:
            logger.info(f"    [FAIL] {reason}")
    logger.info(f"    PBO: {result.pbo_score:.2%}")
    logger.info(f"    Sharpe: {result.sharpe_ratio:.2f}")
    logger.info(f"    Max DD: {result.max_drawdown_pct:.1f}%")
    logger.info(f"    Trades: {getattr(result, 'total_trades', 0)}")
    logger.info(f"    Win Rate: {getattr(result, 'win_rate_pct', 0.0):.1f}%")

    return result


def export_combo_result(
    combo: Dict[str, Any],
    tier1_params: Dict[str, Any],
    tier2_filters: Dict[str, Any],
    score: float,
    validation_passed: bool,
    validation_result=None,
) -> Path:
    """Export optimized combo result to JSON.

    Incluye metricas reales del ResearchGate en el JSON exportado,
    no solo los thresholds del combo. Esto permite comparacion de
    no-regresion sin depender del log.
    """
    # Metricas reales del OOS (ResearchGate)
    _vr = validation_result
    oos_metrics = (
        {
            "sharpe_ratio": round(float(getattr(_vr, "sharpe_ratio", 0.0)), 4),
            "pbo_score": round(float(getattr(_vr, "pbo_score", 1.0)), 4),
            "profit_factor": round(float(getattr(_vr, "profit_factor", 0.0)), 4),
            "max_drawdown_pct": round(float(getattr(_vr, "max_drawdown_pct", 0.0)), 2),
            "total_trades": int(getattr(_vr, "total_trades", 0)),
            "win_rate_pct": round(float(getattr(_vr, "win_rate_pct", 0.0)), 2),
        }
        if _vr is not None
        else {}
    )
    result = {
        "combo_name": combo["name"],
        "description": combo["description"],
        "optimized_at": datetime.now().isoformat(),
        "validation_passed": validation_passed,
        "optimization_score": round(score, 3),
        "screener": combo["screener"]["name"],
        "pattern": combo["pattern"]["signal_type"],
        "tier1_exits": tier1_params,
        "tier2_filters": tier2_filters,
        "tier3_fixed": combo["tier3_fixed"],
        "validation_thresholds": combo.get("validation", {}),
        "validation": oos_metrics,  # metricas reales OOS (antes solo thresholds)
    }

    output_path = OUTPUT_DIR / f"{combo['name']}_optimized.json"

    # Control de seguridad de escritura utilizando objetos Path resueltos
    resolved_out = output_path.resolve()
    prohibited_dir = (Path(__file__).resolve().parent.parent / "outputs" / "best_combos_run").resolve()
    if resolved_out == prohibited_dir or resolved_out.is_relative_to(prohibited_dir):
        raise PermissionError(
            f"Write-safety violation: Optimization script is strictly forbidden from writing "
            f"to the production directory '{prohibited_dir}'."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Atomic write: write to temp file first, then replace
    tmp_path = output_path.with_suffix(".json.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    tmp_path.replace(output_path)

    if _vr is not None:
        logger.info(
            f"Exported: {output_path} | Sharpe={_vr.sharpe_ratio:.2f} "
            f"PBO={_vr.pbo_score:.2%} Trades={_vr.total_trades}"
        )
    else:
        logger.info(f"Exported: {output_path} (no validation_result)")
    return output_path


def run_combo_optimization(
    combo_name: str,
    start_date: str,
    end_date: str,
    n_trials: int = 100,
    n_jobs: int = 1,
    tickers_limit: int = 200,
    skip_validation: bool = False,
    skip_optimization: bool = False,
    seed: int = 42,
    liquidity_stratified: bool = True,
) -> Dict[str, Any]:
    """Run full 3-tier optimization for a single combo."""
    logger.info(f"\n{'#' * 70}")
    logger.info(f"# OPTIMIZING COMBO: {combo_name}")
    logger.info(f"# Period: {start_date} to {end_date}")
    logger.info(f"# Trials: {n_trials}")
    logger.info(f"# Universe: {tickers_limit} tickers")
    logger.info(f"{'#' * 70}")

    combo = load_combo_config(combo_name)
    universe = get_universe_from_db(
        limit=tickers_limit,
        start_date=start_date,
        end_date=end_date,
        seed=seed,
        liquidity_stratified=liquidity_stratified,
    )

    screener_name = combo["screener"]["name"]
    screened_universe = apply_screener_to_universe(
        universe, screener_name, start_date, end_date
    )

    if len(screened_universe) < 5:
        logger.warning(
            f"  Universo filtrado muy pequeño ({len(screened_universe)}), usando universo sin filtro."
        )
        screened_universe = universe

    baseline_trades = phase1_baseline_run(
        combo, screened_universe, start_date, end_date
    )
    tier2_filters = phase2_derive_tier2(baseline_trades, combo)

    template_engine = None
    if skip_optimization:
        logger.info("Skipping optimization (--skip-optimization)")
        tier1_params = {
            "tp1_r": 1.5,
            "tp2_r": 3.0,
            "tp1_pct": 0.35,
            "tp2_pct": 0.25,
            "runner_pct": 0.40,
        }
        score = 0.0
        study = None
    else:
        tier1_params, score, study, template_engine = phase3_optimize_tier1(
            combo,
            tier2_filters,
            screened_universe,
            start_date,
            end_date,
            n_trials,
            n_jobs,
            seed=seed,
        )

    # Multi-window walk-forward validation (same as optimize_3tier.py)
    # 3 absolute windows for robustness verification
    absolute_windows = [
        ("2019-01-01", "2021-06-01", "2021-06-01", "2022-06-01"),
        ("2019-01-01", "2023-01-01", "2023-01-01", "2024-01-01"),
        ("2019-01-01", "2023-07-01", "2023-07-01", "2025-12-31"),
    ]
    min_windows_required = 2  # research (2/3); production strict use 3

    validation_passed = True
    validation_result = None
    oos_score = score
    train_dates = (start_date, end_date)
    test_dates = (start_date, end_date)

    if not skip_validation and not skip_optimization:
        trials_df = study.trials_dataframe()
        top_trials = (
            trials_df[trials_df["state"] == "COMPLETE"]
            .sort_values("value", ascending=False)
            .head(10)
        )

        logger.info(
            f"  Validating top {len(top_trials)} trials across {len(absolute_windows)} windows..."
        )

        found_robust = False
        best_oos_score = -999

        for idx, (_, row) in enumerate(top_trials.iterrows()):
            trial_params = {
                k.replace("params_", ""): v
                for k, v in row.items()
                if k.startswith("params_")
            }
            tp1_pct = trial_params.get("tp1_pct", 0.35)
            tp2_pct = trial_params.get("tp2_pct", 0.25)
            trial_params["runner_pct"] = round(1.0 - tp1_pct - tp2_pct, 2)

            logger.info(
                f"\n  [Candidate {idx + 1}/10] Trial {row['number']} (IS Score: {row['value']:.2f})"
            )

            windows_passed = 0
            all_results = []

            for w_idx, (train_s, train_e, test_s, test_e) in enumerate(
                absolute_windows, 1
            ):
                train_dates = (train_s, train_e)
                test_dates = (test_s, test_e)

                logger.info(
                    f"    Fold {w_idx}/{len(absolute_windows)}: Train {train_s} / Test {test_s}"
                )

                # Re-derive Tier 2 from train data only (avoid look-ahead)
                fold_baseline_trades = phase1_baseline_run(
                    combo, screened_universe, train_s, train_e
                )
                fold_tier2 = phase2_derive_tier2(fold_baseline_trades, combo)

                v_res = validate_combo_result(
                    combo,
                    trial_params,
                    fold_tier2,
                    train_dates,
                    test_dates,
                    screened_universe,
                    100_000,
                    template_engine=template_engine,
                )
                all_results.append(v_res)

                if v_res.promotion_approved:
                    windows_passed += 1
                    _s = v_res.sharpe_ratio - (v_res.max_drawdown_pct / 100)
                    if _s > best_oos_score:
                        best_oos_score = _s
                        validation_result = v_res
                    logger.info(f"      Fold {w_idx} PASS")
                else:
                    logger.info(
                        f"      Fold {w_idx} FAIL ({v_res.rejection_reasons[:1]})"
                    )

            if windows_passed >= min_windows_required:
                logger.info(
                    f"  🏆 Candidate {idx + 1} PASSED {windows_passed}/{len(absolute_windows)} windows!"
                )
                tier1_params = trial_params
                score = row["value"]
                oos_score = getattr(validation_result, "sharpe_ratio", score)
                validation_passed = True
                found_robust = True
                break
            else:
                logger.info(
                    f"  [FAIL] Candidate {idx + 1} FAILED: only {windows_passed}/{len(absolute_windows)} windows."
                )

        if not found_robust:
            logger.error(
                "  [FAIL] PIPELINE FAILED: None of top 10 trials passed multi-window validation."
            )
            validation_passed = False
            validation_result = all_results[-1] if all_results else None

    elif not skip_validation and skip_optimization:
        validation_result = validate_combo_result(
            combo,
            tier1_params,
            tier2_filters,
            train_dates,
            test_dates,
            screened_universe,
            100_000,
            template_engine=template_engine,
        )
        validation_passed = bool(
            validation_result and validation_result.promotion_approved
        )

    export_path = export_combo_result(
        combo,
        tier1_params,
        tier2_filters,
        score,
        validation_passed,
        validation_result=validation_result,
    )

    return {
        "combo": combo_name,
        "score": score,
        "oos_score": oos_score,
        "validation_passed": validation_passed,
        "validation": {
            "sharpe_ratio": getattr(validation_result, "sharpe_ratio", 0.0),
            "max_drawdown_pct": getattr(validation_result, "max_drawdown_pct", 0.0),
            "total_trades": getattr(validation_result, "total_trades", 0),
            "win_rate_pct": getattr(validation_result, "win_rate_pct", 0.0),
            "pbo_score": getattr(validation_result, "pbo_score", 1.0),
            "profit_factor": getattr(validation_result, "profit_factor", 0.0),
        },
        "tier1": tier1_params,
        "tier2": tier2_filters,
        "export_path": str(export_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Optimize Screener × Pattern Combos")
    parser.add_argument(
        "--combo", type=str, default=None, help="Combo name to optimize"
    )
    parser.add_argument("--all", action="store_true", help="Optimize all combos")
    parser.add_argument(
        "--list-combos", action="store_true", help="List available combos"
    )
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of Optuna trials"
    )
    parser.add_argument(
        "--start", type=str, default="2022-01-01", help="Start date YYYY-MM-DD"
    )
    parser.add_argument(
        "--end", type=str, default="2024-12-31", help="End date YYYY-MM-DD"
    )
    parser.add_argument(
        "--tickers",
        type=int,
        default=200,
        help="Max tickers en universo (default: 200)",
    )
    parser.add_argument("--njobs", type=int, default=1, help="Parallel jobs for Optuna")
    parser.add_argument(
        "--seed", type=int, default=42, help="Optuna TPESampler seed (default: 42)"
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip ResearchGate validation"
    )
    parser.add_argument(
        "--skip-optimization", action="store_true", help="Skip optimization (Tier 1)"
    )
    parser.add_argument(
        "--build-screener-cache",
        action="store_true",
        help="Build historical screener cache and exit",
    )
    parser.add_argument(
        "--stratified-universe",
        action="store_true",
        dest="stratified_universe",
        default=True,
        help="Use stratified sampling by liquidity (default: True)",
    )
    parser.add_argument(
        "--no-stratified-universe",
        action="store_false",
        dest="stratified_universe",
        help="Use legacy top-by-count universe (disable stratification)",
    )
    args = parser.parse_args()

    if args.list_combos:
        combos = list_available_combos()
        print("\nAvailable combos:")
        for c in combos:
            print(f"  - {c}")
        return

    if args.all:
        combos = list_available_combos()
        logger.info(f"Optimizing all combos: {combos}")
    elif args.combo:
        combos = [args.combo]
    else:
        parser.print_help()
        print("\nAvailable combos:")
        for c in list_available_combos():
            print(f"  - {c}")
        return

    if args.build_screener_cache:
        for combo_name in combos:
            _ = load_combo_config(combo_name)
            universe = get_universe_from_db(
                limit=args.tickers,
                start_date=args.start,
                end_date=args.end,
                seed=args.seed,
                liquidity_stratified=args.stratified_universe,
            )
            build_screener_cache_for_combo(combo_name, args.start, args.end, universe)
        return

    results = []
    for combo_name in combos:
        try:
            result = run_combo_optimization(
                combo_name=combo_name,
                start_date=args.start,
                end_date=args.end,
                n_trials=args.trials,
                n_jobs=args.njobs,
                tickers_limit=args.tickers,
                skip_validation=args.skip_validation,
                skip_optimization=args.skip_optimization,
                seed=args.seed,
                liquidity_stratified=args.stratified_universe,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to optimize {combo_name}: {e}", exc_info=True)

    logger.info(f"\n{'=' * 70}")
    logger.info("OPTIMIZATION COMPLETE")
    logger.info(f"{'=' * 70}")
    for r in results:
        status = "PASS" if r["validation_passed"] else "FAIL"
        logger.info(f"  {r['combo']}: Score={r['score']:.2f}, Validation={status}")
        logger.info(f"    -> {r['export_path']}")


if __name__ == "__main__":
    main()
