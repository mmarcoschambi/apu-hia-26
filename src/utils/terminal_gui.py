import json
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

from src.utils.sector_rotation import SectorRotationAnalyzer

from src.utils.data_quality import calculate_data_quality
from src.utils.gamma_scraper import fetch_gamma_data

console = Console()


def _build_hot_sectors(date_str: str, top_n: int = 5):
    try:
        as_of = pd.Timestamp(date_str)
        start_date = (as_of - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
        end_date = (as_of + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        analyzer = SectorRotationAnalyzer(start_date=start_date, end_date=end_date)
        if not analyzer.load_sector_data():
            return []
        analyzer.calculate_relative_strength()
        if analyzer.sector_strength is None or analyzer.sector_strength.empty:
            return []
        available = analyzer.sector_strength.index[analyzer.sector_strength.index <= as_of]
        if len(available) == 0:
            return []
        rank_date = available[-1]
        rankings = analyzer.rank_sectors_by_strength(rank_date)
    except Exception:
        return []

    items = []
    for sector_etf, info in rankings.items():
        items.append(
            {
                "sector_etf": sector_etf,
                "rank": info.get("rank"),
                "rs": info.get("rs"),
                "strength": info.get("strength"),
                "tradeable": info.get("rank", 999) <= 6 and info.get("rs", 0) > 0,
            }
        )

    items.sort(key=lambda x: x.get("rank", 999))
    return items[:top_n]


def print_terminal_brief(snapshot_path_or_dict, top_n: int = 5, hq_n: int = 5):
    """Muestra un resumen visual 'bonito' en la terminal usando Rich."""
    if isinstance(snapshot_path_or_dict, (str, Path)):
        path = Path(snapshot_path_or_dict)
        if not path.exists():
            console.print(f"[red]Error: Snapshot not found at {path}[/red]")
            return
        with open(path, "r") as f:
            snapshot = json.load(f)
    else:
        snapshot = snapshot_path_or_dict

    date = snapshot.get("date", "n/a")
    regime_ok = snapshot.get("regime_ok", False)
    signals = snapshot.get("signals", [])
    watchlist_scored = snapshot.get("watchlist_scored", {})
    watchlist_detail = snapshot.get("watchlist_detail", {})

    # 1. Header Panel
    regime_str = "[bold green]PASS[/bold green]" if regime_ok else "[bold red]BLOCKED[/bold red]"
    stats_text = Text.assemble(
        ("Date: ", "cyan"),
        (f"{date}\n", "white"),
        ("Regime: ", "cyan"),
        (f"{regime_str}\n", "white"),
        ("Universe: ", "cyan"),
        (f"{snapshot.get('universe_size', 0)}\n", "white"),
        ("Signals: ", "cyan"),
        (f"{len(signals)}", "white"),
    )

    console.print("\n")
    console.print(
        Panel(
            stats_text,
            title="[bold magenta]🚀 MOMENTUM V2 - DAILY BRIEF[/bold magenta]",
            border_style="bright_blue",
            box=box.ROUNDED,
        )
    )

    # 2. Signals Table
    if signals:
        table = Table(
            title="\n[bold fire]🔥 TOP CONFIRMED SIGNALS[/bold fire]",
            box=box.SIMPLE_HEAD,
            title_justify="left",
        )
        table.add_column("Ticker", style="bold yellow")
        table.add_column("Score", justify="center", style="cyan")
        table.add_column("Price", justify="right", style="green")
        table.add_column("Stop", justify="right", style="red")
        table.add_column("TP1 (1.25R)", justify="right", style="bright_green")
        table.add_column("RVOL", justify="right", style="magenta")
        table.add_column("DV (M)", justify="right", style="blue")

        for s in signals[:10]:
            table.add_row(
                s.get("ticker", "?"),
                f"{s.get('score', 0):.1f}",
                f"${s.get('entry_price', 0):.2f}",
                f"${s.get('stop_loss', 0):.2f}",
                f"${s.get('tp1_price', 0):.2f}",
                f"{s.get('rvol', 1.0):.1f}x",
                f"{int(s.get('dollar_volume_m', 0))}M",
            )
        console.print(table)
    else:
        console.print("\n[yellow]No confirmed signals found for today.[/yellow]")

    hot_sectors = _build_hot_sectors(date, top_n=5)
    if hot_sectors:
        console.print("\n[bold cyan]🔥 HOT SECTORS[/bold cyan]")
        hs = Table(box=box.SIMPLE_HEAD, title_justify="left")
        hs.add_column("ETF", style="bold yellow")
        hs.add_column("Rank", justify="right")
        hs.add_column("RS", justify="right")
        hs.add_column("Strength")
        hs.add_column("S1")

        for row in hot_sectors:
            hs.add_row(
                row["sector_etf"],
                str(row.get("rank", "-")),
                f"{row.get('rs', 0):.2%}",
                row.get("strength", "-"),
                "✓" if row.get("tradeable") else "✗",
            )

        console.print(hs)

    # 3. Watchlist
    if watchlist_scored:
        sig_tickers = {s.get("ticker") for s in signals}
        watchlist = [(t, score) for t, score in watchlist_scored.items() if t not in sig_tickers]
        watchlist.sort(key=lambda x: x[1], reverse=True)

        if watchlist:
            console.print("\n[bold cyan]🔭 WATCHLIST (NEAR-ENTRIES - TOP RS)[/bold cyan]")

            # Crear pequeños paneles para los top 12 de la watchlist
            wl_items = []
            for t, score in watchlist[:15]:
                color = "green" if score > 90 else "yellow" if score > 70 else "white"
                wl_items.append(
                    Panel(
                        f"[bold]{t}[/bold]\n[dim]RS:[/dim] [{color}]{int(score)}[/{color}]",
                        box=box.SIMPLE,
                        border_style="dim",
                    )
                )

            console.print(Columns(wl_items))

            if len(watchlist) > 15:
                console.print(
                    f"[dim]...and {len(watchlist) - 15} more candidates in the radar.[/dim]"
                )

    if watchlist_detail:
        console.print("\n[bold cyan]🧪 WATCHLIST DIAGNOSTIC[/bold cyan]")
        diag = Table(box=box.SIMPLE_HEAD, title_justify="left")
        diag.add_column("Ticker", style="bold yellow")
        diag.add_column("RS", justify="right")
        diag.add_column("Breakout")
        diag.add_column("Break lvl")
        diag.add_column("MA Stack")
        diag.add_column("MA trig")
        diag.add_column("RVOL")
        diag.add_column("Dist SMA20")
        diag.add_column("Sector")
        diag.add_column("Waiting")
        diag.add_column("Fails")

        def _fmt_num(value, suffix=""):
            if value is None:
                return "N/A"
            try:
                return f"{float(value):.2f}{suffix}"
            except Exception:
                return "N/A"

        def _style_for_row(data):
            if data.get("breakout") and data.get("ma_stack") and data.get("sector_etf_ok", True):
                return "green"
            if data.get("breakout") or data.get("ma_stack"):
                return "yellow"
            return "red"

        for ticker, data in sorted(
            watchlist_detail.items(), key=lambda x: x[1].get("score", 0), reverse=True
        )[:15]:
            row_style = _style_for_row(data)
            diag.add_row(
                ticker,
                f"[bold]{data.get('rs_pct', data.get('score', 0)):.1f}[/bold]",
                f"[green]✓[/green]" if data.get("breakout") else "[red]✗[/red]",
                _fmt_num(data.get("breakout_level")),
                f"[green]✓[/green]" if data.get("ma_stack") else "[red]✗[/red]",
                str(data.get("ma_trigger", "OK")),
                _fmt_num(data.get("rvol")),
                _fmt_num(data.get("dist_sma20_pct"), "%"),
                f"[green]✓[/green]" if data.get("sector_etf_ok", True) else "[red]✗[/red]",
                str(data.get("waiting_for", "OK")),
                data.get("primary_reason") or (", ".join(data.get("reasons", [])[:3]) or "OK"),
                style=row_style,
            )

        console.print(diag)

        nearest_ok = []
        nearest_warn = []
        for ticker, data in watchlist_detail.items():
            status, _ = calculate_data_quality(data)
            if status == "bad":
                continue
            
            data["_display_status"] = status
            if status == "warn":
                nearest_warn.append((ticker, data))
            else:
                nearest_ok.append((ticker, data))

        nearest_ok = sorted(
            nearest_ok, key=lambda x: x[1].get("proximity_score", 0), reverse=True
        )[:top_n]
        
        nearest_warn = sorted(
            nearest_warn, key=lambda x: x[1].get("proximity_score", 0), reverse=True
        )[:top_n]

        def _estado(data):
            if data.get("_display_status") == "warn":
                return "[yellow]⚠ Data incompleta[/yellow]"
            
            max_dist = 6.77
            try:
                max_dist = float(data.get("max_dist_sma20", max_dist))
            except Exception:
                pass
            if (
                (not data.get("breakout"))
                and data.get("ma_stack")
                and data.get("sector_etf_ok", True)
            ):
                rvol = data.get("rvol")
                dist = data.get("dist_sma20_pct")
                if (rvol is None or float(rvol) >= 1.0) and (
                    dist is None or abs(float(dist)) <= max_dist
                ):
                    return "⏳ Breakout"
            if data.get("breakout") and data.get("dist_sma20_pct") is not None:
                try:
                    if abs(float(data.get("dist_sma20_pct"))) > max_dist:
                        return "📉 Consolidar"
                except Exception:
                    pass
            return "🔧 Setup incompleto"

        if nearest_ok:
            console.print("\n[bold cyan]🎯 NEAREST TO SIGNAL[/bold cyan]")
            near = Table(box=box.SIMPLE_HEAD, title_justify="left")
            near.add_column("Ticker", style="bold yellow")
            near.add_column("Estado")
            near.add_column("RS", justify="right")
            near.add_column("Break lvl", justify="right")
            near.add_column("Dist SMA20", justify="right")
            near.add_column("RVOL", justify="right")
            near.add_column("Waiting")
            near.add_column("Prox", justify="right")

            for ticker, data in nearest_ok:
                prox = float(data.get("proximity_score", 0))
                prox_style = "green" if prox >= 80 else "yellow" if prox >= 50 else "red"
                near.add_row(
                    ticker,
                    _estado(data),
                    f"{data.get('rs_pct', data.get('score', 0)):.1f}",
                    _fmt_num(data.get("breakout_level")),
                    _fmt_num(data.get("dist_sma20_pct"), "%"),
                    _fmt_num(data.get("rvol")),
                    str(data.get("waiting_for", "OK")),
                    f"[{prox_style}]{prox:.0f}[/{prox_style}]",
                )
            console.print(near)

        if nearest_warn:
            console.print("\n[bold yellow]📡 DATA INCOMPLETE RADAR (VIGILANCIA)[/bold yellow]")
            near_w = Table(box=box.SIMPLE_HEAD, title_justify="left", border_style="dim")
            near_w.add_column("Ticker", style="bold dim yellow")
            near_w.add_column("Estado")
            near_w.add_column("RS", justify="right")
            near_w.add_column("Prox", justify="right")

            for ticker, data in nearest_warn:
                prox = float(data.get("proximity_score", 0))
                near_w.add_row(
                    ticker,
                    _estado(data),
                    f"{data.get('rs_pct', data.get('score', 0)):.1f}",
                    f"{prox:.0f}",
                )
            console.print(near_w)

        high_quality = []
        for t, d in watchlist_detail.items():
            status, _ = calculate_data_quality(d)
            if status != "ok": continue
            
            max_dist = 6.77
            try: max_dist = float(d.get("max_dist_sma20", max_dist))
            except: pass
            
            dist = d.get("dist_sma20_pct")
            if (d.get("rs_pct", d.get("score", 0)) >= 90
                and d.get("ma_stack")
                and d.get("sector_etf_ok", True)
                and (dist is not None and abs(float(dist)) <= max_dist)):
                high_quality.append((t, d))

        high_quality.sort(
            key=lambda x: (
                x[1].get("breakout", False),
                -(x[1].get("dist_sma20_pct") or 9999),
                x[1].get("rs_pct", x[1].get("score", 0)),
            ),
            reverse=True,
        )
        if high_quality:
            console.print("\n[bold cyan]🏆 HIGH QUALITY SETUPS[/bold cyan]")
            hq = Table(box=box.SIMPLE_HEAD, title_justify="left")
            hq.add_column("Ticker", style="bold yellow")
            hq.add_column("RS", justify="right")
            hq.add_column("Breakout", justify="center")
            hq.add_column("Break lvl", justify="right")
            hq.add_column("Dist SMA20", justify="right")
            hq.add_column("RVOL", justify="right")
            hq.add_column("Waiting")

            for ticker, data in high_quality[:hq_n]:
                hq.add_row(
                    ticker,
                    f"{data.get('rs_pct', data.get('score', 0)):.1f}",
                    "✓" if data.get("breakout") else "✗",
                    _fmt_num(data.get("breakout_level")),
                    _fmt_num(data.get("dist_sma20_pct"), "%"),
                    _fmt_num(data.get("rvol")),
                    str(data.get("waiting_for", "OK")),
                )

            console.print(hq)

    console.print("\n" + "─" * console.width + "\n", style="dim")


def build_telegram_brief(snapshot: dict, top_n: int = 5, hq_n: int = 5) -> str:
    """Construye un brief operativo para Telegram con formato visual 'tipo GUI'."""
    date = snapshot.get("date", "n/a")
    regime_ok = snapshot.get("regime_ok", False)
    signals = snapshot.get("signals", [])
    watchlist_detail = snapshot.get("watchlist_detail", {})

    # Intentar obtener datos de Gamma/DarkPools
    gamma_data = fetch_gamma_data()
    gamma_str = ""
    if gamma_data:
        dix = gamma_data['dix']
        gex = gamma_data['gex'] / 1e9 # Convertir a Billones para legibilidad
        dix_status = "🔥" if dix > 0.45 else "❄️"
        gex_status = "✅" if gex > 0 else "⚠️"
        gamma_str = (
            f"\n💎 <b>MARKET ALPHA (Gamma/DIX)</b>\n"
            f"• DIX: <code>{dix:.1%}</code> {dix_status} (Dark Pool Buy %)\n"
            f"• GEX: <code>${gex:.1f}B</code> {gex_status} (Gamma Exposure)\n"
        )

    sector_names = {
        "XLK": "Tecnología", "XLY": "Consumo discrecional", "XLRE": "Real Estate",
        "XLC": "Comunicaciones", "XLI": "Industriales", "XLF": "Financieras",
        "XLE": "Energía", "XLV": "Salud", "XLP": "Consumo defensivo",
        "XLU": "Utilities", "XLB": "Materiales"
    }

    lines = [
        f"🚀 <b>MOMENTUM V2 | {date}</b>",
        f"• Regime: <b>{'PASS' if regime_ok else 'BLOCKED'}</b>",
        f"• Universe: <code>{snapshot.get('universe_size', 0)}</code>",
        f"• Signals: <code>{len(signals)}</code>",
    ]

    if gamma_str:
        lines.append(gamma_str)

    hot_sectors = _build_hot_sectors(date, top_n=5)
    if hot_sectors:
        lines.append("\n🔥 <b>HOT SECTORS</b>")
        for row in hot_sectors:
            etf = row['sector_etf']
            name = sector_names.get(etf, "")
            lines.append(
                f"• <b>{etf} {name}</b> | RS {row.get('rs', 0):.1%} | S1 {'✓' if row.get('tradeable') else '✗'}"
            )

    def _fmt_val(v, suffix="", default="N/A"):
        if v is None: return default
        try: return f"{float(v):.2f}{suffix}"
        except: return default

    def _get_tv_link(ticker):
        # Usar link de símbolos para que TradingView resuelva el exchange (NASDAQ/NYSE) automáticamente
        return f'<a href="https://www.tradingview.com/symbols/{ticker}/">TradingView</a>'

    def _estado_simple(data):
        if data.get("_display_status") == "warn":
            return "⚠ Data incompleta"
        
        max_dist = 6.77
        try: max_dist = float(data.get("max_dist_sma20", max_dist))
        except: pass

        if not data.get("breakout") and data.get("ma_stack") and data.get("sector_etf_ok", True):
            rvol = data.get("rvol")
            dist = data.get("dist_sma20_pct")
            if (rvol is None or float(rvol) >= 1.0) and (dist is None or abs(float(dist)) <= max_dist):
                return "⏳ Breakout"
        if data.get("breakout") and data.get("dist_sma20_pct") is not None:
            try:
                if abs(float(data.get("dist_sma20_pct"))) > max_dist:
                    return "📉 Consolidar"
            except: pass
        return "🔧 Setup incompleto"

    if watchlist_detail:
        nearest_ok = []
        nearest_warn = []
        for ticker, data in watchlist_detail.items():
            status, _ = calculate_data_quality(data)
            if status == "bad": continue
            data["_display_status"] = status
            if status == "warn": nearest_warn.append((ticker, data))
            else: nearest_ok.append((ticker, data))

        nearest_ok = sorted(nearest_ok, key=lambda x: x[1].get("proximity_score", 0), reverse=True)[:top_n]
        if nearest_ok:
            lines.append("\n🎯 <b>NEAREST TO SIGNAL</b>")
            for ticker, data in nearest_ok:
                rs = data.get('rs_pct', data.get('score', 0))
                prox = data.get('proximity_score', 0)
                brk = _fmt_val(data.get('breakout_level'))
                rvol = _fmt_val(data.get('rvol'))
                dist = _fmt_val(data.get('dist_sma20_pct'), "%")
                falta = data.get('primary_reason') or (", ".join(data.get('reasons', [])[:2]) or "OK")
                trigger = data.get('waiting_for', 'OK')
                
                lines.append(
                    f"• <b>{ticker}</b> | RS {rs:.0f} | P {prox:.0f}\n"
                    f"  Chart: {_get_tv_link(ticker)}\n"
                    f"  Estado: {_estado_simple(data)}\n"
                    f"  Break: {brk} | RVOL {rvol} | Dist: {dist}\n"
                    f"  Falta: {falta}\n"
                    f"  Live trigger: <code>{trigger}</code>\n"
                )

        if nearest_warn:
            lines.append("\n📡 <b>DATA INCOMPLETE RADAR</b>")
            for ticker, data in nearest_warn[:3]:
                motivo = ", ".join(data.get('reasons', [])[:2]) or "Incompleto"
                lines.append(f"• <b>{ticker}</b> (RS {data.get('rs_pct', 0):.0f}) | {motivo}")
            lines.append("<i>Nota: Vigila OK+Warn; solo promueve con Breakout+RVOL live</i>")

    lines.append("\n⚠️ <b>RECORDATORIO:</b> Rotar TELEGRAM_BOT_TOKEN si fue expuesto.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    # Permitir ejecutarlo directamente: python3 src/utils/terminal_gui.py path/to/snapshot.json
    if len(sys.argv) > 1:
        print_terminal_brief(sys.argv[1])
