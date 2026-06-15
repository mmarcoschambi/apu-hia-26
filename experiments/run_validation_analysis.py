#!/usr/bin/env python3
import argparse
import json
import os
import pandas as pd
import numpy as np
from pathlib import Path
from src.utils.sector_rotation import SECTOR_MAP

OUTPUT_DIR = Path("outputs/backtests")

def calculate_window_metrics(df_trades, df_equity, start_date, end_date):
    """Calculates trade metrics and drawdown for a specific time window."""
    # Filter trades
    window_trades = df_trades[
        (df_trades["entry_date"] >= start_date) & 
        (df_trades["entry_date"] <= end_date)
    ]
    
    # Filter equity for drawdown calculation
    window_equity = df_equity[
        (df_equity["date"] >= start_date) & 
        (df_equity["date"] <= end_date)
    ].copy()
    
    n_trades = len(window_trades)
    
    if window_trades.empty:
        return {
            "pnl": 0.0,
            "profit_factor": 0.0,
            "trades": 0,
            "win_rate": 0.0,
            "max_dd": 0.0,
            "avg_return": 0.0
        }
        
    pnl_sum = window_trades["pnl"].sum()
    wins = window_trades[window_trades["pnl"] > 0]["pnl"].sum()
    losses = abs(window_trades[window_trades["pnl"] < 0]["pnl"].sum())
    pf = wins / losses if losses > 0 else float("inf")
    win_rate = (window_trades["pnl"] > 0).mean() * 100
    avg_ret = window_trades["return_pct"].mean()
    
    # Calculate Max Drawdown for this window specifically
    max_dd = 0.0
    if not window_equity.empty:
        eq_col = "0" if "0" in window_equity.columns else "equity"
        eq = window_equity[eq_col]
        cummax = eq.cummax()
        dd = (eq - cummax) / cummax * 100
        max_dd = dd.min()
        
    return {
        "pnl": round(float(pnl_sum), 2),
        "profit_factor": round(float(pf), 2),
        "trades": n_trades,
        "win_rate": round(float(win_rate), 2),
        "max_dd": round(float(max_dd), 2),
        "avg_return": round(float(avg_ret), 2)
    }

def main():
    parser = argparse.ArgumentParser(description="Analyze backtest results for temporal robustness and concentration.")
    parser.add_argument("--tag", type=str, required=True, help="Backtest execution tag (e.g. russell_baseline_e25_rs_fixed_2019_2025)")
    args = parser.parse_args()

    trades_file = OUTPUT_DIR / f"{args.tag}_trades.csv"
    equity_file = OUTPUT_DIR / f"{args.tag}_equity.csv"
    metrics_file = OUTPUT_DIR / f"{args.tag}_metrics.json"

    if not trades_file.exists() or not equity_file.exists():
        print(f"Error: Backtest files not found for tag: {args.tag}")
        print(f"Looked for: {trades_file} and {equity_file}")
        return

    print(f"=========================================================")
    print(f"📊 VALIDATION REPORT FOR: {args.tag}")
    print(f"=========================================================\n")

    # Load data
    df_trades = pd.read_csv(trades_file)
    df_equity = pd.read_csv(equity_file)
    
    # Parse dates
    df_trades["entry_date"] = pd.to_datetime(df_trades["entry_date"]).dt.strftime("%Y-%m-%d")
    df_equity["date"] = pd.to_datetime(df_equity["date"]).dt.strftime("%Y-%m-%d")

    # 1. Temporal Window Analysis
    print("## 1. Temporal Windows Analysis")
    print("---------------------------------")
    windows = [
        ("2019-2020 (Bull & Pandemic)", "2019-01-01", "2020-12-31"),
        ("2021-2022 (Bubble & Bear)", "2021-01-01", "2022-12-31"),
        ("2023-2024 (AI Expansion)", "2023-01-01", "2024-12-31"),
        ("2025 (Current Year)", "2025-01-01", "2025-06-30")
    ]
    
    window_results = []
    positive_windows = 0
    pf_checks = 0
    
    print(f"| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |")
    print(f"|---|---|---|---|---|---|---|---|---|")
    
    for name, start, end in windows:
        res = calculate_window_metrics(df_trades, df_equity, start, end)
        window_results.append((name, res))
        
        # Criteria checks
        if res["pnl"] > 0:
            positive_windows += 1
        if res["profit_factor"] >= 1.05:
            pf_checks += 1
            
        print(f"| {name} | {start} | {end} | ${res['pnl']:,} | {res['profit_factor']} | {res['trades']} | {res['win_rate']}% | {res['max_dd']}% | {res['avg_return']}% |")
        
    print("\n--- Criteria validation ---")
    c1 = positive_windows >= 3 or pf_checks >= 3
    print(f"- [Rule] At least 3/4 windows positive or PF >= 1.05: {'PASSED ✅' if c1 else 'FAILED ❌'} ({positive_windows}/4 positive, {pf_checks}/4 PF >= 1.05)")
    
    # Check max drawdown local in windows
    excessive_dd = [w for w, r in window_results if r["max_dd"] < -30.0]
    c2 = len(excessive_dd) == 0
    print(f"- [Rule] No window has excessive local Drawdown (< -30%%): {'PASSED ✅' if c2 else 'FAILED ❌'}")
    if excessive_dd:
        print(f"  ⚠️ Warning: Windows with Max DD < -30%: {', '.join(excessive_dd)}")

    # 2. Concentration Analysis
    print("\n## 2. Concentration and Dependencies")
    print("---------------------------------------")
    total_pnl = df_trades["pnl"].sum()
    print(f"Total Net PnL: ${total_pnl:,.2f}")
    
    # Concentration by ticker
    ticker_pnl = df_trades.groupby("symbol")["pnl"].sum().sort_values(ascending=False)
    top_winners = ticker_pnl.head(5)
    top_losers = ticker_pnl.tail(5)
    
    print("\nTop 5 Profit-Generating Tickers:")
    for ticker, val in top_winners.items():
        pct = (val / total_pnl) * 100 if total_pnl > 0 else 0.0
        print(f"  - {ticker}: ${val:,.2f} ({pct:.2f}% of net PnL)")
        
    print("\nTop 5 Loss-Generating Tickers:")
    for ticker, val in top_losers.items():
        pct = (val / total_pnl) * 100 if total_pnl > 0 else 0.0
        print(f"  - {ticker}: ${val:,.2f} ({pct:.2f}% of net PnL)")

    # Concentration check
    top1_pct = (ticker_pnl.iloc[0] / total_pnl) * 100 if total_pnl > 0 else 0.0
    c3 = top1_pct <= 25.0
    print(f"\n- [Rule] Ticker Concentration (Top 1 Ticker <= 25%% of Net PnL): {'PASSED ✅' if c3 else 'WARNING ⚠️'} (Top 1 ticker is {ticker_pnl.index[0]} at {top1_pct:.2f}%)")
    
    # Concentration by sector
    df_trades["sector"] = df_trades["symbol"].map(lambda s: SECTOR_MAP.get(s, "UNKNOWN"))
    sector_pnl = df_trades.groupby("sector")["pnl"].sum().sort_values(ascending=False)
    
    print("\nPnL Contribution by Sector:")
    for sector, val in sector_pnl.items():
        pct = (val / total_pnl) * 100 if total_pnl > 0 else 0.0
        print(f"  - {sector}: ${val:,.2f} ({pct:.2f}% of net PnL)")
        
    # Sizing metrics
    print("\n## 3. Sizing and E25 Execution Metrics")
    print("----------------------------------------")
    avg_sizing = df_trades["sizing_factor"].mean()
    min_sizing = df_trades["sizing_factor"].min()
    sizing_counts = df_trades["sizing_reason"].value_counts()
    
    print(f"Average Sizing Factor: {avg_sizing:.4f} (1.0 = Base)")
    print(f"Minimum Sizing Factor: {min_sizing:.4f}")
    print("Sizing Adjustments Summary:")
    for reason, count in sizing_counts.items():
        print(f"  - '{reason or 'no_reduction'}': {count} trades")

    # Generate Markdown Summary File
    summary_path = OUTPUT_DIR / f"{args.tag}_validation_summary.md"
    with open(summary_path, "w") as f:
        f.write(f"# Validation Report: {args.tag}\n\n")
        f.write(f"Analyzed on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Temporal Window Performance\n\n")
        f.write(f"| Window | Start | End | Net PnL ($) | Profit Factor | Trades | Win Rate % | Max DD % | Avg Return % |\n")
        f.write(f"|---|---|---|---|---|---|---|---|---|\n")
        for name, start, end in windows:
            res = calculate_window_metrics(df_trades, df_equity, start, end)
            f.write(f"| {name} | {start} | {end} | ${res['pnl']:,} | {res['profit_factor']} | {res['trades']} | {res['win_rate']}% | {res['max_dd']}% | {res['avg_return']}% |\n")
            
        f.write("\n### Rule Validation Checklist\n")
        f.write(f"- **Temporal Consistency Check**: {'PASSED' if c1 else 'FAILED'} ({positive_windows}/4 positive windows, {pf_checks}/4 PF >= 1.05)\n")
        f.write(f"- **Drawdown Excessiveness Check**: {'PASSED' if c2 else 'FAILED'} (Max local drawdown rule)\n")
        f.write(f"- **Concentration Check**: {'PASSED' if c3 else 'WARNING'} (Top 1 ticker is {ticker_pnl.index[0]} contributing {top1_pct:.2f}%)\n\n")
        
        f.write("## Ticker Concentration (Top 10 Contributors)\n\n")
        f.write("| Ticker | Net PnL ($) | % of Net PnL |\n")
        f.write("|---|---|---|\n")
        for ticker, val in ticker_pnl.head(10).items():
            pct = (val / total_pnl) * 100 if total_pnl > 0 else 0.0
            f.write(f"| {ticker} | ${val:,.2f} | {pct:.2f}% |\n")
            
        f.write("\n## Sector Performance\n\n")
        f.write("| Sector | Net PnL ($) | % of Net PnL |\n")
        f.write("|---|---|---|\n")
        for sector, val in sector_pnl.items():
            pct = (val / total_pnl) * 100 if total_pnl > 0 else 0.0
            f.write(f"| {sector} | ${val:,.2f} | {pct:.2f}% |\n")
            
        f.write("\n## E25 Sizing Diagnostics\n\n")
        f.write(f"- **Mean Sizing Factor**: {avg_sizing:.4f}\n")
        f.write(f"- **Minimum Sizing Factor**: {min_sizing:.4f}\n\n")
        f.write("| Sizing Reason | Trade Count | % of Total |\n")
        f.write("|---|---|---|\n")
        for reason, count in sizing_counts.items():
            pct = (count / len(df_trades)) * 100
            f.write(f"| '{reason or 'no_reduction'}' | {count} | {pct:.2f}% |\n")

    print(f"\nSummary validation file generated successfully at {summary_path}")

if __name__ == "__main__":
    main()
