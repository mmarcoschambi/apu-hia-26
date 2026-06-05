"""
tests/test_shadow_weekly_report.py

Unit tests for scripts/shadow_weekly_report.py grouping, calculation, and generation logic.
"""

import json
from pathlib import Path
import pytest
import pandas as pd

from scripts.shadow_weekly_report import (
    to_friday_str,
    load_report_csv,
    load_journal_json,
    generate_weekly_report,
)


def test_to_friday_str():
    # 2026-05-18 is Monday -> Friday is 2026-05-22
    assert to_friday_str("2026-05-18") == "2026-05-22"
    # 2026-05-22 is Friday -> Friday is 2026-05-22
    assert to_friday_str("2026-05-22") == "2026-05-22"
    # 2026-05-23 is Saturday -> next Friday is 2026-05-29
    assert to_friday_str("2026-05-23") == "2026-05-29"
    # 2026-05-24 is Sunday -> next Friday is 2026-05-29
    assert to_friday_str("2026-05-24") == "2026-05-29"
    # 2026-05-25 is Monday -> Friday is 2026-05-29
    assert to_friday_str("2026-05-25") == "2026-05-29"


@pytest.fixture
def temp_replay_csv(tmp_path):
    csv_file = tmp_path / "report_temp.csv"
    data = (
        "date,ticker,sector_etf,rs,breakout_lvl,entry_price,stop_price,tp1,tp2,"
        "r_potential_tp1,r_potential_tp2,position_value,portfolio_pct,"
        "within_ticker_cap,excluded_by_xlv,allowed_shadow_candidate,shadow_status\n"
        "2026-05-18,ADM,XLB,90.1,83.1,83.1,77.283,90.3712,100.551,1.25,3.0,19944.0,0.1994,True,False,True,shadow_allowed\n"
        "2026-05-19,NXPI,XLK,93.9,306.62,306.62,285.1566,333.4493,371.0102,1.25,3.0,19930.3,0.1993,True,False,True,shadow_allowed\n"
        "2026-05-20,XLV_T,XLV,88.0,100.0,100.0,90.0,110.0,120.0,1.0,2.0,10000.0,0.10,True,True,False,blocked_by_sector\n"
        "2026-05-21,BLOCKED_T,XLI,95.0,50.0,50.0,45.0,55.0,60.0,1.0,2.0,0.0,0.0,False,False,False,blocked_by_ticker_cap\n"
    )
    with open(csv_file, "w") as f:
        f.write(data)
    return csv_file


@pytest.fixture
def temp_journal_json(tmp_path):
    journal_file = tmp_path / "journal_temp.json"
    journal_data = [
        {
            "date": "2026-05-18",
            "universe_size": 400,
            "regime_ok": True,
            "signals": [
                {"ticker": "ABC", "signal_date": "2026-05-18"},
                {"ticker": "DEF", "signal_date": "2026-05-18"}
            ]
        },
        {
            "date": "2026-05-20",
            "universe_size": 400,
            "regime_ok": True,
            "signals": [
                {"ticker": "XYZ", "signal_date": "2026-05-20"}
            ]
        }
    ]
    with open(journal_file, "w") as f:
        json.dump(journal_data, f)
    return journal_file


def test_load_report_csv(temp_replay_csv):
    df = load_report_csv(temp_replay_csv)
    assert not df.empty
    assert len(df) == 4
    assert list(df["week_ending"].unique()) == ["2026-05-22"]
    
    # Check boolean mapping
    assert bool(df.loc[df["ticker"] == "ADM", "allowed_shadow_candidate"].values[0]) is True
    assert bool(df.loc[df["ticker"] == "XLV_T", "excluded_by_xlv"].values[0]) is True
    assert bool(df.loc[df["ticker"] == "BLOCKED_T", "within_ticker_cap"].values[0]) is False


def test_load_journal_json(temp_journal_json):
    counts = load_journal_json(temp_journal_json)
    # Both 2026-05-18 and 2026-05-20 map to Friday 2026-05-22
    # The first entry has 2 signals, the second has 1. Total = 3 signals.
    assert counts.get("2026-05-22") == 3


def test_generate_weekly_report(temp_replay_csv, tmp_path):
    df = load_report_csv(temp_replay_csv)
    output_dir = tmp_path / "weekly_reports"
    
    report_path = generate_weekly_report(
        week_ending="2026-05-22",
        week_df=df,
        live_count=3,
        output_dir=output_dir
    )
    
    assert report_path.exists()
    
    # Read the file and check contents
    content = report_path.read_text()
    
    # Weekly summary checks
    assert "New Signals (Total Setups) | 4" in content
    assert "XLV Filtered | 1" in content
    assert "Ticker Cap Blocked | 1" in content
    assert "Allowed Shadow Candidates | 2" in content

    # Candidates List checks
    assert "ADM" in content
    assert "NXPI" in content
    assert "XLV_T" in content
    assert "BLOCKED_T" in content

    # Exposure Summary checks
    assert "XLB" in content
    assert "XLK" in content
    # XLV_T is not allowed so it shouldn't show in Sector Exposure with positive count
    # Let's verify sector exposure rows count
    assert "| XLB | 1 | $19,944.00 |" in content
    assert "| XLK | 1 | $19,930.30 |" in content
    assert "| XLV | 1 |" not in content  # XLV candidate was not allowed in exposure summary

    # Strategy Comparison checks
    # Shadow count = 2 (ADM, NXPI), Sim PnL (TP1) = 1.25+1.25 = 2.50R, Sim PnL (TP2) = 3.0+3.0 = 6.00R
    assert "| **Shadow (Russell E25 + ex-XLV)** | 2 | +2.50 R | +6.00 R |" in content
    
    # Russell E25 (without ex-XLV): allowed if within_ticker_cap is True (ADM, NXPI, XLV_T)
    # Count = 3, Sim PnL (TP1) = 1.25+1.25+1.00 = 3.50R, Sim PnL (TP2) = 3.00+3.00+2.00 = 8.00R
    assert "| **Russell E25 (without ex-XLV)** | 3 | +3.50 R | +8.00 R |" in content

    # Live Paper (VPS) count = 3
    assert "| **Live Paper (VPS)** | 3 | N/A | N/A |" in content
