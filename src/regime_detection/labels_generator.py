from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.regime_detection.baseline_rules import LABEL_GREEN, LABEL_RED, LABEL_YELLOW

FORWARD_RET_COL = "forward_ret_10d"
TARGET_COL = "target_regime"


def generate_forward_labels(
    df: pd.DataFrame,
    close_col: str = "Close",
    horizon: int = 10,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Create forward return labels and GREEN/YELLOW/RED targets."""

    if close_col not in df.columns:
        raise ValueError(f"Missing required column: {close_col}")

    out = df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"])
        out = out.sort_values("date")
    elif not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)
        out = out.sort_index()
    else:
        out = out.sort_index()

    forward_close = out[close_col].shift(-horizon)
    out[FORWARD_RET_COL] = (forward_close / out[close_col]) - 1.0

    out[TARGET_COL] = pd.NA
    out.loc[out[FORWARD_RET_COL] > 0.01, TARGET_COL] = LABEL_GREEN
    out.loc[out[FORWARD_RET_COL] < -0.01, TARGET_COL] = LABEL_RED
    out.loc[out[FORWARD_RET_COL].between(-0.01, 0.01, inclusive="neither"), TARGET_COL] = (
        LABEL_YELLOW
    )
    out.loc[out[FORWARD_RET_COL].between(-0.01, 0.01, inclusive="both"), TARGET_COL] = LABEL_YELLOW

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=True)

    return out


def prepare_regime_dataset(
    features: pd.DataFrame,
    close_col: str = "Close",
    horizon: int = 10,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Convenience wrapper for label generation."""

    return generate_forward_labels(
        features,
        close_col=close_col,
        horizon=horizon,
        output_path=output_path,
    )
