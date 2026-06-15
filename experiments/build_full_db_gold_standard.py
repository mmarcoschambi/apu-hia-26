#!/usr/bin/env python3
"""Build a full-DB Gold Standard experiment without touching validated outputs.

Outputs are written only to:
  - outputs/experiments/full_db_gold_standard/
  - data/processed/experiments/full_db_signal_quality/
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# Set HOME to workspace scratch directory so OpenBB and other packages don't crash on read-only system
scratch_dir = PROJECT_ROOT / "scratch"
scratch_dir.mkdir(parents=True, exist_ok=True)
os.environ["HOME"] = str(scratch_dir)

import numpy as np
import pandas as pd

from src.integration.combo_loader import load_combo_merged
from src.data.pit_universe import PointInTimeUniverse
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.ml_signal.audit import audit_signal_dataset
from src.ml_signal.features import build_signal_features
from src.ml_signal.trainer import SignalWalkForwardTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# =====================================================================
# PERFORMANCE OPTIMIZATION: In-memory TickerCache Batch Loading Cache
# =====================================================================
from src.data.ticker_cache import TickerCache

# Global cache dictionary for storing loaded OHLCV DataFrames
_OHLCV_IN_MEMORY_CACHE: dict[str, pd.DataFrame] = {}

if not hasattr(TickerCache, "_orig_get_ohlcv_batch"):
    TickerCache._orig_get_ohlcv_batch = TickerCache.get_ohlcv_batch

    def get_ohlcv_batch_cached(self, tickers: list[str], start_date: str, end_date: str, offline: bool = False) -> dict[str, pd.DataFrame]:
        start_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
        end_str = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)
        
        # Check which tickers are missing from our in-memory cache
        missing = [t for t in tickers if t not in _OHLCV_IN_MEMORY_CACHE]
        if missing:
            # Query the missing ones using the original batch SQL / disk method
            logger.info(f"💾 In-Memory Cache Miss: fetching {len(missing)} tickers from storage...")
            loaded = self._orig_get_ohlcv_batch(missing, start_date, end_date, offline)
            
            # MEMORY OPTIMIZATION: convert to float32 and int32 immediately to reduce RAM by 50%
            for t, df in loaded.items():
                if df is not None and not df.empty:
                    float_cols = df.select_dtypes(include=[np.float64, float]).columns
                    df[float_cols] = df[float_cols].astype(np.float32)
                    int_cols = df.select_dtypes(include=[np.int64, int]).columns
                    df[int_cols] = df[int_cols].astype(np.int32)
                    _OHLCV_IN_MEMORY_CACHE[t] = df
        
        # Slice in-memory cached DataFrames to match the requested range
        result = {}
        for t in tickers:
            if t in _OHLCV_IN_MEMORY_CACHE:
                df = _OHLCV_IN_MEMORY_CACHE[t]
                # Ensure DatetimeIndex
                if not isinstance(df.index, pd.DatetimeIndex):
                    df = df.copy()
                    df.index = pd.to_datetime(df.index)
                mask = (df.index >= start_str) & (df.index <= end_str)
                result[t] = df.loc[mask]
        return result

    TickerCache.get_ohlcv_batch = get_ohlcv_batch_cached
    logger.info("⚡ In-memory batch cache optimization successfully installed on TickerCache")
# =====================================================================

DEFAULT_START = "2019-01-02"
DEFAULT_END = "2026-04-30"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments" / "full_db_gold_standard"
QUALITY_DIR = PROJECT_ROOT / "data" / "processed" / "experiments" / "full_db_signal_quality"


@dataclass(frozen=True)
class UniverseSpec:
    name: str
    min_days: int | None = None
    min_price: float | None = None
    min_dollar_volume: float | None = None
    min_mkt_cap: float | None = None
    use_pit: bool = True
    use_e11: bool = False


def _ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    QUALITY_DIR.mkdir(parents=True, exist_ok=True)


def _load_db_universe(start: str, end: str, spec: UniverseSpec, limit: int = 500) -> list[str]:
    db = PROJECT_ROOT / "data" / "ticker_cache.db"
    conn = sqlite3.connect(str(db))
    try:
        # PERF: Apply SQLite PRAGMAs for faster index scanning and sorting
        conn.execute("PRAGMA cache_size = -65536")
        conn.execute("PRAGMA temp_store = MEMORY")
        conn.execute("PRAGMA read_uncommitted = TRUE")

        clauses = ["date >= ?", "date <= ?"]
        params: list[Any] = [start, end]

        having_clauses = []
        if spec.min_price is not None:
            having_clauses.append("AVG(close) >= ?")
            params.append(spec.min_price)
        if spec.min_dollar_volume is not None:
            having_clauses.append("AVG(rolling_dollar_vol_20) >= ?")
            params.append(spec.min_dollar_volume)
        if spec.min_days is not None:
            having_clauses.append("COUNT(*) >= ?")
            params.append(spec.min_days)

        sql = "SELECT ticker, AVG(rolling_dollar_vol_20) AS avg_dvol FROM ohlcv_cache WHERE " + " AND ".join(clauses)
        sql += " GROUP BY ticker"
        if having_clauses:
            sql += " HAVING " + " AND ".join(having_clauses)
        sql += " ORDER BY avg_dvol DESC LIMIT ?"
        params.append(limit)

        df = pd.read_sql_query(sql, conn, params=params)
        if df.empty:
            return []
        return df["ticker"].tolist()
    finally:
        conn.close()


def _load_pit_universe(start: str, end: str) -> list[str]:
    pit = PointInTimeUniverse()
    try:
        return pit.get_universe_for_period(start, end, lookback_buffer_days=200)
    except TypeError:
        return pit.get_universe_for_period(start, lookback_buffer_days=200)


def _build_universe_layers(start: str, end: str, limit_u2: int = 1500, limit_u3: int = 2500, limit_u4: int = 5000) -> dict[str, list[str]]:
    pit = _load_pit_universe(start, end)
    
    logger.info(f"⏳ Loading broad database universe (U4, up to {limit_u4} tickers)...")
    db_broad = _load_db_universe(start, end, UniverseSpec(name="db_broad", min_price=2.0, min_dollar_volume=1_000_000, min_days=100), limit=limit_u4)
    
    logger.info(f"⏳ Loading medium liquidity database universe (U3, up to {limit_u3} tickers)...")
    db_medium = _load_db_universe(start, end, UniverseSpec(name="db_medium", min_price=5.0, min_dollar_volume=5_000_000, min_days=150), limit=limit_u3)
    
    logger.info(f"⏳ Loading strong liquidity database universe (U2, up to {limit_u2} tickers)...")
    db_strong = _load_db_universe(start, end, UniverseSpec(name="db_strong", min_price=10.0, min_dollar_volume=15_000_000, min_days=200), limit=limit_u2)
    
    logger.info(f"✅ Loaded universe layers from DB: strong ({len(db_strong)}), medium ({len(db_medium)}), broad ({len(db_broad)})")

    return {
        "U1_pit_validated": pit,
        "U2_db_liquidity_strong": db_strong,
        "U3_db_liquidity_medium": db_medium,
        "U4_db_broad": db_broad,
    }


def _load_market_context(start: str, end: str) -> pd.DataFrame:
    # Reuse the current market regime dataset as context input.
    path = PROJECT_ROOT / "data" / "processed" / "ml_regime" / "ml_regime_labels.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _build_combo_engine(combo_name: str) -> tuple[dict, Any]:
    cfg, meta = load_combo_merged(combo_name)
    return cfg, meta


def _normalize_metrics(result: dict[str, Any]) -> dict[str, float]:
    trades = result.get("total_trades", 0)
    sharpe = float(result.get("sharpe_ratio", 0.0))
    pf = float(result.get("profit_factor", 0.0))
    wr = float(result.get("win_rate", 0.0))
    total_return = float(result.get("total_return_pct", result.get("total_return", 0.0)))
    dd = float(result.get("max_drawdown_pct", result.get("max_drawdown", 0.0)))
    cagr = float(result.get("cagr", result.get("annualized_return", 0.0)))
    return {
        "trades": trades,
        "sharpe": sharpe,
        "profit_factor": pf,
        "win_rate": wr,
        "total_return_pct": total_return,
        "max_drawdown_pct": dd,
        "cagr": cagr,
    }


def _extract_symbol_col(trades_df: pd.DataFrame) -> str:
    for col in ("symbol", "ticker"):
        if col in trades_df.columns:
            return col
    raise ValueError("No symbol column found in trades dataframe")


def _run_combo_on_universe(
    combo_name: str, universe: list[str], start: str, end: str
) -> dict[str, Any]:
    cfg, meta = _build_combo_engine(combo_name)
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start,
        end_date=end,
        initial_capital=100_000,
        **cfg,
    )
    result = engine.run_backtest()
    metrics = _normalize_metrics(result)
    trades_df = result.get("trades_df", pd.DataFrame())
    if not trades_df.empty:
        trades_df = trades_df.copy()
        symbol_col = _extract_symbol_col(trades_df)
        trades_df["combo_name"] = combo_name
        trades_df["universe_size"] = len(universe)
        trades_df["symbol_col"] = symbol_col
    return {
        "combo": combo_name,
        "meta": {
            "source": getattr(meta, "source", None),
            "sections_merged": getattr(meta, "sections_merged", []),
            "base_file": str(getattr(meta, "base_file", "")),
            "best_combo_file": str(getattr(meta, "best_combo_file", ""))
            if getattr(meta, "best_combo_file", None)
            else None,
        },
        "metrics": metrics,
        "trades_df": trades_df,
        "equity_curve": result.get("equity_curve", pd.DataFrame()),
        "raw_result": result,
    }


def _build_signal_quality(
    trades_df: pd.DataFrame,
    market_context: pd.DataFrame,
    out_dir: Path,
    model_name: str = "elasticnet",
) -> dict[str, Any]:
    if trades_df.empty:
        return {}

    layer_summaries = {}
    
    # ── CAPA A CAPA: Isolated walk-forward training to avoid overlap contamination ──
    layers = trades_df["universe_layer"].unique() if "universe_layer" in trades_df.columns else ["all"]
    for layer in layers:
        layer_df = trades_df[trades_df["universe_layer"] == layer] if "universe_layer" in trades_df.columns else trades_df
        if len(layer_df) < 50:
            logger.warning(f"⚠️ Skipping ML training for layer {layer} due to insufficient observations ({len(layer_df)} < 50)")
            continue

        logger.info(f"🧠 Training {model_name} signal quality model for layer {layer} ({len(layer_df)} observations)...")
        target_col = "r_multiple" if "r_multiple" in layer_df.columns else "return_pct"
        featured = build_signal_features(layer_df, market_context, target_col=target_col)
        target_col = featured.attrs.get("resolved_target_col", target_col)
        audit = audit_signal_dataset(layer_df, target_col=target_col)

        feature_cols = [
            c
            for c in [
                "entry_score",
                "signal_size_proxy",
                "vix",
                "breadth_pct",
                "dix",
                "gex_net",
                "spy_return_10d",
                "spy_return_20d",
                "spy_atr_ratio",
                "rvol",
                "adr_pct",
                "dist_sma20",
            ]
            if c in featured.columns
        ]

        trainer = SignalWalkForwardTrainer(model_name=model_name, min_rows=50)
        try:
            result = trainer.run(
                featured,
                date_col="entry_date",
                symbol_col=_extract_symbol_col(layer_df),
                target_col=target_col,
                feature_cols=feature_cols,
            )

            result.predictions.to_parquet(out_dir / f"full_db_signal_predictions_{layer}.parquet", index=False)
            result.folds.to_parquet(out_dir / f"full_db_signal_folds_{layer}.parquet", index=False)
            result.feature_importance.to_parquet(
                out_dir / f"full_db_signal_feature_importance_{layer}.parquet", index=False
            )

            layer_summaries[layer] = {
                "audit": asdict(audit),
                "corr_oos": result.corr_oos,
                "rmse_oos": result.rmse_oos,
                "model_name": result.model_name,
                "rows_predicted": int(len(result.predictions)),
                "folds": int(len(result.folds)),
            }
        except Exception as e:
            logger.error(f"❌ Failed to run ML training for layer {layer}: {e}")

    # ── GLOBAL DEDUPLICATED MODEL: Deduplicated by entry_date + ticker to prevent overlap leakage ──
    dedup_cols = ["combo_name", "entry_date"]
    for c in ["symbol", "ticker"]:
        if c in trades_df.columns:
            dedup_cols.append(c)
            break

    trades_dedup = trades_df.drop_duplicates(subset=dedup_cols)
    if len(trades_dedup) >= 50:
        logger.info(f"🧠 Training global model on completely DEDUPLICATED dataset ({len(trades_dedup)} unique observations)...")
        target_col = "r_multiple" if "r_multiple" in trades_dedup.columns else "return_pct"
        featured = build_signal_features(trades_dedup, market_context, target_col=target_col)
        target_col = featured.attrs.get("resolved_target_col", target_col)
        audit = audit_signal_dataset(trades_dedup, target_col=target_col)

        feature_cols = [
            c
            for c in [
                "entry_score",
                "signal_size_proxy",
                "vix",
                "breadth_pct",
                "dix",
                "gex_net",
                "spy_return_10d",
                "spy_return_20d",
                "spy_atr_ratio",
                "rvol",
                "adr_pct",
                "dist_sma20",
            ]
            if c in featured.columns
        ]

        trainer = SignalWalkForwardTrainer(model_name=model_name, min_rows=50)
        try:
            result = trainer.run(
                featured,
                date_col="entry_date",
                symbol_col=_extract_symbol_col(trades_dedup),
                target_col=target_col,
                feature_cols=feature_cols,
            )

            result.predictions.to_parquet(out_dir / "full_db_signal_predictions_global_dedup.parquet", index=False)
            result.folds.to_parquet(out_dir / "full_db_signal_folds_global_dedup.parquet", index=False)
            result.feature_importance.to_parquet(
                out_dir / "full_db_signal_feature_importance_global_dedup.parquet", index=False
            )

            layer_summaries["global_dedup"] = {
                "audit": asdict(audit),
                "corr_oos": result.corr_oos,
                "rmse_oos": result.rmse_oos,
                "model_name": result.model_name,
                "rows_predicted": int(len(result.predictions)),
                "folds": int(len(result.folds)),
            }
        except Exception as e:
            logger.error(f"❌ Failed to run ML training for global deduplicated: {e}")
    else:
        logger.warning(f"⚠️ Skipping global ML training due to insufficient unique observations ({len(trades_dedup)} < 50)")

    (out_dir / "full_db_signal_quality.json").write_text(json.dumps(layer_summaries, indent=2, default=str))
    return layer_summaries


def _run_subprocess_job(
    combo: str,
    layer_name: str,
    start: str,
    end: str,
    limit_u2: int,
    limit_u3: int,
    limit_u4: int,
    part_dir: Path,
) -> int:
    import subprocess
    cmd = [
        sys.executable,
        __file__,
        "--start", start,
        "--end", end,
        "--limit-u2", str(limit_u2),
        "--limit-u3", str(limit_u3),
        "--limit-u4", str(limit_u4),
        "--single-combo", combo,
        "--single-layer", layer_name,
        "--part-dir", str(part_dir),
    ]
    logger.info(f"🚀 Spawning isolated subprocess: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    return res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build full DB gold standard experiment")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    parser.add_argument(
        "--combos", nargs="*", default=["combo_pullback_entry", "combo_pure_momentum"]
    )
    parser.add_argument(
        "--model", default="elasticnet", choices=["ridge", "elasticnet", "lightgbm"]
    )
    parser.add_argument("--save-trades", action="store_true", default=True)
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers for backtesting (spawns isolated subprocesses)")
    parser.add_argument("--limit-u4", type=int, default=5000, help="Maximum tickers for U4_db_broad layer")
    parser.add_argument("--limit-u3", type=int, default=2500, help="Maximum tickers for U3_db_liquidity_medium layer")
    parser.add_argument("--limit-u2", type=int, default=1500, help="Maximum tickers for U2_db_liquidity_strong layer")
    parser.add_argument("--single-combo", default=None, help="Internal worker flag to run a single combo")
    parser.add_argument("--single-layer", default=None, help="Internal worker flag to run a single layer")
    parser.add_argument("--part-dir", default=None, help="Internal worker flag to store temporary part files")
    args = parser.parse_args()

    # ── SUBPROCESS WORKER MODE ──
    if args.single_combo and args.single_layer:
        _ensure_dirs()
        part_dir = Path(args.part_dir) if args.part_dir else OUTPUT_DIR / "parts"
        part_dir.mkdir(parents=True, exist_ok=True)
        
        # Load the universe layers using the exact same arguments
        layers = _build_universe_layers(
            args.start, args.end, 
            limit_u2=args.limit_u2, 
            limit_u3=args.limit_u3, 
            limit_u4=args.limit_u4
        )
        universe = layers.get(args.single_layer, [])
        if not universe:
            logger.warning(f"⚠️ Universe is empty for layer {args.single_layer}. Nothing to do.")
            sys.exit(0)
            
        logger.info(f"🚀 [Subprocess Worker] Running {args.single_combo} on {args.single_layer} with {len(universe)} tickers...")
        
        try:
            res = _run_combo_on_universe(args.single_combo, universe, args.start, args.end)
            
            trades_df = res["trades_df"]
            if not trades_df.empty:
                trades_df = trades_df.copy()
                trades_df["combo_name"] = args.single_combo
                trades_df["universe_layer"] = args.single_layer
                trades_df.to_csv(part_dir / f"part_{args.single_combo}_{args.single_layer}_trades.csv", index=False)
                
            eq = res.get("equity_curve", pd.DataFrame())
            if isinstance(eq, pd.DataFrame) and not eq.empty:
                eq = eq.copy()
                eq["combo_name"] = args.single_combo
                eq["universe_layer"] = args.single_layer
                eq.to_csv(part_dir / f"part_{args.single_combo}_{args.single_layer}_equity.csv", index=False)
                
            metrics_dict = {
                "combo": args.single_combo,
                "layer": args.single_layer,
                "universe_size": len(universe),
                **res["metrics"]
            }
            
            with open(part_dir / f"part_{args.single_combo}_{args.single_layer}_metrics.json", "w") as f:
                json.dump(metrics_dict, f, indent=2)
                
            logger.info(f"✅ [Subprocess Worker] Successfully completed {args.single_combo} on {args.single_layer}")
            sys.exit(0)
        except Exception as e:
            import traceback
            logger.error(f"❌ [Subprocess Worker] Failed {args.single_combo} on {args.single_layer}: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)

    # ── PARENT MODE ──
    _ensure_dirs()
    run_config = {
        "start": args.start,
        "end": args.end,
        "combos": args.combos,
        "model": args.model,
        "workers": args.workers,
        "limit_u4": args.limit_u4,
        "limit_u3": args.limit_u3,
        "limit_u2": args.limit_u2,
        "outputs": {
            "gold_dir": str(OUTPUT_DIR),
            "quality_dir": str(QUALITY_DIR),
        },
        "run_at": datetime.now().isoformat(),
    }
    (OUTPUT_DIR / "run_config.json").write_text(json.dumps(run_config, indent=2, default=str))

    layers = _build_universe_layers(
        args.start, args.end, 
        limit_u2=args.limit_u2, 
        limit_u3=args.limit_u3, 
        limit_u4=args.limit_u4
    )
    (OUTPUT_DIR / "universe_layers.json").write_text(
        json.dumps({k: len(v) for k, v in layers.items()}, indent=2)
    )

    market_context = _load_market_context(args.start, args.end)
    all_trade_frames: list[pd.DataFrame] = []
    all_equity_frames: list[pd.DataFrame] = []
    metrics_summary: dict[str, Any] = {"runs": []}

    part_dir = OUTPUT_DIR / "parts"
    if part_dir.exists():
        import shutil
        try:
            shutil.rmtree(part_dir)
        except Exception as e:
            logger.warning(f"Could not clear temporary part directory {part_dir}: {e}")
    part_dir.mkdir(parents=True, exist_ok=True)

    # Prepare jobs
    jobs = []
    for combo in args.combos:
        for layer_name, universe in layers.items():
            if not universe:
                continue
            jobs.append((combo, layer_name))

    # Execute backtesting jobs using subprocess spawning and ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    logger.info(f"⚡ Spawning isolated subprocess workers (max concurrent: {args.workers})...")
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _run_subprocess_job,
                combo,
                layer_name,
                args.start,
                args.end,
                args.limit_u2,
                args.limit_u3,
                args.limit_u4,
                part_dir,
            ): (combo, layer_name)
            for combo, layer_name in jobs
        }
        
        for future in as_completed(futures):
            combo, layer_name = futures[future]
            try:
                ret_code = future.result()
                if ret_code != 0:
                    logger.error(f"❌ Subprocess failed with exit code {ret_code} for {combo} on {layer_name}")
                else:
                    logger.info(f"✅ Subprocess finished successfully for {combo} on {layer_name}")
            except Exception as e:
                logger.error(f"❌ Failed to execute job for {combo} on {layer_name} - {e}")
                import traceback
                logger.error(traceback.format_exc())

    # Load all successful part files
    for combo, layer_name in jobs:
        trades_file = part_dir / f"part_{combo}_{layer_name}_trades.csv"
        equity_file = part_dir / f"part_{combo}_{layer_name}_equity.csv"
        metrics_file = part_dir / f"part_{combo}_{layer_name}_metrics.json"
        
        if trades_file.exists():
            try:
                df = pd.read_csv(trades_file)
                if not df.empty:
                    all_trade_frames.append(df)
            except Exception as e:
                logger.error(f"Error reading {trades_file}: {e}")
                
        if equity_file.exists():
            try:
                df = pd.read_csv(equity_file)
                if not df.empty:
                    all_equity_frames.append(df)
            except Exception as e:
                logger.error(f"Error reading {equity_file}: {e}")
                
        if metrics_file.exists():
            try:
                with open(metrics_file, "r") as f:
                    metrics_dict = json.load(f)
                    metrics_summary["runs"].append(metrics_dict)
            except Exception as e:
                logger.error(f"Error reading {metrics_file}: {e}")

    # Clean up parts directory
    if part_dir.exists():
        import shutil
        try:
            shutil.rmtree(part_dir)
        except Exception as e:
            logger.warning(f"Could not delete temporary part directory {part_dir}: {e}")

    if all_trade_frames:
        trades_all = pd.concat(all_trade_frames, ignore_index=True)
        trades_all.to_csv(OUTPUT_DIR / "full_db_gold_trades.csv", index=False)
        trades_all.to_parquet(OUTPUT_DIR / "full_db_gold_signal_candidates.parquet", index=False)

        if all_equity_frames:
            equity_all = pd.concat(all_equity_frames, ignore_index=True)
            equity_all.to_csv(OUTPUT_DIR / "full_db_gold_equity.csv", index=False)

        if not market_context.empty:
            quality = _build_signal_quality(
                trades_all, market_context, QUALITY_DIR, model_name=args.model
            )
            metrics_summary["signal_quality"] = quality
    else:
        (OUTPUT_DIR / "full_db_gold_trades.csv").write_text("")

    (OUTPUT_DIR / "full_db_gold_metrics.json").write_text(
        json.dumps(metrics_summary, indent=2, default=str)
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
