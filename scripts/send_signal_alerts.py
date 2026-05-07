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
import ast
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()
from src.utils.telegram_client import telegram_send as shared_telegram_send
from src.utils.telegram_client import telegram_send_html

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
ALERTS_DIR = PROJECT_ROOT / "outputs" / "alerts"
SENT_DIR = PROJECT_ROOT / "outputs" / "telegram_alerts"

logger = logging.getLogger(__name__)


def _flatten_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    tier2_metrics y tier1_metrics se guardan como string de dict Python en el CSV.
    Esta función los parsea y aplana como columnas directas en el DataFrame,
    sin pisar columnas ya existentes.

    Ejemplo antes:  row['rvol'] -> KeyError  (no existe)
    Ejemplo después: row['rvol'] -> 1.33  (aplanado desde tier2_metrics)
    """
    for col in ("tier2_metrics", "tier1_metrics"):
        if col not in df.columns:
            continue
        parsed_rows = []
        for val in df[col]:
            if pd.isna(val) or val == "" or val is None:
                parsed_rows.append({})
                continue
            try:
                parsed_rows.append(ast.literal_eval(str(val)))
            except Exception:
                parsed_rows.append({})

        flat = pd.DataFrame(parsed_rows, index=df.index)
        # Solo agregar columnas que no existan ya para no pisar entry_price, etc.
        new_cols = [c for c in flat.columns if c not in df.columns]
        df = pd.concat([df, flat[new_cols]], axis=1)

    return df


def load_signals(
    date: str, agents: list[str] | None = None, tickers: list[str] | None = None
) -> pd.DataFrame:
    combined_path = OUTPUT_DIR / date / "combined.csv"
    if not combined_path.exists():
        # Retornar DF vacio con columnas minimas esperadas
        return pd.DataFrame(columns=[
            "ticker", "agent_name", "entry_score", "entry_price", 
            "stop_loss", "rvol", "dollar_vol_M"
        ])

    try:
        df = pd.read_csv(combined_path)
        df = _flatten_metrics(df)
    except Exception:
        return pd.DataFrame(columns=["ticker", "agent_name", "entry_score"])

    # Normalizar entry_score
    if "entry_score" not in df.columns:
        df["entry_score"] = 0.5
    else:
        df["entry_score"] = pd.to_numeric(df["entry_score"], errors='coerce').fillna(0.5)

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
        f"  Total signals: {len(df)}  |  Unique tickers: {df['ticker'].nunique() if not df.empty else 0}",
        f"  Agents: {sorted(df['agent_name'].unique()) if not df.empty else 'none'}",
        f"{sep}",
    ]

    if df.empty:
        lines.append("  No signals match criteria")
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


def build_telegram_html(
    df: pd.DataFrame,
    date: str,
    min_score: float = 0.0,
    top_n: int = 0,
    summary_only: bool = False,
) -> str:
    """
    Genera un mensaje formateado en HTML para Telegram, más visual que el texto plano.
    """
    import html

    # Header
    title = f"🚀 <b>SIGNAL ALERTS | {date}</b>"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"{title}\n<i>Generated: {timestamp}</i>\n"

    if df.empty:
        return f"{header}\n⚠️ <b>No signals match criteria</b>"

    df_filtered = df[df["entry_score"] >= min_score]
    if df_filtered.empty:
        return f"{header}\n⚠️ <b>No signals above score {min_score}</b>"

    # Market Regime (usando el primer registro como referencia del SPY)
    spy_above = df_filtered.iloc[0].get("spy_above_sma200", None)
    spy_status = ""
    if spy_above is not None:
        if bool(spy_above):
            spy_status = "🟢 <b>Market Bullish</b> (SPY > SMA200)"
        else:
            spy_status = "🔴 <b>Market Bearish</b> (SPY < SMA200)"

    # Stats
    total = len(df_filtered)
    unique = df_filtered["ticker"].nunique()
    source = "Local DB"
    if "finviz" in str(OUTPUT_DIR).lower():
        source = "Finviz"

    stats = (
        f"\n📊 <b>Stats:</b>\n"
        f"• Total signals: {total}\n"
        f"• Unique tickers: {unique}\n"
        f"• Source: <code>{source}</code>\n"
    )
    if spy_status:
        stats += f"• {spy_status}\n"

    # Agents Summary
    agents_summary = "\n🤖 <b>Agents:</b>\n"
    for agent, grp in df_filtered.groupby("agent_name"):
        agents_summary += (
            f"• <code>{agent}</code>: {len(grp)} signals "
            f"(top: {grp['entry_score'].max():.3f})\n"
        )

    if summary_only:
        return header + stats + agents_summary

    # Top Candidates (con emojis y negritas)
    high_score = df_filtered[df_filtered["entry_score"] >= 0.7].head(5)
    top_candidates = ""
    if not high_score.empty:
        top_candidates = "\n🔥 <b>TOP CANDIDATES:</b>\n"
        for _, row in high_score.iterrows():
            price = row.get("entry_price", 0)
            ticker = row["ticker"]
            top_candidates += (
                f"⭐ <b>{ticker}</b> (Score: {row['entry_score']:.3f})\n"
                f"   Price: ${price:.2f} | RVOL: {row.get('rvol', 0):.1f}x | "
                f"DV: {row.get('dollar_vol_M', 0):.0f}M\n"
            )

    # Signal Table (Monospaced para alineación)
    if top_n > 0:
        df_show = df_filtered.head(top_n)
    else:
        df_show = df_filtered.head(15)  # Evitar mensajes gigantes

    table_header = "\n📋 <b>SIGNAL TABLE:</b>\n"
    table_content = "<pre>"
    table_content += f"{'Ticker':<7} {'Score':<6} {'Price':<8} {'RVOL':<4}\n"
    table_content += f"{'-' * 7} {'-' * 6} {'-' * 8} {'-' * 4}\n"

    for _, row in df_show.iterrows():
        table_content += (
            f"{row['ticker']:<7} "
            f"{row['entry_score']:<6.3f} "
            f"{row.get('entry_price', 0):<8.2f} "
            f"{row.get('rvol', 0):<4.1f}\n"
        )
    table_content += "</pre>"

    # Footer con link a Finviz del primero
    footer = ""
    if not df_filtered.empty:
        first_ticker = df_filtered.iloc[0]["ticker"]
        footer = f"\n🔗 <a href='https://finviz.com/quote.ashx?t={first_ticker}'>View {first_ticker} on Finviz</a>"

    return (
        header
        + stats
        + agents_summary
        + top_candidates
        + table_header
        + table_content
        + footer
    )


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


def _is_already_sent(date: str, mode: str) -> bool:
    marker = SENT_DIR / date / f"sent_{mode}.json"
    return marker.exists()


def _mark_sent(date: str, mode: str, count: int) -> None:
    marker_dir = SENT_DIR / date
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / f"sent_{mode}.json"
    payload = {
        "date": date,
        "mode": mode,
        "sent_at": datetime.now().isoformat(),
        "signal_count": count,
    }
    marker.write_text(json.dumps(payload, indent=2))


def _save_snapshot(
    date: str,
    df: pd.DataFrame,
    top_candidates: list[dict],
    agents: list[str],
    top_n: int,
    min_score: float,
) -> Path:
    day_dir = SENT_DIR / date
    day_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = day_dir / "snapshot.json"
    snapshot = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "signals_count": len(df),
        "unique_tickers": int(df["ticker"].nunique()) if not df.empty else 0,
        "agents": agents,
        "filters": {"top_n": top_n, "min_score": min_score},
        "top_candidates": top_candidates,
        "signals": df.head(50).to_dict(orient="records") if not df.empty else [],
    }
    snapshot_path.write_text(json.dumps(snapshot, indent=2, default=str))
    return snapshot_path


def _build_top_candidates(df: pd.DataFrame, limit: int = 5) -> list[dict]:
    if df.empty or "entry_score" not in df.columns:
        return []
    
    high = df[df["entry_score"] >= 0.7].head(limit)
    result = []
    for _, row in high.iterrows():
        try:
            result.append(
                {
                    "ticker": row["ticker"],
                    "score": float(row["entry_score"]),
                    "price": float(row.get("entry_price", 0)),
                    "rvol": float(row.get("rvol", 0)),
                    "dv_M": float(row.get("dollar_vol_M", 0)),
                }
            )
        except (ValueError, TypeError):
            continue
    return result


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
    parser.add_argument(
        "--auto-threshold",
        type=float,
        default=0.70,
        help="Min top score required to send the auto summary",
    )
    parser.add_argument(
        "--no-auto", action="store_true", help="Disable auto summary message"
    )
    parser.add_argument(
        "--no-manual", action="store_true", help="Disable manual detail message"
    )
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    df = load_signals(date, agents=args.agents, tickers=args.tickers)

    if df.empty:
        print(f"  No signals found for {date}")
        if args.telegram:
            _save_snapshot(date, df, [], [], args.top, args.min_score)
            _mark_sent(date, "no_signals", 0)
        return

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
        filtered = df[df["entry_score"] >= args.min_score] if not df.empty else df
        agents_list = (
            sorted(filtered["agent_name"].unique().tolist())
            if not filtered.empty
            else []
        )
        top_candidates = _build_top_candidates(filtered)

        snapshot_path = _save_snapshot(
            date, filtered, top_candidates, agents_list, args.top, args.min_score
        )

        if filtered.empty:
            print(f"  No signals for {date}")
            _mark_sent(date, "no_signals", 0)
            print(f"  Snapshot saved: {snapshot_path}")
            return

        top_score = float(filtered["entry_score"].max())
        sent_any = False

        if not args.no_auto and top_score >= args.auto_threshold:
            if _is_already_sent(date, "auto"):
                print(f"  Telegram auto: already sent (idempotent skip)")
            else:
                auto_html = build_telegram_html(
                    filtered,
                    date,
                    min_score=args.auto_threshold,
                    top_n=3,
                    summary_only=False,
                )
                auto_html = auto_html.replace(
                    "🚀 <b>SIGNAL ALERTS |", "🚀 <b>PRE-MARKET AUTO |"
                )
                ok = shared_telegram_send(auto_html)
                sent_any = sent_any or ok
                if ok:
                    _mark_sent(date, "auto", len(filtered))
                    print(f"  Telegram auto: ✓ enviado")
                else:
                    print(f"  Telegram auto: ✗ error")
        elif not args.no_auto:
            print(
                f"  Telegram auto: skipped (top_score={top_score:.3f} < {args.auto_threshold:.2f})"
            )

        if not args.no_manual:
            if _is_already_sent(date, "manual"):
                print(f"  Telegram manual: already sent (idempotent skip)")
            else:
                manual_html = build_telegram_html(
                    filtered,
                    date,
                    min_score=args.min_score,
                    top_n=args.top if args.top > 0 else 15,
                    summary_only=False,
                )
                manual_html = manual_html.replace(
                    "🚀 <b>SIGNAL ALERTS |", "🧭 <b>MANUAL REVIEW |"
                )
                ok = shared_telegram_send(manual_html)
                sent_any = sent_any or ok
                if ok:
                    _mark_sent(date, "manual", len(filtered))
                    print(f"  Telegram manual: ✓ enviado")
                else:
                    print(f"  Telegram manual: ✗ error")

        if not sent_any and not args.no_auto and not args.no_manual:
            print("  Telegram: no new messages sent")

        print(f"  Snapshot saved: {snapshot_path}")


if __name__ == "__main__":
    main()
