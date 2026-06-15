#!/usr/bin/env python3
"""Signal-Level Deduplication and True Incremental U2 Analysis.

Groups trade legs by symbol + entry_date to represent unique base signals,
isolates U2_only tickers, and computes true non-overlapping performance.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _calculate_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "signals": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_rmult": 0.0,
            "expectancy_pnl": 0.0,
            "expectancy_pct": 0.0,
        }

    total_signals = len(df)
    
    # Net trade PnL > 0 defines a winning trade
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] < 0]
    
    win_count = len(wins)
    win_rate = float(win_count / total_signals * 100) if total_signals > 0 else 0.0
    
    gross_profits = float(wins["pnl"].sum())
    gross_losses = float(losses["pnl"].sum())
    
    profit_factor = (
        float(gross_profits / abs(gross_losses))
        if gross_losses != 0
        else (gross_profits if gross_profits > 0 else 1.0)
    )
    if np.isinf(profit_factor) or np.isnan(profit_factor):
        profit_factor = 99.0
        
    expectancy_rmult = float(df["r_multiple"].mean()) if "r_multiple" in df.columns else 0.0
    expectancy_pnl = float(df["pnl"].mean()) if "pnl" in df.columns else 0.0
    expectancy_pct = float(df["return_pct"].mean()) if "return_pct" in df.columns else 0.0
    
    return {
        "signals": int(total_signals),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_rmult": round(expectancy_rmult, 4),
        "expectancy_pnl": round(expectancy_pnl, 2),
        "expectancy_pct": round(expectancy_pct, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run signal-level deduplication and incremental U2 analysis")
    parser.add_argument("--trades", required=True, help="Path to full_db_gold_trades.csv")
    parser.add_argument("--output", required=True, help="Path to output signal_level_dedup_report.json")
    args = parser.parse_args()

    if not Path(args.trades).exists() or Path(args.trades).stat().st_size == 0:
        print(f"Error: {args.trades} not found or empty.")
        return 1

    trades = pd.read_csv(args.trades)
    if trades.empty:
        print("Error: Trades dataframe is empty.")
        return 1

    # Ensure required columns
    required = ["symbol", "entry_date", "pnl", "r_multiple", "return_pct", "combo_name", "universe_layer"]
    for col in required:
        if col not in trades.columns:
            print(f"Error: Required column '{col}' is missing.")
            return 1

    # Ensure datetime format for entry_date
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])

    # 1. STRATEGY REDUNDANCY ANALYSIS (Before leg deduplication)
    # Get unique base signals per strategy to calculate intersection
    sig_cols = ["symbol", "entry_date", "universe_layer"]
    pullback_sigs = trades[trades["combo_name"] == "combo_pullback_entry"].drop_duplicates(subset=sig_cols)
    momentum_sigs = trades[trades["combo_name"] == "combo_pure_momentum"].drop_duplicates(subset=sig_cols)
    
    merged_sigs = pd.merge(pullback_sigs[sig_cols], momentum_sigs[sig_cols], on=sig_cols, how="inner")
    
    redundancy = {
        "pullback_unique_signals": int(len(pullback_sigs)),
        "momentum_unique_signals": int(len(momentum_sigs)),
        "intersecting_signals": int(len(merged_sigs)),
        "redundancy_pct": round(float(len(merged_sigs) / max(len(pullback_sigs), 1) * 100), 2)
    }

    # 2. SIGNAL-LEVEL CONSOLIDATION (Aggregating multi-leg exits)
    # We group by symbol + entry_date + combo_name + universe_layer to isolate unique signals
    # To compute net return_pct accurately, we use the average return_pct of the legs, 
    # weighted by the shares sold on each leg.
    if "shares" not in trades.columns:
        trades["shares"] = 1.0

    def aggregate_legs(group: pd.DataFrame) -> pd.Series:
        total_pnl = group["pnl"].sum()
        total_r = group["r_multiple"].sum()
        
        # Weighted average return pct
        total_shares = group["shares"].sum()
        weighted_ret = (group["return_pct"] * group["shares"]).sum() / total_shares if total_shares > 0 else group["return_pct"].mean()
        
        first_row = group.iloc[0]
        return pd.Series({
            "pnl": total_pnl,
            "r_multiple": total_r,
            "return_pct": weighted_ret,
            "entry_score": first_row.get("entry_score", 0.5),
        })

    print("⏳ Aggregating multi-leg exits to signal-level...")
    group_cols = ["symbol", "entry_date", "combo_name", "universe_layer"]
    signals = trades.groupby(group_cols, group_keys=False).apply(aggregate_legs).reset_index()
    print(f"✅ Consolidated {len(trades)} trade leg rows into {len(signals)} unique strategy signal rows.")

    # 3. SEGMENT TICKERS AND ISOLATE U2_ONLY
    # Get the sets of tickers for U1 and U2
    u1_tickers = set(signals[signals["universe_layer"] == "U1_pit_validated"]["symbol"].unique())
    u2_tickers = set(signals[signals["universe_layer"] == "U2_db_liquidity_strong"]["symbol"].unique())
    u2_only_tickers = u2_tickers - u1_tickers

    # Extract groups
    u1_signals = signals[signals["universe_layer"] == "U1_pit_validated"]
    u2_signals = signals[signals["universe_layer"] == "U2_db_liquidity_strong"]
    u2_only_signals = u2_signals[u2_signals["symbol"].isin(u2_only_tickers)]

    # Compute metrics for each cohort
    cohort_metrics = {
        "U1_pit_validated": _calculate_metrics(u1_signals),
        "U2_db_liquidity_strong": _calculate_metrics(u2_signals),
        "U2_only": _calculate_metrics(u2_only_signals),
    }

    # Add relative/absolute difference for U2_only vs U1
    u1_m = cohort_metrics["U1_pit_validated"]
    u2_only_m = cohort_metrics["U2_only"]
    
    if u1_m["signals"] > 0 and u2_only_m["signals"] > 0:
        cohort_metrics["U2_only_vs_U1_diff"] = {
            "win_rate_diff": round(u2_only_m["win_rate"] - u1_m["win_rate"], 2),
            "profit_factor_diff": round(u2_only_m["profit_factor"] - u1_m["profit_factor"], 2),
            "expectancy_rmult_diff": round(u2_only_m["expectancy_rmult"] - u1_m["expectancy_rmult"], 4),
            "win_rate_pct_change": round((u2_only_m["win_rate"] - u1_m["win_rate"]) / u1_m["win_rate"] * 100, 2),
            "profit_factor_pct_change": round((u2_only_m["profit_factor"] - u1_m["profit_factor"]) / u1_m["profit_factor"] * 100, 2),
        }

    # Fetch sector mapping to show sector breakdown in U2_only
    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    sector_map = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            sec_df = pd.read_sql_query("SELECT ticker, sector FROM universe", conn)
            sector_map = dict(zip(sec_df["ticker"], sec_df["sector"]))
            conn.close()
        except Exception as e:
            print(f"Warning: Could not fetch metadata from SQLite ({e})", file=sys.stderr)

    u2_only_signals = u2_only_signals.copy()
    u2_only_signals["sector"] = u2_only_signals["symbol"].map(sector_map).fillna("Unknown")
    
    sector_breakdown = []
    for sector, grp in u2_only_signals.groupby("sector"):
        m = _calculate_metrics(grp)
        m["sector"] = sector
        sector_breakdown.append(m)
        
    # Sort sector breakdown by number of signals descending
    sector_breakdown = sorted(sector_breakdown, key=lambda x: x["signals"], reverse=True)

    # 4. STRUCTURE FINAL JSON REPORT
    report = {
        "status": "ok",
        "ticker_overlap": {
            "u1_unique_tickers": len(u1_tickers),
            "u2_unique_tickers": len(u2_tickers),
            "intersecting_tickers": len(u1_tickers & u2_tickers),
            "u2_only_unique_tickers": len(u2_only_tickers),
        },
        "strategy_redundancy": redundancy,
        "cohort_metrics": cohort_metrics,
        "u2_only_sector_breakdown": sector_breakdown,
    }

    # Output JSON file
    Path(args.output).write_text(json.dumps(report, indent=2, default=str))
    print(f"💾 Report saved successfully to {args.output}")

    # Print markdown report to stdout
    print("\n" + "="*80)
    print("      🚀 INCREMENTAL U2 & SIGNAL-LEVEL DEDUPLICATION REPORT 🚀")
    print("="*80)
    print(f"  • Consolidated rows: {len(trades)} trade legs ➡️  {len(signals)} unique signals")
    print(f"  • Strategy Redundancy: {redundancy['redundancy_pct']}% identical signals")
    print(f"    (Pullback: {redundancy['pullback_unique_signals']} | Momentum: {redundancy['momentum_unique_signals']} | Intersect: {redundancy['intersecting_signals']})")
    print("-"*80)
    
    print("  📊 COHORT METRICS COMPARISON:")
    print("  " + "-"*76)
    print(f"  {'Cohort':<26} | {'Signals':<8} | {'Win Rate %':<10} | {'Profit Factor':<13} | {'Expectancy (R)':<14}")
    print("  " + "-"*76)
    
    for cohort, m in cohort_metrics.items():
        if cohort == "U2_only_vs_U1_diff":
            continue
        print(f"  {cohort:<26} | {m['signals']:<8} | {m['win_rate']:<10}% | {m['profit_factor']:<13} | {m['expectancy_rmult']:<14}")
    print("  " + "-"*76)

    if "U2_only_vs_U1_diff" in cohort_metrics:
        diff = cohort_metrics["U2_only_vs_U1_diff"]
        print(f"  🔎 TRUE INCREMENTAL U2 IMPACT (U2_only vs U1 Baseline):")
        print(f"    • Win Rate Change:      {diff['win_rate_diff']}% ({diff['win_rate_pct_change']}% relative)")
        print(f"    • Profit Factor Change:  {diff['profit_factor_diff']} ({diff['profit_factor_pct_change']}% relative)")
        print(f"    • Expectancy (R) Diff:  {diff['expectancy_rmult_diff']}")
    print("-"*80)

    print("  Sector Breakdown for U2_only (Incremental Tickers):")
    for sec_m in sector_breakdown:
        print(f"    • {sec_m['sector']:<24}: {sec_m['signals']:<3} signals | WR: {sec_m['win_rate']:<5}% | PF: {sec_m['profit_factor']:<4} | Expectancy (R): {sec_m['expectancy_rmult']}")
    print("="*80 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
