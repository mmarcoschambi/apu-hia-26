"""
Structure Pivot indicator (LL->HL / HH->LH) with confirmed pivots only.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class PivotState:
    """State for one pivot length and one side (long/short)."""

    length: int
    prev_p: Optional[float] = None
    prev_idx: Optional[int] = None
    curr_p: Optional[float] = None
    curr_idx: Optional[int] = None
    is_setup: bool = False
    break_val: Optional[float] = None
    break_idx: Optional[int] = None
    is_long: bool = True
    invalidated: bool = False
    breakout_triggered: bool = False
    breakout_idx: Optional[int] = None
    distance_to_break_pct: Optional[float] = None


def _col(df: pd.DataFrame, lower: str, upper: str) -> pd.Series:
    if lower in df.columns:
        return df[lower]
    return df[upper]


def _is_confirmed_pivot_low(lows: np.ndarray, pivot_idx: int, length: int) -> bool:
    window = lows[pivot_idx - length : pivot_idx + length + 1]
    center = lows[pivot_idx]
    return bool(center == np.min(window))


def _is_confirmed_pivot_high(highs: np.ndarray, pivot_idx: int, length: int) -> bool:
    window = highs[pivot_idx - length : pivot_idx + length + 1]
    center = highs[pivot_idx]
    return bool(center == np.max(window))


def _scan_single_length(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    length: int,
    is_long: bool,
) -> PivotState:
    state = PivotState(length=length, is_long=is_long)
    bars = len(closes)

    if bars < (2 * length + 1):
        return state

    for t in range(2 * length, bars):
        pivot_idx = t - length
        is_new_pivot = (
            _is_confirmed_pivot_low(lows, pivot_idx, length)
            if is_long
            else _is_confirmed_pivot_high(highs, pivot_idx, length)
        )

        if is_new_pivot:
            pivot_val = float(lows[pivot_idx] if is_long else highs[pivot_idx])
            state.prev_p = state.curr_p
            state.prev_idx = state.curr_idx
            state.curr_p = pivot_val
            state.curr_idx = pivot_idx
            state.is_setup = False
            state.break_val = None
            state.break_idx = None
            state.invalidated = False
            state.breakout_triggered = False
            state.breakout_idx = None

            if state.prev_p is not None and state.prev_idx is not None:
                if is_long and state.curr_p > state.prev_p:
                    segment = highs[state.prev_idx : state.curr_idx + 1]
                    rel_idx = int(np.argmax(segment))
                    state.break_val = float(segment[rel_idx])
                    state.break_idx = state.prev_idx + rel_idx
                    state.is_setup = True
                elif (not is_long) and state.curr_p < state.prev_p:
                    segment = lows[state.prev_idx : state.curr_idx + 1]
                    rel_idx = int(np.argmin(segment))
                    state.break_val = float(segment[rel_idx])
                    state.break_idx = state.prev_idx + rel_idx
                    state.is_setup = True

        if state.is_setup and state.curr_p is not None and state.break_val is not None:
            if is_long:
                if lows[t] < state.curr_p:
                    state.invalidated = True
                    state.is_setup = False
                elif closes[t] > state.break_val:
                    state.breakout_triggered = True
                    state.breakout_idx = t
                    state.is_setup = False
            else:
                if highs[t] > state.curr_p:
                    state.invalidated = True
                    state.is_setup = False
                elif closes[t] < state.break_val:
                    state.breakout_triggered = True
                    state.breakout_idx = t
                    state.is_setup = False

    if state.break_val is not None and closes[-1] > 0:
        close_now = float(closes[-1])
        if is_long:
            state.distance_to_break_pct = (state.break_val - close_now) / close_now * 100.0
        else:
            state.distance_to_break_pct = (close_now - state.break_val) / close_now * 100.0

    return state


def select_winner(
    states: List[PivotState],
    mode: str = "tightest",
) -> Optional[PivotState]:
    """Select winner from active setups by priority mode."""
    valid = [
        s
        for s in states
        if s.is_setup and s.break_val is not None and not s.invalidated and not s.breakout_triggered
    ]
    if not valid:
        return None

    if mode == "longest":
        return max(valid, key=lambda s: s.length)
    if mode == "shortest":
        return min(valid, key=lambda s: s.length)

    if valid[0].is_long:
        return min(valid, key=lambda s: s.break_val)
    return max(valid, key=lambda s: s.break_val)


def scan_structures(
    df: pd.DataFrame,
    min_len: int = 2,
    max_len: int = 10,
    priority_mode: str = "tightest",
) -> Dict[str, Optional[PivotState]]:
    """
    Scan LL->HL and HH->LH structures for lengths in [min_len, max_len].

    Uses only confirmed pivots (no lookahead in signal availability).
    """
    if min_len < 1 or max_len < min_len:
        raise ValueError("Invalid pivot range: require 1 <= min_len <= max_len")

    high = _col(df, "high", "High").astype(float).to_numpy()
    low = _col(df, "low", "Low").astype(float).to_numpy()
    close = _col(df, "close", "Close").astype(float).to_numpy()

    states_long: List[PivotState] = []
    states_short: List[PivotState] = []

    for length in range(min_len, max_len + 1):
        states_long.append(_scan_single_length(high, low, close, length, is_long=True))
        states_short.append(_scan_single_length(high, low, close, length, is_long=False))

    return {
        "long": select_winner(states_long, priority_mode),
        "short": select_winner(states_short, priority_mode),
        "all_long": states_long,
        "all_short": states_short,
    }
