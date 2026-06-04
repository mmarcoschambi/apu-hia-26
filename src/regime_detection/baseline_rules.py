from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


LABEL_RED = "RED"
LABEL_YELLOW = "YELLOW"
LABEL_GREEN = "GREEN"


@dataclass(frozen=True)
class BaselineThresholds:
    red_vix: float = 25.0
    red_breadth_pct: float = -20.0
    red_dix: float = 40.0
    yellow_vix_low: float = 15.0
    yellow_vix_high: float = 25.0
    yellow_breadth_low: float = -10.0
    yellow_breadth_high: float = 10.0


def classify_regime_baseline(
    df: pd.DataFrame,
    thresholds: BaselineThresholds | None = None,
) -> pd.DataFrame:
    """Classify each row into GREEN, YELLOW, or RED using fixed rules."""

    thresholds = thresholds or BaselineThresholds()
    required_columns = {"vix", "breadth_pct", "dix"}
    missing = required_columns.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df.copy()
    red_condition = (out["vix"] > thresholds.red_vix) | (
        (out["breadth_pct"] < thresholds.red_breadth_pct) & (out["dix"] < thresholds.red_dix)
    )
    yellow_condition = (
        out["vix"].between(thresholds.yellow_vix_low, thresholds.yellow_vix_high, inclusive="both")
    ) | out["breadth_pct"].between(
        thresholds.yellow_breadth_low,
        thresholds.yellow_breadth_high,
        inclusive="both",
    )

    out["regime_signal"] = np.select(
        [red_condition, yellow_condition],
        [LABEL_RED, LABEL_YELLOW],
        default=LABEL_GREEN,
    )
    return out
