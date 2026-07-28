"""
scratch/run_benchmark_tier0.py
Golden Baseline Benchmark — Tier 0 (100% Offline / Read-Only)
Windows NTFS · Python 3.13.2

Mide tiempos por etapa y RAM pico. Exporta artefactos golden.
Delega el backtest real a scripts.backtest_via_signal_engine.run_backtest().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("benchmark_tier0")

# ---------------------------------------------------------------------------
# CLI  (same flags as backtest_via_signal_engine.py + benchmark-specific)
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Tier 0 Golden Baseline Benchmark")
parser.add_argument("--no-ingest", action="store_true", default=True)
parser.add_argument("--read-only", action="store_true", default=True)
parser.add_argument("--start", default="2023-01-01")
parser.add_argument("--end", default="2024-12-31")
parser.add_argument("--capital", type=float, default=100000.0)
parser.add_argument("--universe-size", type=int, default=200)
parser.add_argument("--index", default="RUSSELL1000", choices=["SP500", "RUSSELL1000", "RUSSELL2000", "NASDAQ100"])
parser.add_argument("--tag", default="golden_baseline")
parser.add_argument("--cold", action="store_true", help="Cold run flag (no page cache)")
parser.add_argument("--skip-backtest", action="store_true", help="Only measure data + features")
parser.add_argument("--variant-e", action=argparse.BooleanOptionalAction, default=True, help="Enable Thematic Divergence Filter")
parser.add_argument("--no-pit", action="store_false", dest="use_pit", default=True, help="Disable PIT filter")
parser.add_argument("--e25-sizing", action=argparse.BooleanOptionalAction, default=True, help="Enable E25 Dynamic Extension sizing")
parser.add_argument("--e25-version", default="v2_atlas_informed", choices=["v1_monotonic", "v2_atlas_informed"])
parser.add_argument("--ticker-cap", type=float, default=None)
parser.add_argument("--sector-cap", type=float, default=None)
parser.add_argument("--exclude-tickers", nargs="+", default=[], metavar="TICKER")
parser.add_argument("--exclude-sectors", nargs="+", default=[], metavar="SECTOR")
parser.add_argument("--universe-source", default="pit", choices=["pit", "shadow_finviz"])
args = parser.parse_args()

GOLDEN_DIR = PROJECT_ROOT / "outputs" / "golden" / "windows_baseline_2026-07-24"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = GOLDEN_DIR / "artifacts"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Offline enforcement
# ---------------------------------------------------------------------------
_HTTP_BLOCKED: list[str] = []


def _block_http():
    import urllib.request
    def _blocked_open(*a, **kw):
        url = str(a[0]) if a else kw.get("url", "unknown")
        _HTTP_BLOCKED.append(url)
        raise RuntimeError(f"BLOCKED HTTP (--no-ingest): {url}")
    urllib.request.urlopen = _blocked_open
    logger.info("HTTP blocked")


if args.no_ingest:
    _block_http()

# ---------------------------------------------------------------------------
# Memory Sampler
# ---------------------------------------------------------------------------
_process = None


def _get_process():
    global _process
    if _process is None:
        import psutil
        _process = psutil.Process()
    return _process


class MemorySampler:
    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self._stop = Event()
        self._samples: list[float] = []
        self._thread: Thread | None = None

    def start(self):
        self._samples.clear()
        self._stop.clear()
        def _sample():
            p = _get_process()
            while not self._stop.wait(self.interval):
                try:
                    self._samples.append(p.memory_info().rss / 1024 / 1024)
                except Exception:
                    pass
        self._thread = Thread(target=_sample, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        if not self._samples:
            return {"peak_mib": 0.0, "mean_mib": 0.0}
        return {
            "peak_mib": round(max(self._samples), 1),
            "mean_mib": round(sum(self._samples) / len(self._samples), 1),
            "samples": len(self._samples),
        }


# ---------------------------------------------------------------------------
# Stage Timer
# ---------------------------------------------------------------------------
class StageTimer:
    stages: dict[str, float] = {}

    def __init__(self, name: str):
        self.name = name
        self._start: float | None = None

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *a):
        elapsed = time.perf_counter() - self._start
        self.stages[self.name] = round(elapsed, 4)
        logger.info("  %-30s %8.2fs", self.name, elapsed)

    @classmethod
    def summary(cls) -> dict[str, float]:
        return dict(cls.stages)

    @classmethod
    def reset(cls):
        cls.stages.clear()


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------
def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _hash_dir(path: Path, pattern: str = "**/*.py") -> str:
    h = hashlib.sha256()
    for f in sorted(path.glob(pattern)):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


def _hash_json_sorted(path: Path) -> str:
    data = json.loads(path.read_bytes())
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


# ===================================================================
# MAIN BENCHMARK
# ===================================================================
def run_tier0():
    today_str = "2026-07-24"
    env_info = {
        "host": os.environ.get("COMPUTERNAME", "unknown"),
        "os": f"{sys.platform}",
        "python": sys.version,
        "date": today_str,
        "cold_run": args.cold,
        "start": args.start,
        "end": args.end,
        "capital": args.capital,
        "universe_size": args.universe_size,
        "index": args.index,
        "e25_sizing": args.e25_sizing,
        "e25_version": args.e25_version,
        "variant_e": args.variant_e,
        "use_pit": args.use_pit,
    }
    logger.info("=" * 60)
    logger.info("TIER 0 BASELINE BENCHMARK")
    logger.info("=" * 60)
    for k, v in env_info.items():
        logger.info("  %-20s %s", k, v)

    StageTimer.reset()

    # ---------------------------------------------------------------
    # Stage 1 — Data Load (fast: universe building + SQL queries)
    # ---------------------------------------------------------------
    mem = MemorySampler()
    mem.start()

    with StageTimer("data_load"):
        from src.config.dynamic_config import load_production_config
        from src.integration.combo_loader import load_combo_merged
        from src.integration.universe_builder import build_universe_for_fold
        from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

        DB_PATH = str(PROJECT_ROOT / "data" / "ticker_cache.db")
        load_production_config()
        cfg_a, _ = load_combo_merged("combo_pure_momentum")
        cfg_b, _ = load_combo_merged("combo_stage2_breakout")

        conn = sqlite3.connect(DB_PATH)
        dates_str = sorted(
            pd.read_sql(
                "SELECT DISTINCT date FROM ohlcv_cache WHERE ticker='SPY' AND date >= ? AND date <= ? || ' 23:59:59' ORDER BY date",
                conn, params=(args.start, args.end),
            )["date"].unique().tolist()
        )
        logger.info("  Trading dates: %d", len(dates_str))
        conn.close()

        universe_by_date: dict[str, list[str]] = {}
        superset_tickers: set[str] = set()
        for d_str in dates_str:
            u_start = (pd.to_datetime(d_str) - timedelta(days=730)).strftime("%Y-%m-%d")
            snap = build_universe_for_fold(
                Path(DB_PATH), d_str, u_start,
                max_tickers=args.universe_size, index_name=args.index, use_pit=args.use_pit,
            )
            universe_by_date[d_str] = snap.tickers
            superset_tickers.update(snap.tickers)

        superset_tickers.update(["SPY", "^VIX"])
        superset_tickers.update(SECTOR_ETFS)

        # Pre-load RS rankings for coverage check
        conn = sqlite3.connect(DB_PATH)
        rs_all = pd.read_sql(
            "SELECT date, ticker, rs_composite FROM daily_rs_rankings WHERE date >= ? AND date <= ? || ' 23:59:59'",
            conn, params=(args.start, args.end),
        )
        rs_all["date"] = pd.to_datetime(rs_all["date"], format="mixed").dt.normalize()
        rs_lookup = rs_all.set_index(["date", "ticker"])["rs_composite"].to_dict()
        conn.close()

    load_mem = mem.stop()
    logger.info("  Memory after data_load: peak=%.1f MiB", load_mem["peak_mib"])

    # ---------------------------------------------------------------
    # Stage 2 — Data Quality Checks
    # ---------------------------------------------------------------
    mem.start()
    with StageTimer("data_quality_checks"):
        missing_rs = 0
        for d_str, day_universe in universe_by_date.items():
            curr_dt = pd.to_datetime(d_str).normalize()
            for ticker in day_universe:
                if (curr_dt, ticker) not in rs_lookup:
                    missing_rs += 1
        quality_report = {
            "trading_dates": len(dates_str),
            "universe_tickers": len(superset_tickers),
            "missing_rs_lookups": missing_rs,
            "missing_rs_pct": round(missing_rs / max(1, len(dates_str) * 200) * 100, 2),
        }
        data_quality_ok = missing_rs == 0
        logger.info("  Quality OK: %s | missing_rs=%d (%.1f%%)",
                     data_quality_ok, missing_rs, quality_report["missing_rs_pct"])
    qc_mem = mem.stop()

    if args.skip_backtest:
        peak = max(load_mem["peak_mib"], qc_mem["peak_mib"])
        _dump_early(quality_report, peak)
        return

    # ---------------------------------------------------------------
    # Stage 3-6: Real backtest via scripts.backtest_via_signal_engine
    # ---------------------------------------------------------------
    mem.start()
    backtest_tag = f"{args.tag}_{args.index.lower()}"
    bt_start = time.perf_counter()

    with StageTimer("backtest_engine"):
        from scripts.backtest_via_signal_engine import run_backtest

        run_backtest(
            start_date=args.start,
            end_date=args.end,
            initial_capital=args.capital,
            max_tickers=args.universe_size,
            tag=backtest_tag,
            use_variant_e=args.variant_e,
            index_name=args.index,
            use_e25_sizing=args.e25_sizing,
            e25_version=args.e25_version,
            exclude_tickers=list(args.exclude_tickers) if args.exclude_tickers else None,
            exclude_sectors=list(args.exclude_sectors) if args.exclude_sectors else None,
            use_pit=args.use_pit,
            ticker_cap=args.ticker_cap,
            sector_cap=args.sector_cap,
            universe_source=args.universe_source,
        )

    bt_mem = mem.stop()
    logger.info("  Memory after backtest: peak=%.1f MiB", bt_mem["peak_mib"])

    bt_elapsed = time.perf_counter() - bt_start
    peak_overall = max(load_mem["peak_mib"], qc_mem["peak_mib"], bt_mem["peak_mib"])

    # ---------------------------------------------------------------
    # Stage 7 — Export Golden Artifacts
    # ---------------------------------------------------------------
    mem.start()
    with StageTimer("outputs_export"):
        bt_output_dir = PROJECT_ROOT / "outputs" / "backtests"

        trades_path = bt_output_dir / f"{backtest_tag}_trades.csv"
        equity_path = bt_output_dir / f"{backtest_tag}_equity.csv"
        metrics_path = bt_output_dir / f"{backtest_tag}_metrics.json"
        robustness_path = bt_output_dir / f"{backtest_tag}_robustness.json"

        df_trades = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
        df_equity_raw = pd.read_csv(equity_path) if equity_path.exists() else pd.DataFrame()
        backtest_metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}

        # Rename equity column: the backtest script exports as {"date", "0"}
        df_equity = df_equity_raw.rename(columns={"0": "equity"}) if not df_equity_raw.empty else pd.DataFrame()

        # Build signals.parquet from trades (signal=1 for each trade entry)
        signals_rows: list[dict] = []
        if not df_trades.empty and "entry_date" in df_trades.columns and "symbol" in df_trades.columns:
            for _, row in df_trades.iterrows():
                signals_rows.append({
                    "date": row["entry_date"],
                    "ticker": row["symbol"],
                    "signal": 1,
                    "entry_score": row.get("entry_score", 0),
                    "trade_id": row.get("trade_id", row.name),
                })
        df_signals = pd.DataFrame(signals_rows)
        if not df_signals.empty:
            df_signals = df_signals.sort_values(["date", "ticker"]).reset_index(drop=True)

        # Build positions.parquet from trade sizing data
        positions_rows: list[dict] = []
        if not df_trades.empty:
            for _, row in df_trades.iterrows():
                positions_rows.append({
                    "date": row["entry_date"],
                    "ticker": row["symbol"],
                    "position": row.get("initial_size", 0),
                    "entry_price": row.get("entry_price", 0),
                    "exit_date": row.get("exit_date", ""),
                    "trade_id": row.get("trade_id", row.name),
                })
        df_positions = pd.DataFrame(positions_rows)
        if not df_positions.empty:
            df_positions = df_positions.sort_values(["date", "ticker"]).reset_index(drop=True)

        # Build rejection_audit (empty for now; the real script doesn't audit rejections to CSV)
        df_rejection = pd.DataFrame()

        canonical_metrics = {
            "total_return_pct": backtest_metrics.get("total_return", 0),
            "annualized_return_pct": backtest_metrics.get("annualized_return", 0),
            "max_drawdown_pct": backtest_metrics.get("max_drawdown", 0),
            "sharpe_ratio": backtest_metrics.get("sharpe_ratio", 0),
            "win_rate_pct": backtest_metrics.get("win_rate", 0),
            "profit_factor": backtest_metrics.get("profit_factor", 0),
            "total_trades": backtest_metrics.get("total_trades", 0),
            "initial_capital": args.capital,
            "data_quality_ok": data_quality_ok,
        }

        # Write golden artifacts
        df_signals.to_parquet(OUTPUT_DIR / "signals.parquet", index=False)
        df_trades.to_parquet(OUTPUT_DIR / "trades.parquet", index=False)
        df_positions.to_parquet(OUTPUT_DIR / "positions.parquet", index=False)
        df_equity.to_parquet(OUTPUT_DIR / "equity_curve.parquet", index=False)
        df_rejection.to_csv(OUTPUT_DIR / "rejection_audit.csv", index=False)
        with open(OUTPUT_DIR / "canonical_metrics.json", "w") as f:
            json.dump(canonical_metrics, f, indent=2)

        # Copy robustness report if exists
        if robustness_path.exists():
            import shutil
            shutil.copy2(robustness_path, OUTPUT_DIR / "robustness_report.json")

        # Benchmark result JSON
        timing = StageTimer.summary()
        benchmark_result = {
            "environment": env_info,
            "timing_seconds": timing,
            "total_pipeline_seconds": sum(timing.values()),
            "memory_mib": {
                "peak_overall": peak_overall,
                "after_data_load": load_mem["peak_mib"],
                "after_quality_checks": qc_mem["peak_mib"],
                "after_backtest": bt_mem["peak_mib"],
            },
            "data_quality": quality_report,
            "metrics": canonical_metrics,
        }
        with open(OUTPUT_DIR / "benchmark_result.json", "w") as f:
            json.dump(benchmark_result, f, indent=2, default=str)

        # ---------------------------------------------------------------
        # Manifest (7 dimensions)
        # ---------------------------------------------------------------
        raw_data_dir = PROJECT_ROOT / "data" / "golden" / "windows_baseline_2026-07-24" / "raw"
        src_dir = PROJECT_ROOT / "src"
        config_file = PROJECT_ROOT / "config" / "production_config.json"
        lockfile = PROJECT_ROOT / "requirements-lock.txt"
        universe_dir = PROJECT_ROOT / "data" / "universe"
        models_dir = PROJECT_ROOT / "models"

        raw_hash = _hash_dir(raw_data_dir, "**/*") if raw_data_dir.exists() else "MISSING"
        code_hash = _hash_dir(src_dir, "**/*.py")
        config_hash = _hash_json_sorted(config_file) if config_file.exists() else "MISSING"
        lock_hash = _hash_file(lockfile) if lockfile.exists() else "MISSING"
        univ_hash = _hash_dir(universe_dir, "*.json") if universe_dir.exists() else "MISSING"
        model_hash = _hash_dir(models_dir, "*") if models_dir.exists() else "MISSING"

        feature_defs = {
            "sma_periods": [20, 50, 100, 150, 200],
            "atr_period": 14,
            "adr_period": 20,
            "rvol_period": 20,
            "consolidation_period": 20,
            "bb_std": 2,
            "returns_periods": [1, 5, 20],
            "rs_ranking_lookback": 60,
            "source": "src/indicators/technical.py + config/production_config.json + backtest_via_signal_engine.py",
        }
        feature_hash = hashlib.sha256(json.dumps(feature_defs, sort_keys=True).encode()).hexdigest()

        manifest = {
            "baseline_date": today_str,
            "generated_by": "scratch/run_benchmark_tier0.py",
            "raw_data_manifest_hash": raw_hash,
            "code_tree_hash": code_hash,
            "canonical_config_hash": config_hash,
            "lockfile_hash": lock_hash,
            "universe_metadata_hash": univ_hash,
            "feature_defs_hash": feature_hash,
            "model_artifacts_hash": model_hash,
            "artifacts": {},
        }
        for fname in ["signals.parquet", "trades.parquet", "positions.parquet",
                       "equity_curve.parquet", "rejection_audit.csv", "canonical_metrics.json"]:
            fp = OUTPUT_DIR / fname
            manifest["artifacts"][fname] = _hash_file(fp) if fp.exists() else "MISSING"

        with open(GOLDEN_DIR / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info("  Manifest written to %s", GOLDEN_DIR / "manifest.json")

    export_mem = mem.stop()

    logger.info("=" * 60)
    logger.info("BENCHMARK COMPLETE")
    logger.info("  Total pipeline: %.2fs", sum(StageTimer.summary().values()))
    logger.info("  Peak RAM: %.1f MiB", peak_overall)
    logger.info("  Trades: %d | Return: %.2f%% | Sharpe: %.2f | MDD: %.2f%%",
                canonical_metrics["total_trades"],
                canonical_metrics["total_return_pct"],
                canonical_metrics["sharpe_ratio"],
                canonical_metrics["max_drawdown_pct"])
    logger.info("=" * 60)
    _print_timing_table(StageTimer.summary())


def _dump_early(quality_report: dict, peak_mib: float):
    timing = StageTimer.summary()
    result = {
        "environment": {"skip_backtest": True, "date": "2026-07-24"},
        "timing_seconds": timing,
        "total_pipeline_seconds": sum(timing.values()),
        "memory_mib": {"peak_overall": peak_mib},
        "data_quality": quality_report,
        "metrics": {"note": "Backtest skipped via --skip-backtest"},
    }
    with open(OUTPUT_DIR / "benchmark_result.json", "w") as f:
        json.dump(result, f, indent=2)
    logger.info("Early artifacts dumped (--skip-backtest)")


def _print_timing_table(stages: dict[str, float]):
    total = sum(stages.values())
    logger.info("  %-30s %10s  %5s", "Stage", "Seconds", "%")
    logger.info("  %s", "-" * 50)
    for name, secs in sorted(stages.items()):
        pct = secs / total * 100 if total > 0 else 0
        logger.info("  %-30s %8.2fs  %4.1f%%", name, secs, pct)
    logger.info("  %s", "-" * 50)
    logger.info("  %-30s %8.2fs 100.0%%", "TOTAL", total)


# ===================================================================
# GOLDEN CONTRACT
# ===================================================================
def write_golden_contract():
    contract = {
        "level_1_strict_columns": [
            "signal", "ticker", "date", "rank", "trade_id",
            "entry_date", "exit_date", "position",
        ],
        "level_2_float_columns": [
            "ma_20", "ma_50", "ma_200", "adr_pct_20",
            "rs_score", "rs_rank", "trend_intensity",
            "ret_1d", "ret_5d", "ret_20d",
        ],
        "tolerances": {
            "level_1": "strict_zero_tolerance",
            "level_2_rtol": 1e-10,
            "level_2_atol": 1e-12,
            "equal_nan": True,
        },
        "fatal_rule": (
            "Cualquier diferencia flotante que provoque la alteración de "
            "una señal (0/1), un trade o un ranking se considera fallo "
            "fatal de regresión."
        ),
        "generated_at": "2026-07-24",
        "baseline_tag": "baseline-windows-ntfs-2026-07-24",
    }
    path = GOLDEN_DIR / "golden_contract.json"
    with open(path, "w") as f:
        json.dump(contract, f, indent=2)
    logger.info("Golden contract written to %s", path)


# ===================================================================
# ENTRY
# ===================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SCRATCH BENCHMARK TIER 0")
    logger.info("=" * 60)
    write_golden_contract()
    run_tier0()
    logger.info("All done. Artifacts at: %s", GOLDEN_DIR)
