#!/usr/bin/env python3
"""Regression tests for historical F4 preflight inputs."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.edge_analytics import compute_preflight


def test_preflight_uses_signal_time_when_trade_date_missing():
    plans = []
    for day in range(1, 62):
        date_str = f"2024-03-{day:02d}" if day <= 31 else f"2024-04-{day-31:02d}"
        plans.append(
            {
                "source_system": "A",
                "signal_time": f"{date_str}T00:00:00",
                "hydrated_price_source": "close_signal_date",
            }
        )
        plans.append(
            {
                "source_system": "B",
                "signal_time": f"{date_str}T00:00:00",
                "hydrated_price_source": "input",
                "metadata": {
                    "historical_plan": True,
                    "price_origin": "trades_csv",
                },
            }
        )

    preflight = compute_preflight(plans)
    assert preflight.common_sessions >= 60
    assert preflight.passed


def test_preflight_accepts_historical_b_without_explicit_hydrated_source():
    plans = []
    for day in range(1, 62):
        date_str = f"2024-03-{day:02d}" if day <= 31 else f"2024-04-{day-31:02d}"
        plans.append(
            {
                "source_system": "A",
                "signal_time": f"{date_str}T00:00:00",
                "hydrated_price_source": "close_signal_date",
            }
        )
        plans.append(
            {
                "source_system": "B",
                "signal_time": f"{date_str}T00:00:00",
                "entry_price_ref": 100.0,
                "metadata": {
                    "historical_plan": True,
                    "price_origin": "trades_csv",
                },
            }
        )

    preflight = compute_preflight(plans)
    assert preflight.hydrated_rate_B == 1.0
    assert preflight.passed


def main():
    test_preflight_uses_signal_time_when_trade_date_missing()
    test_preflight_accepts_historical_b_without_explicit_hydrated_source()
    print("[PASS] test_preflight_uses_signal_time_when_trade_date_missing")
    print("[PASS] test_preflight_accepts_historical_b_without_explicit_hydrated_source")


if __name__ == "__main__":
    main()
