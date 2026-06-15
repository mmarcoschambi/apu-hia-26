#!/usr/bin/env python3
"""run_e20_u2_incremental.py - E20: Incremental U2 Only Validation.

Strictly implements the Research & Validation Protocol to assess the true,
non-overlapping value of the U2 universe expansion.
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


def _calculate_max_drawdown(pnl_series: pd.Series, initial_cap: float = 100000.0) -> float:
    if pnl_series.empty:
        return 0.0
    equity = initial_cap + pnl_series.cumsum()
    peaks = equity.cummax()
    drawdowns = (equity - peaks) / peaks * 100
    return round(float(drawdowns.min()), 2)


def _calculate_cohort_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "signals": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_rmult": 0.0,
            "expectancy_pnl": 0.0,
            "expectancy_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }

    total_signals = len(df)
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
    
    # Estimate drawdown sequentially
    mdd = _calculate_max_drawdown(df["pnl"])
    
    return {
        "signals": int(total_signals),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_rmult": round(expectancy_rmult, 4),
        "expectancy_pnl": round(expectancy_pnl, 2),
        "expectancy_pct": round(expectancy_pct, 2),
        "max_drawdown_pct": mdd,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="E20 Incremental U2 Validation")
    parser.add_argument("--trades", required=True, help="Path to full_db_gold_trades.csv")
    parser.add_argument("--output", required=True, help="Path to output e20_u2_incremental_report.json")
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

    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    
    # ── CONSOLIDATE & RESOLVE REDUNDANCY ──
    # Since combos pullback_entry and pure_momentum have 100% redundancy, we only process ONE strategy's signals
    trades_one = trades[trades["combo_name"] == "combo_pullback_entry"]
    if trades_one.empty:
        # Fallback in case of custom naming
        trades_one = trades[trades["combo_name"] == trades["combo_name"].unique()[0]]

    if "shares" not in trades_one.columns:
        trades_one = trades_one.copy()
        trades_one["shares"] = 1.0

    def aggregate_legs(group: pd.DataFrame) -> pd.Series:
        total_pnl = group["pnl"].sum()
        total_r = group["r_multiple"].sum()
        total_shares = group["shares"].sum()
        weighted_ret = (group["return_pct"] * group["shares"]).sum() / total_shares if total_shares > 0 else group["return_pct"].mean()
        
        first_row = group.iloc[0]
        return pd.Series({
            "pnl": total_pnl,
            "r_multiple": total_r,
            "return_pct": weighted_ret,
            "entry_score": first_row.get("entry_score", 0.5),
        })

    print("⏳ Aggregating multi-leg exits to signal-level unique trades...")
    group_cols = ["symbol", "entry_date", "universe_layer"]
    signals = trades_one.groupby(group_cols, group_keys=False).apply(aggregate_legs).reset_index()
    signals = signals.sort_values(by="entry_date").reset_index(drop=True)
    print(f"✅ Consolidated trade rows into {len(signals)} unique signal-level trades.")

    # ── DEFINE COHORTS ──
    u1_tickers = set(signals[signals["universe_layer"] == "U1_pit_validated"]["symbol"].unique())
    u2_tickers = set(signals[signals["universe_layer"] == "U2_db_liquidity_strong"]["symbol"].unique())
    u2_only_tickers = u2_tickers - u1_tickers

    u1_core = signals[signals["universe_layer"] == "U1_pit_validated"]
    u2_all = signals[signals["universe_layer"] == "U2_db_liquidity_strong"]
    u2_only = u2_all[u2_all["symbol"].isin(u2_only_tickers)]
    u1_plus_u2_only = pd.concat([u1_core, u2_only], ignore_index=True).sort_values(by="entry_date").reset_index(drop=True)

    # ── MODULE A: WALK-FORWARD TEMPORAL ANALYSIS ──
    yearly_metrics = {}
    years = sorted(signals["entry_date"].dt.year.dropna().unique().tolist())
    
    for cohort_name, cohort_df in [
        ("U1_core", u1_core),
        ("U2_all", u2_all),
        ("U2_only", u2_only),
        ("U1_plus_U2_only", u1_plus_u2_only),
    ]:
        cohort_yearly = []
        for year in years:
            grp = cohort_df[cohort_df["entry_date"].dt.year == year]
            m = _calculate_cohort_metrics(grp)
            m["year"] = int(year)
            cohort_yearly.append(m)
        yearly_metrics[cohort_name] = cohort_yearly

    # ── MODULE B: ROBUSTNESS BY SECTOR ──
    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    sector_map = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            sec_df = pd.read_sql_query("SELECT ticker, sector FROM universe", conn)
            sector_map = dict(zip(sec_df["ticker"], sec_df["sector"]))
            conn.close()
        except Exception as e:
            print(f"Warning: Sector query failed ({e})", file=sys.stderr)

    u2_only = u2_only.copy()
    u2_only["sector"] = u2_only["symbol"].map(sector_map).fillna("Unknown")
    
    sector_raw = []
    for sector, grp in u2_only.groupby("sector"):
        m = _calculate_cohort_metrics(grp)
        m["sector"] = sector
        
        # Robustness Classification
        if sector == "Unknown":
            m["status"] = "DataIssue"
        elif m["signals"] >= 30:
            m["status"] = "Actionable"
        else:
            m["status"] = "Observational"
            
        sector_raw.append(m)
    sector_raw = sorted(sector_raw, key=lambda x: x["signals"], reverse=True)

    # ── MODULE C: VARIANT ANALYSIS (INCREMENTAL COMPARISONS) ──
    u2_only_no_tech_utilities = u2_only[~u2_only["sector"].isin(["Technology", "Utilities"])]
    u2_only_no_unknown = u2_only[u2_only["sector"] != "Unknown"]

    variant_metrics = {
        "U1_core": _calculate_cohort_metrics(u1_core),
        "U2_all": _calculate_cohort_metrics(u2_all),
        "U2_only": _calculate_cohort_metrics(u2_only),
        "U1_plus_U2_only": _calculate_cohort_metrics(u1_plus_u2_only),
        "U2_only_no_tech_utilities": _calculate_cohort_metrics(u2_only_no_tech_utilities),
        "U2_only_no_unknown": _calculate_cohort_metrics(u2_only_no_unknown),
    }

    # ── MODULE D: PNL CONCENTRATION RISK ──
    concentration_metrics = {}
    for name, df in [
        ("U1_core", u1_core),
        ("U2_only", u2_only),
        ("U1_plus_U2_only", u1_plus_u2_only),
    ]:
        if df.empty:
            concentration_metrics[name] = {"top_5_tickers": {}, "top_5_pnl_pct": 0.0, "top_5_trade_pct": 0.0}
            continue
            
        ticker_grp = df.groupby("symbol").agg(
            trades=("pnl", "count"),
            total_pnl=("pnl", "sum"),
            total_r=("r_multiple", "sum")
        )
        
        # Sort by absolute PnL contribution
        ticker_grp["abs_pnl"] = ticker_grp["total_pnl"].abs()
        top_5 = ticker_grp.sort_values(by="abs_pnl", ascending=False).head(5)
        
        total_cohort_pnl = df["pnl"].abs().sum()
        top_5_pnl_sum = top_5["abs_pnl"].sum()
        top_5_pnl_pct = float(top_5_pnl_sum / total_cohort_pnl * 100) if total_cohort_pnl > 0 else 0.0
        
        total_cohort_trades = len(df)
        top_5_trades_sum = top_5["trades"].sum()
        top_5_trade_pct = float(top_5_trades_sum / total_cohort_trades * 100) if total_cohort_trades > 0 else 0.0
        
        concentration_metrics[name] = {
            "top_5_tickers": top_5[["trades", "total_pnl", "total_r"]].to_dict(orient="index"),
            "top_5_pnl_pct": round(top_5_pnl_pct, 2),
            "top_5_trade_pct": round(top_5_trade_pct, 2),
        }

    # ── EVALUATE GO/NO-GO CRITERIA GATES ──
    u1_m = variant_metrics["U1_core"]
    u2_only_m = variant_metrics["U2_only"]
    u1_plus_u2_m = variant_metrics["U1_plus_U2_only"]
    
    # Gate 1: U2_only maintains Profit Factor > 1.25
    gate_pf_val = u2_only_m["profit_factor"]
    gate_pf = "PASS" if gate_pf_val > 1.25 else "FAIL"
    
    # Gate 2: Expectancy R positive in >= 5 out of 7 full years (2019-2025)
    positive_years = 0
    full_years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    for y_m in yearly_metrics["U2_only"]:
        if y_m["year"] in full_years and y_m["expectancy_rmult"] > 0:
            positive_years += 1
    gate_years = "PASS" if positive_years >= 5 else "FAIL"
    
    # Gate 3: U1_core + U2_only improves expectancy or trade count without degrading PF by > 5% vs U1_core baseline
    # Limit: U1 PF = 1.32, degrading by <= 5% means >= 1.254
    gate_pf_degradation_val = float((u1_plus_u2_m["profit_factor"] - u1_m["profit_factor"]) / u1_m["profit_factor"] * 100)
    gate_pf_degradation = "PASS" if gate_pf_degradation_val >= -5.0 else "FAIL"
    
    # Gate 4: Top 5 tickers do not explain more than 20-25% of total PnL
    gate_concentration_val = concentration_metrics["U2_only"]["top_5_pnl_pct"]
    gate_concentration = "PASS" if gate_concentration_val <= 25.0 else "FAIL"
    
    # Sector Diagnostic Gate: Technology and Utilities remain negative in walk-forward
    tech_m = next((x for x in sector_raw if x["sector"] == "Technology"), None)
    util_m = next((x for x in sector_raw if x["sector"] == "Utilities"), None)
    tech_neg = tech_m["expectancy_rmult"] < 0 if tech_m else True
    util_neg = util_m["expectancy_rmult"] < 0 if util_m else True
    gate_sector_block = "PASS" if (tech_neg and util_neg) else "WARN"

    # Final Verdict
    all_pass = (gate_pf == "PASS" and gate_years == "PASS" and gate_pf_degradation == "PASS" and gate_concentration == "PASS")
    verdict = "GO_SHADOW" if all_pass else "NO_GO"

    gates_evaluation = {
        "verdict": verdict,
        "gates": {
            "gate1_u2_only_pf_gt_1.25": {
                "status": gate_pf,
                "value": gate_pf_val,
                "criterion": "> 1.25"
            },
            "gate2_positive_years_ge_5_of_7": {
                "status": gate_years,
                "value": f"{positive_years} of 7",
                "criterion": ">= 5"
            },
            "gate3_combined_pf_degradation_le_5pct": {
                "status": gate_pf_degradation,
                "value": f"{round(gate_pf_degradation_val, 2)}%",
                "criterion": ">= -5.0%"
            },
            "gate4_pnl_concentration_le_25pct": {
                "status": gate_concentration,
                "value": f"{gate_concentration_val}%",
                "criterion": "<= 25.0%"
            },
            "diagnostic_sector_drag_tech_utilities_negative": {
                "status": gate_sector_block,
                "value": f"Tech R: {tech_m['expectancy_rmult'] if tech_m else 0.0} | Util R: {util_m['expectancy_rmult'] if util_m else 0.0}",
                "criterion": "Expectancy R < 0"
            }
        }
    }

    # ── SAVE AND OUTPUT ──
    report = {
        "status": "ok",
        "ticker_overlap": {
            "u1_unique_tickers": len(u1_tickers),
            "u2_unique_tickers": len(u2_tickers),
            "u2_only_unique_tickers": len(u2_only_tickers),
        },
        "gates_evaluation": gates_evaluation,
        "cohort_metrics": variant_metrics,
        "yearly_metrics": yearly_metrics,
        "sector_metrics": sector_raw,
        "concentration_metrics": concentration_metrics,
    }

    Path(args.output).write_text(json.dumps(report, indent=2, default=str))
    print(f"💾 E20 Report saved successfully to {args.output}")

    # Print markdown console report
    print("\n" + "="*80)
    print("                🛡️  E20: INCREMENTAL U2 VALIDATION REPORT 🛡️")
    print("="*80)
    print(f"  • CONSOLIDATED SIGNALS: {len(signals)} unique trades (Deduplicated legs & combos)")
    print(f"  • TICKERS OVERLAP: U1 ({len(u1_tickers)}) | U2 ({len(u2_tickers)}) | U2_only ({len(u2_only_tickers)})")
    print("-"*80)
    
    print(f"  🚦 GATES VERDICT: {verdict.upper()} (All criteria gates evaluated)")
    print("  " + "-"*76)
    for gate_name, gate_data in gates_evaluation["gates"].items():
        icon = "✅" if gate_data["status"] == "PASS" else ("⚠️" if gate_data["status"] == "WARN" else "❌")
        print(f"    {icon} {gate_name:<46}: {gate_data['status']:<6} (Value: {gate_data['value']} | Req: {gate_data['criterion']})")
    print("-"*80)

    print("  📊 COHORT VARIANT METRICS:")
    print("  " + "-"*76)
    print(f"  {'Cohort / Variant':<28} | {'Signals':<8} | {'Win Rate %':<10} | {'Profit Factor':<13} | {'Expectancy (R)':<14}")
    print("  " + "-"*76)
    for name, m in variant_metrics.items():
        print(f"  {name:<28} | {m['signals']:<8} | {m['win_rate']:<10}% | {m['profit_factor']:<13} | {m['expectancy_rmult']:<14}")
    print("  " + "-"*76)

    print("  📅 YEARLY WALK-FORWARD TEMPORAL ANALYSIS (U2_only):")
    print("  " + "-"*76)
    print(f"    {'Year':<6} | {'Signals':<8} | {'Win Rate %':<10} | {'Profit Factor':<13} | {'Expectancy (R)':<14} | {'Drawdown %':<10}")
    print("  " + "-"*76)
    for y_m in yearly_metrics["U2_only"]:
        print(f"    {y_m['year']:<6} | {y_m['signals']:<8} | {y_m['win_rate']:<10}% | {y_m['profit_factor']:<13} | {y_m['expectancy_rmult']:<14} | {y_m['max_drawdown_pct']:<10}%")
    print("-"*80)

    print("  💼 SECTOR SIGNIFICANCE ANALYSIS (U2_only Tickers):")
    print("  " + "-"*76)
    print(f"    {'Sector':<24} | {'Signals':<8} | {'Win Rate %':<10} | {'Profit Factor':<13} | {'Expectancy (R)':<14} | {'Robustness':<12}")
    print("  " + "-"*76)
    for s_m in sector_raw:
        print(f"    {s_m['sector']:<24} | {s_m['signals']:<8} | {s_m['win_rate']:<10}% | {s_m['profit_factor']:<13} | {s_m['expectancy_rmult']:<14} | {s_m['status']:<12}")
    print("-"*80)

    print("  ⚖️ TICKER CONCENTRATION RISK (top 5 PnL explanation):")
    print("  " + "-"*76)
    for name, c_data in concentration_metrics.items():
        print(f"    • {name:<16}: Top 5 tickers account for {c_data['top_5_pnl_pct']}% of PnL ({c_data['top_5_trade_pct']}% of trades)")
    print("="*80 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
