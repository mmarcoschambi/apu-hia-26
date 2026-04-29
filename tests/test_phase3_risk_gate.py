#!/usr/bin/env python3
"""Tests for Phase 3 Risk Gate."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.integration.execution_plan import ExecutionPlanRow
from src.integration.price_hydrator import hydrate_prices
from src.integration.risk_gate import (
    RiskGateConfig,
    apply_risk_gate,
)


def create_routed_signal(
    ticker="AAPL",
    source="A",
    entry_price=150.0,
    stop_price=140.0,
    score=75.0,
):
    from src.integration.unified_signal import UnifiedSignal
    from src.integration.routed_signal import RoutedSignal

    signal = UnifiedSignal(
        source_system=source,
        strategy_id="test_strategy",
        ticker=ticker,
        timeframe="1D",
        signal_time="2026-04-22T00:00:00",
        side="long",
        entry_type="next_open",
        entry_price_ref=entry_price,
        stop_price=stop_price,
        normalized_score=score,
    )
    return RoutedSignal(
        signal=signal,
        router_decision="accepted",
        router_reason="won_by_score",
        collision_key=f"{ticker}_2026-04-22_daily",
    )


def test_hydrate_price_keeps_existing_entry_ref():
    routed = create_routed_signal(entry_price=150.0)
    hydrated, rejected = hydrate_prices([routed], MagicMock())

    assert len(hydrated) == 1
    assert hydrated[0].signal.entry_price_ref == 150.0
    assert hydrated[0].signal.metadata.get("hydrated_price_source") == "input"
    print("[PASS] test_hydrate_price_keeps_existing_entry_ref")


def test_hydrate_price_uses_close_for_zero_entry_ref():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS ohlcv_cache ("
            "ticker TEXT, date TEXT, open REAL, high REAL, "
            "low REAL, close REAL, volume INTEGER, "
            "dollar_volume REAL, rolling_dollar_vol_20 REAL, "
            "PRIMARY KEY (ticker, date))"
        )
        conn.execute(
            "INSERT INTO ohlcv_cache VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "AAPL",
                "2026-04-22",
                153.0,
                156.0,
                152.5,
                155.0,
                50000000,
                7750000000.0,
                7500000000.0,
            ),
        )
        conn.commit()
        conn.close()

        from src.integration.unified_signal import UnifiedSignal
        from src.integration.routed_signal import RoutedSignal

        signal = UnifiedSignal(
            source_system="A",
            strategy_id="test",
            ticker="AAPL",
            timeframe="1D",
            signal_time="2026-04-22T00:00:00",
            side="long",
            entry_type="next_open",
            entry_price_ref=0.0,
        )
        routed = RoutedSignal(
            signal=signal,
            router_decision="accepted",
            router_reason="won_by_score",
            collision_key="AAPL_2026-04-22_daily",
        )

        hydrated, rejected = hydrate_prices([routed], db_path)

        assert len(hydrated) == 1
        assert hydrated[0].signal.entry_price_ref == 155.0
        assert (
            hydrated[0].signal.metadata.get("hydrated_price_source")
            == "close_signal_date"
        )
    print("[PASS] test_hydrate_price_uses_close_for_zero_entry_ref")


def test_missing_price_goes_to_rejected_pricing():
    routed = create_routed_signal(entry_price=0.0)
    hydrated, rejected = hydrate_prices([routed], MagicMock())

    assert len(hydrated) == 0
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "missing_price"
    print("[PASS] test_missing_price_goes_to_rejected_pricing")


def test_risk_per_trade_sizing_basic():
    routed = create_routed_signal(entry_price=100.0, stop_price=90.0)
    config = RiskGateConfig(risk_per_trade_usd=100.0)

    planned, rejected = apply_risk_gate([routed], config)

    assert len(planned) == 1
    plan = planned[0]
    assert plan.per_share_risk == 10.0
    assert plan.shares == 10
    assert plan.notional_usd == 1000.0
    print("[PASS] test_risk_per_trade_sizing_basic")


def test_invalid_stop_uses_default_stop_pct():
    routed = create_routed_signal(entry_price=100.0, stop_price=None)
    config = RiskGateConfig(risk_per_trade_usd=100.0, default_stop_pct=0.1)

    planned, rejected = apply_risk_gate([routed], config)

    assert len(planned) == 1
    plan = planned[0]
    assert plan.per_share_risk == 10.0
    assert plan.shares == 10
    print("[PASS] test_invalid_stop_uses_default_stop_pct")


def test_budget_split_enforced_A_70_B_30():
    signals = [
        create_routed_signal(
            ticker="A", source="A", entry_price=100.0, stop_price=90.0, score=80.0
        ),
        create_routed_signal(
            ticker="B", source="B", entry_price=100.0, stop_price=90.0, score=70.0
        ),
    ]
    config = RiskGateConfig(
        capital_total_usd=1000.0,
        risk_per_trade_usd=100.0,
        budget_split={"A": 0.7, "B": 0.3},
    )

    planned, rejected = apply_risk_gate(signals, config)

    a_plans = [p for p in planned if p.source_system == "A"]
    b_plans = [p for p in planned if p.source_system == "B"]

    assert len(a_plans) == 1
    assert len(b_plans) == 0
    print("[PASS] test_budget_split_enforced_A_70_B_30")


def test_max_exposure_total_enforced():
    signals = [
        create_routed_signal(
            ticker="A", source="A", entry_price=100.0, stop_price=90.0, score=80.0
        ),
        create_routed_signal(
            ticker="B", source="A", entry_price=100.0, stop_price=90.0, score=70.0
        ),
        create_routed_signal(
            ticker="C", source="A", entry_price=100.0, stop_price=90.0, score=60.0
        ),
    ]
    config = RiskGateConfig(
        capital_total_usd=10000.0,
        risk_per_trade_usd=100.0,
        max_exposure_total_pct=0.2,
        min_shares=1,
    )

    planned, rejected = apply_risk_gate(signals, config)

    total_notional = sum(p.notional_usd for p in planned)
    assert total_notional <= 2000.0
    assert any(r.get("reason") == "max_exposure_total" for r in rejected)
    print("[PASS] test_max_exposure_total_enforced")


def test_max_exposure_per_ticker_enforced():
    signals = [
        create_routed_signal(
            ticker="AAPL", source="A", entry_price=100.0, stop_price=90.0, score=80.0
        ),
        create_routed_signal(
            ticker="AAPL", source="A", entry_price=100.0, stop_price=90.0, score=70.0
        ),
    ]
    config = RiskGateConfig(
        capital_total_usd=100000.0,
        risk_per_trade_usd=100.0,
        max_exposure_per_ticker_pct=0.05,
    )

    planned, rejected = apply_risk_gate(signals, config)

    aapl_plans = [p for p in planned if p.ticker == "AAPL"]
    total_aapl = sum(p.notional_usd for p in aapl_plans)
    assert total_aapl <= 5000.0
    print("[PASS] test_max_exposure_per_ticker_enforced")


def test_max_positions_per_source_enforced():
    signals = [
        create_routed_signal(
            ticker="A", source="B", entry_price=100.0, stop_price=90.0, score=90.0 - i
        )
        for i in range(6)
    ]
    config = RiskGateConfig(
        capital_total_usd=100000.0,
        risk_per_trade_usd=100.0,
        max_positions_per_source={"B": 3},
    )

    planned, rejected = apply_risk_gate(signals, config)

    b_positions = sum(1 for p in planned if p.source_system == "B")
    assert b_positions <= 3
    print("[PASS] test_max_positions_per_source_enforced")


def test_execution_plan_deterministic_order():
    routed = [
        create_routed_signal(ticker="C", source="B", score=70.0),
        create_routed_signal(ticker="A", source="A", score=80.0),
        create_routed_signal(ticker="B", source="A", score=75.0),
    ]
    config = RiskGateConfig(risk_per_trade_usd=100.0)

    planned1, _ = apply_risk_gate(routed, config)
    planned2, _ = apply_risk_gate(routed[:], config)

    assert len(planned1) == len(planned2)
    for p1, p2 in zip(planned1, planned2):
        assert p1.ticker == p2.ticker
    print("[PASS] test_execution_plan_deterministic_order")


def main():
    test_hydrate_price_keeps_existing_entry_ref()
    test_hydrate_price_uses_close_for_zero_entry_ref()
    test_missing_price_goes_to_rejected_pricing()
    test_risk_per_trade_sizing_basic()
    test_invalid_stop_uses_default_stop_pct()
    test_budget_split_enforced_A_70_B_30()
    test_max_exposure_total_enforced()
    test_max_exposure_per_ticker_enforced()
    test_max_positions_per_source_enforced()
    test_execution_plan_deterministic_order()
    print("\n=== All Phase 3 tests passed ===")


if __name__ == "__main__":
    main()
