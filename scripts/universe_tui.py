#!/usr/bin/env python3
"""
Universe TUI Viewer - Navegador completo del universo con métricas y filtrado.
"""

import argparse
import pandas as pd
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from glob import glob

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align

ROOT = Path(__file__).parent.parent
PAPER_DIR = ROOT / "outputs" / "paper_trading"
console = Console()


def get_latest_files(target_date=None):
    if target_date:
        csv_pattern = f"watchlist_alerts_{target_date}.csv"
        json_pattern = f"pre_report_{target_date}.json"
        csv_files = glob(str(PAPER_DIR / csv_pattern))
        json_files = glob(str(PAPER_DIR / json_pattern))
    else:
        csv_files = glob(str(PAPER_DIR / "watchlist_alerts_*.csv"))
        json_files = glob(str(PAPER_DIR / "pre_report_*.json"))

    if not csv_files or not json_files:
        # Fallback a buscar el más reciente si no hay fecha específica
        csv_files = glob(str(PAPER_DIR / "watchlist_alerts_*.csv"))
        json_files = glob(str(PAPER_DIR / "pre_report_*.json"))

    if not csv_files or not json_files:
        return None, None

    return max(csv_files, key=os.path.getmtime), max(json_files, key=os.path.getmtime)


def generate_layout(limit: int, target_date: str = None):
    csv_path, json_path = get_latest_files(target_date)

    if not csv_path:
        return [
            Panel(
                "[red]No se encontraron archivos de resultados en outputs/paper_trading/.[/red]"
            )
        ]

    # Cargar datos
    try:
        with open(json_path, "r") as f:
            report = json.load(f)
        df = pd.read_csv(csv_path)
    except Exception as e:
        return [Panel(f"[red]Error cargando datos: {e}[/red]")]

    # --- HEADER ---
    date_str = report.get("date", "N/A")
    header = Panel(
        Align.center(
            Text.assemble(
                ("📊 FULL UNIVERSE EXPLORER: ", "bold cyan"), (date_str, "bold yellow")
            )
        ),
        style="bold white",
    )

    # --- REGIME & STATUS ---
    regime = report.get("market_regime") or report.get("regime", {})
    status_text = Text()
    status_text.append("MERCADO: ", style="bold white")
    pass_val = regime.get("effective_pass", regime.get("effective_regime_ok", False))
    status_text.append(
        "PASS" if pass_val else "FAIL", style="bold green" if pass_val else "bold red"
    )
    status_text.append(
        f"  |  SPY: ${regime.get('spy_price', 0):.2f} (SMA50: ${regime.get('spy_sma50', 0):.2f})",
        style="dim",
    )
    status_text.append(
        f"  |  VIX: {regime.get('vix_value', regime.get('vix', 0)):.2f}", style="dim"
    )

    status_panel = Panel(status_text, border_style="blue", title="Estado del Mercado")

    # --- TABLE ---
    table = Table(
        show_header=True,
        header_style="bold cyan",
        expand=True,
        title="Métricas del Universo",
    )
    table.add_column("Ticker", style="bold yellow", width=12)
    table.add_column("Prox Score", justify="right")
    table.add_column("Blk", justify="center")
    table.add_column("Motivos de Bloqueo / Faltantes", ratio=1)
    table.add_column("Precio", justify="right")
    table.add_column("RVOL", justify="right")
    table.add_column("ADR", justify="right")
    table.add_column("RS %", justify="right")

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

    # Ordenar por bloques (menos bloques primero) y luego por proximidad
    if col_n_block:
        df_sorted = df.sort_values(by=[col_n_block, "proximity_score"]).head(limit)
    else:
        df_sorted = df.sort_values(by=["proximity_score"]).head(limit)

    for _, row in df_sorted.iterrows():
        raw_fails = str(row.get(col_fails, "N/A"))
        fails = raw_fails.replace("[", "").replace("]", "").replace("'", "")

        # Color según bloques
        n_blks = int(row.get(col_n_block, 0)) if col_n_block else 0
        blk_color = "green" if n_blks == 0 else ("yellow" if n_blks == 1 else "red")

        table.add_row(
            row["ticker"],
            f"{row.get('proximity_score', 0):.2f}",
            Text(str(n_blks), style=f"bold {blk_color}"),
            fails,
            f"${row.get('close', 0):.2f}",
            f"{row.get('rvol', 0):.2f}",
            f"{row.get('adr', 0):.2f}",
            f"{row.get('rs_pct', 0):.1f}%",
        )

    footer = Text(
        f"\nFuente: {os.path.basename(csv_path)} | Mostrando {len(df_sorted)} de {len(df)} tickers.",
        style="dim italic",
    )

    return [header, status_panel, table, footer]


def main():
    parser = argparse.ArgumentParser(description="Universe TUI Explorer")
    parser.add_argument("--date", type=str, default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=40, help="Max tickers to show")
    parser.add_argument("--watch", action="store_true", help="Watch mode")
    args = parser.parse_args()

    if args.watch:
        with Live(auto_refresh=False) as live:
            from rich.console import Group

            while True:
                renderables = generate_layout(args.limit, args.date)
                live.update(Group(*renderables), refresh=True)
                time.sleep(10)
    else:
        renderables = generate_layout(args.limit, args.date)
        for r in renderables:
            console.print(r)


if __name__ == "__main__":
    main()
