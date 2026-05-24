#!/usr/bin/env python3
"""Run signal-quality scoring for gold-standard trades."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ml_signal import audit_signal_dataset, build_signal_features, SignalWalkForwardTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run phase 2 signal quality scoring")
    parser.add_argument("--signals", required=True, help="Historical signals/trades CSV")
    parser.add_argument("--market", required=True, help="Market context CSV/Parquet")
    parser.add_argument("--output-dir", default="data/processed/signal_quality")
    parser.add_argument("--model", default="ridge", choices=["ridge", "elasticnet", "lightgbm"])
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    signals = pd.read_csv(args.signals)
    market = (
        pd.read_parquet(args.market)
        if str(args.market).endswith(".parquet")
        else pd.read_csv(args.market)
    )
    audit = audit_signal_dataset(signals)
    logger.info(json.dumps(audit.__dict__, indent=2, default=str))

    featured = build_signal_features(signals, market)
    feature_cols = [
        c
        for c in [
            "vix",
            "vix_change_5d",
            "vix_vs_ma",
            "breadth_pct",
            "breadth_change_5d",
            "breadth_vs_ma",
            "dix",
            "dix_change_5d",
            "gex_net",
            "gex_zscore",
            "spy_return_5d",
            "spy_return_10d",
            "spy_return_20d",
            "spy_atr_ratio",
            "rsi_entry",
            "rvol",
            "adr_pct",
            "dist_sma20",
            "dollar_vol_M",
            "entry_score",
            "regime_signal",
            "signal_size_proxy",
        ]
        if c in featured.columns
    ]

    trainer = SignalWalkForwardTrainer(model_name=args.model)
    result = trainer.run(
        featured,
        date_col="entry_date",
        symbol_col="symbol",
        target_col="r_multiple" if "r_multiple" in featured.columns else "return_pct",
        feature_cols=feature_cols,
    )

    result.predictions.to_parquet(out / "signal_predictions.parquet", index=False)
    result.folds.to_parquet(out / "signal_folds.parquet", index=False)
    result.feature_importance.to_parquet(out / "signal_feature_importance.parquet", index=False)

    summary = {
        "audit": audit.__dict__,
        "corr_oos": result.corr_oos,
        "rmse_oos": result.rmse_oos,
        "model_name": result.model_name,
        "rows_predicted": int(len(result.predictions)),
        "folds": int(len(result.folds)),
    }
    (out / "signal_results.json").write_text(json.dumps(summary, indent=2, default=str))
    logger.info(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
