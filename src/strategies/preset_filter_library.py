"""Preset filter library for system B ablation presets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


def _col(df: pd.DataFrame, lower: str, upper: str) -> pd.Series:
    if lower in df.columns:
        return df[lower]
    return df[upper]


@dataclass
class _PivotPoint:
    pivot_idx: int
    confirm_idx: int
    price: float


def _confirmed_pivots(
    series: pd.Series,
    left: int,
    right: int,
    mode: str,
) -> list[_PivotPoint]:
    values = series.astype(float).values
    n = len(values)
    points: list[_PivotPoint] = []
    if left < 1 or right < 1:
        return points

    for idx in range(left, n - right):
        center = values[idx]
        if not np.isfinite(center):
            continue
        left_slice = values[idx - left : idx]
        right_slice = values[idx + 1 : idx + right + 1]
        if mode == "low":
            is_pivot = np.all(center < left_slice) and np.all(center <= right_slice)
        else:
            is_pivot = np.all(center > left_slice) and np.all(center >= right_slice)
        if is_pivot:
            points.append(
                _PivotPoint(
                    pivot_idx=idx,
                    confirm_idx=idx + right,
                    price=float(center),
                )
            )
    return points


def market_cap_min(df: pd.DataFrame, minimum: float) -> pd.Series:
    if "market_cap" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["market_cap"].astype(float) >= float(minimum)


def avg_volume_50_min(df: pd.DataFrame, minimum: float) -> pd.Series:
    vol = _col(df, "volume", "Volume").astype(float)
    return vol.rolling(50, min_periods=50).mean() >= float(minimum)


def adr_50_min(df: pd.DataFrame, minimum_pct: float) -> pd.Series:
    high = _col(df, "high", "High").astype(float)
    low = _col(df, "low", "Low").astype(float)
    close = _col(df, "close", "Close").astype(float).replace(0.0, np.nan)
    adr = ((high - low) / close * 100.0).rolling(50, min_periods=50).mean()
    return adr >= float(minimum_pct)


def rs_1m_percentile_min(
    close: pd.Series,
    universe_returns_21d: pd.Series,
    minimum_pct: float,
) -> bool:
    """
    close is unused but kept for API parity.
    universe_returns_21d: cross-sectional 21d returns for current date.
    """
    if universe_returns_21d.empty:
        return False
    me = universe_returns_21d.iloc[-1]
    pct = float((universe_returns_21d < me).mean() * 100.0)
    return pct >= float(minimum_pct)


def _wma(series: pd.Series, period: int) -> pd.Series:
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def trend_base(
    df: pd.DataFrame, sma_period: int = 50, wma_short: int = 10, wma_long: int = 30
) -> pd.Series:
    close = _col(df, "close", "Close").astype(float)
    sma = close.rolling(sma_period, min_periods=sma_period).mean()
    w_short = _wma(close, wma_short)
    w_long = _wma(close, wma_long)
    return (close > sma) & (w_short > w_long)


def rel_volume_min(df: pd.DataFrame, minimum: float, period: int = 50) -> pd.Series:
    vol = _col(df, "volume", "Volume").astype(float)
    avg = vol.rolling(period, min_periods=period).mean().replace(0.0, np.nan)
    return (vol / avg) >= float(minimum)


def power_play(df: pd.DataFrame, window: int = 10) -> pd.Series:
    open_ = _col(df, "open", "Open").astype(float)
    close = _col(df, "close", "Close").astype(float)
    vol = _col(df, "volume", "Volume").astype(float)
    max_prev = vol.rolling(window, min_periods=window).max().shift(1)
    return (close > open_) & (vol > max_prev)


def power_play_cluster_20d_min3(df: pd.DataFrame) -> pd.Series:
    pp = power_play(df, window=10)
    return pp.rolling(20, min_periods=20).sum() >= 3


def weekly_return_min(df: pd.DataFrame, minimum_pct: float = 20.0) -> pd.Series:
    close = _col(df, "close", "Close").astype(float)
    ret_5d = (close / close.shift(5) - 1.0) * 100.0
    return ret_5d >= float(minimum_pct)


def near_52w_high_band(df: pd.DataFrame, min_pct: float, max_pct: float) -> pd.Series:
    close = _col(df, "close", "Close").astype(float)
    high_52w = close.rolling(252, min_periods=50).max().replace(0.0, np.nan)
    dist = (close / high_52w - 1.0) * 100.0
    return (dist >= float(min_pct)) & (dist <= float(max_pct))


def vcs_score_min(df: pd.DataFrame, minimum: float = 55.0) -> pd.Series:
    from src.screeners.vcp_enhanced import VCPEnhancedScreener

    s = VCPEnhancedScreener()
    out = pd.Series(False, index=df.index)
    if len(df) < 70:
        return out

    for i in range(70, len(df) + 1):
        score, _ = s.calculate_vcs_score(df.iloc[:i])
        out.iloc[i - 1] = score >= float(minimum)
    return out


def ll_hl_confirmed(
    df: pd.DataFrame,
    pivot_left: int = 3,
    pivot_right: int = 3,
) -> pd.Series:
    """Detecta estructura LL -> HL con pivotes confirmados (sin repaint operativo)."""
    low = _col(df, "low", "Low").astype(float)
    pivots = _confirmed_pivots(low, left=pivot_left, right=pivot_right, mode="low")
    out = pd.Series(False, index=df.index)
    if len(pivots) < 3:
        return out

    structure_active = False
    pivot_lows: list[_PivotPoint] = []
    for p in pivots:
        pivot_lows.append(p)
        if len(pivot_lows) < 3:
            continue

        l0, l1, l2 = pivot_lows[-3], pivot_lows[-2], pivot_lows[-1]
        if l1.price < l0.price and l2.price > l1.price:
            structure_active = True

        if structure_active:
            out.iloc[p.confirm_idx] = True
            latest_close_idx = min(len(out) - 1, p.confirm_idx)
            out.iloc[latest_close_idx:] = True
            break

    return out


def _ll_hl_setups(
    df: pd.DataFrame,
    pivot_left: int,
    pivot_right: int,
) -> list[dict]:
    low = _col(df, "low", "Low").astype(float)
    high = _col(df, "high", "High").astype(float)
    pivots_low = _confirmed_pivots(low, left=pivot_left, right=pivot_right, mode="low")
    setups: list[dict] = []
    if len(pivots_low) < 3:
        return setups

    for i in range(2, len(pivots_low)):
        l0, ll, hl = pivots_low[i - 2], pivots_low[i - 1], pivots_low[i]
        if not (ll.price < l0.price and hl.price > ll.price):
            continue
        if hl.pivot_idx <= ll.pivot_idx:
            continue

        swing_high = high.iloc[ll.pivot_idx : hl.pivot_idx + 1].max()
        if not np.isfinite(swing_high):
            continue
        setups.append(
            {
                "ll_idx": ll.pivot_idx,
                "hl_idx": hl.pivot_idx,
                "hl_confirm_idx": hl.confirm_idx,
                "hl_price": hl.price,
                "swing_high": float(swing_high),
            }
        )
    return setups


def fib_0618_break_between_hl_and_swing_high(
    df: pd.DataFrame,
    pivot_left: int = 3,
    pivot_right: int = 3,
    fib_ratio: float = 0.618,
) -> pd.Series:
    """Trigger por close-cross sobre Fib 0.618 calculado desde HL hacia swing high."""
    close = _col(df, "close", "Close").astype(float)
    out = pd.Series(False, index=df.index)
    setups = _ll_hl_setups(df, pivot_left=pivot_left, pivot_right=pivot_right)
    if not setups:
        return out

    for setup in setups:
        fib_level = setup["hl_price"] + float(fib_ratio) * (
            setup["swing_high"] - setup["hl_price"]
        )
        start = max(1, int(setup["hl_confirm_idx"]))
        for i in range(start, len(close)):
            prev_close = float(close.iloc[i - 1])
            cur_close = float(close.iloc[i])
            if prev_close <= fib_level < cur_close:
                out.iloc[i] = True
                break
    return out


def second_pivot_break_swing_high(
    df: pd.DataFrame,
    pivot_left: int = 3,
    pivot_right: int = 3,
) -> pd.Series:
    """Segundo gatillo: ruptura por cierre del swing high entre LL y HL."""
    close = _col(df, "close", "Close").astype(float)
    out = pd.Series(False, index=df.index)
    setups = _ll_hl_setups(df, pivot_left=pivot_left, pivot_right=pivot_right)
    if not setups:
        return out

    for setup in setups:
        level = float(setup["swing_high"])
        start = max(1, int(setup["hl_confirm_idx"]))
        for i in range(start, len(close)):
            prev_close = float(close.iloc[i - 1])
            cur_close = float(close.iloc[i])
            if prev_close <= level < cur_close:
                out.iloc[i] = True
                break
    return out


def downtrend_line_break(
    df: pd.DataFrame,
    pivot_left: int = 3,
    pivot_right: int = 3,
    highs_window: int = 5,
    min_negative_slope: float = 0.02,
) -> pd.Series:
    """Ruptura de línea bajista por cierre usando regresión de swing highs recientes."""
    high = _col(df, "high", "High").astype(float)
    close = _col(df, "close", "Close").astype(float)
    out = pd.Series(False, index=df.index)

    pivots_high = _confirmed_pivots(
        high, left=pivot_left, right=pivot_right, mode="high"
    )
    if len(pivots_high) < highs_window:
        return out

    for i in range(max(1, highs_window), len(close)):
        confirmed = [p for p in pivots_high if p.confirm_idx <= i]
        if len(confirmed) < highs_window:
            continue
        sample = confirmed[-highs_window:]
        x = np.array([float(p.pivot_idx) for p in sample], dtype=float)
        y = np.array([float(p.price) for p in sample], dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        if slope >= -abs(float(min_negative_slope)):
            continue

        line_now = slope * float(i) + intercept
        line_prev = slope * float(i - 1) + intercept
        prev_close = float(close.iloc[i - 1])
        cur_close = float(close.iloc[i])
        if prev_close <= line_prev < cur_close:
            out.iloc[i] = True

    return out
