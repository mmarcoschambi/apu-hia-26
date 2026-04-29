#!/usr/bin/env python3
"""
paper_report.py - Reporte de performance para runs paper.

Uso:
    python3 scripts/paper_report.py --date 2026-04-24
    python3 scripts/paper_report.py --date 2026-04-24 --export-json
    python3 scripts/paper_report.py --all
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "outputs" / "paper_trading" / "runs"


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def build_report(date: str) -> dict:
    run_dir = RUNS_DIR / date
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    positions_path = run_dir / "positions.csv"
    equity_path = run_dir / "equity_curve.csv"
    summary_path = run_dir / "run_report.json"

    if (
        not positions_path.exists()
        or not equity_path.exists()
        or not summary_path.exists()
    ):
        raise FileNotFoundError(f"Missing artifacts in {run_dir}")

    positions = pd.read_csv(positions_path)
    equity = pd.read_csv(equity_path)
    summary = json.loads(summary_path.read_text())

    trades = positions[positions["exited"] == True].copy()  # noqa: E712
    if "realized_pnl" not in trades.columns:
        trades["realized_pnl"] = 0.0
    trades["realized_pnl"] = trades["realized_pnl"].fillna(0.0)

    wins = trades[trades["realized_pnl"] > 0]
    losses = trades[trades["realized_pnl"] < 0]

    gross_profit = float(wins["realized_pnl"].sum()) if not wins.empty else 0.0
    gross_loss = float(losses["realized_pnl"].sum()) if not losses.empty else 0.0
    realized_net_pnl = float(trades["realized_pnl"].sum()) if not trades.empty else 0.0
    run_net_pnl = float(summary.get("pnl", realized_net_pnl))
    n_trades = int(len(trades))

    win_rate = float(len(wins) / n_trades * 100) if n_trades > 0 else 0.0
    profit_factor = (
        float(gross_profit / abs(gross_loss))
        if gross_loss < 0
        else (999.0 if gross_profit > 0 else 0.0)
    )
    expectancy = float(realized_net_pnl / n_trades) if n_trades > 0 else 0.0

    eq_series = (
        equity["equity"] if "equity" in equity.columns else pd.Series(dtype=float)
    )
    max_dd = _max_drawdown(eq_series)

    by_agent = {}
    if "agent" in trades.columns:
        for agent, grp in trades.groupby("agent"):
            agent_pnl = float(grp["realized_pnl"].sum())
            agent_trades = int(len(grp))
            agent_win = int((grp["realized_pnl"] > 0).sum())
            by_agent[agent] = {
                "trades": agent_trades,
                "pnl": round(agent_pnl, 2),
                "win_rate_pct": round(
                    (agent_win / agent_trades * 100) if agent_trades else 0.0, 2
                ),
            }

    return {
        "date": date,
        "starting_capital": summary.get("starting_capital", 0.0),
        "ending_capital": summary.get("ending_capital", 0.0),
        "net_pnl": round(run_net_pnl, 2),
        "realized_pnl_positions": round(realized_net_pnl, 2),
        "orders": summary.get("orders_count", 0),
        "fills": summary.get("fills_count", 0),
        "trades": n_trades,
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3),
        "expectancy": round(expectancy, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "by_agent": by_agent,
    }


def print_report(report: dict) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  PAPER REPORT  |  {report['date']}")
    print(f"{sep}")
    print(f"  Start capital:     ${report['starting_capital']:,.2f}")
    print(f"  End capital:       ${report['ending_capital']:,.2f}")
    print(f"  Net P&L (run):     ${report['net_pnl']:,.2f}")
    print(f"  Realized P&L:      ${report['realized_pnl_positions']:,.2f}")
    print(
        f"  Trades:            {report['trades']}  (wins={report['wins']} losses={report['losses']})"
    )
    print(f"  Win rate:          {report['win_rate_pct']:.2f}%")
    print(f"  Profit factor:     {report['profit_factor']:.3f}")
    print(f"  Expectancy/trade:  ${report['expectancy']:.2f}")
    print(f"  Max drawdown:      {report['max_drawdown_pct']:.2f}%")
    print(f"{sep}")

    if report["by_agent"]:
        print("  By Agent:")
        for agent, vals in report["by_agent"].items():
            print(
                f"    {agent:<30} trades={vals['trades']:<3} "
                f"pnl=${vals['pnl']:<10.2f} win={vals['win_rate_pct']:.1f}%"
            )
        print(sep)


def aggregate_reports() -> dict:
    if not RUNS_DIR.exists():
        raise FileNotFoundError(f"Runs directory not found: {RUNS_DIR}")

    dates = sorted([p.name for p in RUNS_DIR.iterdir() if p.is_dir()])
    if not dates:
        return {"runs": 0}

    reports = [build_report(d) for d in dates]
    total_pnl = sum(r["net_pnl"] for r in reports)
    total_trades = sum(r["trades"] for r in reports)
    avg_win_rate = sum(r["win_rate_pct"] for r in reports) / len(reports)

    return {
        "runs": len(reports),
        "first_date": dates[0],
        "last_date": dates[-1],
        "total_pnl": round(total_pnl, 2),
        "total_trades": total_trades,
        "avg_win_rate_pct": round(avg_win_rate, 2),
        "dates": dates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper trading performance report")
    parser.add_argument("--date", type=str, help="Date for single report (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Aggregate all run dates")
    parser.add_argument("--export-json", action="store_true", help="Export report json")
    args = parser.parse_args()

    if args.all:
        agg = aggregate_reports()
        print("\nAggregate Paper Report")
        print(json.dumps(agg, indent=2))
        return

    if not args.date:
        print("❌ Provide --date or --all")
        sys.exit(1)

    report = build_report(args.date)
    print_report(report)

    if args.export_json:
        out = RUNS_DIR / args.date / "performance_report.json"
        out.write_text(json.dumps(report, indent=2))
        print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
