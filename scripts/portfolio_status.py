#!/usr/bin/env python3
"""
portfolio_status.py - Consolida el estado del paper portfolio.

Lee `outputs/paper_trading/runs/*/positions.csv`, reconstruye métricas de
performance y, si corresponde, manda una alerta por Telegram.

Usage:
    python3 scripts/portfolio_status.py
    python3 scripts/portfolio_status.py --since 2025-04-01
    python3 scripts/portfolio_status.py --telegram
"""

from __future__ import annotations

import argparse
import importlib.util
import html
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "outputs" / "paper_trading" / "runs"
OUT_DIR = PROJECT_ROOT / "outputs" / "portfolio_status"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()
from src.utils.telegram_client import telegram_send
from src.utils.telegram_client import telegram_send


@dataclass
class PortfolioMetrics:
    generated_at: str
    starting_capital: float
    ending_capital: float
    total_pnl: float
    total_trades: int
    total_partial_exits: int
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    equity_curve: list[float]
    trade_dates: list[str]
    wf_min_profit_factor: float
    wf_max_drawdown_pct: float
    dd_alert_triggered: bool
    since: str | None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _safe_date(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).normalize()
    except Exception:
        return None


def _load_run_report(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_report.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def _load_positions(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "positions.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    df["_run_date"] = run_dir.name
    return df

def _load_fills(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "fills.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    df["_run_date"] = run_dir.name
    return df


def _load_equity_curve(run_dir: Path) -> pd.DataFrame:
    path = run_dir / "equity_curve.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (pd.errors.EmptyDataError, Exception):
        return pd.DataFrame()


def _load_paper_report_module():
    path = PROJECT_ROOT / "scripts" / "paper_report.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("paper_report_mod", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _portfolio_from_report(report: dict[str, Any]) -> PortfolioMetrics:
    starting_capital = _safe_float(report.get("starting_capital", 100000), 100000.0)
    ending_capital = _safe_float(
        report.get("ending_capital", starting_capital), starting_capital
    )
    total_pnl = _safe_float(
        report.get("net_pnl", ending_capital - starting_capital), 0.0
    )
    total_trades = int(report.get("trades", 0))
    wins = int(report.get("wins", 0))
    losses = int(report.get("losses", 0))
    win_rate_pct = _safe_float(report.get("win_rate_pct", 0.0), 0.0)
    profit_factor = _safe_float(report.get("profit_factor", 0.0), 0.0)
    max_dd = _safe_float(report.get("max_drawdown_pct", 0.0), 0.0)

    return PortfolioMetrics(
        generated_at=datetime.now().isoformat(),
        starting_capital=starting_capital,
        ending_capital=ending_capital,
        total_pnl=total_pnl,
        total_trades=total_trades,
        total_partial_exits=int(report.get("total_partial_exits", 0)),
        wins=wins,
        losses=losses,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        max_drawdown_pct=max_dd,
        equity_curve=[starting_capital, ending_capital],
        trade_dates=[],
        wf_min_profit_factor=_safe_float(
            os.getenv("WF_MIN_PROFIT_FACTOR", "1.40"), 1.40
        ),
        wf_max_drawdown_pct=_safe_float(os.getenv("MAX_DD_ALERT_PCT", "33"), 33.0),
        dd_alert_triggered=max_dd
        > _safe_float(os.getenv("MAX_DD_ALERT_PCT", "33"), 33.0),
        since=None,
    )


def _collect_positions(
    since: str | None = None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame]:
    if not RUNS_DIR.exists():
        return pd.DataFrame(), [], pd.DataFrame()

    run_dirs = sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()])
    frames: list[pd.DataFrame] = []
    fill_frames: list[pd.DataFrame] = []
    run_reports: list[dict[str, Any]] = []

    since_ts = _safe_date(since) if since else None

    for run_dir in run_dirs:
        df = _load_positions(run_dir)
        fills = _load_fills(run_dir)
        if df.empty:
            continue
            
        if not fills.empty:
            fill_frames.append(fills)

        report = _load_run_report(run_dir)
        if report:
            report["run_dir"] = run_dir.name
            run_reports.append(report)

        if "exited" in df.columns:
            closed_mask = df["exited"].map(_to_bool)
            if closed_mask.any():
                df = df[closed_mask]
        elif "exit_date" in df.columns:
            closed_mask = pd.to_datetime(df["exit_date"], errors="coerce").notna()
            if closed_mask.any():
                df = df[closed_mask]

        if since_ts is not None:
            date_cols = []
            for col in ("exit_date", "entry_date", "signal_date"):
                if col in df.columns:
                    date_cols.append(col)
            if date_cols:
                mask = pd.Series(False, index=df.index)
                for col in date_cols:
                    parsed = pd.to_datetime(df[col], errors="coerce")
                    mask = mask | (parsed >= since_ts)
                df = df[mask]

        if not df.empty:
            frames.append(df)

    all_fills = pd.concat(fill_frames, ignore_index=True) if fill_frames else pd.DataFrame()

    if not frames:
        return pd.DataFrame(), run_reports, all_fills

    return pd.concat(frames, ignore_index=True), run_reports, all_fills


def _normalize_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    if "exited" in out.columns:
        out["exited"] = out["exited"].map(_to_bool)
    else:
        out["exited"] = False

    if "realized_pnl" not in out.columns:
        out["realized_pnl"] = 0.0
    out["realized_pnl"] = (
        out["realized_pnl"].fillna(0.0).map(lambda x: _safe_float(x, 0.0))
    )

    if "size" in out.columns:
        out["size"] = out["size"].fillna(0).map(lambda x: _safe_float(x, 0.0))
    else:
        out["size"] = 0.0

    for col in ("entry_price", "exit_price", "position_value"):
        if col in out.columns:
            out[col] = out[col].fillna(0.0).map(lambda x: _safe_float(x, 0.0))

    out["entry_dt"] = pd.NaT
    if "entry_date" in out.columns:
        out["entry_dt"] = pd.to_datetime(out["entry_date"], errors="coerce")
    elif "signal_date" in out.columns:
        out["entry_dt"] = pd.to_datetime(out["signal_date"], errors="coerce")

    out["exit_dt"] = pd.NaT
    if "exit_date" in out.columns:
        out["exit_dt"] = pd.to_datetime(out["exit_date"], errors="coerce")
    elif "signal_date" in out.columns:
        out["exit_dt"] = pd.to_datetime(out["signal_date"], errors="coerce")

    out["holding_days"] = None
    if "entry_dt" in out.columns and "exit_dt" in out.columns:
        holding = (
            pd.to_datetime(out["exit_dt"], errors="coerce")
            - pd.to_datetime(out["entry_dt"], errors="coerce")
        ).dt.days
        out["holding_days"] = holding

    if "ticker" not in out.columns:
        out["ticker"] = "UNKNOWN"

    if "agent" not in out.columns:
        out["agent"] = out["agent_name"] if "agent_name" in out.columns else "UNKNOWN"
    if "combo" not in out.columns:
        out["combo"] = out["combo_name"] if "combo_name" in out.columns else "UNKNOWN"

    out["is_closed"] = (
        out["exited"] | out["exit_dt"].notna() | (out["realized_pnl"].abs() > 0)
    )
    out["is_open"] = ~out["is_closed"]

    return out


def _compute_metrics(trades: pd.DataFrame, fills: pd.DataFrame = None) -> PortfolioMetrics:
    if fills is None:
        fills = pd.DataFrame()
        
    starting_capital = _safe_float(os.getenv("PAPER_CAPITAL", "100000"), 100000.0)
    wf_min_pf = _safe_float(os.getenv("WF_MIN_PROFIT_FACTOR", "1.40"), 1.40)
    wf_max_dd = _safe_float(os.getenv("MAX_DD_ALERT_PCT", "33"), 33.0)

    if trades.empty:
        return PortfolioMetrics(
            generated_at=datetime.now().isoformat(),
            starting_capital=starting_capital,
            ending_capital=starting_capital,
            total_pnl=0.0,
            total_trades=0,
            total_partial_exits=0,
            wins=0,
            losses=0,
            win_rate_pct=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            equity_curve=[starting_capital],
            trade_dates=[],
            wf_min_profit_factor=wf_min_pf,
            wf_max_drawdown_pct=wf_max_dd,
            dd_alert_triggered=False,
            since=None,
        )

    closed = (
        trades[trades["is_closed"]].copy()
        if "is_closed" in trades.columns
        else trades.copy()
    )
    ordered = closed.copy()
    ordered["_sort_dt"] = pd.to_datetime(
        ordered["exit_dt"].fillna(ordered["entry_dt"]), errors="coerce"
    )
    ordered = ordered.sort_values(["_sort_dt", "ticker"], na_position="last")

    pnls = ordered["realized_pnl"].astype(float).tolist()
    equity = [starting_capital]
    for pnl in pnls:
        equity.append(equity[-1] + float(pnl))

    equity_series = pd.Series(equity, dtype=float)
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak.replace(0, pd.NA)
    max_dd_pct = abs(float(drawdown.min() * 100)) if not drawdown.empty else 0.0

    wins = ordered[ordered["realized_pnl"] > 0]
    losses = ordered[ordered["realized_pnl"] < 0]
    gross_profit = float(wins["realized_pnl"].sum()) if not wins.empty else 0.0
    gross_loss = float(losses["realized_pnl"].sum()) if not losses.empty else 0.0
    if gross_loss < 0:
        profit_factor = gross_profit / abs(gross_loss)
    else:
        profit_factor = 999.0 if gross_profit > 0 else 0.0

    total_trades = int(len(ordered))
    total_partial_exits = len(fills[fills["reason"].isin(["TP1", "TP2"])]) if not fills.empty and "reason" in fills.columns else 0
    
    win_rate_pct = (len(wins) / total_trades * 100.0) if total_trades else 0.0
    ending_capital = float(equity[-1])
    total_pnl = ending_capital - starting_capital
    trade_dates = []
    if "exit_dt" in ordered.columns:
        trade_dates = [str(d.date()) for d in ordered["exit_dt"].dropna()]

    dd_alert = max_dd_pct > wf_max_dd

    return PortfolioMetrics(
        generated_at=datetime.now().isoformat(),
        starting_capital=starting_capital,
        ending_capital=ending_capital,
        total_pnl=total_pnl,
        total_trades=total_trades,
        total_partial_exits=total_partial_exits,
        wins=int(len(wins)),
        losses=int(len(losses)),
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        max_drawdown_pct=max_dd_pct,
        equity_curve=[float(x) for x in equity],
        trade_dates=trade_dates,
        wf_min_profit_factor=wf_min_pf,
        wf_max_drawdown_pct=wf_max_dd,
        dd_alert_triggered=dd_alert,
        since=None,
    )


def _print_table(
    trades: pd.DataFrame, metrics: PortfolioMetrics, since: str | None
) -> None:
    sep = "=" * 72
    print(f"\n{sep}")
    print("  PORTFOLIO STATUS")
    print(f"{sep}")
    print(f"  Generated:        {metrics.generated_at}")
    print(f"  Since:            {since or 'all'}")
    print(f"  Unique Entries:   {metrics.total_trades}")
    print(f"  Partial Exits:    {metrics.total_partial_exits}")
    print(f"  Win rate:         {metrics.win_rate_pct:.2f}%")
    print(f"  Profit factor:    {metrics.profit_factor:.3f}")
    print(f"  Max drawdown:     {metrics.max_drawdown_pct:.2f}%")
    print(f"  Start capital:    ${metrics.starting_capital:,.2f}")
    print(f"  End capital:      ${metrics.ending_capital:,.2f}")
    print(f"  Net P&L:          ${metrics.total_pnl:+,.2f}")
    print(f"  WF threshold PF:  {metrics.wf_min_profit_factor:.2f}")
    print(f"  WF threshold DD:  {metrics.wf_max_drawdown_pct:.2f}%")
    print(f"{sep}")

    closed = trades[trades["is_closed"]] if "is_closed" in trades.columns else trades
    open_positions = (
        trades[trades["is_open"]] if "is_open" in trades.columns else pd.DataFrame()
    )

    if closed.empty:
        print("  No closed trades found.")
        if not open_positions.empty:
            print(f"  Open positions: {len(open_positions)}")
        return

    show_cols = [
        c
        for c in ["ticker", "agent", "combo", "exit_dt", "realized_pnl", "holding_days"]
        if c in trades.columns
    ]
    display = closed.copy()
    if "exit_dt" in display.columns:
        display["exit_dt"] = pd.to_datetime(
            display["exit_dt"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    if "holding_days" in display.columns:
        display["holding_days"] = display["holding_days"].fillna("")

    print(display[show_cols].tail(12).to_string(index=False))

    if not open_positions.empty:
        print("\n  Open positions:")
        open_cols = [
            c
            for c in ["ticker", "agent", "combo", "entry_dt", "size", "entry_price"]
            if c in open_positions.columns
        ]
        if open_cols:
            temp = open_positions.copy()
            if "entry_dt" in temp.columns:
                temp["entry_dt"] = pd.to_datetime(
                    temp["entry_dt"], errors="coerce"
                ).dt.strftime("%Y-%m-%d")
            print(temp[open_cols].tail(12).to_string(index=False))


def build_portfolio_telegram_html(
    metrics: PortfolioMetrics, trades: pd.DataFrame, since: str | None
) -> str:
    """
    Genera un reporte de portfolio visual para Telegram.
    """
    title = "💼 <b>PORTFOLIO STATUS</b>"
    if metrics.dd_alert_triggered:
        title = "⚠️ <b>PORTFOLIO ALERT (DD)</b>"
    elif metrics.profit_factor < metrics.wf_min_profit_factor:
        title = "📉 <b>PORTFOLIO STATUS (LOW PF)</b>"

    status_icon = "🟢" if not metrics.dd_alert_triggered else "🔴"
    if metrics.profit_factor < metrics.wf_min_profit_factor:
        status_icon = "🟡"

    header = (
        f"{title}\n<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n"
    )
    if since:
        header += f"📅 Since: <code>{since}</code>\n"

    # Core Metrics
    pnl_color = "🟢" if metrics.total_pnl >= 0 else "🔴"
    summary = (
        f"\n{status_icon} <b>Performance Summary:</b>\n"
        f"• Unique Entries: <b>{metrics.total_trades}</b>\n"
        f"• Partial Exits: <b>{metrics.total_partial_exits}</b>\n"
        f"• Win Rate: <b>{metrics.win_rate_pct:.1f}%</b>\n"
        f"• Profit Factor: <b>{metrics.profit_factor:.2f}</b>\n"
        f"• Max DD: <b>{metrics.max_drawdown_pct:.1f}%</b>\n"
        f"• {pnl_color} Net P&L: <b>${metrics.total_pnl:+,.2f}</b>\n"
        f"• Equity: <b>${metrics.ending_capital:,.2f}</b>\n"
    )

    # Open Positions
    open_pos = (
        trades[trades["is_open"].fillna(False)]
        if "is_open" in trades.columns
        else pd.DataFrame()
    )
    open_summary = ""
    if not open_pos.empty:
        open_summary = f"\n📂 <b>Open Positions ({len(open_pos)}):</b>\n"
        # Mostrar top 5 abiertas
        for _, row in open_pos.head(5).iterrows():
            open_summary += f"• <b>{row['ticker']}</b> ({row.get('agent', 'N/A')})\n"
        if len(open_pos) > 5:
            open_summary += f"  <i>... and {len(open_pos) - 5} more</i>\n"
    else:
        open_summary = "\n📂 <b>No open positions</b>\n"

    # Closed trades table (compact)
    closed = (
        trades[trades["is_closed"].fillna(False)]
        if "is_closed" in trades.columns
        else pd.DataFrame()
    )
    table = ""
    if not closed.empty:
        table = "\n📋 <b>LAST CLOSED TRADES:</b>\n"
        table += "<pre>"
        table += f"{'Ticker':<7} {'P&L':>8} {'Days':>4}\n"
        table += f"{'-' * 7} {'-' * 8} {'-' * 4}\n"
        for _, row in closed.tail(8).iterrows():
            pnl = row.get("realized_pnl", 0)
            days = row.get("holding_days", 0)
            table += f"{row['ticker']:<7} {pnl:>8.0f}$ {days:>4.0f}\n"
        table += "</pre>"

    return header + summary + open_summary + table


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio status aggregator")
    parser.add_argument(
        "--date", type=str, default=None, help="Use a single paper report date"
    )
    parser.add_argument(
        "--all", action="store_true", help="Aggregate all paper report dates"
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Only include trades from YYYY-MM-DD onward",
    )
    parser.add_argument(
        "--telegram", action="store_true", help="Send summary/alert via Telegram"
    )
    parser.add_argument("--json-only", action="store_true", help="Skip table output")
    args = parser.parse_args()

    paper_report = _load_paper_report_module()

    if paper_report is not None and args.all:
        agg = paper_report.aggregate_reports()
        print(json.dumps(agg, indent=2))
        return

    if paper_report is not None and args.date:
        try:
            report = paper_report.build_report(args.date)
            metrics = _portfolio_from_report(report)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = (
                OUT_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_check.json"
            )
            payload = asdict(metrics)
            payload["source"] = "scripts/paper_report.py"
            payload["report_date"] = args.date
            out_path.write_text(json.dumps(payload, indent=2, default=str))
            if not args.json_only:
                print(f"\n{'=' * 72}")
                print("  PORTFOLIO STATUS")
                print(f"{'=' * 72}")
                print(f"  Date:             {args.date}")
                print(f"  Trades:           {metrics.total_trades}")
                print(f"  Win rate:         {metrics.win_rate_pct:.2f}%")
                print(f"  Profit factor:    {metrics.profit_factor:.3f}")
                print(f"  Max drawdown:     {metrics.max_drawdown_pct:.2f}%")
                print(f"  Net P&L:          ${metrics.total_pnl:+,.2f}")
                print(f"\nSaved: {out_path}")
            if args.telegram:
                html_msg = build_portfolio_telegram_html(
                    metrics, pd.DataFrame(), args.date
                )
                ok = telegram_send(html_msg)
                print(f"Telegram: {'sent' if ok else 'failed'}")
            return
        except Exception as exc:
            print(f"⚠ paper_report fallback failed: {exc}")

    trades, run_reports, all_fills = _collect_positions(since=args.since)
    trades = _normalize_trades(trades)
    metrics = _compute_metrics(trades, fills=all_fills)
    metrics.since = args.since

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_check.json"
    payload = asdict(metrics)
    payload["runs_seen"] = len(run_reports)
    payload["trades_rows"] = int(len(trades))
    payload["source"] = "outputs/paper_trading/runs"
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    if not args.json_only:
        _print_table(trades, metrics, args.since)
        print(f"\nSaved: {out_path}")

    if args.telegram:
        msg = build_portfolio_telegram_html(metrics, trades, args.since)
        ok = telegram_send(msg)
        print(f"Telegram: {'sent' if ok else 'failed'}")


if __name__ == "__main__":
    main()
