#!/usr/bin/env python3
"""Run signal-quality scoring for gold-standard trades."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ml_signal import audit_signal_dataset, build_signal_features, SignalWalkForwardTrainer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def calculate_trade_metrics(
    df: pd.DataFrame,
    pnl_col: str,
    weight_col: str | None = None,
    initial_capital: float = 100000.0,
    risk_per_trade_r: float = 1000.0,
) -> dict:
    if df.empty:
        return {}

    # Calculate PnL for selected trades
    if weight_col is not None:
        pnl = df[pnl_col] * df[weight_col]
        active_mask = df[weight_col] > 0
    else:
        pnl = df[pnl_col]
        active_mask = pd.Series(True, index=df.index)

    active_pnl = pnl[active_mask]
    if len(active_pnl) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "mean_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "cagr": 0.0,
        }

    wins = active_pnl[active_pnl > 0]
    losses = active_pnl[active_pnl < 0]
    win_rate = len(wins) / len(active_pnl)
    
    pos_sum = float(wins.sum())
    neg_sum = float(abs(losses.sum()))
    profit_factor = pos_sum / neg_sum if neg_sum > 0 else float("inf")

    # Trade-level Sharpe (annualized assuming 252 trades/year)
    mean_pnl = float(active_pnl.mean())
    std_pnl = float(active_pnl.std(ddof=1))
    sharpe = (mean_pnl / std_pnl * np.sqrt(252)) if (std_pnl > 0 and not pd.isna(std_pnl)) else 0.0

    # Drawdown calculation - sort chronologically
    sorted_df = df.copy()
    sorted_df["pnl_val"] = pnl
    if "entry_date" in sorted_df.columns:
        sorted_df["entry_date"] = pd.to_datetime(sorted_df["entry_date"])
        sorted_df = sorted_df.sort_values("entry_date")
    
    cum_pnl = sorted_df["pnl_val"].cumsum()
    is_pct = pnl_col == "return_pct" or active_pnl.abs().mean() < 0.5
    
    if is_pct:
        equity = initial_capital * (1.0 + sorted_df["pnl_val"]).cumprod()
    else:
        equity = initial_capital + cum_pnl * risk_per_trade_r
        
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_dd = float(drawdown.min() * 100.0) if not drawdown.empty else 0.0

    # Calculate CAGR based on the entire period's duration
    years = 0.0
    if "entry_date" in df.columns and len(df) > 1:
        dates = pd.to_datetime(df["entry_date"]).dropna()
        if len(dates) > 1:
            years = (dates.max() - dates.min()).days / 365.25

    cagr = 0.0
    if years > 0 and not equity.empty:
        ending_val = float(equity.iloc[-1])
        if ending_val > 0:
            cagr = (ending_val / initial_capital) ** (1.0 / years) - 1.0
        else:
            cagr = -1.0

    return {
        "total_trades": int(len(active_pnl)),
        "win_rate": round(win_rate * 100.0, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "total_pnl": round(float(active_pnl.sum()), 2),
        "mean_pnl": round(mean_pnl, 3),
        "sharpe_ratio": round(float(sharpe), 3),
        "max_drawdown_pct": round(max_dd, 2),
        "cagr": round(cagr * 100.0, 2),
    }


def calculate_decile_analysis(df: pd.DataFrame, score_col: str, target_col: str) -> list[dict]:
    if df.empty or len(df) < 10:
        return []

    work = df.copy()
    work["decile"] = pd.cut(
        work[score_col],
        bins=np.linspace(0, 100, 11),
        labels=[f"D{i}" for i in range(1, 11)],
        include_lowest=True,
    )

    decile_rows = []
    for name, group in work.groupby("decile", observed=False):
        if group.empty:
            decile_rows.append({
                "decile": name,
                "trades": 0,
                "win_rate": 0.0,
                "mean_pnl": 0.0,
                "total_pnl": 0.0,
            })
            continue

        pnl = pd.to_numeric(group[target_col], errors="coerce").dropna()
        wins = pnl[pnl > 0]
        win_rate = len(wins) / len(pnl) if len(pnl) > 0 else 0.0
        
        decile_rows.append({
            "decile": str(name),
            "trades": int(len(pnl)),
            "win_rate": round(win_rate * 100.0, 2),
            "mean_pnl": round(float(pnl.mean()), 3) if len(pnl) > 0 else 0.0,
            "total_pnl": round(float(pnl.sum()), 2) if len(pnl) > 0 else 0.0,
        })
        
    return decile_rows


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
    target_col = "r_multiple" if "r_multiple" in signals.columns else "return_pct"
    audit = audit_signal_dataset(signals, target_col=target_col)
    logger.info(json.dumps(audit.__dict__, indent=2, default=str))

    featured = build_signal_features(signals, market, target_col=target_col)
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

    target_col = "r_multiple" if "r_multiple" in featured.columns else "return_pct"
    comparison = {
        "original_gold_standard": calculate_trade_metrics(result.predictions, pnl_col=target_col),
        "ml_filtered": calculate_trade_metrics(result.predictions, pnl_col=target_col, weight_col="take_trade"),
        "ml_sized": calculate_trade_metrics(result.predictions, pnl_col=target_col, weight_col="risk_multiplier"),
    }
    decile_an = calculate_decile_analysis(result.predictions, score_col="pred_score", target_col=target_col)

    summary = {
        "audit": audit.__dict__,
        "corr_oos": result.corr_oos,
        "rmse_oos": result.rmse_oos,
        "model_name": result.model_name,
        "rows_predicted": int(len(result.predictions)),
        "folds": int(len(result.folds)),
        "comparison": comparison,
        "decile_analysis": decile_an,
    }
    (out / "signal_results.json").write_text(json.dumps(summary, indent=2, default=str))
    (out / "ml_vs_original_report.json").write_text(json.dumps(comparison, indent=2, default=str))
    logger.info("Comparison and decile reports generated successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
