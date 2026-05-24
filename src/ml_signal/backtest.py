from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SignalFilterConfig:
    low_threshold: float = 50.0
    mid_threshold: float = 70.0
    high_threshold: float = 80.0


def score_to_percentile(train_scores: pd.Series, test_scores: pd.Series) -> pd.Series:
    train = pd.Series(train_scores).dropna().values
    test = pd.Series(test_scores).fillna(0.0)
    if len(train) == 0:
        return pd.Series(np.zeros(len(test)), index=test.index)
    return pd.Series([100.0 * (train <= score).mean() for score in test.values], index=test.index)


def score_to_percentile(train_scores: pd.Series, test_scores: pd.Series) -> pd.Series:
    train = pd.Series(train_scores).dropna().values
    test = pd.Series(test_scores).fillna(train.min() if len(train) else 0.0).values
    if len(train) == 0:
        return pd.Series(np.zeros(len(test)), index=test_scores.index)
    ranks = [100.0 * (train <= score).mean() for score in test]
    return pd.Series(ranks, index=test_scores.index)


def apply_score_filter(
    df: pd.DataFrame,
    *,
    score_col: str = "pred_score",
    cfg: SignalFilterConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or SignalFilterConfig()
    out = df.copy()
    out["score_bucket"] = pd.cut(
        out[score_col],
        bins=[-np.inf, cfg.low_threshold, cfg.mid_threshold, cfg.high_threshold, np.inf],
        labels=["skip", "small", "normal", "aggressive"],
        right=False,
    )
    out["take_trade"] = out[score_col] >= cfg.low_threshold
    out["risk_multiplier"] = (
        out["score_bucket"]
        .map({"skip": 0.0, "small": 0.5, "normal": 1.0, "aggressive": 2.0})
        .astype(float)
    )
    return out
