"""Tests para filtros complejos y backtest event-driven de presets (System B)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from scripts.backtest_presets_pack import (
    compute_metrics,
    evaluate_filter_series,
    simulate_preset_trades,
)
from src.strategies.preset_filter_library import (
    downtrend_line_break,
    fib_0618_break_between_hl_and_swing_high,
    ll_hl_confirmed,
    second_pivot_break_swing_high,
)


def _ohlcv_from_lists(
    close: list[float], high: list[float], low: list[float]
) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(close), freq="B")
    open_ = [c * 0.99 for c in close]
    volume = [1_000_000.0] * len(close)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


def test_ll_hl_confirmed_emits_only_after_confirmation() -> None:
    low = [12, 11, 10, 11, 12, 9, 10, 11, 10, 11, 12]
    high = [l + 5 for l in low]
    close = [l + 3 for l in low]
    df = _ohlcv_from_lists(close=close, high=high, low=low)

    out = ll_hl_confirmed(df, pivot_left=1, pivot_right=1)

    assert bool(out.iloc[8]) is False
    assert bool(out.iloc[9]) is True


def test_fib_0618_break_cross_after_hl_confirmation() -> None:
    low = [12, 11, 10, 11, 12, 9, 10, 11, 10, 11, 12]
    high = [14, 15, 14, 15, 14, 14, 15, 14, 13, 13, 13]
    close = [12, 12, 11, 12, 12, 10, 12, 12, 12, 13.0, 13.2]
    df = _ohlcv_from_lists(close=close, high=high, low=low)

    out = fib_0618_break_between_hl_and_swing_high(
        df,
        pivot_left=1,
        pivot_right=1,
        fib_ratio=0.618,
    )

    assert bool(out.iloc[9]) is False
    assert bool(out.iloc[10]) is True


def test_second_pivot_break_cross_after_hl_confirmation() -> None:
    low = [12, 11, 10, 11, 12, 9, 10, 11, 10, 11, 12]
    high = [14, 15, 14, 15, 14, 14, 15, 14, 13, 13, 13]
    close = [12, 12, 11, 12, 12, 10, 12, 12, 12, 14.9, 15.2]
    df = _ohlcv_from_lists(close=close, high=high, low=low)

    out = second_pivot_break_swing_high(df, pivot_left=1, pivot_right=1)

    assert bool(out.iloc[9]) is False
    assert bool(out.iloc[10]) is True


def test_downtrend_line_break_regression_trigger() -> None:
    high = [19.0, 20.0, 18.0, 19.0, 17.0, 18.0, 16.0, 17.0, 15.0, 16.0, 15.8, 15.7]
    close = [18.2, 19.2, 17.2, 18.2, 16.2, 17.2, 15.2, 16.2, 14.8, 15.0, 16.2, 16.0]
    low = [c - 1.0 for c in close]
    df = _ohlcv_from_lists(close=close, high=high, low=low)

    out = downtrend_line_break(
        df,
        pivot_left=1,
        pivot_right=1,
        highs_window=5,
        min_negative_slope=0.05,
    )

    assert bool(out.iloc[9]) is False
    assert bool(out.iloc[10]) is True


def test_event_driven_entries_use_next_open_and_are_reproducible() -> None:
    dates = pd.date_range("2024-01-01", periods=8, freq="B")
    df = pd.DataFrame(
        {
            "open": [10, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7],
            "high": [10.2, 10.3, 10.4, 10.5, 10.9, 11.0, 11.2, 11.1],
            "low": [9.8, 9.9, 10.0, 10.1, 10.2, 10.3, 10.4, 10.5],
            "close": [10.0, 10.1, 10.2, 10.3, 10.8, 10.9, 11.0, 10.95],
            "volume": [1_000_000.0] * 8,
        },
        index=dates,
    )
    preset_hit = pd.Series(
        [False, False, False, True, False, False, False, False], index=dates
    )
    requires = ["rel_volume_min"]
    filter_states = {"rel_volume_min": pd.Series([True] * 8, index=dates)}
    backtest_cfg = {
        "stop_pct": 0.05,
        "target_pct": 0.1,
        "timeout_bars": 2,
        "slippage_bps": 5,
        "fee_bps": 5,
    }

    first = simulate_preset_trades(
        preset_id="preset_99",
        ticker="TEST",
        df=df,
        preset_hit=preset_hit,
        requires=requires,
        filter_states=filter_states,
        backtest_cfg=backtest_cfg,
    )
    second = simulate_preset_trades(
        preset_id="preset_99",
        ticker="TEST",
        df=df,
        preset_hit=preset_hit,
        requires=requires,
        filter_states=filter_states,
        backtest_cfg=backtest_cfg,
    )

    assert len(first.signal_rows) == 1
    assert first.signal_rows[0]["entry_date"] == dates[4].strftime("%Y-%m-%d")
    assert first.signal_rows[0]["entry_price_rule"] == "open_t_plus_1"
    assert first.rows == second.rows


def test_compute_metrics_sorts_trades_chronologically_for_drawdown() -> None:
    trades_df = pd.DataFrame(
        [
            {
                "ticker": "BBB",
                "entry_date": "2024-01-01",
                "exit_date": "2024-01-02",
                "entry_price": 10.0,
                "pnl": -200.0,
                "r_multiple": -1.0,
            },
            {
                "ticker": "AAA",
                "entry_date": "2023-12-29",
                "exit_date": "2024-01-01",
                "entry_price": 10.0,
                "pnl": 100.0,
                "r_multiple": 0.5,
            },
        ]
    )

    metrics = compute_metrics(trades_df, initial_capital=1000.0)

    assert metrics["max_dd"] < 0


def test_unknown_filter_id_raises_explicit_error() -> None:
    dates = pd.date_range("2024-01-01", periods=5, freq="B")
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10, 10],
            "high": [11, 11, 11, 11, 11],
            "low": [9, 9, 9, 9, 9],
            "close": [10, 10, 10, 10, 10],
            "volume": [1_000_000.0] * 5,
        },
        index=dates,
    )

    with pytest.raises(ValueError, match="Filter id no implementado"):
        evaluate_filter_series(
            filter_id="unknown_filter_typo",
            df=df,
            ticker="TEST",
            filter_defaults={},
            preset_params={},
            rs_rank_map={},
        )
