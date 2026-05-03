from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import src.paper.demo_portfolio as demo_portfolio


def _patch_demo_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(demo_portfolio, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(demo_portfolio, "DEMO_ROOT", tmp_path / "outputs" / "paper_demo_telegram" / "runs")
    monkeypatch.setattr(
        demo_portfolio,
        "STATE_FILE",
        tmp_path / "outputs" / "paper_demo_telegram" / "system_state.json",
    )


def _signals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "combo": "combo_alpha",
                "entry_price": 100.0,
                "stop_loss": 92.0,
                "position_size": 10,
                "tp1_price": 110.0,
                "tp2_price": 120.0,
                "entry_score": 0.81,
            },
            {
                "ticker": "MSFT",
                "combo": "combo_beta",
                "entry_price": 200.0,
                "stop_loss": 188.0,
                "position_size": 5,
                "tp1_price": 215.0,
                "tp2_price": 230.0,
                "entry_score": 0.79,
            },
        ]
    )


def test_approve_and_close_preserve_history(monkeypatch, tmp_path):
    _patch_demo_paths(monkeypatch, tmp_path)
    date = "2024-06-17"

    intents = demo_portfolio.persist_candidates(date, _signals(), source_universe="finviz")
    first_signal = intents[0].signal_id
    second_signal = intents[1].signal_id

    result_one = demo_portfolio.approve_intent(date, first_signal, "chat", "user", "cb-1")
    assert result_one["ok"] is True

    result_two = demo_portfolio.approve_intent(date, second_signal, "chat", "user", "cb-2")
    assert result_two["ok"] is True

    orders = pd.read_csv(demo_portfolio.day_dir(date) / "orders.csv")
    positions = pd.read_csv(demo_portfolio.day_dir(date) / "positions.csv")
    intents_df = pd.read_csv(demo_portfolio.day_dir(date) / "execution_intents.csv")
    report = json.loads((demo_portfolio.day_dir(date) / "run_report.json").read_text())

    assert len(orders) == 2
    assert len(positions) == 2
    assert set(intents_df["status"]) == {"approved"}
    assert report["open_positions"] == 2

    first_position = positions.iloc[0]["position_id"]
    preview = demo_portfolio.close_position(date, first_position, "chat", "user", "cb-3", confirm=False)
    assert preview["confirm_required"] is True
    close = demo_portfolio.close_position(date, first_position, "chat", "user", "cb-4", confirm=True)
    assert close["ok"] is True

    orders_after = pd.read_csv(demo_portfolio.day_dir(date) / "orders.csv")
    fills_after = pd.read_csv(demo_portfolio.day_dir(date) / "fills.csv")
    positions_after = pd.read_csv(demo_portfolio.day_dir(date) / "positions.csv")
    report_after = json.loads((demo_portfolio.day_dir(date) / "run_report.json").read_text())

    assert len(orders_after) == 3
    assert len(fills_after) == 3
    assert len(positions_after) == 2
    assert (positions_after["status"] == "closed").sum() == 1
    assert report_after["closed_positions"] == 1
    assert report_after["open_positions"] == 1


def test_reject_and_snooze_update_intent_status(monkeypatch, tmp_path):
    _patch_demo_paths(monkeypatch, tmp_path)
    date = "2024-06-18"

    intents = demo_portfolio.persist_candidates(date, _signals().head(1), source_universe="finviz")
    signal_id = intents[0].signal_id

    rejected = demo_portfolio.reject_intent(date, signal_id, "chat", "user", "cb-1")
    assert rejected["ok"] is True

    intents_df = pd.read_csv(demo_portfolio.day_dir(date) / "execution_intents.csv")
    assert intents_df.iloc[0]["status"] == "rejected"

    intents = demo_portfolio.persist_candidates(date, _signals().head(1), source_universe="finviz")
    signal_id = intents[0].signal_id
    snoozed = demo_portfolio.snooze_intent(date, signal_id, "chat", "user", "cb-2")
    assert snoozed["ok"] is True
    assert snoozed["snoozed_until"]

    intents_df = pd.read_csv(demo_portfolio.day_dir(date) / "execution_intents.csv")
    assert intents_df.iloc[0]["status"] == "snoozed"
    report = json.loads((demo_portfolio.day_dir(date) / "run_report.json").read_text())
    assert report["snoozed_intents"] == 1
