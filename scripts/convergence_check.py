#!/usr/bin/env python3
"""
scripts/convergence_check.py
Shadow Convergence Audit — Track B, Phase 5.

Compares backtest signal outputs vs live/shadow signal outputs to quantify
convergence (Jaccard overlap), detect timing/price discrepancies (>2%), and
generate root-cause reports with degraded-mode fallback.

Usage:
    python3 scripts/convergence_check.py --start 2026-05 --end 2026-06
    python3 scripts/convergence_check.py --start 2026-05 --end 2026-06 --backtest-tag shadow_may_2026
"""

import argparse
import json
import logging
import sys
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# --- Constants ---
CONVERGENCE_THRESHOLD = 0.80  # 80% minimum convergence
CONVERGENCE_THRESHOLD_PCT = "80%"  # Display string for reports (ASCII-safe)
PRICE_DISCREPANCY_THRESHOLD = 0.02  # 2% max price difference

# --- Paths ---
BACKTEST_DIR = PROJECT_ROOT / "outputs" / "backtests"
LIVE_SIGNALS_DIR = PROJECT_ROOT / "outputs" / "live_signals"
PAPER_FINVIZ_DIR = PROJECT_ROOT / "outputs" / "paper_finviz"
SHADOW_SANDBOX_DIR = PROJECT_ROOT / "outputs" / "shadow_sandbox"
CONVERGENCE_REPORT_PATH = SHADOW_SANDBOX_DIR / "convergence_report.md"


# --- Dataclasses ---

@dataclass
class PriceAnomaly:
    """A single price/timing discrepancy between backtest and shadow signals."""
    ticker: str
    backtest_price: float
    shadow_price: float
    discrepancy_pct: float
    category: str = "unexplained"


@dataclass
class ConvergenceResult:
    """Convergence result for a single trading session."""
    date: str
    overlap: int
    union: int
    convergence_score: float
    threshold_passed: bool
    price_anomalies: list[PriceAnomaly] = field(default_factory=list)
    degradation_mode: str = "NORMAL"
    backtest_signal_count: int = 0
    shadow_signal_count: int = 0
    missing_from_backtest: list[str] = field(default_factory=list)
    missing_from_shadow: list[str] = field(default_factory=list)
    vps_available: bool = True


# ============================================================
# Core computation functions (pure, testable)
# ============================================================

def compute_convergence_score(
    backtest_signals: set[str],
    shadow_signals: set[str],
) -> tuple[int, int, float]:
    """
    Compute Jaccard convergence score.

    Args:
        backtest_signals: Set of ticker symbols from backtest.
        shadow_signals: Set of ticker symbols from shadow (daily_scan).

    Returns:
        (overlap, union, score) where score = overlap / union.
        Returns (0, 0, 1.0) for empty union (perfect agreement, no action needed).
    """
    union = backtest_signals | shadow_signals
    if not union:
        return 0, 0, 1.0

    overlap = backtest_signals & shadow_signals
    score = len(overlap) / len(union)
    return len(overlap), len(union), score


def compute_price_discrepancies(
    backtest_prices: dict[str, float],
    shadow_prices: dict[str, float],
    threshold: float = PRICE_DISCREPANCY_THRESHOLD,
) -> list[PriceAnomaly]:
    """
    For matching signals, compare entry prices and flag > threshold.

    Args:
        backtest_prices: {ticker: entry_price} from backtest.
        shadow_prices: {ticker: entry_price} from daily_scan.
        threshold: Max allowed price discrepancy fraction (default 2%).

    Returns:
        List of PriceAnomaly for flagged discrepancies.
    """
    anomalies: list[PriceAnomaly] = []
    common = set(backtest_prices.keys()) & set(shadow_prices.keys())

    for ticker in sorted(common):
        bt_price = backtest_prices[ticker]
        sh_price = shadow_prices[ticker]
        if bt_price == 0:
            continue

        discrepancy = abs(bt_price - sh_price) / bt_price
        if discrepancy > threshold:
            anomalies.append(PriceAnomaly(
                ticker=ticker,
                backtest_price=bt_price,
                shadow_price=sh_price,
                discrepancy_pct=discrepancy,
            ))

    return anomalies


def categorize_anomaly(
    anomaly: PriceAnomaly,
    backtest_signals: set[str],
    shadow_signals: set[str],
    vps_snapshot_available: bool,
) -> str:
    """
    Assign a root-cause category to a price anomaly.

    Categories: data_freshness, universe_mismatch, config_drift, unexplained.
    """
    if not vps_snapshot_available:
        return "data_freshness"
    if anomaly.ticker in shadow_signals and anomaly.ticker not in backtest_signals:
        return "universe_mismatch"
    if anomaly.discrepancy_pct > 0.05:
        return "config_drift"
    return "unexplained"


# ============================================================
# Data loading
# ============================================================

def load_backtest_signals(
    start_date: str,
    end_date: str,
    backtest_tag: str = "gold_standard_variant_e",
) -> dict[str, set[str]]:
    """
    Load backtest trade signals grouped by date.

    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        backtest_tag: Tag used for backtest output files.

    Returns:
        dict[date_str, set[ticker_symbols]]
    """
    trades_path = BACKTEST_DIR / f"{backtest_tag}_trades.csv"
    if not trades_path.exists():
        logger.warning(f"Backtest trades file not found: {trades_path}")
        return {}

    try:
        df = pd.read_csv(trades_path)
    except pd.errors.EmptyDataError:
        logger.warning(f"Backtest trades file is empty (0 trades): {trades_path}")
        return {}
    if "entry_date" in df.columns:
        date_col = "entry_date"
    elif "date" in df.columns:
        date_col = "date"
    else:
        logger.warning(f"No expected date column in {trades_path}")
        return {}

    df[date_col] = pd.to_datetime(df[date_col], format="mixed")
    mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
    df = df[mask]

    signals_by_date: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        d = row[date_col].strftime("%Y-%m-%d")
        ticker = row.get("symbol", row.get("ticker", ""))
        if ticker:
            signals_by_date.setdefault(d, set()).add(ticker)

    return signals_by_date


def load_shadow_signals(
    start_date: str,
    end_date: str,
) -> dict[str, set[str]]:
    """
    Load shadow (daily_scan) signals grouped by date.

    Reads from outputs/live_signals/<date>/combined.csv.

    Returns:
        dict[date_str, set[ticker_symbols]]
    """
    signals_by_date: dict[str, set[str]] = {}
    dates_in_range = pd.date_range(start=start_date, end=end_date, freq="D")

    for d in dates_in_range:
        d_str = d.strftime("%Y-%m-%d")
        combined_path = LIVE_SIGNALS_DIR / d_str / "combined.csv"
        if not combined_path.exists():
            continue

        df = pd.read_csv(combined_path)
        if "ticker" not in df.columns:
            continue

        tickers = set(df["ticker"].dropna().unique())
        if tickers:
            signals_by_date[d_str] = tickers

    return signals_by_date


def load_shadow_prices(
    start_date: str,
    end_date: str,
) -> dict[str, dict[str, float]]:
    """
    Load shadow signal entry prices grouped by date.

    Returns:
        dict[date_str, dict[ticker, entry_price]]
    """
    prices_by_date: dict[str, dict[str, float]] = {}
    dates_in_range = pd.date_range(start=start_date, end=end_date, freq="D")

    for d in dates_in_range:
        d_str = d.strftime("%Y-%m-%d")
        combined_path = LIVE_SIGNALS_DIR / d_str / "combined.csv"
        if not combined_path.exists():
            continue

        df = pd.read_csv(combined_path)
        if "ticker" not in df.columns:
            continue

        price_col = None
        for col in ["entry_price", "close"]:
            if col in df.columns:
                price_col = col
                break
        if price_col is None:
            continue

        prices: dict[str, float] = {}
        for _, row in df.iterrows():
            ticker = row.get("ticker", "")
            price = row.get(price_col)
            if ticker and pd.notna(price):
                prices[ticker] = float(price)

        if prices:
            prices_by_date[d_str] = prices

    return prices_by_date


def load_backtest_prices(
    start_date: str,
    end_date: str,
    backtest_tag: str = "gold_standard_variant_e",
) -> dict[str, dict[str, float]]:
    """
    Load backtest entry prices grouped by date.
    """
    trades_path = BACKTEST_DIR / f"{backtest_tag}_trades.csv"
    if not trades_path.exists():
        return {}

    try:
        df = pd.read_csv(trades_path)
    except pd.errors.EmptyDataError:
        return {}
    if "entry_date" in df.columns:
        date_col = "entry_date"
    elif "date" in df.columns:
        date_col = "date"
    else:
        return {}

    df[date_col] = pd.to_datetime(df[date_col], format="mixed")
    mask = (df[date_col] >= start_date) & (df[date_col] <= end_date)
    df = df[mask]

    prices_by_date: dict[str, dict[str, float]] = {}
    for _, row in df.iterrows():
        d = row[date_col].strftime("%Y-%m-%d")
        ticker = row.get("symbol", row.get("ticker", ""))
        entry_price = row.get("entry_price")
        if ticker and pd.notna(entry_price):
            prices_by_date.setdefault(d, {})[ticker] = float(entry_price)

    return prices_by_date


def check_vps_availability() -> bool:
    """Check if VPS paper_finviz snapshots are available."""
    if not PAPER_FINVIZ_DIR.exists():
        return False
    snapshots = list(PAPER_FINVIZ_DIR.glob("*/snapshot.json"))
    return len(snapshots) > 0


# ============================================================
# Reporting
# ============================================================

def generate_report(
    results: list[ConvergenceResult],
    output_path: Path = CONVERGENCE_REPORT_PATH,
) -> str:
    """
    Generate a root-cause convergence report in markdown.

    Args:
        results: List of ConvergenceResult per trading session.
        output_path: Where to write the report.

    Returns:
        Report text (also written to output_path).
    """
    lines = [
        "# Shadow Convergence Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Sessions analyzed:** {len(results)}",
        "",
    ]

    passed = sum(1 for r in results if r.threshold_passed)
    failed = sum(1 for r in results if not r.threshold_passed)
    total_anomalies = sum(len(r.price_anomalies) for r in results)
    degraded = sum(1 for r in results if r.degradation_mode != "NORMAL")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Sessions passed (>={CONVERGENCE_THRESHOLD_PCT}) | {passed} |")
    lines.append(f"| Sessions below threshold | {failed} |")
    lines.append(f"| Total price anomalies | {total_anomalies} |")
    lines.append(f"| Degraded mode sessions | {degraded} |")

    if degraded > 0:
        lines.append("")
        lines.append("> ⚠️ **Degraded Mode**: Some sessions ran without VPS snapshot data.")
        lines.append("")

    lines.append("")
    lines.append("## Daily Scores")
    lines.append("")
    lines.append("| Date | Score | Overlap/Union | BT Signals | SH Signals | Anomalies | Status |")
    lines.append("|------|-------|---------------|------------|------------|-----------|--------|")

    for r in sorted(results, key=lambda x: x.date):
        status = "PASS" if r.threshold_passed else "FAIL"
        mode_tag = f" ({r.degradation_mode})" if r.degradation_mode != "NORMAL" else ""
        lines.append(
            f"| {r.date} | {r.convergence_score:.1%} | {r.overlap}/{r.union} "
            f"| {r.backtest_signal_count} | {r.shadow_signal_count} "
            f"| {len(r.price_anomalies)} | {status}{mode_tag} |"
        )

    if total_anomalies > 0:
        lines.append("")
        lines.append("## Price Anomalies")
        lines.append("")
        lines.append("| Ticker | Date | Backtest $ | Shadow $ | Δ% | Category |")
        lines.append("|--------|------|------------|----------|-----|----------|")
        for r in sorted(results, key=lambda x: x.date):
            for a in r.price_anomalies:
                lines.append(
                    f"| {a.ticker} | {r.date} | ${a.backtest_price:.2f} "
                    f"| ${a.shadow_price:.2f} | {a.discrepancy_pct:.2%} | {a.category} |"
                )

    if failed > 0 or total_anomalies > 0:
        lines.append("")
        lines.append("## Root Cause Analysis")
        lines.append("")

        # Count anomaly categories
        category_counts: dict[str, int] = {}
        for r in results:
            for a in r.price_anomalies:
                category_counts[a.category] = category_counts.get(a.category, 0) + 1

        # Count missing signals
        missing_bt_total = sum(len(r.missing_from_backtest) for r in results)
        missing_sh_total = sum(len(r.missing_from_shadow) for r in results)

        lines.append("### Discrepancy Categories")
        lines.append("")
        for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count} occurrences")
        if not category_counts:
            lines.append("- No categorized anomalies.")

        lines.append("")
        lines.append("### Signal Coverage")
        lines.append("")
        lines.append(f"- **Missing from backtest** (present in shadow only): "
                     f"{missing_bt_total} occurrences")
        lines.append(f"- **Missing from shadow** (present in backtest only): "
                     f"{missing_sh_total} occurrences")

        if missing_bt_total > 0 or missing_sh_total > 0:
            lines.append("")
            lines.append("### Recommendations")
            if missing_bt_total > 0:
                lines.append("- **Universe mismatch**: review backtest universe vs "
                             "live scanner universe alignment.")
            if missing_sh_total > 0:
                lines.append("- **Shadow capture gap**: verify daily_scan captures all "
                             "tickers that backtest processes.")
            if any(a.category == "config_drift" for r in results for a in r.price_anomalies):
                lines.append("- **Config drift**: verify production_config.json matches "
                             "backtest config overrides.")
            if any(a.category == "data_freshness" for r in results for a in r.price_anomalies):
                lines.append("- **Data freshness**: VPS snapshot may be stale. "
                             "Check sync timestamp.")

    report = "\n".join(lines)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info(f"Report written to {output_path}")

    return report


# ============================================================
# Main audit orchestrator
# ============================================================

def run_convergence_audit(
    start_date: str,
    end_date: str,
    backtest_tag: str = "gold_standard_variant_e",
) -> list[ConvergenceResult]:
    """
    Run the full convergence audit across a date range.

    Loads backtest and shadow signals from standard output paths,
    computes convergence for each overlapping date, and returns
    a list of ConvergenceResult objects.

    Degraded mode (VPS_UNAVAILABLE) is activated when paper_finviz
    snapshots are absent.
    """
    vps_available = check_vps_availability()
    if not vps_available:
        logger.warning("VPS paper_finviz snapshots not available — "
                       "running in DEGRADED mode.")

    bt_signals = load_backtest_signals(start_date, end_date, backtest_tag)
    sh_signals = load_shadow_signals(start_date, end_date)
    bt_prices = load_backtest_prices(start_date, end_date, backtest_tag)
    sh_prices = load_shadow_prices(start_date, end_date)

    all_dates = sorted(set(list(bt_signals.keys()) + list(sh_signals.keys())))
    if not all_dates:
        logger.warning("No signal data found in the specified range.")
        return []

    results: list[ConvergenceResult] = []
    for d in all_dates:
        bt_set = bt_signals.get(d, set())
        sh_set = sh_signals.get(d, set())

        overlap, union, score = compute_convergence_score(bt_set, sh_set)

        bt_price_map = bt_prices.get(d, {})
        sh_price_map = sh_prices.get(d, {})

        anomalies = compute_price_discrepancies(bt_price_map, sh_price_map)

        # Categorize each anomaly
        for anomaly in anomalies:
            anomaly.category = categorize_anomaly(
                anomaly, bt_set, sh_set, vps_available
            )

        result = ConvergenceResult(
            date=d,
            overlap=overlap,
            union=union,
            convergence_score=score,
            threshold_passed=score >= CONVERGENCE_THRESHOLD,
            price_anomalies=anomalies,
            degradation_mode="NORMAL" if vps_available else "VPS_UNAVAILABLE",
            backtest_signal_count=len(bt_set),
            shadow_signal_count=len(sh_set),
            missing_from_backtest=sorted(sh_set - bt_set),
            missing_from_shadow=sorted(bt_set - sh_set),
            vps_available=vps_available,
        )

        status = "PASS" if result.threshold_passed else "FAIL"
        mode_info = f" ({result.degradation_mode})"
        logger.info(
            f"[{d}] Convergence: {score:.1%} ({overlap}/{union}) | "
            f"Anomalies: {len(anomalies)} | {status}{mode_info}"
        )

        results.append(result)

    return results


# ============================================================
# CLI
# ============================================================

def normalize_date_range(start_date: str, end_date: str) -> tuple[str, str]:
    """
    Normalize YYYY-MM or YYYY-MM-DD input to full YYYY-MM-DD range.

    If only YYYY-MM is provided, expand to full month.
    """
    result_start = start_date
    result_end = end_date

    if len(start_date) == 7 and start_date.count("-") == 1:
        result_start = f"{start_date}-01"
    if len(end_date) == 7 and end_date.count("-") == 1:
        year_str, month_str = end_date.split("-")
        last_day = monthrange(int(year_str), int(month_str))[1]
        result_end = f"{end_date}-{last_day:02d}"

    return result_start, result_end


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Shadow Convergence Audit — compare backtest vs live signals"
    )
    parser.add_argument(
        "--start", required=True,
        help="Start date (YYYY-MM-DD or YYYY-MM)",
    )
    parser.add_argument(
        "--end", required=True,
        help="End date (YYYY-MM-DD or YYYY-MM)",
    )
    parser.add_argument(
        "--backtest-tag", default="gold_standard_variant_e",
        help="Backtest tag for output files (default: gold_standard_variant_e)",
    )
    parser.add_argument(
        "--output", default=str(CONVERGENCE_REPORT_PATH),
        help=f"Report output path (default: {CONVERGENCE_REPORT_PATH})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    """Entry point for CLI execution."""
    args = parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )

    start_date, end_date = normalize_date_range(args.start, args.end)

    logger.info(f"Running convergence audit: {start_date} → {end_date}")
    logger.info(f"Backtest tag: {args.backtest_tag}")

    results = run_convergence_audit(start_date, end_date, args.backtest_tag)

    output_path = Path(args.output)

    if not results:
        logger.warning("No results — no convergence data to report.")
        report = generate_report([], output_path)
        print(report)
        return

    report = generate_report(results, output_path)
    print(report)

    # Summary
    passed = sum(1 for r in results if r.threshold_passed)
    failed = len(results) - passed
    total_anomalies = sum(len(r.price_anomalies) for r in results)
    degraded = sum(1 for r in results if r.degradation_mode != "NORMAL")

    logger.info("=" * 60)
    logger.info("CONVERGENCE AUDIT COMPLETE")
    logger.info(f"  Sessions: {len(results)} | Passed: {passed} | Failed: {failed}")
    logger.info(f"  Price anomalies: {total_anomalies}")
    if degraded:
        logger.info(f"  Degraded mode sessions: {degraded}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
