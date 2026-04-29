import pandas as pd
import json
import os
from glob import glob
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.columns import Columns
from rich.text import Text
from datetime import datetime

console = Console()


def get_latest_files():
    csv_files = glob("outputs/paper_trading/watchlist_alerts_*.csv")
    json_files = glob("outputs/paper_trading/pre_report_*.json")
    if not csv_files or not json_files:
        return None, None
    return max(csv_files, key=os.path.getmtime), max(json_files, key=os.path.getmtime)


def format_regime(val):
    return "PASS" if val else "FAIL"


def run_tui():
    csv_path, json_path = get_latest_files()

    if not csv_path:
        console.print(
            "[red]No se encontraron archivos de resultados en outputs/paper_trading/[/red]"
        )
        return

    # Cargar datos
    with open(json_path, "r") as f:
        report = json.load(f)

    df = pd.read_csv(csv_path)

    # --- HEADER ---
    date_str = report.get("date", datetime.now().strftime("%Y-%m-%d"))
    console.print(
        Panel(
            f"[bold cyan]MOMENTUM V2 - PAPER TRADING DASHBOARD[/bold cyan]\n[yellow]Fecha: {date_str}[/yellow]",
            expand=False,
        )
    )

    # --- REGIME & STATUS ---
    regime = report.get("market_regime") or report.get("regime", {})
    status_text = Text()
    status_text.append("ESTADO DEL MERCADO: ", style="bold white")
    regime_pass = regime.get("effective_pass", regime.get("effective_regime_ok", False))
    status_text.append(
        format_regime(regime_pass), style="bold green" if regime_pass else "bold red"
    )
    status_text.append(
        f"  |  SPY: ${regime.get('spy_price', 0):.2f} (SMA50: ${regime.get('spy_sma50', 0):.2f})",
        style="dim",
    )
    status_text.append(
        f"  |  VIX: {regime.get('vix_value', regime.get('vix', 0)):.2f}",
        style="dim text",
    )

    console.print(Panel(status_text, title="Resumen Operativo"))

    # --- STRATEGY WARNINGS ---
    strategies = report.get("strategies", {})
    for strat, data in strategies.items():
        if not data.get("approved", False):
            warnings = "\n".join([f"• {r}" for r in data.get("rejection_reasons", [])])
            console.print(
                Panel(
                    f"[yellow]{warnings}[/yellow]",
                    title=f"⚠️ Alerta Estrategia: {strat}",
                    border_style="yellow",
                )
            )

    # --- WATCHLIST TABLE ---
    table = Table(
        title=f"Top Candidatos (Watchlist)",
        title_style="bold magenta",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Ticker", justify="left", style="bold yellow")
    table.add_column("Prox Score", justify="right")
    table.add_column("Blocks", justify="center")
    table.add_column("Faltante / Motivo", justify="left", ratio=1)
    table.add_column("Price", justify="right")
    table.add_column("RVOL", justify="right")

    # Identificar nombres de columnas reales
    col_n_block = (
        "n_blockers"
        if "n_blockers" in df.columns
        else ("n_block" if "n_block" in df.columns else None)
    )
    col_fails = (
        "blockers"
        if "blockers" in df.columns
        else ("failed_checks" if "failed_checks" in df.columns else None)
    )

    if col_n_block:
        top_candidates = df.sort_values(by=[col_n_block, "proximity_score"]).head(15)
    else:
        top_candidates = df.sort_values(by=["proximity_score"]).head(15)

    for _, row in top_candidates.iterrows():
        # Limpiar el string de fallos para que sea legible
        raw_fails = str(row[col_fails]) if col_fails else "N/A"
        fails = raw_fails.replace("[", "").replace("]", "").replace("'", "")

        n_block_val = str(int(row[col_n_block])) if col_n_block else "0"

        table.add_row(
            row["ticker"],
            f"{row['proximity_score']:.2f}",
            n_block_val,
            fails,
            f"${row.get('close', 0):.2f}",
            f"{row.get('rvol', 0):.2f}",
        )

    console.print(table)
    console.print(
        f"\n[dim]Archivos fuente: {os.path.basename(json_path)} | {os.path.basename(csv_path)}[/dim]"
    )


if __name__ == "__main__":
    run_tui()
