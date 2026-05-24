from __future__ import annotations

import numpy as np
import pandas as pd


def build_ml_features(
    df: pd.DataFrame,
    *,
    date_col: str = "date",
    close_col: str = "Close",
) -> pd.DataFrame:
    """Generate ML-ready features for regime detection."""

    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    out = out.sort_values(date_col).reset_index(drop=True)

    out["vix_change_5d"] = out["vix"].pct_change(5)
    out["vix_ma_20"] = out["vix"].rolling(20).mean()
    out["vix_vs_ma"] = out["vix"] / out["vix_ma_20"] - 1.0

    out["breadth_change_5d"] = out["breadth_pct"].diff(5)
    out["breadth_ma_20"] = out["breadth_pct"].rolling(20).mean()
    out["breadth_vs_ma"] = out["breadth_pct"] - out["breadth_ma_20"]

    out["spy_return_5d"] = out[close_col].pct_change(5)
    out["spy_return_10d"] = out[close_col].pct_change(10)
    out["spy_return_20d"] = out[close_col].pct_change(20)

    prev_close_20 = out[close_col].shift(20)
    out["spy_atr_ratio"] = (
        out[close_col].rolling(20).max() - out[close_col].rolling(20).min()
    ) / prev_close_20

    if "dix" in out.columns:
        out["dix_change_5d"] = out["dix"].pct_change(5)
        out["dix_ma_20"] = out["dix"].rolling(20).mean()

    if "gex_net" in out.columns:
        out["gex_ma_20"] = out["gex_net"].rolling(20).mean()
        out["gex_zscore"] = (out["gex_net"] - out["gex_ma_20"]) / (
            out["gex_net"].rolling(20).std(ddof=0) + 1e-8
        )

    if "sector_momentum_dispersion" not in out.columns:
        out["sector_momentum_dispersion"] = np.nan
    if "put_call_ratio" not in out.columns:
        out["put_call_ratio"] = np.nan

    required = [
        "vix_change_5d",
        "breadth_change_5d",
        "spy_return_20d",
        "spy_atr_ratio",
    ]
    out = out.dropna(subset=required)
    return out
