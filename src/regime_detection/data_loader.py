from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data.market_data import MarketDataProvider


DEFAULT_BREADTH_UNIVERSE = (
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLY",
    "XLP",
    "XLI",
    "XLB",
    "XLRE",
    "XLU",
    "XLC",
    "IWM",
    "QQQ",
    "DIA",
    "SMH",
    "XBI",
)


def load_regime_market_frame(
    start_date: str,
    end_date: str,
    *,
    provider: MarketDataProvider | None = None,
    breadth_universe: Iterable[str] = DEFAULT_BREADTH_UNIVERSE,
    gamma_path: str | Path | None = None,
) -> pd.DataFrame:
    """Build the daily regime feature frame from market data sources."""

    provider = provider or MarketDataProvider()

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    buffer_start = (start - pd.Timedelta(days=260)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    spy = _load_ohlcv(provider.get_daily_data("SPY", period="max"), buffer_start, end_str)
    if spy.empty:
        raise ValueError("Could not load SPY data")

    vix = _load_ohlcv(provider.get_daily_data("^VIX", period="max"), buffer_start, end_str)
    if vix.empty:
        raise ValueError("Could not load VIX data")

    breadth = _build_breadth_series(provider, breadth_universe, buffer_start, end_str)
    gamma = _load_gamma_history(gamma_path)

    frame = pd.DataFrame(index=spy.index)
    frame["Close"] = spy["Close"]
    frame["date"] = frame.index.normalize()
    frame["vix"] = vix["Close"].reindex(frame.index).ffill()
    # Convert breadth from 0..1 to a centered percentage scale so the
    # heuristic thresholds can distinguish weak/neutral/strong regimes.
    frame["breadth_pct"] = (breadth.reindex(frame.index).ffill() - 0.5) * 100.0

    if gamma is not None and not gamma.empty:
        gamma = gamma.copy()
        gamma["date"] = pd.to_datetime(gamma["date"]).dt.normalize()
        gamma = gamma.drop_duplicates(subset=["date"]).set_index("date")
        if gamma["dix"].dropna().between(0, 1).mean() > 0.8:
            gamma["dix"] = gamma["dix"] * 100.0
        frame = frame.join(gamma[[c for c in ["dix", "gex_net"] if c in gamma.columns]], how="left")
    else:
        # Neutral fallback so the baseline can run without gamma history.
        frame["dix"] = 50.0
        frame["gex_net"] = 0.0

    frame = frame.loc[(frame.index >= start) & (frame.index <= end)].copy()
    frame["date"] = frame.index.normalize()
    return frame.reset_index(drop=True)


def _build_breadth_series(
    provider: MarketDataProvider,
    tickers: Iterable[str],
    start_date: str,
    end_date: str,
) -> pd.Series:
    closes = []
    for ticker in tickers:
        df = _load_ohlcv(provider.get_daily_data(ticker, period="max"), start_date, end_date)
        if df.empty or "Close" not in df.columns:
            continue
        closes.append(df["Close"].rename(ticker))

    if not closes:
        raise ValueError("Could not build breadth series from sector ETFs")

    sector_df = pd.concat(closes, axis=1).sort_index().ffill()
    breadth = (sector_df > sector_df.rolling(20).mean()).mean(axis=1)
    breadth.name = "breadth_pct"
    return breadth


def _load_gamma_history(gamma_path: str | Path | None) -> pd.DataFrame | None:
    if gamma_path is None:
        return None

    path = Path(gamma_path)
    if not path.exists():
        raise FileNotFoundError(f"Gamma history not found: {path}")

    if path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)

    if df.empty:
        return None

    df = df.copy()
    if "gex_net" not in df.columns and "gex" in df.columns:
        df["gex_net"] = df["gex"]
    if "date" not in df.columns:
        raise ValueError("Gamma history must include a 'date' column")
    if "dix" not in df.columns:
        raise ValueError("Gamma history must include a 'dix' column")
    if "gex_net" not in df.columns:
        df["gex_net"] = pd.NA
    return df[["date", "dix", "gex_net"]]


def _load_ohlcv(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out.index = pd.to_datetime(out.index)
    if getattr(out.index, "tz", None) is not None:
        out.index = out.index.tz_localize(None)

    rename_map = {
        col: col.title()
        for col in out.columns
        if col.lower() in {"open", "high", "low", "close", "volume"}
    }
    if rename_map:
        out = out.rename(columns=rename_map)

    return out.loc[pd.to_datetime(start_date) : pd.to_datetime(end_date)]
