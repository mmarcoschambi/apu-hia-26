#!/usr/bin/env python3
"""
scripts/shadow_weekly_report.py

Generates weekly markdown reports from shadow replay and paper trading data.
Groups candidates by week ending on Friday, calculates exposure and performance,
and outputs a summary report YYYY-MM-DD_report.md for each week.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Project structure setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def to_friday_str(dt) -> str:
    """
    Map any date to its Friday week-ending date as a string (YYYY-MM-DD).
    If weekday is Saturday (5) or Sunday (6), it rolls forward to the next Friday.
    """
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    weekday = dt.weekday()  # Monday=0, Sunday=6
    if weekday <= 4:
        friday = dt + timedelta(days=(4 - weekday))
    else:
        # Saturday/Sunday map to next week's Friday
        friday = dt + timedelta(days=(4 - weekday + 7))
    return friday.strftime("%Y-%m-%d")


def load_report_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load and clean report.csv from shadow replay sandbox.
    """
    if not csv_path.exists():
        logger.warning(f"Replay report CSV not found at {csv_path}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        logger.error(f"Error reading replay report CSV {csv_path}: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    # Basic cleanup
    df["date"] = pd.to_datetime(df["date"])
    df["week_ending"] = df["date"].apply(to_friday_str)

    # Boolean mapping
    def to_bool(val):
        if pd.isna(val):
            return False
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ("true", "1", "yes", "t")

    for col in ["within_ticker_cap", "excluded_by_xlv", "allowed_shadow_candidate"]:
        if col in df.columns:
            df[col] = df[col].apply(to_bool)
        else:
            df[col] = False

    # Numeric mapping
    numeric_cols = [
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
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    return df


def load_journal_json(journal_path: Path) -> dict:
    """
    Load journal.json and count signals per week ending Friday.
    Returns a dict of {week_ending_str: signal_count}
    """
    counts = {}
    if not journal_path.exists():
        logger.warning(f"Paper journal not found at {journal_path}")
        return counts

    try:
        with open(journal_path, "r") as f:
            data = json.load(f)
        
        for entry in data:
            date_str = entry.get("date")
            if not date_str:
                continue
            
            # Use to_friday_str to map entry date to week ending Friday
            try:
                week_ending = to_friday_str(date_str)
            except Exception as e:
                logger.error(f"Error parsing date {date_str} in journal.json: {e}")
                continue
            
            signals = entry.get("signals", [])
            # Count the number of signals for this day
            sig_count = len(signals)
            counts[week_ending] = counts.get(week_ending, 0) + sig_count
            
    except Exception as e:
        logger.error(f"Error parsing paper journal JSON {journal_path}: {e}")

    return counts


def generate_weekly_report(
    week_ending: str,
    week_df: pd.DataFrame,
    live_count: int,
    output_dir: Path
) -> Path:
    """
    Generate the markdown report for a single week.
    """
    # 1. Weekly summary counts
    total_setups = len(week_df)
    xlv_filtered = int(week_df["excluded_by_xlv"].sum())
    ticker_cap_blocked = int((~week_df["within_ticker_cap"]).sum())
    allowed_shadow = int(week_df["allowed_shadow_candidate"].sum())

    # 2. Candidates List
    candidates_rows = []
    for _, row in week_df.iterrows():
        ticker = row["ticker"]
        sector = row["sector_etf"]
        rs = row["rs"]
        pos_val = row["position_value"]
        port_pct = row["portfolio_pct"]
        status = row["shadow_status"]

        # If portfolio_pct is like 0.1994, show it as 19.94%
        # If it is like 19.94, show it as 19.94%
        # Standard in report.csv: portfolio_pct is decimal (e.g. 0.1994)
        pct_display = f"{port_pct:.2%}" if port_pct < 1.0 and port_pct > 0 else f"{port_pct:.2f}%"
        
        candidates_rows.append(
            f"| {ticker} | {sector} | {rs:.1f} | ${pos_val:,.2f} | {pct_display} | {status} |"
        )
    candidates_list_str = "\n".join(candidates_rows) if candidates_rows else "| None | - | - | - | - | - |"

    # 3. Exposure Summary (for allowed shadow candidates only)
    allowed_df = week_df[week_df["allowed_shadow_candidate"]]
    
    # Sector exposure
    sector_rows = []
    if not allowed_df.empty:
        sector_grp = allowed_df.groupby("sector_etf").agg(
            count=("ticker", "count"),
            total_val=("position_value", "sum"),
            total_pct=("portfolio_pct", "sum")
        ).reset_index()
        for _, row in sector_grp.iterrows():
            sec = row["sector_etf"]
            cnt = int(row["count"])
            val = row["total_val"]
            pct = row["total_pct"]
            pct_disp = f"{pct:.2%}" if pct < 1.0 and pct > 0 else f"{pct:.2f}%"
            sector_rows.append(f"| {sec} | {cnt} | ${val:,.2f} | {pct_disp} |")
    sector_exposure_str = "\n".join(sector_rows) if sector_rows else "| None | 0 | $0.00 | 0.00% |"

    # Ticker exposure
    ticker_rows = []
    if not allowed_df.empty:
        for _, row in allowed_df.iterrows():
            tick = row["ticker"]
            sec = row["sector_etf"]
            val = row["position_value"]
            pct = row["portfolio_pct"]
            pct_disp = f"{pct:.2%}" if pct < 1.0 and pct > 0 else f"{pct:.2f}%"
            ticker_rows.append(f"| {tick} | {sec} | ${val:,.2f} | {pct_disp} |")
    ticker_exposure_str = "\n".join(ticker_rows) if ticker_rows else "| None | - | $0.00 | 0.00% |"

    # 4. Strategy Comparison
    # Shadow (Russell E25 + ex-XLV): allowed_shadow_candidate == True
    shadow_df = allowed_df
    shadow_count = len(shadow_df)
    shadow_pnl_tp1 = shadow_df["r_potential_tp1"].sum()
    shadow_pnl_tp2 = shadow_df["r_potential_tp2"].sum()

    # Russell E25 (without ex-XLV): allowed if within_ticker_cap == True (ignoring xlv exclusion)
    russell_df = week_df[week_df["within_ticker_cap"]]
    russell_count = len(russell_df)
    russell_pnl_tp1 = russell_df["r_potential_tp1"].sum()
    russell_pnl_tp2 = russell_df["r_potential_tp2"].sum()

    live_display_count = str(live_count) if live_count >= 0 else "N/A"

    report_content = f"""# Shadow Weekly Report - Week Ending {week_ending}

## Weekly Summary
| Metric | Count |
|---|---|
| New Signals (Total Setups) | {total_setups} |
| XLV Filtered | {xlv_filtered} |
| Ticker Cap Blocked | {ticker_cap_blocked} |
| Allowed Shadow Candidates | {allowed_shadow} |

## Candidates List
| Ticker | Sector | RS | Position Value ($) | Portfolio % | Status |
|---|---|---|---|---|---|
{candidates_list_str}

## Exposure Summary
### Sector Exposure
| Sector | Candidates Count | Total Position Value ($) | Total Portfolio % |
|---|---|---|---|
{sector_exposure_str}

### Ticker Exposure
| Ticker | Sector | Position Value ($) | Portfolio % |
|---|---|---|---|
{ticker_exposure_str}

## Strategy Comparison
| Strategy / System | Signals / Candidates Count | Sim PnL (TP1) | Sim PnL (TP2) |
|---|---|---|---|
| **Shadow (Russell E25 + ex-XLV)** | {shadow_count} | {shadow_pnl_tp1:+.2f} R | {shadow_pnl_tp2:+.2f} R |
| **Russell E25 (without ex-XLV)** | {russell_count} | {russell_pnl_tp1:+.2f} R | {russell_pnl_tp2:+.2f} R |
| **Live Paper (VPS)** | {live_display_count} | N/A | N/A |
"""

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{week_ending}_report.md"
    
    with open(report_path, "w") as f:
        f.write(report_content)
        
    logger.info(f"Generated weekly report: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Generate weekly reports for Shadow Mode.")
    parser.add_argument(
        "--csv",
        type=str,
        default=str(PROJECT_ROOT / "outputs" / "shadow_sandbox" / "replay" / "report.csv"),
        help="Path to the shadow replay report.csv"
    )
    parser.add_argument(
        "--journal",
        type=str,
        default=str(PROJECT_ROOT / "outputs" / "paper_finviz" / "journal.json"),
        help="Path to the VPS paper trading journal.json"
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=str(PROJECT_ROOT / "outputs" / "shadow_sandbox" / "weekly"),
        help="Directory where weekly reports will be written"
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    journal_path = Path(args.journal)
    outdir = Path(args.outdir)

    df = load_report_csv(csv_path)
    if df.empty:
        logger.error(f"No records found in {csv_path}. Cannot generate weekly reports.")
        sys.exit(1)

    journal_counts = load_journal_json(journal_path)

    # Group records by week ending Friday
    grouped = df.groupby("week_ending")
    
    for week_ending, group_df in grouped:
        live_count = journal_counts.get(week_ending, -1)
        generate_weekly_report(week_ending, group_df, live_count, outdir)

    logger.info("Weekly report generation finished successfully.")


if __name__ == "__main__":
    main()
