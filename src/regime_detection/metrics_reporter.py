from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from src.regime_detection.baseline_rules import LABEL_GREEN, LABEL_RED, LABEL_YELLOW


def compare_baseline_to_buy_and_hold(
    signals: pd.DataFrame,
    labels: pd.DataFrame | None = None,
    *,
    date_col: str = "date",
) -> dict[str, Any]:
    """Compare baseline strategy metrics against buy-and-hold."""

    if signals.empty:
        return {}

    work = signals.copy()
    work[date_col] = pd.to_datetime(work[date_col])

    market_return_col = "market_return"
    strategy_return_col = "strategy_return"
    if market_return_col not in work.columns or strategy_return_col not in work.columns:
        raise ValueError("signals must include market_return and strategy_return")

    bh_equity = (1.0 + work[market_return_col]).cumprod()
    strat_equity = work.get("equity_curve")
    if strat_equity is None:
        strat_equity = (1.0 + work[strategy_return_col]).cumprod() * 100000.0

    report = {
        "buy_and_hold": {
            "cagr": _cagr(bh_equity),
            "max_drawdown": _max_drawdown(bh_equity),
            "sharpe": _sharpe_ratio(work[market_return_col]),
        },
        "baseline": {
            "cagr": _cagr(strat_equity),
            "max_drawdown": _max_drawdown(strat_equity),
            "sharpe": _sharpe_ratio(work[strategy_return_col]),
            "cash_pct": float((work["exposure"] == 0).mean())
            if "exposure" in work.columns
            else None,
        },
    }

    if labels is not None and not labels.empty:
        merged = _merge_signals_and_labels(work, labels, date_col=date_col)
        report["classification"] = _classification_report(merged)
        report["regime_returns"] = _regime_return_report(merged)
        report["stat_test"] = _prediction_ttest_report(merged)

    return report


def generate_metrics_report(
    signals: pd.DataFrame,
    labels: pd.DataFrame | None = None,
    *,
    output_path: str | Path | None = None,
    date_col: str = "date",
) -> dict[str, Any]:
    """Build a JSON-serializable summary and optionally write it to disk."""

    report = compare_baseline_to_buy_and_hold(signals, labels, date_col=date_col)
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(report, f, indent=2, default=str)
    return report


def _merge_signals_and_labels(
    signals: pd.DataFrame, labels: pd.DataFrame, date_col: str
) -> pd.DataFrame:
    left = signals.copy()
    right = labels.copy()

    left[date_col] = pd.to_datetime(left[date_col])
    if date_col in right.columns:
        right[date_col] = pd.to_datetime(right[date_col])
    elif isinstance(right.index, pd.DatetimeIndex):
        right = right.reset_index().rename(columns={right.index.name or "index": date_col})
        right[date_col] = pd.to_datetime(right[date_col])
    else:
        right = right.reset_index().rename(columns={right.index.name or "index": date_col})
        right[date_col] = pd.to_datetime(right[date_col])

    label_cols = [col for col in ["target_regime", "forward_ret_10d"] if col in right.columns]
    return left.merge(right[[date_col] + label_cols], on=date_col, how="left")


def _classification_report(df: pd.DataFrame) -> dict[str, Any]:
    if "target_regime" not in df.columns:
        return {}

    ct = pd.crosstab(df["target_regime"], df["regime_signal"], dropna=False)
    red_mask = df["target_regime"] == LABEL_RED
    green_mask = df["target_regime"] == LABEL_GREEN
    red_recall = (
        float((df.loc[red_mask, "regime_signal"] == LABEL_RED).mean()) if red_mask.any() else None
    )
    green_false_positive = (
        float((df.loc[green_mask, "regime_signal"] == LABEL_RED).mean())
        if green_mask.any()
        else None
    )
    return {
        "confusion_matrix": ct.to_dict(),
        "red_recall": red_recall,
        "green_false_positive_as_red": green_false_positive,
        "signal_distribution": df["regime_signal"].value_counts(dropna=False).to_dict(),
    }


def _regime_return_report(df: pd.DataFrame) -> dict[str, Any]:
    if "forward_ret_10d" in df.columns and df["forward_ret_10d"].notna().any():
        source = "forward_ret_10d"
    elif "market_return" in df.columns:
        source = "market_return"
    else:
        return {}

    signal_green = df.loc[df["regime_signal"] == LABEL_GREEN, source].dropna()
    signal_red = df.loc[df["regime_signal"] == LABEL_RED, source].dropna()
    return {
        "green_mean_return": float(signal_green.mean()) if not signal_green.empty else None,
        "red_mean_return": float(signal_red.mean()) if not signal_red.empty else None,
        "yellow_mean_return": float(df.loc[df["regime_signal"] == LABEL_YELLOW, source].mean())
        if (df["regime_signal"] == LABEL_YELLOW).any()
        else None,
    }


def _prediction_ttest_report(df: pd.DataFrame) -> dict[str, Any]:
    if "forward_ret_10d" not in df.columns:
        return {}

    green = df.loc[df["regime_signal"] == LABEL_GREEN, "forward_ret_10d"].dropna()
    red = df.loc[df["regime_signal"] == LABEL_RED, "forward_ret_10d"].dropna()
    if len(green) < 2 or len(red) < 2:
        return {"p_value": None}

    stat = stats.ttest_ind(red, green, equal_var=False, nan_policy="omit")
    return {"p_value": float(stat.pvalue), "statistic": float(stat.statistic)}


def _sharpe_ratio(returns: pd.Series, annualization_factor: int = 252) -> float:
    returns = pd.Series(returns).dropna()
    if returns.empty or returns.std(ddof=0) == 0:
        return 0.0
    return float(np.sqrt(annualization_factor) * returns.mean() / returns.std(ddof=0))


def _max_drawdown(equity: pd.Series) -> float:
    equity = pd.Series(equity).dropna()
    if equity.empty:
        return 0.0
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def _cagr(equity: pd.Series, annualization_factor: int = 252) -> float:
    equity = pd.Series(equity).dropna()
    if equity.empty or len(equity) < 2:
        return 0.0
    start = equity.iloc[0]
    end = equity.iloc[-1]
    years = (len(equity) - 1) / annualization_factor
    if start <= 0 or years <= 0:
        return 0.0
    return float((end / start) ** (1.0 / years) - 1.0)
