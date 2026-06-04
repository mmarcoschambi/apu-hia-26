"""Tests for the Shadow Replay engine."""

from pathlib import Path

import pytest
import pandas as pd

from src.shadow.replay import (
    ShadowReplayEngine,
    ReplayRecord,
    STOP_PCT,
    TP1_R,
    TP2_R,
    TICKER_CAP_PCT,
)

FIXTURE_ETL_DIR = Path(__file__).resolve().parents[1] / "outputs" / "shadow_sandbox"


@pytest.fixture
def sample_setups_csv(tmp_path):
    """Create a minimal ETL output dir with a setups.csv for testing."""
    out_dir = tmp_path / "finviz_runs" / "2026-05-19"
    out_dir.mkdir(parents=True)
    df = pd.DataFrame(
        [
            {
                "run_date": "2026-05-19",
                "ticker": "NXPI",
                "rs": 93.9,
                "breakout_lvl": 306.62,
                "dist_sma20_pct": 5.52,
                "rvol": 0.8,
                "waiting_desc": "Breakout > 306.62",
                "sector_etf": "XLK",
                "excluded_by_xlv": False,
                "allowed_shadow_candidate": True,
                "shadow_status": "shadow_allowed",
            },
            {
                "run_date": "2026-05-18",
                "ticker": "ADM",
                "rs": 90.1,
                "breakout_lvl": 83.10,
                "dist_sma20_pct": 6.64,
                "rvol": 1.12,
                "waiting_desc": "Breakout > 83.10",
                "sector_etf": "XLB",
                "excluded_by_xlv": False,
                "allowed_shadow_candidate": True,
                "shadow_status": "shadow_allowed",
            },
        ]
    )
    df.to_csv(out_dir / "setups.csv", index=False)
    return tmp_path


@pytest.fixture
def sample_setups_xlv_only(tmp_path):
    out_dir = tmp_path / "finviz_runs" / "2026-05-19"
    out_dir.mkdir(parents=True)
    df = pd.DataFrame(
        [
            {
                "run_date": "2026-05-19",
                "ticker": "UNH",
                "rs": 85.2,
                "breakout_lvl": 500.00,
                "dist_sma20_pct": 3.0,
                "rvol": 1.2,
                "waiting_desc": "Breakout > 500.00",
                "sector_etf": "XLV",
                "excluded_by_xlv": True,
                "allowed_shadow_candidate": False,
                "shadow_status": "blocked_by_sector",
            },
        ]
    )
    df.to_csv(out_dir / "setups.csv", index=False)
    return tmp_path


class TestShadowReplayEngine:
    def test_run_with_samples(self, sample_setups_csv):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_csv)
        records = engine.run()
        assert len(records) == 2

        nxpi = records[0]
        assert nxpi.ticker == "NXPI"
        assert nxpi.sector_etf == "XLK"
        assert nxpi.rs == 93.9
        assert nxpi.breakout_lvl == 306.62
        assert nxpi.entry_price == 306.62

        expected_stop = round(306.62 * (1 - STOP_PCT), 4)
        assert nxpi.stop_price == expected_stop

        expected_shares = int((100_000 * TICKER_CAP_PCT) / 306.62)
        expected_position = round(expected_shares * 306.62, 2)
        assert nxpi.position_value == expected_position
        assert nxpi.portfolio_pct == round(expected_position / 100_000, 4)
        assert nxpi.within_ticker_cap is True
        assert nxpi.shadow_status == "shadow_allowed"

    def test_r_potential_calculation(self, sample_setups_csv):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_csv)
        records = engine.run()

        for r in records:
            risk = r.entry_price - r.stop_price
            assert r.r_potential_tp1 == round((r.tp1 - r.entry_price) / risk, 2)
            assert r.r_potential_tp2 == round((r.tp2 - r.entry_price) / risk, 2)
            assert r.r_potential_tp1 == TP1_R
            assert r.r_potential_tp2 == TP2_R

    def test_xlv_blocked(self, sample_setups_xlv_only):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_xlv_only)
        records = engine.run()
        assert len(records) == 1
        r = records[0]
        assert r.ticker == "UNH"
        assert r.excluded_by_xlv is True
        assert r.allowed_shadow_candidate is False
        assert r.shadow_status == "blocked_by_sector"

    def test_output_files_created(self, sample_setups_csv):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_csv)
        engine.run()
        assert (engine.replay_dir / "report.csv").exists()
        assert (engine.replay_dir / "summary.md").exists()

    def test_report_csv_content(self, sample_setups_csv):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_csv)
        engine.run()
        df = pd.read_csv(engine.replay_dir / "report.csv")
        assert len(df) == 2
        assert list(df.columns) == [
            "date",
            "ticker",
            "sector_etf",
            "rs",
            "breakout_lvl",
            "entry_price",
            "stop_price",
            "tp1",
            "tp2",
            "r_potential_tp1",
            "r_potential_tp2",
            "position_value",
            "portfolio_pct",
            "within_ticker_cap",
            "excluded_by_xlv",
            "allowed_shadow_candidate",
            "shadow_status",
            "price_source",
        ]
        assert df.iloc[0]["ticker"] == "NXPI"
        assert df.iloc[1]["ticker"] == "ADM"

    def test_summary_md_content(self, sample_setups_csv):
        engine = ShadowReplayEngine(shadow_dir=sample_setups_csv)
        engine.run()
        text = (engine.replay_dir / "summary.md").read_text()
        assert "Shadow Replay v1 Summary" in text
        assert "ADM" in text
        assert "NXPI" in text
        assert "Ticker cap" in text

    def test_no_setups_dir(self, tmp_path):
        engine = ShadowReplayEngine(shadow_dir=tmp_path)
        records = engine.run()
        assert records == []
        assert (engine.replay_dir / "summary.md").exists()

    def test_empty_setups_csv(self, tmp_path):
        out_dir = tmp_path / "finviz_runs" / "2026-05-19"
        out_dir.mkdir(parents=True)
        pd.DataFrame().to_csv(out_dir / "setups.csv", index=False)
        engine = ShadowReplayEngine(shadow_dir=tmp_path)
        records = engine.run()
        assert records == []

    def test_missing_breakout_lvl(self, tmp_path):
        out_dir = tmp_path / "finviz_runs" / "2026-05-19"
        out_dir.mkdir(parents=True)
        df = pd.DataFrame(
            [
                {
                    "ticker": "BAD",
                    "breakout_lvl": 0,
                    "rs": 0,
                    "sector_etf": "XLK",
                    "excluded_by_xlv": False,
                    "allowed_shadow_candidate": True,
                    "shadow_status": "shadow_allowed",
                }
            ]
        )
        df.to_csv(out_dir / "setups.csv", index=False)
        engine = ShadowReplayEngine(shadow_dir=tmp_path)
        records = engine.run()
        assert len(records) == 0


class TestIntegration:
    def test_with_real_etl_output(self):
        if not (FIXTURE_ETL_DIR / "finviz_runs").exists():
            pytest.skip("No real ETL output found")
        engine = ShadowReplayEngine(shadow_dir=FIXTURE_ETL_DIR)
        records = engine.run()
        assert len(records) >= 2
        assert all(isinstance(r, ReplayRecord) for r in records)
        assert (engine.replay_dir / "report.csv").exists()

    def test_with_real_etl_no_xlv(self):
        if not (FIXTURE_ETL_DIR / "finviz_runs").exists():
            pytest.skip("No real ETL output found")
        engine = ShadowReplayEngine(shadow_dir=FIXTURE_ETL_DIR)
        records = engine.run()
        xlv_count = sum(1 for r in records if r.excluded_by_xlv)
        assert xlv_count == 0
