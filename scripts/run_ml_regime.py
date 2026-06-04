#!/usr/bin/env python3
"""Run ML-based regime detection with walk-forward validation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.regime_detection import generate_forward_labels
from src.regime_detection.backtest_engine import WalkForwardRegimeBacktester
from src.regime_detection.data_loader import load_regime_market_frame
from src.regime_detection.ml_features import build_ml_features
from src.regime_detection.ml_trainer import WalkForwardMLTrainer
from src.regime_detection.metrics_reporter import generate_metrics_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "vix",
    "vix_change_5d",
    "vix_vs_ma",
    "breadth_pct",
    "breadth_change_5d",
    "breadth_vs_ma",
    "spy_return_5d",
    "spy_return_10d",
    "spy_return_20d",
    "spy_atr_ratio",
    "dix",
    "dix_change_5d",
    "gex_net",
    "gex_zscore",
    "sector_momentum_dispersion",
    "put_call_ratio",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ML regime detection pipeline")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--gamma-path", help="Historical gamma data file")
    parser.add_argument("--output-dir", default="data/processed/ml_regime")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading market regime dataset...")
    frame = load_regime_market_frame(args.start, args.end, gamma_path=args.gamma_path)

    logger.info("Generating forward labels...")
    labeled = generate_forward_labels(
        frame,
        close_col="Close",
        horizon=10,
        output_path=output_dir / "ml_regime_labels.parquet",
    )

    logger.info("Building ML features...")
    featured = build_ml_features(labeled, date_col="date", close_col="Close")

    logger.info("Running walk-forward ML training...")
    trainer = WalkForwardMLTrainer(train_years=3, test_months=3, step_months=3, purge_days=10)
    result = trainer.run(
        featured,
        date_col="date",
        close_col="Close",
        target_col="target_regime",
        feature_cols=[c for c in FEATURE_COLS if c in featured.columns],
    )

    logger.info("Saving results...")
    if not result.equity_curve.empty:
        result.equity_curve.to_parquet(output_dir / "ml_equity_curve.parquet", index=False)
    if not result.signals.empty:
        result.signals.to_parquet(output_dir / "ml_signals.parquet", index=False)
    if not result.folds.empty:
        result.folds.to_parquet(output_dir / "ml_folds.parquet", index=False)
    if not result.feature_importance.empty:
        result.feature_importance.to_parquet(
            output_dir / "ml_feature_importance.parquet", index=False
        )

    ml_report = generate_metrics_report(
        result.signals,
        labeled[["date", "target_regime", "forward_ret_10d"]],
        output_path=None,
        date_col="date",
    )

    baseline_path = PROJECT_ROOT / "data" / "processed" / "baseline_results.json"
    baseline_metrics = None
    if baseline_path.exists():
        try:
            with open(baseline_path, "r") as f:
                baseline_metrics = json.load(f)
            logger.info("Loaded Phase 0 baseline metrics for comparison.")
        except Exception as e:
            logger.warning(f"Could not load Phase 0 baseline metrics: {e}")

    comparison_report = {
        "buy_and_hold": ml_report.get("buy_and_hold"),
        "baseline_phase0": baseline_metrics.get("baseline") if baseline_metrics else None,
        "ml_phase1": ml_report.get("baseline"),
        "classification": {
            "baseline_phase0": baseline_metrics.get("classification") if baseline_metrics else None,
            "ml_phase1": ml_report.get("classification"),
        },
        "regime_returns": {
            "baseline_phase0": baseline_metrics.get("regime_returns") if baseline_metrics else None,
            "ml_phase1": ml_report.get("regime_returns"),
        },
        "stat_test": {
            "baseline_phase0": baseline_metrics.get("stat_test") if baseline_metrics else None,
            "ml_phase1": ml_report.get("stat_test"),
        }
    }

    with open(output_dir / "ml_vs_baseline_report.json", "w") as f:
        json.dump(comparison_report, f, indent=2, default=str)

    summary = {
        "rows": int(len(featured)),
        "signals": int(len(result.signals)),
        "folds": int(len(result.folds)),
        "oos_accuracy": float(result.oos_accuracy),
        "oos_f1_weighted": float(result.oos_f1_weighted),
        "oos_f1_macro": float(result.oos_f1_macro),
        "oos_balanced_accuracy": float(result.oos_balanced_accuracy),
        "report_keys": sorted(ml_report.keys()),
        "feature_importance": result.feature_importance.to_dict(orient="records"),
    }

    with open(output_dir / "ml_results.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(
        json.dumps(
            {
                "oos_accuracy": summary["oos_accuracy"],
                "oos_f1_weighted": summary["oos_f1_weighted"],
                "oos_f1_macro": summary["oos_f1_macro"],
                "oos_balanced_accuracy": summary["oos_balanced_accuracy"],
                "top_features": result.feature_importance.head(5).to_dict(orient="records"),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
