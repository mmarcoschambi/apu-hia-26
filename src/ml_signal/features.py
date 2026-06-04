from __future__ import annotations

import numpy as np
import pandas as pd


def build_signal_features(
    signals: pd.DataFrame,
    market: pd.DataFrame,
    *,
    signal_date_col: str = "entry_date",
    market_date_col: str = "date",
    signal_price_col: str = "entry_price",
    target_col: str = "r_multiple",
) -> pd.DataFrame:
    """Build signal-level features without look-ahead."""

    sig = signals.copy()
    mk = market.copy()

    sig[signal_date_col] = pd.to_datetime(sig[signal_date_col], errors="coerce")
    mk[market_date_col] = pd.to_datetime(mk[market_date_col], errors="coerce")
    sig = sig.sort_values(signal_date_col).reset_index(drop=True)
    mk = (
        mk.sort_values(market_date_col)
        .drop_duplicates(subset=[market_date_col])
        .set_index(market_date_col)
    )

    if signal_date_col not in sig.columns:
        raise ValueError(f"missing signal date column: {signal_date_col}")

    # Calculate rolling market features on the daily market frame FIRST
    if "Close" in mk.columns:
        mk["spy_return_5d"] = mk["Close"].pct_change(5)
        mk["spy_return_10d"] = mk["Close"].pct_change(10)
        mk["spy_return_20d"] = mk["Close"].pct_change(20)
        mk["spy_atr_ratio"] = (mk["Close"].rolling(20).max() - mk["Close"].rolling(20).min()) / mk[
            "Close"
        ].shift(20)

    if "vix" in mk.columns:
        mk["vix_change_5d"] = mk["vix"].pct_change(5)
        mk["vix_ma_20"] = mk["vix"].rolling(20).mean()
        mk["vix_vs_ma"] = mk["vix"] / mk["vix_ma_20"] - 1.0

    if "breadth_pct" in mk.columns:
        mk["breadth_change_5d"] = mk["breadth_pct"].diff(5)
        mk["breadth_ma_20"] = mk["breadth_pct"].rolling(20).mean()
        mk["breadth_vs_ma"] = mk["breadth_pct"] - mk["breadth_ma_20"]

    if "dix" in mk.columns:
        mk["dix_change_5d"] = mk["dix"].pct_change(5)
        mk["dix_ma_20"] = mk["dix"].rolling(20).mean()

    if "gex_net" in mk.columns:
        mk["gex_ma_20"] = mk["gex_net"].rolling(20).mean()
        mk["gex_zscore"] = (mk["gex_net"] - mk["gex_ma_20"]) / (
            mk["gex_net"].rolling(20).std(ddof=0) + 1e-8
        )

    features = sig.merge(
        mk, how="left", left_on=signal_date_col, right_index=True, suffixes=("", "_mkt")
    )

    if signal_price_col in features.columns:
        features["signal_size_proxy"] = np.log1p(
            pd.to_numeric(features[signal_price_col], errors="coerce")
        )

    for col in ("rsi_entry", "rvol", "adr_pct", "dist_sma20", "dollar_vol_M", "entry_score"):
        if col in features.columns:
            features[col] = pd.to_numeric(features[col], errors="coerce")

    if "regime_signal" not in features.columns:
        features["regime_signal"] = pd.NA

    actual_target = target_col
    if actual_target not in features.columns:
        if actual_target == "r_multiple" and "return_pct" in features.columns:
            actual_target = "return_pct"
        else:
            raise ValueError(f"missing target column: {actual_target}")

    features.attrs["resolved_target_col"] = actual_target
    return features
