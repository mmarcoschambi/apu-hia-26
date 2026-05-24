#!/usr/bin/env python3
"""
Run the heuristic market-regime baseline end to end.

Outputs:
  - data/processed/regime_labels.parquet
  - data/processed/baseline_results.json
  - data/processed/baseline_equity_curve.parquet
  - data/processed/baseline_signals.parquet
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.market_data import MarketDataProvider
from src.regime_detection import (
    WalkForwardBacktestResult,
    WalkForwardRegimeBacktester,
    compare_baseline_to_buy_and_hold,
    generate_forward_labels,
)
from src.regime_detection.data_loader import load_regime_market_frame
from src.regime_detection.metrics_reporter import generate_metrics_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the regime baseline pipeline")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--gamma-path",
        help="Historical gamma data file (csv/parquet) with date,dix,gex_net",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "processed"),
        help="Directory for generated outputs",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = MarketDataProvider()
    logger.info("Loading market regime dataset...")
    frame = load_regime_market_frame(
        args.start,
        args.end,
        provider=provider,
        gamma_path=args.gamma_path,
    )

    logger.info("Generating forward labels...")
    labeled = generate_forward_labels(
        frame,
        close_col="Close",
        horizon=10,
        output_path=output_dir / "regime_labels.parquet",
    )

    labeled = labeled.dropna(subset=["vix", "breadth_pct"]).reset_index(drop=True)
    logger.info("Running walk-forward backtest...")
    backtester = WalkForwardRegimeBacktester()
    result = backtester.run(labeled, date_col="date", close_col="Close")

    logger.info("Building metrics report...")
    report = generate_metrics_report(
        result.signals,
        labeled[["date", "target_regime", "forward_ret_10d"]],
        output_path=output_dir / "baseline_results.json",
        date_col="date",
    )

    if not result.equity_curve.empty:
        result.equity_curve.to_parquet(output_dir / "baseline_equity_curve.parquet", index=False)
    if not result.signals.empty:
        result.signals.to_parquet(output_dir / "baseline_signals.parquet", index=False)
    if not result.folds.empty:
        result.folds.to_parquet(output_dir / "baseline_folds.parquet", index=False)

    summary = {
        "rows": int(len(labeled)),
        "signals": int(len(result.signals)),
        "folds": int(len(result.folds)),
        "report_keys": sorted(report.keys()),
    }
    logger.info(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
