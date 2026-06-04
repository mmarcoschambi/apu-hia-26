"""
Shadow Sandbox ETL — Parsea logs Finviz/VPS y genera dataset shadow.

Fuente primaria: logs/vps/cron_finviz_monitor.log
Output: outputs/shadow_sandbox/finviz_runs/<date>/
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from src.utils.sector_rotation import SECTOR_MAP

SECTOR_MAP_FALLBACK = {
    "ADM": "XLB",
}

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "shadow_sandbox"

XLV_SECTOR = "XLV"
SECTOR_ETFS = {"XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC"}

RE_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)")
RE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

RE_RUN_START = re.compile(r"PAPER FINVIZ")
RE_MODE = re.compile(r"MODE:\s*(\w+(?:\s*\w+)*)")
RE_UNIVERSE = re.compile(r"Universe:\s*(\d+)\s*tickers")
RE_PERIOD = re.compile(r"Period:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})")
RE_RISK = re.compile(r"Risk:\s*(\w+(?:\s*\w+)*)\s*\(?(\$?\d+(?:\.\d+)?)\)?")
RE_LIQUIDITY = re.compile(
    r"Liquidity:\s*vol\u2265(\d+)k,\s*\$vol\u2265\$(\d+)M,"
    r"\s*ADR\u2265([\d.]+)%,\s*RVOL\u2265([\d.]+)x"
)
RE_POS_SIZE = re.compile(
    r"Position Size:\s*RVOL Danger\u2265([\d.]+)x\u2192(\d+)%,"
    r"\s*Warning\u2265([\d.]+)x\u2192(\d+)%"
)
RE_SECTOR_MONEY_FLOW = re.compile(
    r"(XLK|XLF|XLV|XLE|XLY|XLP|XLI|XLB|XLRE|XLU|XLC)\s+"
    r".*?"
    r"(\d+)\u2192(\d+)\s+"
    r"([+-]?\d+\.\d+)%\s+"
    r"(\u2705|Tradeable|\u26A0\uFE0F|Blocked)"
)
RE_HOT_SECTORS_SIMPLE = re.compile(
    r"(XLK|XLF|XLV|XLE|XLY|XLP|XLI|XLB|XLRE|XLU|XLC)\s+"
    r"(\d+)\s+"
    r"([+-]?\d+\.\d+)%\s+"
    r"(STRONG|WEAK|NEUTRAL|VERY_WEAK|VERY_STRONG)\s+"
)
RE_SETUP_LINE = re.compile(
    r"(\w+)\s+(\d+\.\d)\s+([\u2713\u2717\u2718\u2714\u2716\xD7xX])\s+"
    r"(\d+\.\d{2})\s+(\d+\.\d{2})%\s+(\d+\.\d{2})\s+(.+)"
)
RE_EXIT_DIST = re.compile(
    r"Exit distribution:\s*STOP=(\d+),\s*TP1=(\d+),\s*TP2=(\d+),\s*RUNNER=(\d+)"
)
RE_ALERT_LINE = re.compile(r"(\w+)\s+n_block=(\d+)\s+prox=([\d.]+)\s*\|\s*(.+)")
RE_EXIT_DIST = re.compile(
    r"Exit distribution:\s*STOP=(\d+),\s*TP1=(\d+),\s*TP2=(\d+),\s*RUNNER=(\d+)"
)
RE_ALERT_LINE = re.compile(r"\s{2,}(\w+)\s+n_block=(\d+)\s+prox=([\d.]+)\s*\|\s*(.+)")
RE_NO_AUTO_ENTRY = re.compile(r"MANUAL REVIEW - NO AUTO ENTRY")
RE_CACHE_WARN = re.compile(r"no such column: sma20")
RE_SECTOR_FLOW_HEADER = re.compile(r"SECTOR MONEY FLOW")
RE_HOT_SECTORS_HEADER = re.compile(r"HOT SECTORS")
RE_HIGH_QUALITY_HEADER = re.compile(r"HIGH QUALITY SETUPS")


@dataclass
class RunContext:
    run_date: str = ""
    timestamp: str = ""
    mode: str = ""
    universe_size: int = 0
    period_start: str = ""
    period_end: str = ""
    risk_type: str = ""
    risk_value: str = ""
    filters: dict = field(default_factory=dict)
    position_size: dict = field(default_factory=dict)


@dataclass
class SectorRecord:
    run_date: str
    sector_etf: str
    rank: int = 0
    rank_prev: Optional[int] = None
    rank_curr: Optional[int] = None
    performance_pct: Optional[float] = None
    rs_pct: Optional[float] = None
    strength: str = ""
    status: str = ""


@dataclass
class SetupRecord:
    run_date: str
    ticker: str
    rs: float
    breakout_lvl: Optional[float]
    dist_sma20_pct: float
    rvol: float
    waiting_desc: str
    sector_etf: str = ""
    excluded_by_xlv: bool = False
    allowed_shadow_candidate: bool = False
    shadow_status: str = "unknown"


@dataclass
class AlertRecord:
    run_date: str
    ticker: str
    n_block: int
    proximity_score: float
    reason: str


@dataclass
class ExitDistribution:
    run_date: str
    stop: int = 0
    tp1: int = 0
    tp2: int = 0
    runner: int = 0


@dataclass
class DataQuality:
    run_date: str
    total_parsed_setups: int = 0
    total_sectors: int = 0
    total_alerts: int = 0
    tickers_not_in_sector_map: list = field(default_factory=list)
    xlv_filtered: int = 0
    ticker_duplicates: list = field(default_factory=list)
    missing_critical_fields: list = field(default_factory=list)
    sma20_cache_warning: bool = False
    incomplete_blocks: bool = False
    multiple_runs_today: int = 0


class FinvizLogParser:
    """Parses cron_finviz_monitor.log into structured records per run."""

    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.runs: List[dict] = []

    def parse(self) -> List[dict]:
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return self._parse_lines(lines)

    def _parse_lines(self, lines: List[str]) -> List[dict]:
        runs = []
        current_run = None
        in_sector_block = False
        in_setup_block = False
        in_alert_block = False
        block_type = None

        for line in lines:
            stripped = line.strip()

            if RE_RUN_START.search(line) and "PAPER FINVIZ" in line:
                if current_run:
                    runs.append(self._finalize_run(current_run))
                current_run = self._init_run()
                ts_match = RE_TIMESTAMP.search(line)
                if ts_match:
                    current_run["run_context"].timestamp = ts_match.group(1)
                    current_run["run_context"].run_date = ts_match.group(1).split(" ")[0]
                in_sector_block = False
                in_setup_block = False
                in_alert_block = False
                block_type = None
                continue

            if current_run is None:
                continue

            rc = current_run["run_context"]

            if "MODE:" in line:
                m = RE_MODE.search(line)
                if m:
                    rc.mode = m.group(1).strip()
                continue

            if "Universe:" in line and "tickers" in line:
                m = RE_UNIVERSE.search(line)
                if m:
                    rc.universe_size = int(m.group(1))
                continue

            if "Period:" in line:
                m = RE_PERIOD.search(line)
                if m:
                    rc.period_start = m.group(1)
                    rc.period_end = m.group(2)
                continue

            if "Risk:" in line and ("FIXED" in line or "DOLLAR" in line):
                m = RE_RISK.search(line)
                if m:
                    rc.risk_type = m.group(1).strip()
                    rc.risk_value = m.group(2).strip()
                continue

            if "Liquidity:" in line:
                m = RE_LIQUIDITY.search(line)
                if m:
                    rc.filters = {
                        "min_vol_k": int(m.group(1)),
                        "min_dollar_vol_M": int(m.group(2)),
                        "min_adr_pct": float(m.group(3)),
                        "min_rvol": float(m.group(4)),
                    }
                continue

            if "Position Size:" in line:
                m = RE_POS_SIZE.search(line)
                if m:
                    rc.position_size = {
                        "rvol_danger": float(m.group(1)),
                        "rvol_danger_size_pct": int(m.group(2)),
                        "rvol_warning": float(m.group(3)),
                        "rvol_warning_size_pct": int(m.group(4)),
                    }
                continue

            if RE_CACHE_WARN.search(line):
                current_run["quality"].sma20_cache_warning = True
                continue

            if RE_SECTOR_FLOW_HEADER.search(line):
                in_sector_block = True
                block_type = "money_flow"
                in_setup_block = False
                in_alert_block = False
                continue

            if RE_HOT_SECTORS_HEADER.search(line):
                in_sector_block = True
                block_type = "hot_sectors"
                in_setup_block = False
                in_alert_block = False
                continue

            if RE_HIGH_QUALITY_HEADER.search(line):
                in_sector_block = False
                in_setup_block = True
                in_alert_block = False
                block_type = None
                continue

            if "proximity_score" in line.lower() or "prox=" in line:
                in_alert_block = True
                in_sector_block = False
                in_setup_block = False
                block_type = None
                continue

            if "near-threshold" in line.lower() or "Top candidatos" in line:
                in_alert_block = True
                in_sector_block = False
                in_setup_block = False
                block_type = None
                continue

            if "Exit distribution:" in line or ("STOP=" in line and "TP1=" in line):
                m = RE_EXIT_DIST.search(line)
                if m:
                    current_run["exit_dist"] = ExitDistribution(
                        run_date=rc.run_date,
                        stop=int(m.group(1)),
                        tp1=int(m.group(2)),
                        tp2=int(m.group(3)),
                        runner=int(m.group(4)),
                    )
                in_setup_block = False
                in_sector_block = False
                in_alert_block = False
                block_type = None
                continue

            if RE_NO_AUTO_ENTRY.search(line):
                current_run["no_auto_entry"] = True
                continue

            if in_sector_block and block_type == "money_flow":
                m = RE_SECTOR_MONEY_FLOW.search(line)
                if m:
                    status = (
                        "tradeable"
                        if (m.group(5) == "Tradeable" or m.group(5) == "\u2705")
                        else "blocked"
                    )
                    sector = SectorRecord(
                        run_date=rc.run_date,
                        sector_etf=m.group(1),
                        rank_prev=int(m.group(2)),
                        rank_curr=int(m.group(3)),
                        performance_pct=float(m.group(4)),
                        status=status,
                    )
                    current_run["sectors"].append(sector)
                continue

            if in_sector_block and block_type == "hot_sectors":
                m = RE_HOT_SECTORS_SIMPLE.search(line)
                if m:
                    sector = SectorRecord(
                        run_date=rc.run_date,
                        sector_etf=m.group(1),
                        rank=int(m.group(2)),
                        rs_pct=float(m.group(3)),
                        strength=m.group(4).strip(),
                    )
                    current_run["sectors"].append(sector)
                continue

            if in_setup_block:
                m = RE_SETUP_LINE.search(line)
                if m:
                    ticker = m.group(1)
                    breakout_raw = m.group(3)
                    breakout_lvl_str = m.group(4)
                    try:
                        breakout_lvl = float(breakout_lvl_str)
                    except ValueError:
                        breakout_lvl = None
                    setup = SetupRecord(
                        run_date=rc.run_date,
                        ticker=ticker,
                        rs=float(m.group(2)),
                        breakout_lvl=breakout_lvl,
                        dist_sma20_pct=float(m.group(5).replace("%", "")),
                        rvol=float(m.group(6)),
                        waiting_desc=m.group(7).strip(),
                    )
                    current_run["setups"].append(setup)
                continue

            if in_alert_block:
                m = RE_ALERT_LINE.search(line)
                if m:
                    alert = AlertRecord(
                        run_date=rc.run_date,
                        ticker=m.group(1),
                        n_block=int(m.group(2)),
                        proximity_score=float(m.group(3)),
                        reason=m.group(4).strip(),
                    )
                    current_run["alerts"].append(alert)
                continue

        if current_run:
            runs.append(self._finalize_run(current_run))

        self.runs = runs
        return runs

    def _init_run(self) -> dict:
        return {
            "run_context": RunContext(),
            "sectors": [],
            "setups": [],
            "alerts": [],
            "exit_dist": None,
            "quality": DataQuality(run_date=""),
            "no_auto_entry": False,
        }

    def _finalize_run(self, run: dict) -> dict:
        rc = run["run_context"]
        run["quality"].run_date = rc.run_date
        run["quality"].total_sectors = len(run["sectors"])
        run["quality"].total_parsed_setups = len(run["setups"])
        run["quality"].total_alerts = len(run["alerts"])
        return run


class FinvizShadowETL:
    """Orchestrates parsing + enrichment + output for the shadow sandbox."""

    def __init__(
        self,
        log_path: str = "logs/vps/cron_finviz_monitor.log",
        signals_path: Optional[str] = "data/signals_a_today.csv",
        output_dir: Optional[Path] = None,
    ):
        self.log_path = Path(log_path)
        self.signals_path = Path(signals_path) if signals_path else None
        self.output_dir = output_dir or OUTPUT_DIR
        self.signals_df: Optional[pd.DataFrame] = None
        self.parser = FinvizLogParser(str(self.log_path))
        self.runs: List[dict] = []
        self.summary_rows: List[dict] = []

    def load_signals(self) -> None:
        if self.signals_path and self.signals_path.exists():
            self.signals_df = pd.read_csv(self.signals_path)
            self.signals_df["signal_date"] = pd.to_datetime(self.signals_df["signal_date"]).dt.date
            logger.info(
                "Loaded %d signals from %s",
                len(self.signals_df),
                self.signals_path,
            )
        else:
            logger.info("No signals file at %s; skipping join", self.signals_path)

    def run(self) -> List[dict]:
        self.load_signals()
        self.runs = self.parser.parse()
        logger.info("Parsed %d runs from %s", len(self.runs), self.log_path)

        for run in self.runs:
            self._enrich_run(run)
            self._write_run_output(run)

        self._write_summary()
        self._write_data_quality_report()
        return self.runs

    def _enrich_run(self, run: dict) -> None:
        rc = run["run_context"]

        seen_setups = set()
        deduped = []
        for s in run["setups"]:
            key = (s.ticker, s.rs, s.dist_sma20_pct)
            if key not in seen_setups:
                seen_setups.add(key)
                deduped.append(s)
        run["setups"] = deduped
        run["quality"].total_parsed_setups = len(deduped)

        for setup in run["setups"]:
            ticker = setup.ticker.upper()
            sector_map = {**SECTOR_MAP, **SECTOR_MAP_FALLBACK}
            setup.sector_etf = sector_map.get(ticker, "UNKNOWN")
            setup.excluded_by_xlv = setup.sector_etf == XLV_SECTOR
            if setup.sector_etf == "UNKNOWN":
                run["quality"].tickers_not_in_sector_map.append(ticker)
            if setup.excluded_by_xlv:
                run["quality"].xlv_filtered += 1
                setup.allowed_shadow_candidate = False
                setup.shadow_status = "blocked_by_sector"
            else:
                setup.allowed_shadow_candidate = True
                setup.shadow_status = "shadow_allowed"

        if self.signals_df is not None:
            run_date = rc.run_date
            for setup in run["setups"]:
                match = self.signals_df[
                    (self.signals_df["signal_date"] == pd.to_datetime(run_date).date())
                    & (self.signals_df["ticker"] == setup.ticker)
                ]
                if not match.empty:
                    setup.waiting_desc += (
                        f" | signal_price={match.iloc[0]['signal_price']}"
                        f" entry_price={match.iloc[0]['entry_price_actual']}"
                        f" stop={match.iloc[0]['stop_price']}"
                        f" tp1={match.iloc[0]['tp1']}"
                        f" tp2={match.iloc[0]['tp2']}"
                    )

        tickers = [s.ticker for s in run["setups"]]
        seen = set()
        dupes = []
        for t in tickers:
            if t in seen:
                dupes.append(t)
            seen.add(t)
        run["quality"].ticker_duplicates = list(set(dupes))

    def _write_run_output(self, run: dict) -> None:
        rc = run["run_context"]
        run_date = rc.run_date
        out_dir = self.output_dir / "finviz_runs" / run_date
        out_dir.mkdir(parents=True, exist_ok=True)

        setups_df = pd.DataFrame([asdict(s) for s in run["setups"]])
        if not setups_df.empty:
            setups_df.to_csv(out_dir / "setups.csv", index=False)

        sectors_df = pd.DataFrame([asdict(s) for s in run["sectors"]])
        if not sectors_df.empty:
            sectors_df.to_csv(out_dir / "sectors.csv", index=False)

        alerts_df = pd.DataFrame([asdict(a) for a in run["alerts"]])
        if not alerts_df.empty:
            alerts_df.to_csv(out_dir / "alerts.csv", index=False)

        exit_dist = run.get("exit_dist")
        run_ctx = {
            "run_date": rc.run_date,
            "timestamp": rc.timestamp,
            "mode": rc.mode,
            "universe_size": rc.universe_size,
            "period_start": rc.period_start,
            "period_end": rc.period_end,
            "risk_type": rc.risk_type,
            "risk_value": rc.risk_value,
            "filters": rc.filters,
            "position_size": rc.position_size,
            "no_auto_entry": run.get("no_auto_entry", False),
            "exit_distribution": asdict(exit_dist) if exit_dist else None,
        }
        (out_dir / "run_context.json").write_text(
            json.dumps(run_ctx, indent=2, default=str), encoding="utf-8"
        )

        self.summary_rows.append(
            {
                "date": rc.run_date,
                "mode": rc.mode,
                "universe_size": rc.universe_size,
                "setups": len(run["setups"]),
                "sectors": len(run["sectors"]),
                "alerts": len(run["alerts"]),
                "xlv_filtered": run["quality"].xlv_filtered,
                "shadow_candidates": sum(1 for s in run["setups"] if s.allowed_shadow_candidate),
                "no_auto_entry": run.get("no_auto_entry", False),
                "cache_warning": run["quality"].sma20_cache_warning,
                "exit_stop": exit_dist.stop if exit_dist else 0,
                "exit_tp1": exit_dist.tp1 if exit_dist else 0,
                "exit_tp2": exit_dist.tp2 if exit_dist else 0,
                "exit_runner": exit_dist.runner if exit_dist else 0,
            }
        )

    def _write_summary(self) -> None:
        summary_path = self.output_dir / "summary.md"
        if not self.summary_rows:
            summary_path.write_text("# Shadow Sandbox Summary\n\nNo runs parsed.\n")
            return

        df = pd.DataFrame(self.summary_rows)
        df.to_csv(self.output_dir / "summary.csv", index=False)

        total_setups = int(df["setups"].sum())
        total_shadow = int(df["shadow_candidates"].sum())
        total_xlv = int(df["xlv_filtered"].sum())
        days_with_data = int((df["setups"] > 0).sum())
        days_total = len(df)

        lines = [
            "# Shadow Sandbox Summary",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Source: {self.log_path}",
            "",
            "## Global Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Days with runs | {days_total} |",
            f"| Days with setups | {days_with_data} |",
            f"| Total raw setups | {total_setups} |",
            f"| XLV filtered | {total_xlv} |",
            f"| Shadow candidates | {total_shadow} |",
            f"| Cache warnings (sma20) | {int(df['cache_warning'].sum())} |",
            "",
            "## Per-Day Breakdown",
            "",
            "| Date | Setups | XLV Filtered | Shadow Candidates | Mode | No Auto Entry |",
            "|------|--------|--------------|-------------------|------|---------------|",
        ]
        for _, row in df.iterrows():
            lines.append(
                f"| {row['date']} | {row['setups']} | {row['xlv_filtered']} "
                f"| {row['shadow_candidates']} | {row['mode']} "
                f"| {row['no_auto_entry']} |"
            )

        lines.extend(
            [
                "",
                "## Legend",
                "- **raw_setup**: senal detectada en el log, sin filtrar",
                "- **shadow_allowed**: pasa el filtro ex-XLV, candidato valido",
                "- **blocked_by_sector**: ticker en sector XLV (healthcare), excluido",
                "- **missing_data**: ticker no encontrado en SECTOR_MAP",
            ]
        )

        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Summary written to %s", summary_path)

    def _write_data_quality_report(self) -> None:
        quality_path = self.output_dir / "data_quality.json"
        reports = []
        for run in self.runs:
            q = run["quality"]
            reports.append(
                {
                    "run_date": q.run_date,
                    "total_parsed_setups": q.total_parsed_setups,
                    "total_sectors": q.total_sectors,
                    "total_alerts": q.total_alerts,
                    "tickers_not_in_sector_map": q.tickers_not_in_sector_map,
                    "xlv_filtered": q.xlv_filtered,
                    "ticker_duplicates": q.ticker_duplicates,
                    "missing_critical_fields": q.missing_critical_fields,
                    "sma20_cache_warning": q.sma20_cache_warning,
                    "incomplete_blocks": q.incomplete_blocks,
                    "multiple_runs_today": q.multiple_runs_today,
                }
            )
        quality_path.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
        logger.info("Data quality report written to %s", quality_path)


def run_etl(
    log_path: str = "logs/vps/cron_finviz_monitor.log",
    signals_path: Optional[str] = "data/signals_a_today.csv",
    output_dir: Optional[Path] = None,
) -> List[dict]:
    etl = FinvizShadowETL(
        log_path=log_path,
        signals_path=signals_path,
        output_dir=output_dir,
    )
    return etl.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    runs = run_etl()
    print(f"ETL complete: {len(runs)} runs processed.")
