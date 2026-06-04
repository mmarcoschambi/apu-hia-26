"""Tests for the Shadow Sandbox ETL parser."""

import json
from pathlib import Path
from dataclasses import asdict

import pytest
import pandas as pd

from src.shadow.etl import (
    FinvizLogParser,
    FinvizShadowETL,
    RunContext,
    SectorRecord,
    SetupRecord,
    AlertRecord,
    ExitDistribution,
    SECTOR_MAP_FALLBACK,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_LOG = PROJECT_ROOT / "logs" / "vps" / "cron_finviz_monitor.log"

SAMPLE_LOG_LINES = [
    "2026-05-19 08:37:03,345 [INFO] ============================================================",
    "2026-05-19 08:37:03,345 [INFO] PAPER FINVIZ | Trade: 2026-05-19 | Data: 2026-05-18",
    "2026-05-19 08:37:03,345 [INFO] ============================================================",
    "2026-05-19 08:37:06,580 [INFO] 🚀 MODE: PRODUCTION (Fixed Dollar Risk)",
    "2026-05-19 08:37:06,580 [INFO]    • Risk: FIXED DOLLAR ($2878)",
    "2026-05-19 08:37:06,580 [INFO] 📅 Period: 2025-07-22 to 2026-05-18",
    "2026-05-19 08:37:06,580 [INFO] 🎯 Universe: 587 tickers",
    "2026-05-19 08:37:06,580 [INFO] 🎛️  Liquidity: vol≥100k, $vol≥$20M, ADR≥1.8714%, RVOL≥1.1048x",
    "2026-05-19 08:37:06,580 [INFO] 🎛️  Position Size: RVOL Danger≥3.0x→50%, Warning≥2.0x→75%",
    "",
    "🏛️ SECTOR MONEY FLOW (DINERO INSTITUCIONAL)",
    "  XLK       ➡️        1→1    -43.90%   ✅ Tradeable",
    "  XLE       ➡️        2→2    +40.40%   ✅ Tradeable",
    "  XLV      🔥 ⬆️      5→4    +33.52%   ⚠️ Blocked",
    "",
    "🏆 HIGH QUALITY SETUPS",
    "  NXPI     93.9      ✗          306.62        5.52%   0.80   Breakout > 306.62",
    "",
    "Exit distribution: STOP=7, TP1=30, TP2=0, RUNNER=0",
]

SAMPLE_LOG_WITH_HOT_SECTORS = [
    "2026-05-08 08:30:30,740 [INFO] ============================================================",
    "2026-05-08 08:30:30,740 [INFO] PAPER FINVIZ - PRE-MARKET",
    "2026-05-08 08:30:30,740 [INFO] ============================================================",
    "2026-05-08 08:30:44,580 [INFO] 🚀 MODE: PRODUCTION (Fixed Dollar Risk)",
    "2026-05-08 08:30:44,580 [INFO]    • Risk: FIXED DOLLAR ($2878)",
    "2026-05-08 08:30:44,581 [INFO] 📅 Period: 2025-07-11 to 2026-05-07",
    "2026-05-08 08:30:44,581 [INFO] 🎯 Universe: 590 tickers",
    "",
    "🔥 HOT SECTORS",
    "  XLK       1   155.82%   STRONG      ✓",
    "  XLY       2   -16.66%   VERY_WEAK   ✗",
    "  XLRE      3   -48.57%   VERY_WEAK   ✗",
    "",
    "Exit distribution: STOP=4, TP1=2, TP2=0, RUNNER=1",
]

SAMPLE_LOG_SKIP_WATCHLIST_DIAGNOSTIC = [
    "2026-05-08 08:30:30,740 [INFO] PAPER FINVIZ - PRE-MARKET",
    "🧪 WATCHLIST DIAGNOSTIC",
    "  MXL    100.0   ✗      85.50   ✗      SMA5…   0.68   78.75%   ✓      Breakout > 85.43   Failed breakout",
    "🏆 HIGH QUALITY SETUPS",
    "  NXPI     93.9      ✗          306.62        5.52%   0.80   Breakout > 306.62",
]

SAMPLE_LOG_EMPTY_DAY = [
    "2026-05-13 08:46:06,588 [INFO] PAPER FINVIZ | Trade: 2026-05-13 | Data: 2026-05-12",
    "2026-05-13 08:46:20,576 [INFO] 🚀 MODE: PRODUCTION (Fixed Dollar Risk)",
    "🔥 HOT SECTORS",
    "  XLK       1   192.69%   STRONG      ✓",
    "  XLP       2   -42.09%   VERY_WEAK   ✗",
    "Exit distribution: STOP=3, TP1=0, TP2=0, RUNNER=0",
]


class TestFinvizLogParser:
    def test_parse_single_run_money_flow(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_LINES)
        assert len(runs) == 1

        rc = runs[0]["run_context"]
        assert rc.run_date == "2026-05-19"
        assert rc.mode == "PRODUCTION"
        assert rc.universe_size == 587
        assert rc.period_start == "2025-07-22"
        assert rc.period_end == "2026-05-18"
        assert rc.risk_type == "FIXED DOLLAR"
        assert rc.risk_value == "$2878"
        assert rc.filters["min_vol_k"] == 100
        assert rc.filters["min_dollar_vol_M"] == 20
        assert rc.filters["min_rvol"] == 1.1048

    def test_parse_sectors_money_flow(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_LINES)
        sectors = runs[0]["sectors"]
        assert len(sectors) == 3

        xlk = sectors[0]
        assert xlk.sector_etf == "XLK"
        assert xlk.rank_prev == 1
        assert xlk.rank_curr == 1
        assert xlk.performance_pct == -43.90
        assert xlk.status == "tradeable"

        xlv = sectors[2]
        assert xlv.sector_etf == "XLV"
        assert xlv.performance_pct == 33.52
        assert xlv.status == "blocked"

    def test_parse_sectors_hot_sectors(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_WITH_HOT_SECTORS)
        sectors = runs[0]["sectors"]
        assert len(sectors) == 3

        xlk = sectors[0]
        assert xlk.sector_etf == "XLK"
        assert xlk.rank == 1
        assert xlk.rs_pct == 155.82
        assert xlk.strength == "STRONG"

    def test_parse_setups(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_LINES)
        setups = runs[0]["setups"]
        assert len(setups) == 1

        s = setups[0]
        assert s.ticker == "NXPI"
        assert s.rs == 93.9
        assert s.breakout_lvl == 306.62
        assert s.dist_sma20_pct == 5.52
        assert s.rvol == 0.80
        assert "Breakout > 306.62" in s.waiting_desc

    def test_parse_exit_distribution(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_LINES)
        ed = runs[0]["exit_dist"]
        assert ed is not None
        assert ed.stop == 7
        assert ed.tp1 == 30
        assert ed.tp2 == 0
        assert ed.runner == 0

    def test_skips_watchlist_diagnostic(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_SKIP_WATCHLIST_DIAGNOSTIC)
        setups = runs[0]["setups"]
        assert len(setups) == 1
        assert setups[0].ticker == "NXPI"

    def test_empty_day_no_setups(self):
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(SAMPLE_LOG_EMPTY_DAY)
        assert len(runs) == 1
        assert len(runs[0]["setups"]) == 0
        assert len(runs[0]["sectors"]) == 2

    def test_cache_warning_detected(self):
        lines = SAMPLE_LOG_WITH_HOT_SECTORS + [
            "no such column: sma20",
        ]
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(lines)
        assert runs[0]["quality"].sma20_cache_warning is True

    def test_multiple_runs(self):
        lines = SAMPLE_LOG_LINES + [
            "2026-05-20 08:30:00,000 [INFO] PAPER FINVIZ | Trade: 2026-05-20",
            "2026-05-20 08:30:00,001 [INFO] 🚀 MODE: PRODUCTION (Fixed Dollar Risk)",
            "🏆 HIGH QUALITY SETUPS",
            "  ADM      90.1      ✗           83.10        6.64%   1.12   Breakout > 83.10",
            "Exit distribution: STOP=1, TP1=0, TP2=0, RUNNER=0",
        ]
        parser = FinvizLogParser("dummy.log")
        runs = parser._parse_lines(lines)
        assert len(runs) == 2
        assert runs[0]["run_context"].run_date == "2026-05-19"
        assert runs[1]["run_context"].run_date == "2026-05-20"
        assert len(runs[1]["setups"]) == 1


class TestFinvizShadowETL:
    def test_enrichment_sector_mapping(self):
        parser = FinvizLogParser("dummy.log")
        etl = FinvizShadowETL(log_path="dummy.log", signals_path=None)
        etl.runs = parser._parse_lines(SAMPLE_LOG_LINES)
        etl._enrich_run(etl.runs[0])
        setup = etl.runs[0]["setups"][0]
        assert setup.sector_etf == "XLK"
        assert setup.excluded_by_xlv is False
        assert setup.allowed_shadow_candidate is True
        assert setup.shadow_status == "shadow_allowed"

    def test_enrichment_xlv_filtered(self):
        lines = [
            "2026-05-19 08:37:03,345 [INFO] PAPER FINVIZ | Trade: 2026-05-19",
            "🏆 HIGH QUALITY SETUPS",
            "  UNH      85.2      ✗          500.00        3.00%   1.20   Breakout > 500",
            "  AAPL     95.0      ✗          200.00        2.00%   1.50   Breakout > 200",
        ]
        parser = FinvizLogParser("dummy.log")
        etl = FinvizShadowETL(log_path="dummy.log", signals_path=None)
        etl.runs = parser._parse_lines(lines)
        etl._enrich_run(etl.runs[0])

        setups = etl.runs[0]["setups"]
        assert len(setups) == 2

        unh = setups[0]
        assert unh.ticker == "UNH"
        assert unh.sector_etf == "XLV"
        assert unh.excluded_by_xlv is True
        assert unh.allowed_shadow_candidate is False
        assert unh.shadow_status == "blocked_by_sector"

        aapl = setups[1]
        assert aapl.sector_etf == "XLK"
        assert aapl.allowed_shadow_candidate is True

        assert etl.runs[0]["quality"].xlv_filtered == 1

    def test_enrichment_fallback_sector_map(self):
        lines = [
            "2026-05-18 08:30:00,000 [INFO] PAPER FINVIZ | Trade: 2026-05-18",
            "🏆 HIGH QUALITY SETUPS",
            "  ADM      90.1      ✗           83.10        6.64%   1.12   Breakout > 83.10",
        ]
        parser = FinvizLogParser("dummy.log")
        etl = FinvizShadowETL(log_path="dummy.log", signals_path=None)
        etl.runs = parser._parse_lines(lines)
        etl._enrich_run(etl.runs[0])

        s = etl.runs[0]["setups"][0]
        assert s.sector_etf == "XLB"
        assert s.allowed_shadow_candidate is True
        assert SECTOR_MAP_FALLBACK.get("ADM") == "XLB"

    def test_enrichment_dedup_setups(self):
        lines = [
            "2026-05-19 08:37:03,345 [INFO] PAPER FINVIZ | Trade: 2026-05-19",
            "🏆 HIGH QUALITY SETUPS",
            "  NXPI     93.9      ✗          306.62        5.52%   0.80   Breakout > 306.62",
            "",
            "🏆 HIGH QUALITY SETUPS",
            "  NXPI     93.9      ✗          306.62        5.52%   0.80   Breakout > 306.62",
        ]
        parser = FinvizLogParser("dummy.log")
        etl = FinvizShadowETL(log_path="dummy.log", signals_path=None)
        etl.runs = parser._parse_lines(lines)
        assert len(etl.runs[0]["setups"]) == 2
        etl._enrich_run(etl.runs[0])
        assert len(etl.runs[0]["setups"]) == 1

    def test_output_structure(self, tmp_path):
        etl = FinvizShadowETL(
            log_path="dummy.log",
            signals_path=None,
            output_dir=tmp_path,
        )
        parser = FinvizLogParser("dummy.log")
        etl.runs = parser._parse_lines(SAMPLE_LOG_LINES)
        etl._enrich_run(etl.runs[0])
        etl._write_run_output(etl.runs[0])

        date_str = etl.runs[0]["run_context"].run_date
        out_dir = tmp_path / "finviz_runs" / date_str
        assert (out_dir / "setups.csv").exists()
        assert (out_dir / "sectors.csv").exists()
        assert (out_dir / "run_context.json").exists()

        df = pd.read_csv(out_dir / "setups.csv")
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "NXPI"
        assert df.iloc[0]["sector_etf"] == "XLK"

        ctx = json.loads((out_dir / "run_context.json").read_text())
        assert ctx["run_date"] == "2026-05-19"
        assert ctx["universe_size"] == 587
        assert ctx["exit_distribution"]["stop"] == 7

    def test_summary_generation(self, tmp_path):
        etl = FinvizShadowETL(
            log_path="dummy.log",
            signals_path=None,
            output_dir=tmp_path,
        )
        parser = FinvizLogParser("dummy.log")
        etl.runs = parser._parse_lines(SAMPLE_LOG_LINES)
        etl._enrich_run(etl.runs[0])
        etl._write_run_output(etl.runs[0])
        etl._write_summary()

        summary_path = tmp_path / "summary.md"
        assert summary_path.exists()
        text = summary_path.read_text()
        assert "Shadow candidates" in text
        assert "NXPI" not in text

    def test_data_quality_report(self, tmp_path):
        etl = FinvizShadowETL(
            log_path="dummy.log",
            signals_path=None,
            output_dir=tmp_path,
        )
        parser = FinvizLogParser("dummy.log")
        etl.runs = parser._parse_lines(SAMPLE_LOG_LINES)
        etl._enrich_run(etl.runs[0])
        etl._write_data_quality_report()

        quality_path = tmp_path / "data_quality.json"
        assert quality_path.exists()
        report = json.loads(quality_path.read_text())
        assert len(report) == 1
        assert report[0]["run_date"] == "2026-05-19"
        assert report[0]["total_parsed_setups"] == 1


class TestIntegrationWithRealLog:
    def test_parse_real_log(self):
        if not FIXTURE_LOG.exists():
            pytest.skip("Real log not available")
        parser = FinvizLogParser(str(FIXTURE_LOG))
        runs = parser.parse()
        assert len(runs) >= 8
        assert all(r["run_context"].run_date for r in runs)

    def test_run_etl_integration(self, tmp_path):
        if not FIXTURE_LOG.exists():
            pytest.skip("Real log not available")
        from src.shadow.etl import run_etl

        runs = run_etl(
            log_path=str(FIXTURE_LOG),
            signals_path=None,
            output_dir=tmp_path,
        )
        assert len(runs) >= 8
        assert (tmp_path / "summary.md").exists()
        assert (tmp_path / "data_quality.json").exists()

    def test_xlv_filter_count(self):
        if not FIXTURE_LOG.exists():
            pytest.skip("Real log not available")
        from src.shadow.etl import run_etl
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            runs = run_etl(
                log_path=str(FIXTURE_LOG),
                signals_path=None,
                output_dir=Path(tmp),
            )
            total_xlv = sum(r["quality"].xlv_filtered for r in runs)
            assert isinstance(total_xlv, int)
