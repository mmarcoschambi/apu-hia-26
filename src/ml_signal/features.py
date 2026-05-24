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

    features = sig.merge(
        mk, how="left", left_on=signal_date_col, right_index=True, suffixes=("", "_mkt")
    )

    if "Close" in features.columns:
        features["spy_return_5d"] = features["Close"].pct_change(5)
        features["spy_return_10d"] = features["Close"].pct_change(10)
        features["spy_return_20d"] = features["Close"].pct_change(20)
        features["spy_atr_ratio"] = (
            features["Close"].rolling(20).max() - features["Close"].rolling(20).min()
        ) / features["Close"].shift(20)

    if "vix" in features.columns:
        features["vix_change_5d"] = features["vix"].pct_change(5)
        features["vix_ma_20"] = features["vix"].rolling(20).mean()
        features["vix_vs_ma"] = features["vix"] / features["vix_ma_20"] - 1.0

    if "breadth_pct" in features.columns:
        features["breadth_change_5d"] = features["breadth_pct"].diff(5)
        features["breadth_ma_20"] = features["breadth_pct"].rolling(20).mean()
        features["breadth_vs_ma"] = features["breadth_pct"] - features["breadth_ma_20"]

    if "dix" in features.columns:
        features["dix_change_5d"] = features["dix"].pct_change(5)
        features["dix_ma_20"] = features["dix"].rolling(20).mean()

    if "gex_net" in features.columns:
        features["gex_ma_20"] = features["gex_net"].rolling(20).mean()
        features["gex_zscore"] = (features["gex_net"] - features["gex_ma_20"]) / (
            features["gex_net"].rolling(20).std(ddof=0) + 1e-8
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

    if target_col not in features.columns:
        raise ValueError(f"missing target column: {target_col}")

    return features
