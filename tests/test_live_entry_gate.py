from __future__ import annotations

import sys
from pathlib import Path
import pytest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.finviz_live_promoter import check_snapshot_gate_partial
from src.signals.signal_engine import evaluate_ticker, compute_tier2_metrics


@pytest.fixture
def base_config():
    return {
        "tier1_strategy": {
            "risk_dollars": 2878.0
        },
        "tier2_filters": {
            "min_rvol": 1.1048,
            "min_adr": 1.8714,
            "max_dist_sma20": 6.768,
            "min_rs_percentile": 58.01,
            "use_rs_percentile": True,
            "min_dollar_volume": 20000000,
            "use_sector_etf_filter": True
        }
    }


def test_check_snapshot_gate_partial_pass(base_config):
    detail = {
        "rs_pct": 75.0,
        "adr": 3.5,
        "dollar_volume_m": 50.0,
        "dist_sma20_pct": 2.5,
        "sector_etf_ok": True,
        "sector_etf_dist_pct": 1.2
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is True
    assert reason == "passed"


def test_check_snapshot_gate_partial_fail_rs(base_config):
    detail = {
        "rs_pct": 45.0,  # below 58.01
        "adr": 3.5,
        "dollar_volume_m": 50.0,
        "dist_sma20_pct": 2.5,
        "sector_etf_ok": True
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is False
    assert "rs_percentile" in reason


def test_check_snapshot_gate_partial_fail_adr(base_config):
    detail = {
        "rs_pct": 75.0,
        "adr": 1.2,  # below 1.8714
        "dollar_volume_m": 50.0,
        "dist_sma20_pct": 2.5,
        "sector_etf_ok": True
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is False
    assert "adr" in reason


def test_check_snapshot_gate_partial_fail_dv(base_config):
    detail = {
        "rs_pct": 75.0,
        "adr": 3.5,
        "dollar_volume_m": 5.0,  # below 20.0M
        "dist_sma20_pct": 2.5,
        "sector_etf_ok": True
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is False
    assert "dollar_volume" in reason


def test_check_snapshot_gate_partial_fail_dist_sma20(base_config):
    detail = {
        "rs_pct": 75.0,
        "adr": 3.5,
        "dollar_volume_m": 50.0,
        "dist_sma20_pct": 8.5,  # above 6.768
        "sector_etf_ok": True
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is False
    assert "dist_sma20" in reason


def test_check_snapshot_gate_partial_fail_sector(base_config):
    detail = {
        "rs_pct": 75.0,
        "adr": 3.5,
        "dollar_volume_m": 50.0,
        "dist_sma20_pct": 2.5,
        "sector_etf_ok": False,  # blocked sector
        "sector_etf_dist_pct": -1.5
    }
    passed, reason = check_snapshot_gate_partial(detail, base_config)
    assert passed is False
    assert "sector_etf" in reason


def test_telegram_message_structure():
    # Simulate variables used during Telegram alert formatting
    entry_gate_status = "PASS"
    entry_gate_reason = "passed"
    entry_gate_source = "canonical_signal_engine"
    gate_rs_percentile = 85.5
    gate_adr_pct = 4.22
    gate_dollar_vol_M = 150.0
    gate_dist_sma20 = 2.3
    gate_sector_etf_dist = 1.15
    ticker = "AAPL"
    sec = "XLK"
    price = 210.5
    breakout_lvl = 205.0
    live_rvol = 2.5
    price_flag = ""

    # Determine icon and instruction for gate status
    if entry_gate_status == "PASS":
        gate_icon = "🟢"
        action_text = "Eligible for manual entry review"
    elif entry_gate_status == "BLOCKED":
        gate_icon = "🔴"
        action_text = "Research/watch only, no entry signal"
    else:
        gate_icon = "🟡"
        action_text = "Manual verification required"
    
    rs_str = f"{gate_rs_percentile:.1f}%" if gate_rs_percentile is not None else "N/A"
    adr_str = f"{gate_adr_pct:.2f}%" if gate_adr_pct is not None else "N/A"
    dv_str = f"${gate_dollar_vol_M:.1f}M" if gate_dollar_vol_M is not None else "N/A"
    dist20_str = f"{gate_dist_sma20:.2f}%" if gate_dist_sma20 is not None else "N/A"
    sec_dist_str = f"{gate_sector_etf_dist:.2f}%" if gate_sector_etf_dist is not None else "N/A"

    msg = (
        f"🧭 <b>LIVE SIGNAL: {ticker}</b> ({sec})\n\n"
        f"⚡ <b>TRIGGER DETAILS:</b>\n"
        f"• Live Trigger: <b>PASS</b>\n"
        f"• Price: <b>${price:.2f}</b>{price_flag} (Break: ${breakout_lvl:.2f})\n"
        f"• Live RVOL: <b>{live_rvol:.2f}x</b>\n\n"
        f"{gate_icon} <b>ENTRY GATE STATUS: {entry_gate_status}</b>\n"
        f"• Gate Reason: <code>{entry_gate_reason}</code>\n"
        f"• Source: <i>{entry_gate_source}</i>\n\n"
        f"📊 <b>GATE METRICS:</b>\n"
        f"• RS Percentile: <b>{rs_str}</b>\n"
        f"• ADR %: <b>{adr_str}</b>\n"
        f"• Dollar Volume: <b>{dv_str}</b>\n"
        f"• Dist SMA20: <b>{dist20_str}</b>\n"
        f"• Sector ETF Dist: <b>{sec_dist_str}</b>\n\n"
        f"📢 <b>ACTION:</b>\n"
        f"<b>{action_text}</b>"
    )

    assert "🧭 <b>LIVE SIGNAL: AAPL</b> (XLK)" in msg
    assert "🟢 <b>ENTRY GATE STATUS: PASS</b>" in msg
    assert "Gate Reason: <code>passed</code>" in msg
    assert "Source: <i>canonical_signal_engine</i>" in msg
    assert "RS Percentile: <b>85.5%</b>" in msg
    assert "ADR %: <b>4.22%</b>" in msg
    assert "Dollar Volume: <b>$150.0M</b>" in msg
    assert "Dist SMA20: <b>2.30%</b>" in msg
    assert "Sector ETF Dist: <b>1.15%</b>" in msg
    assert "Eligible for manual entry review" in msg


def test_dbrg_like_blocked_gate(base_config):
    # DBRG scenario: price breakouts and live RVOL are sufficient, but fails on RS or ADR.
    # We will generate a mock history DataFrame for a stock.
    # Needs at least 65 rows for evaluate_ticker
    dates = pd.date_range(end="2026-05-21", periods=100)
    mock_df = pd.DataFrame(
        {
            "open": [10.0] * 100,
            "high": [10.01] * 100,
            "low": [9.99] * 100,
            "close": [10.0] * 100,
            "volume": [500000.0] * 100
        },
        index=dates
    )
    # Give it very low ADR (e.g. 0.5% instead of min 1.8714%) so it fails ADR
    # Close high low are identical, so rolling ADR will be very low
    
    spy_df = pd.DataFrame(
        {
            "open": [400.0] * 100,
            "high": [401.0] * 100,
            "low": [399.0] * 100,
            "close": [400.0] * 100,
            "volume": [10000000.0] * 100
        },
        index=dates
    )

    # Let's verify compute_tier2_metrics on mock_df
    metrics = compute_tier2_metrics(mock_df, spy_df)
    assert metrics.adr_pct < 1.8714

    # Spike volume on the last day so RVOL passes
    mock_df.loc[dates[-1], "volume"] = 5000000.0

    # Let's call evaluate_ticker on this mock stock
    # We can pass custom combo config similar to base_config
    combo_cfg = {
        "screener": {},
        "pattern": {"signal_type": "breakout"},
        "tier1_strategy": base_config["tier1_strategy"],
        "tier2_filters": base_config["tier2_filters"]
    }

    decision = evaluate_ticker(
        ticker="DBRG",
        df=mock_df,
        spy_df=spy_df,
        combo_cfg=combo_cfg,
        mode="A",
        rs_percentile=45.0,  # low RS
        scan_date="2026-05-21",
        sector_etf_dist=0.03
    )

    assert decision.passed is False
    # Verify that it is blocked due to low RS (failing breakout rs_percentile is the first check if breakout_min is set,
    # or tier2_fail:rs_percentile inside apply_tier2_filters)
    assert "rs_percentile" in decision.reject_reason or "adr" in decision.reject_reason


def test_gate_evaluation_parity(base_config):
    # This test verifies that check_snapshot_gate_partial and evaluate_ticker produce coherent decisions
    # under similar conditions (mocked history vs snapshot details).
    dates = pd.date_range(end="2026-05-21", periods=100)
    
    # 1. Let's create a passing mock history that should PASS both engines
    # High volume, moderate volatility, close to breakout, aligned MA stack
    # ADR needs to be >= 1.8714% (e.g. daily high/low range 3%)
    mock_df_pass = pd.DataFrame(
        {
            "open": [100.0] * 100,
            "high": [101.5] * 100,
            "low": [98.5] * 100,
            "close": [100.0] * 100,
            "volume": [1000000.0] * 100
        },
        index=dates
    )
    # Ensure SMA stack is aligned: sma10 > sma20 > sma50 > sma200
    # Let's set close prices to be gradually increasing to satisfy SMA stack alignment
    for i in range(100):
        mock_df_pass.iloc[i, mock_df_pass.columns.get_loc("close")] = 100.0 + i * 0.5
        mock_df_pass.iloc[i, mock_df_pass.columns.get_loc("open")] = 100.0 + i * 0.5 - 0.2
        mock_df_pass.iloc[i, mock_df_pass.columns.get_loc("high")] = 100.0 + i * 0.5 + 1.5
        mock_df_pass.iloc[i, mock_df_pass.columns.get_loc("low")] = 100.0 + i * 0.5 - 1.5
    
    # Spike volume on the last day so RVOL passes min_rvol
    mock_df_pass.iloc[-1, mock_df_pass.columns.get_loc("volume")] = 3000000.0

    spy_df = pd.DataFrame(
        {
            "open": [400.0] * 100,
            "high": [401.0] * 100,
            "low": [399.0] * 100,
            "close": [400.0] * 100,
            "volume": [10000000.0] * 100
        },
        index=dates
    )

    # Calculate metrics
    metrics = compute_tier2_metrics(mock_df_pass, spy_df)
    assert metrics.adr_pct >= 1.8714
    
    combo_cfg = {
        "screener": {},
        "pattern": {"signal_type": "breakout"},
        "tier1_strategy": base_config["tier1_strategy"],
        "tier2_filters": base_config["tier2_filters"]
    }

    # Evaluate using canonical engine (which should PASS)
    decision_pass = evaluate_ticker(
        ticker="PASSING",
        df=mock_df_pass,
        spy_df=spy_df,
        combo_cfg=combo_cfg,
        mode="A",
        rs_percentile=75.0,  # high RS
        scan_date="2026-05-21",
        sector_etf_dist=0.03
    )
    
    # Snapshot details for the same ticker
    detail_pass = {
        "rs_pct": 75.0,
        "adr": metrics.adr_pct,
        "dollar_volume_m": metrics.dollar_vol_M,
        "dist_sma20_pct": metrics.dist_sma20,
        "sector_etf_ok": True,
        "sector_etf_dist_pct": 3.0
    }
    
    passed_partial, reason_partial = check_snapshot_gate_partial(detail_pass, base_config)
    
    # Both should pass or match
    assert decision_pass.passed == passed_partial


def test_cascaded_evaluation_loop_diagnostics():
    from unittest.mock import MagicMock
    
    # Setup mock decisions
    decision_a = MagicMock()
    decision_a.passed = False
    decision_a.reject_reason = "screener_fail:qullamaggie_momentum=FAIL"
    
    decision_b = MagicMock()
    decision_b.passed = False
    decision_b.reject_reason = "tier2_fail:dist_sma20:34.91>12.00"
    
    ACTIVE_COMBOS_MOCK = [
        ("combo_pure_momentum", "A"),
        ("combo_stage2_breakout", "B"),
    ]
    
    reasons_list = []
    best_decision = None
    passed_combo_name = None
    
    decisions = {
        "combo_pure_momentum": decision_a,
        "combo_stage2_breakout": decision_b
    }
    
    for combo_name, mode in ACTIVE_COMBOS_MOCK:
        decision = decisions[combo_name]
        if decision.passed:
            passed_combo_name = combo_name
            best_decision = decision
            break
        else:
            lbl = "Qulla" if combo_name == "combo_pure_momentum" else "Minervini" if combo_name == "combo_stage2_breakout" else combo_name
            reasons_list.append(f"{lbl}:{decision.reject_reason}")
            if best_decision is None:
                best_decision = decision
                
    if passed_combo_name:
        entry_gate_status = "PASS"
        entry_gate_reason = "passed"
    elif best_decision:
        entry_gate_status = "BLOCKED"
        entry_gate_reason = "; ".join(reasons_list)
        
    assert entry_gate_status == "BLOCKED"
    assert entry_gate_reason == "Qulla:screener_fail:qullamaggie_momentum=FAIL; Minervini:tier2_fail:dist_sma20:34.91>12.00"


def test_load_watchlist_tickers(tmp_path, monkeypatch):
    import json
    import pandas as pd
    from scripts.finviz_live_promoter import _load_watchlist_tickers
    
    # Mock FINVIZ_DIR and OUT_DIR to point to tmp_path
    monkeypatch.setattr("scripts.finviz_live_promoter.FINVIZ_DIR", tmp_path / "paper_finviz")
    monkeypatch.setattr("scripts.finviz_live_promoter.OUT_DIR", tmp_path / "live_signals")
    
    date = "2026-05-23"
    
    # 1. Create a mock snapshot.json with some tickers
    snapshot_dir = tmp_path / "paper_finviz" / date
    snapshot_dir.mkdir(parents=True)
    snapshot_data = {
        "watchlist_detail": {
            # Candidate 1: Proximity >= 70
            "AAPL": {
                "proximity_score": 75.0,
                "reasons": ["RVOL bajo"],
                "rs_pct": 50.0
            },
            # Candidate 2: RS >= 90, Proximity >= 50
            "MSFT": {
                "proximity_score": 55.0,
                "reasons": ["RVOL bajo", "Extendido"],
                "rs_pct": 95.0
            },
            # Non-candidate: reasons >= 3
            "TSLA": {
                "proximity_score": 80.0,
                "reasons": ["RVOL bajo", "Extendido", "MA stack roto"],
                "rs_pct": 95.0
            },
            # Non-candidate: proximity < 70 and RS < 90
            "NVDA": {
                "proximity_score": 45.0,
                "reasons": ["RVOL bajo"],
                "rs_pct": 80.0
            }
        }
    }
    with open(snapshot_dir / "snapshot.json", "w") as f:
        json.dump(snapshot_data, f)
        
    # 2. Create a mock combined.csv under live_signals
    combined_dir = tmp_path / "live_signals" / date
    combined_dir.mkdir(parents=True)
    df_combined = pd.DataFrame({
        "ticker": ["GOOG", "AMZN"]
    })
    df_combined.to_csv(combined_dir / "combined.csv", index=False)
    
    # Run the function
    watchlist_tickers = _load_watchlist_tickers(date)
    
    # Verify candidates from snapshot: AAPL, MSFT
    # Verify tickers from combined.csv: GOOG, AMZN
    # Verify non-candidates are excluded: TSLA, NVDA
    assert "AAPL" in watchlist_tickers
    assert "MSFT" in watchlist_tickers
    assert "GOOG" in watchlist_tickers
    assert "AMZN" in watchlist_tickers
    assert "TSLA" not in watchlist_tickers
    assert "NVDA" not in watchlist_tickers

