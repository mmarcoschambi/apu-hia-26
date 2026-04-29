#!/usr/bin/env python3
"""
send_signal_alerts.py - Genera alertas legible desde señales de run_combo_scanner.

Uso:
    # Todas las señales del día, consola
    python3 scripts/send_signal_alerts.py --date 2026-04-24

    # Top 10 por score, consola
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --top 10

    # Solo ciertos agentes
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --agents combo_pure_momentum combo_pullback_entry

    # Solo ciertos tickers
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --tickers NVDA TSLA

    # Min score threshold
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --min-score 0.7

    # Exportar a markdown
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --export-md

    # Solo mostrar resumen (sin detalle de cada ticker)
    python3 scripts/send_signal_alerts.py --date 2026-04-24 --summary-only
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()


def telegram_send(text: str) -> bool:
    import httpx
    import html

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados en .env")
        return False

    text = html.escape(text)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram tiene límite de 4096 chars por mensaje
    chunks = [text[i : i + 4000] for i in range(0, len(text), 4000)]
    success = True
    try:
        with httpx.Client() as client:
            for chunk in chunks:
                r = client.post(
                    url,
                    json={"chat_id": chat_id, "text": f"<pre>{chunk}</pre>", "parse_mode": "HTML"},
                    timeout=10.0,
                )
                if r.status_code != 200:
                    print(f"❌ Telegram error: {r.text}")
                    success = False
    except Exception as e:
        print(f"❌ Telegram exception: {e}")
        success = False
    return success

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
ALERTS_DIR = PROJECT_ROOT / "outputs" / "alerts"


def load_signals(
    date: str, agents: list[str] | None = None, tickers: list[str] | None = None
) -> pd.DataFrame:
    combined_path = OUTPUT_DIR / date / "combined.csv"
    if not combined_path.exists():
        raise FileNotFoundError(f"signals not found: {combined_path}")

    df = pd.read_csv(combined_path)

    if agents:
        df = df[df["agent_name"].isin(agents)]
    if tickers:
        df = df[df["ticker"].isin(tickers)]

    return df.sort_values("entry_score", ascending=False)


def build_alert_text(
    df: pd.DataFrame,
    date: str,
    min_score: float = 0.0,
    top_n: int = 0,
    summary_only: bool = False,
) -> str:
    sep = "=" * 60
    lines = [
        f"{sep}",
        f"  SIGNAL ALERTS  |  {date}",
        f"{sep}",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Total signals: {len(df)}  |  Unique tickers: {df['ticker'].nunique()}",
        f"  Agents: {sorted(df['agent_name'].unique())}",
        f"{sep}",
    ]

    if df.empty:
        lines.append("  ⚠ No signals match criteria")
        return "\n".join(lines)

    df = df[df["entry_score"] >= min_score]

    # Summary por agente
    lines.append("\n  AGENTS SUMMARY:")
    for agent, grp in df.groupby("agent_name"):
        lines.append(
            f"    {agent:<35} {len(grp):>3} signals  (top: {grp['entry_score'].max():.3f})"
        )

    if summary_only:
        return "\n".join(lines)

    # Tabla principal
    if top_n > 0:
        df_show = df.head(top_n)
        note = f"  (showing top {top_n} of {len(df)} filtered)"
    else:
        df_show = df
        note = ""

    lines.append(f"\n  SIGNAL TABLE{note if note else ''}:")
    lines.append(
        f"  {'Ticker':<8} {'Agent':<28} {'Score':<8} {'Price':<10} {'RVOL':<7} {'ADR%':<7} {'Dist%':<7} {'Tier2'}"
    )
    lines.append(
        f"  {'-' * 7} {'-' * 27} {'-' * 7} {'-' * 9} {'-' * 6} {'-' * 6} {'-' * 6} {'-' * 20}"
    )

    for _, row in df_show.iterrows():
        tier2 = str(row.get("tier2_filter", "passed"))[:20]
        price = row.get("entry_price", 0)
        lines.append(
            f"  {row['ticker']:<8} {row['agent_name']:<28} "
            f"{row['entry_score']:<8.3f} "
            f"{price:<10.2f} "
            f"{row.get('rvol', 0):<7.2f} "
            f"{row.get('adr_pct', 0):<7.2f} "
            f"{row.get('dist_sma20', 0):<7.2f} "
            f"{tier2}"
        )

    if top_n > 0 and len(df) > top_n:
        lines.append(f"\n  ... and {len(df) - top_n} more (use --top N to see more)")

    # Operables: candidatos claros
    high_score = df[df["entry_score"] >= 0.7]
    if not high_score.empty:
        lines.append("\n  TOP CANDIDATES (score >= 0.7):")
        for _, row in high_score.iterrows():
            price = row.get("entry_price", 0)
            lines.append(
                f"    ★ {row['ticker']}  score={row['entry_score']:.3f}  "
                f"price=${price:.2f}  rvol={row.get('rvol', 0):.1f}x  "
                f"dv={row.get('dollar_vol_M', 0):.0f}M"
            )

    lines.append(f"\n{sep}")

    return "\n".join(lines)


def export_md(df: pd.DataFrame, date: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"alerts_{date}.md"

    lines = [
        f"# Signal Alerts — {date}",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Total signals:** {len(df)} | **Tickers:** {df['ticker'].nunique()} | **Agents:** {len(df['agent_name'].unique())}",
        "",
        "## Summary by Agent",
        "",
    ]

    for agent, grp in df.groupby("agent_name"):
        lines.append(f"### {agent}")
        lines.append(f"- Signals: {len(grp)}")
        lines.append(f"- Top score: {grp['entry_score'].max():.3f}")
        lines.append(f"- Tickers: {', '.join(grp['ticker'].tolist())}")
        lines.append("")

    lines.append("## All Signals")
    lines.append("")
    lines.append(
        "| Ticker | Agent | Score | Price | RVOL | ADR% | Dist% | Tier2 Filter |"
    )
    lines.append(
        "|--------|-------|-------|-------|------|------|-------|--------------|"
    )

    for _, row in df.iterrows():
        lines.append(
            f"| {row['ticker']} | {row['agent_name']} | {row['entry_score']:.3f} | "
            f"{row.get('entry_price', 0):.2f} | {row.get('rvol', 0):.2f} | "
            f"{row.get('adr_pct', 0):.2f} | {row.get('dist_sma20', 0):.2f} | "
            f"{row.get('tier2_filter', 'passed')} |"
        )

    path.write_text("\n".join(lines))
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate signal alerts")
    parser.add_argument("--date", type=str, default=None, help="Scan date (YYYY-MM-DD)")
    parser.add_argument("--agents", nargs="+", help="Filter by agent names")
    parser.add_argument("--tickers", nargs="+", help="Filter by tickers")
    parser.add_argument(
        "--min-score", type=float, default=0.0, help="Min entry_score filter"
    )
    parser.add_argument("--top", type=int, default=0, help="Show only top N signals")
    parser.add_argument(
        "--summary-only", action="store_true", help="Show only agent summary"
    )
    parser.add_argument(
        "--export-md", action="store_true", help="Export to markdown file"
    )
    parser.add_argument(
        "--telegram", action="store_true", help="Send alert via Telegram"
    )
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    try:
        df = load_signals(date, agents=args.agents, tickers=args.tickers)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    text = build_alert_text(
        df,
        date,
        min_score=args.min_score,
        top_n=args.top,
        summary_only=args.summary_only,
    )
    print(text)

    if args.export_md:
        path = export_md(df, date, ALERTS_DIR)
        print(f"\n  📄 Alert exported to: {path}")

    if args.telegram:
        ok = telegram_send(text)
        print(f"  Telegram: {'✓ enviado' if ok else '✗ error'}")


if __name__ == "__main__":
    main()
