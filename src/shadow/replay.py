"""
Shadow Replay v1 — Simula entrada/salida sobre shadow candidates.

Lee los outputs del ETL (setups.csv por dia), enriquece con precios
y aplica constraints (ex-XLV, ticker cap 20%).
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHADOW_DIR = PROJECT_ROOT / "outputs" / "shadow_sandbox"
REPLAY_DIR = SHADOW_DIR / "replay"

STOP_PCT = 0.07
TP1_R = 1.25
TP2_R = 3.0
TICKER_CAP_PCT = 0.20
PORTFOLIO_VALUE = 100_000.0


@dataclass
class ReplayRecord:
    date: str
    ticker: str
    sector_etf: str
    rs: float
    breakout_lvl: float
    entry_price: float
    stop_price: float
    tp1: float
    tp2: float
    r_potential_tp1: float
    r_potential_tp2: float
    position_value: float
    portfolio_pct: float
    within_ticker_cap: bool
    excluded_by_xlv: bool
    allowed_shadow_candidate: bool
    shadow_status: str
    price_source: str = "breakout_level"


class ShadowReplayEngine:
    """Simula entrada/salida sobre los shadow candidates del ETL."""

    def __init__(self, shadow_dir: Optional[Path] = None):
        self.shadow_dir = shadow_dir or SHADOW_DIR
        self.replay_dir = REPLAY_DIR
        self.replay_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[ReplayRecord] = []
        self.summary_lines: List[str] = []

    def run(self) -> List[ReplayRecord]:
        self.records = []
        runs_dir = self.shadow_dir / "finviz_runs"

        if not runs_dir.exists():
            logger.warning("No ETL output found at %s", runs_dir)
            return []

        date_dirs = sorted(runs_dir.iterdir())
        for date_dir in date_dirs:
            if not date_dir.is_dir():
                continue
            date = date_dir.name
            setups_path = date_dir / "setups.csv"
            if not setups_path.exists() or setups_path.stat().st_size == 0:
                continue

            try:
                df = pd.read_csv(setups_path)
            except pd.errors.EmptyDataError:
                continue

            if df.empty:
                continue

            for _, row in df.iterrows():
                rec = self._build_record(date, row)
                if rec:
                    self.records.append(rec)

        self._write_report()
        self._write_summary()
        logger.info("Replay complete: %d records", len(self.records))
        return self.records

    def _build_record(self, date: str, row: pd.Series) -> Optional[ReplayRecord]:
        ticker = str(row.get("ticker", "")).strip()
        if not ticker:
            return None

        breakout_lvl = float(row.get("breakout_lvl", 0) or 0)
        if breakout_lvl <= 0:
            return None

        rs = float(row.get("rs", 0) or 0)
        sector = str(row.get("sector_etf", "UNKNOWN"))
        excluded = bool(row.get("excluded_by_xlv", False))
        allowed = bool(row.get("allowed_shadow_candidate", False))
        status = str(row.get("shadow_status", "unknown"))

        entry_price = breakout_lvl
        stop_price = round(entry_price * (1 - STOP_PCT), 4)
        stop_distance = entry_price - stop_price

        tp1 = round(entry_price + stop_distance * TP1_R, 4)
        tp2 = round(entry_price + stop_distance * TP2_R, 4)

        risk_per_share = stop_distance
        if risk_per_share <= 0:
            return None

        shares = int((PORTFOLIO_VALUE * TICKER_CAP_PCT) / entry_price)
        if shares <= 0:
            shares = 1

        position_value = round(shares * entry_price, 2)
        portfolio_pct = round(position_value / PORTFOLIO_VALUE, 4)

        r_potential_tp1 = round((tp1 - entry_price) / risk_per_share, 2)
        r_potential_tp2 = round((tp2 - entry_price) / risk_per_share, 2)

        return ReplayRecord(
            date=date,
            ticker=ticker,
            sector_etf=sector,
            rs=rs,
            breakout_lvl=breakout_lvl,
            entry_price=entry_price,
            stop_price=stop_price,
            tp1=tp1,
            tp2=tp2,
            r_potential_tp1=r_potential_tp1,
            r_potential_tp2=r_potential_tp2,
            position_value=position_value,
            portfolio_pct=portfolio_pct,
            within_ticker_cap=portfolio_pct <= TICKER_CAP_PCT,
            excluded_by_xlv=excluded,
            allowed_shadow_candidate=allowed,
            shadow_status=status,
            price_source="breakout_level",
        )

    def _write_report(self) -> None:
        if not self.records:
            return
        df = pd.DataFrame([asdict(r) for r in self.records])
        df.to_csv(self.replay_dir / "report.csv", index=False)
        logger.info("Report written: %s", self.replay_dir / "report.csv")

    def _write_summary(self) -> None:
        lines = [
            "# Shadow Replay v1 Summary",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Source: ETL output en {self.shadow_dir}/finviz_runs/",
            "",
            "## Configuration",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Portfolio value | ${PORTFOLIO_VALUE:,.0f} |",
            f"| Stop loss | {STOP_PCT * 100:.0f}% below entry |",
            f"| TP1 | {TP1_R}R |",
            f"| TP2 | {TP2_R}R |",
            f"| Ticker cap | {TICKER_CAP_PCT * 100:.0f}% |",
            f"| Price source | breakout level from log |",
            "",
            "## Candidates",
            "",
        ]

        if not self.records:
            lines.append("No shadow candidates found.")
        else:
            lines.append(
                "| Date | Ticker | Sector | RS | Entry | Stop | TP1 | TP2 "
                "| R(TP1) | R(TP2) | Position $ | Port % | Cap OK | Status |"
            )
            lines.append(
                "|------|--------|--------|----|-------|------|-----|-----"
                "|--------|--------|------------|--------|--------|--------|"
            )
            for r in self.records:
                cap_ok = "✅" if r.within_ticker_cap else "⚠️ Exceeds"
                lines.append(
                    f"| {r.date} | {r.ticker} | {r.sector_etf} | {r.rs} "
                    f"| {r.entry_price:.2f} | {r.stop_price:.4f} | {r.tp1:.2f} | {r.tp2:.2f} "
                    f"| {r.r_potential_tp1:.2f} | {r.r_potential_tp2:.2f} "
                    f"| ${r.position_value:,.0f} | {r.portfolio_pct:.1%} "
                    f"| {cap_ok} | {r.shadow_status} |"
                )

            total_potential = sum(r.r_potential_tp2 for r in self.records)

            lines.extend(
                [
                    "",
                    "## Aggregate",
                    "",
                    f"Total candidates: {len(self.records)}",
                    f"Candidates within ticker cap: {sum(1 for r in self.records if r.within_ticker_cap)}",
                    f"Candidates excluded by XLV: {sum(1 for r in self.records if r.excluded_by_xlv)}",
                    f"Sum R potential (TP2): {total_potential:.2f}R",
                    "",
                    "## Notes",
                    "- Entry price = breakout level from the log (trigger price)",
                    "- Stop = 7% below entry (standard fixed stop)",
                    "- TP1 = 1.25R, TP2 = 3.0R (from combo_pure_momentum tier1 config)",
                    "- Position size = 20% of $100k portfolio per candidate (max)",
                    "- No price history fetched yet; this is a static parameter simulation",
                    "- Next step: fetch post-signal price data from yfinance for actual PnL",
                ]
            )

        summary_path = self.replay_dir / "summary.md"
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Summary written: %s", summary_path)


def run_replay(
    shadow_dir: Optional[Path] = None,
) -> List[ReplayRecord]:
    engine = ShadowReplayEngine(shadow_dir=shadow_dir)
    return engine.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    records = run_replay()
    print(f"Replay complete: {len(records)} records.")
