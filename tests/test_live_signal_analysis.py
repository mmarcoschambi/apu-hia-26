from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_live_signals import compute_forward_metrics, infer_signal_quality


def test_infer_signal_quality_clean():
    row = pd.Series({"data_quality_status": "ok", "dist_sma20": 2.5})
    assert infer_signal_quality(row) == "clean"


def test_infer_signal_quality_clean_with_ok_blocker():
    row = pd.Series(
        {
            "data_quality_status": "OK",
            "snapshot_waiting_for": "OK",
            "snapshot_blocker": "OK",
            "trigger_price": 10,
            "breakout_level": 9,
            "dist_sma20": 0.6,
        }
    )
    assert infer_signal_quality(row) == "clean"


def test_infer_signal_quality_breakout_resolved():
    row = pd.Series(
        {
            "data_quality_status": "warn",
            "trigger_price": 10,
            "breakout_level": 9,
            "snapshot_blocker": "waiting for breakout",
        }
    )
    assert infer_signal_quality(row) == "breakout_resolved"


def test_infer_signal_quality_ma_stack_broken():
    row = pd.Series({"snapshot_blocker": "ma stack broken", "dist_sma20": 1.0})
    assert infer_signal_quality(row) == "ma_stack_broken"


def test_compute_forward_metrics_handles_missing_future_data():
    history = pd.DataFrame(columns=["Close", "High", "Low"])
    history.index = pd.DatetimeIndex([])
    metrics = compute_forward_metrics(history, "2026-05-21", 100.0)
    assert pd.isna(metrics["forward_return_1d"])
    assert pd.isna(metrics["max_favorable_excursion"])


def test_compute_forward_metrics_uses_future_prices():
    history = pd.DataFrame(
        {
            "Close": [100, 102, 101, 105],
            "High": [101, 103, 102, 106],
            "Low": [99, 101, 100, 104],
        },
        index=pd.to_datetime(["2026-05-21", "2026-05-22", "2026-05-23", "2026-05-26"]),
    )
    metrics = compute_forward_metrics(history, "2026-05-21", 100.0)
    assert round(metrics["forward_return_1d"], 4) == 0.02
    assert round(metrics["forward_return_3d"], 4) == 0.05


def test_markdown_report_does_not_require_tabulate():
    from scripts.analyze_live_signals import _df_to_markdown_safe

    df = pd.DataFrame({"ticker": ["DBRG"], "signal_quality": ["clean"]})
    md = _df_to_markdown_safe(df)
    assert "| ticker" in md
    assert "DBRG" in md
