import json
import html
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
            near.add_column("#", justify="right", style="dim")
            near.add_column("Ticker", style="bold yellow")
            near.add_column("Estado")
            near.add_column("Trend", justify="center")
            near.add_column("Prev R", justify="center", style="dim")
            near.add_column("RS", justify="right")
            near.add_column("Break lvl", justify="right")
            near.add_column("Dist SMA20", justify="right")
            near.add_column("RVOL", justify="right")
            near.add_column("Waiting")
            near.add_column("Prox", justify="right")

            # Mapa de flujo para inyectar en la tabla principal
            nearest_flow = snapshot.get("nearest_flow") or {}
            flow_data = {r.get("ticker"): r for r in nearest_flow.get("rows", [])}

            for idx, (ticker, data) in enumerate(nearest_ok, 1):
                prox = float(data.get("proximity_score", 0))
                prox_style = "green" if prox >= 80 else "yellow" if prox >= 50 else "red"
                
                # Obtener info de flujo si existe
                f_row = flow_data.get(ticker, {})
                drift = f_row.get("rank_drift", 0)
                if drift == "NEW": trend = "🆕"
                else:
                    try:
                        dv = int(drift)
                        trend = "⬆️" if dv > 0 else "⬇️" if dv < 0 else "➡️"
                    except: trend = "➡️"
                
                prev_rank = str(f_row.get("previous_rank", "-"))

                near.add_row(
                    str(idx),
                    ticker,
                    _estado(data),
                    trend,
                    prev_rank,
                    f"{data.get('rs_pct', data.get('score', 0)):.1f}",
                    _fmt_num(data.get("breakout_level")),
                    _fmt_num(data.get("dist_sma20_pct"), "%"),
                    _fmt_num(data.get("rvol")),
                    str(data.get("waiting_for", "OK")),
                    f"[{prox_style}]{prox:.0f}[/{prox_style}]",
                )
            console.print(near)

        if nearest_warn:
            console.print("\n[bold yellow]📡 DATA INCOMPLETE RADAR (VIGILANCIA - REVISAR MANAL)[/bold yellow]")
            near_w = Table(box=box.SIMPLE_HEAD, title_justify="left", border_style="dim")
            near_w.add_column("#", justify="right", style="dim")
            near_w.add_column("Ticker", style="bold dim yellow")
            near_w.add_column("Estado")
            near_w.add_column("RS", justify="right")
            near_w.add_column("Prox", justify="right")

            for idx, (ticker, data) in enumerate(nearest_warn, 1):
                prox = float(data.get("proximity_score", 0))
                near_w.add_row(
                    str(idx),
                    ticker,
                    _estado(data),
                    f"{data.get('rs_pct', data.get('score', 0)):.1f}",
                    f"{prox:.0f}",
                )
            console.print(near_w)

        nearest_flow = snapshot.get("nearest_flow") or {}
        flow_rows = nearest_flow.get("rows") or []
        if flow_rows:
            prev_date = nearest_flow.get("previous_date", "previo")
            console.print(f"\n[bold cyan]🔁 NEAREST FLOW ({prev_date} → {date})[/bold cyan]")
            flow = Table(box=box.SIMPLE_HEAD, title_justify="left")
            flow.add_column("Ticker", style="bold yellow")
            flow.add_column("Estado")
            flow.add_column("Prox", justify="right")
            flow.add_column("Px %", justify="right")
            flow.add_column("Break gap")
            flow.add_column("Dist SMA20")
            flow.add_column("RVOL")
            flow.add_column("Hoy espera")
            flow.add_column("Fallo")

            state_map = {
                "SIGNAL": "[green]Signal[/green]",
                "STILL_NEAR": "[green]Sigue top[/green]",
                "DROPPED": "[yellow]Cayo[/yellow]",
                "DATA_BAD": "[yellow]Data mala[/yellow]",
                "OUT_OF_RADAR": "[red]Fuera radar[/red]",
            }

            def _fmt_delta(value, suffix=""):
                if value is None:
                    return "N/A"
                try:
                    value_f = float(value)
                    sign = "+" if value_f > 0 else ""
                    return f"{sign}{value_f:.2f}{suffix}"
                except Exception:
                    return "N/A"

            for row in flow_rows:
                state_txt = state_map.get(row.get("state"), str(row.get("state", "-")))
                
                # Indicador de tendencia basado en drift de ranking
                drift = row.get("rank_drift", 0)
                if drift == "NEW":
                    trend = "🆕"
                elif drift == "OUT":
                    trend = "❌"
                else:
                    try:
                        drift_val = int(drift)
                        if drift_val > 0:
                            trend = f"⬆️{drift_val:+} "
                        elif drift_val < 0:
                            trend = f"⬇️{drift_val:+} "
                        else:
                            trend = "➡️  "
                    except:
                        trend = "➡️  "
                
                ticker_txt = f"{trend}{row.get('ticker', '?')} (R{row.get('previous_rank', '-')})"
                
                prox_txt = (
                    f"{_fmt_num(row.get('previous_proximity'))}"
                    f"→{_fmt_num(row.get('current_proximity'))}"
                )
                gap_txt = (
                    f"{_fmt_delta(row.get('previous_breakout_gap_pct'), '%')}"
                    f"→{_fmt_delta(row.get('current_breakout_gap_pct'), '%')}"
                )
                dist_txt = (
                    f"{_fmt_delta(row.get('previous_dist_sma20_pct'), '%')}"
                    f"→{_fmt_delta(row.get('current_dist_sma20_pct'), '%')}"
                )
                rvol_txt = (
                    f"{_fmt_num(row.get('previous_rvol'))}"
                    f"→{_fmt_num(row.get('current_rvol'))}"
                )
                flow.add_row(
                    ticker_txt,
                    state_txt,
                    prox_txt,
                    _fmt_delta(row.get("price_delta_pct"), "%"),
                    gap_txt,
                    dist_txt,
                    rvol_txt,
                    str(row.get("current_waiting_for", "N/A")),
                    str(row.get("current_reason", "N/A")),
                )

            console.print(flow)

        sector_flow = snapshot.get("sector_flow") or {}
        sf_rows = sector_flow.get("rows") or []
        if sf_rows:
            console.print("\n[bold cyan]🏛️ SECTOR MONEY FLOW (DINERO INSTITUCIONAL)[/bold cyan]")
            sf = Table(box=box.SIMPLE_HEAD, title_justify="left")
            sf.add_column("ETF", style="bold yellow")
            sf.add_column("Tendencia", justify="center")
            sf.add_column("Rank", justify="center")
            sf.add_column("RS Flow", justify="right")
            sf.add_column("Estado")

            for row in sf_rows:
                drift = row.get("rank_drift", 0)
                trend = "🔥 ⬆️" if drift > 0 else "❄️ ⬇️" if drift < 0 else "➡️"
                rs_drift = row.get("rs_drift", 0)
                rs_txt = f"{rs_drift:+.2%}" if rs_drift != 0 else "="
                
                sf.add_row(
                    row["sector_etf"],
                    trend,
                    f"{row.get('previous_rank') or '-'}→{row.get('current_rank') or '-'}",
                    rs_txt,
                    "✅ Tradeable" if row.get("tradeable") else "⚠️ Blocked"
                )
            console.print(sf)

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


def build_telegram_brief(snapshot: dict, top_n: int = 5, hq_n: int = 5) -> tuple[str, list]:
    """Construye un brief operativo para Telegram con formato visual 'tipo GUI' y botones inline."""
    date = snapshot.get("date", "n/a")
    data_as_of = snapshot.get("data_as_of")
    regime_ok = snapshot.get("regime_ok", False)
    signals = snapshot.get("signals", [])
    watchlist_detail = snapshot.get("watchlist_detail", {})
    breadth = snapshot.get("breadth", {})

    date_esc = html.escape(str(date))
    header_date = f"🚀 <b>MOMENTUM V2 | {date_esc}</b>"
    if data_as_of and data_as_of != date:
        data_as_of_esc = html.escape(str(data_as_of))
        header_date += f" (Data: {data_as_of_esc})"

    # 1. Breadth Health Section
    breadth_lines = []
    if breadth:
        data_status = breadth.get("data_status", "OK")
        vix = breadth.get("vix")
        vix_status = "🟢" if (vix and vix < 20) else "🟡" if (vix and vix < 30) else "🔴"
        
        if data_status == "STALE" or breadth.get("sample_size", 0) == 0:
            breadth_lines = [
                f"\n📊 <b>BREADTH HEALTH: ⚪ N/A</b>",
                f"• VIX: <code>{vix if vix else 'N/A'}</code> {vix_status}",
                f"• Status: <code>DATA STALE (0/0)</code> ⚠️",
            ]
        else:
            nh = breadth.get("new_highs", 0)
            nl = breadth.get("new_lows", 0)
            nh_nl_ratio = nh / (nl if nl > 0 else 1)
            nh_status = "🟢" if nh_nl_ratio > 1.5 else "🟡" if nh_nl_ratio > 0.7 else "🔴"
            
            adv = breadth.get("advances", 0)
            dec = breadth.get("declines", 0)
            ad_ratio = adv / (dec if dec > 0 else 1)
            ad_status = "🟢" if ad_ratio > 1.2 else "🟡" if ad_ratio > 0.8 else "🔴"
            
            verdict = breadth.get("verdict", "NEUTRAL")
            v_emoji = "✅ GREEN" if verdict == "GREEN" else "⚠️ CAUTION" if verdict == "CAUTION" else "⚖️ NEUTRAL"
            sample = breadth.get("sample_size", 0)

            breadth_lines = [
                f"\n📊 <b>BREADTH HEALTH: {v_emoji}</b>",
                f"• VIX: <code>{vix if vix else 'N/A'}</code> {vix_status}",
                f"• NH/NL: <code>{nh}/{nl}</code> {nh_status} | A/D: <code>{adv}/{dec}</code> {ad_status}",
                f"• Sample: <code>{sample} tickers</code>",
            ]
            pc = breadth.get("put_call")
            if pc: breadth_lines[-1] += f" | P/C: <code>{pc:.2f}</code>"

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
        header_date,
        f"• Regime: <b>{'PASS' if regime_ok else 'BLOCKED'}</b>",
        f"• Universe: <code>{snapshot.get('universe_size', 0)}</code>",
        f"• Signals: <code>{len(signals)}</code>",
    ]
    
    if breadth_lines:
        lines.extend(breadth_lines)

    if gamma_str:
        lines.append(gamma_str)

    hot_sectors = _build_hot_sectors(date, top_n=5)
    hot_sector_order = {}
    if hot_sectors:
        lines.append("\n🔥 <b>HOT SECTORS</b>")
        for idx, row in enumerate(hot_sectors):
            etf = row['sector_etf']
            hot_sector_order[etf] = idx
            name = html.escape(sector_names.get(etf, ""))
            lines.append(
                f"• <b>{etf} {name}</b> | RS {row.get('rs', 0):.1%} | S1 {'✓' if row.get('tradeable') else '✗'}"
            )

    def _fmt_val(v, suffix="", default="N/A"):
        if v is None: return default
        try: return f"{float(v):.2f}{suffix}"
        except: return default

    def _get_tv_link(ticker):
        ticker_esc = html.escape(str(ticker))
        return f'<a href="https://www.tradingview.com/symbols/{ticker_esc}/">TradingView</a>'

    def _estado_simple(data):
        if data.get("_display_status") == "warn":
            return "⚠ Data incompleta"
        
        waiting = data.get("waiting_for", "OK")
        reason = data.get("primary_reason", "OK")
        breakout = data.get("breakout", False)
        rvol = data.get("rvol")
        dist = data.get("dist_sma20_pct")
        
        max_dist = 6.77
        try: max_dist = float(data.get("max_dist_sma20", max_dist))
        except: pass

        # Lógica mejorada según plan
        if waiting == "OK" and reason == "OK":
            return "✅ Trigger listo"
        if reason == "Extendido de SMA20" or (dist is not None and abs(float(dist)) > max_dist):
            return "📉 Consolidar"
        if reason == "Falta breakout" or not breakout:
            return "⏳ Esperar breakout"
        if reason == "RVOL bajo" or (rvol is not None and float(rvol) < 1.0):
            return "📡 Esperar volumen"
        
        return "🔧 Setup incompleto"

    buttons = []
    
    if watchlist_detail:
        nearest_ok = []
        nearest_warn = []
        for ticker, data in watchlist_detail.items():
            status, _ = calculate_data_quality(data)
            if status == "bad": continue
            data["_display_status"] = status
            if status == "warn": nearest_warn.append((ticker, data))
            else: nearest_ok.append((ticker, data))

        # Mapa de flujo para inyectar tendencias en el reporte principal
        nearest_flow = snapshot.get("nearest_flow") or {}
        flow_data = {r.get("ticker"): r for r in nearest_flow.get("rows", [])}

        nearest_ok = sorted(nearest_ok, key=lambda x: x[1].get("proximity_score", 0), reverse=True)
        rendered_tickers = []
        if nearest_ok:
            lines.append("\n🎯 <b>SECTORES CON CANDIDATOS</b>")
            
            # Agrupar por sector
            by_sector = {}
            for t, d in nearest_ok: # Cogemos todos para agrupar, limitamos al renderizar
                sec = d.get("sector_etf", "OTHER")
                if sec not in by_sector: by_sector[sec] = []
                by_sector[sec].append((t, d))
            
            def _sector_sort_key(sec):
                best_prox = max((d.get("proximity_score", 0) for _, d in by_sector.get(sec, [])), default=0)
                return (hot_sector_order.get(sec, 99), -best_prox, sec)

            total_shown = 0
            for sec in sorted(by_sector.keys(), key=_sector_sort_key):
                if total_shown >= top_n: break
                sec_name = sector_names.get(sec, sec)
                lines.append(f"<b>[{sec} {sec_name}]</b>")
                
                for ticker, data in sorted(by_sector[sec], key=lambda x: x[1].get("proximity_score", 0), reverse=True):
                    if total_shown >= top_n: break
                    total_shown += 1
                    rendered_tickers.append(ticker)
                    
                    ticker_esc = html.escape(str(ticker))
                    rs = data.get('rs_pct', data.get('score', 0))
                    prox = data.get('proximity_score', 0)
                    brk = data.get('breakout_level', 0)
                    rvol = _fmt_val(data.get('rvol'))
                    dist_val = data.get('dist_sma20_pct', 0)
                    dist = _fmt_val(dist_val, "%")
                    max_dist = _fmt_val(data.get("max_dist_sma20", 6.77), "%")
                    
                    htf_badge = " 🔥 HTF" if data.get("htf_candidate") else ""
                    
                    entry = float(brk) if brk else data.get('price', 0)
                    sl_approx = entry * 0.95
                    tp1_approx = entry + (entry - sl_approx) * 1.25
                    
                    f_row = flow_data.get(ticker, {})
                    drift = f_row.get("rank_drift", 0)
                    if drift == "NEW": trend = "🆕 "
                    else:
                        try:
                            dv = int(drift)
                            trend = "⬆️ " if dv > 0 else "⬇️ " if dv < 0 else "➡️ "
                        except: trend = "➡️ "
                    
                    # Bloqueos combinados
                    reasons = data.get('reasons', [])
                    if not reasons:
                        falta = "OK"
                    else:
                        falta = ", ".join(reasons[:2])
                    
                    falta = html.escape(str(falta))
                    trigger = html.escape(str(data.get('waiting_for', 'OK')))
                    
                    lines.append(
                        f"• {trend}<code>{ticker_esc}</code>{htf_badge}\n"
                        f"  RS: <b>{rs:.0f}</b> | Prox: <b>{prox:.0f}</b> | {_get_tv_link(ticker)}\n"
                        f"  Estado: <b>{html.escape(_estado_simple(data))}</b>\n"
                        f"  Dist SMA20: {dist} / max {max_dist}\n"
                        f"  RVOL: {rvol} | Break: <code>{entry:.2f}</code>\n"
                        f"  Bloqueos: {falta} | Live: <code>{trigger}</code>\n"
                    )

            # Crear el teclado inline
            row = []
            for ticker in rendered_tickers[:6]:
                row.append({"text": f"🔎 {ticker}", "callback_data": f"detail:{ticker}"})
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

        if nearest_warn:
            lines.append("\n📡 <b>DATA INCOMPLETE RADAR</b>")
            quality_map = {
                "rvol_1.0_default": "RVOL premarket no confiable",
                "adr_0": "ADR faltante",
                "zero_dollar_vol": "Dollar volume faltante",
                "missing_avg_volume_20d": "sin baseline volumen 20d",
                "dist_sma20_zero_suspect": "SMA20 suspect (0.0)"
            }
            for ticker, data in nearest_warn[:3]:
                ticker_esc = html.escape(str(ticker))
                sec = data.get("sector_etf", "?")
                q_reasons = data.get('data_quality_reasons', [])
                if q_reasons:
                    motivo = ", ".join([quality_map.get(r, r) for r in q_reasons[:2]])
                else:
                    motivo = ", ".join(data.get('reasons', [])[:2]) or "Incompleto"
                
                motivo = html.escape(str(motivo))
                lines.append(f"• <b>{ticker_esc}</b> ({sec}) | RS {data.get('rs_pct', 0):.0f} | {motivo}")

        # 2. ALERTA TOP Section (basada solo en lo renderizado)
        if rendered_tickers:
            rendered_data = [(t, watchlist_detail[t]) for t in rendered_tickers]
            grouped_rendered = {}
            for t, d in rendered_data:
                grouped_rendered.setdefault(d.get("sector_etf", "OTHER"), []).append((t, d))

            top_sec = sorted(grouped_rendered.keys(), key=lambda sec: (
                hot_sector_order.get(sec, 99),
                -max((d.get("proximity_score", 0) for _, d in grouped_rendered.get(sec, [])), default=0),
                sec,
            ))[0]
            top_sector_candidates = sorted(
                grouped_rendered[top_sec], key=lambda x: x[1].get("proximity_score", 0), reverse=True
            )
            top_names = " / ".join(t for t, _ in top_sector_candidates[:3])
            
            # Blocker predominante
            blocker_counts = {}
            for _, data in top_sector_candidates:
                blocker = data.get("primary_reason") or "OK"
                blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
            main_blocker = max(blocker_counts, key=blocker_counts.get)
            
            action = (
                f"Esperar {top_sector_candidates[0][1].get('waiting_for', 'trigger live')}"
                if main_blocker != "OK" else "Monitorear Breakout live + RVOL"
            )
            lines.append(
                f"\n🚨 <b>ALERTA TOP: Sector {top_sec}</b>\n"
                f"Candidatos: <code>{html.escape(top_names)}</code>\n"
                f"Blocker: <b>{html.escape(str(main_blocker))}</b>\n"
                f"Acción: <b>{html.escape(str(action))}</b>"
            )

        sector_flow = snapshot.get("sector_flow") or {}
        sf_rows = sector_flow.get("rows") or []
        if sf_rows:
            lines.append("\n🏛️ <b>SECTOR MONEY FLOW</b>")
            flow_secs = []
            for row in sf_rows[:5]:
                etf = row['sector_etf']
                flow_secs.append(etf)
                name = html.escape(sector_names.get(etf, ""))
                drift = row.get("rank_drift", 0)
                trend = "🔥 ⬆️" if drift > 0 else "❄️ ⬇️" if drift < 0 else "➡️"
                rs_drift = row.get("rs_drift", 0)
                rs_txt = f"{rs_drift:+.2%}" if rs_drift != 0 else "="
                lines.append(f"• <b>{etf} {name}</b> | {trend} | RS {rs_txt}")
            
            # Bloque compacto: CANDIDATOS GENERALES POR FLOW
            all_detail = watchlist_detail
            gen_lines = []
            for etf in flow_secs:
                sec_candidates = [
                    t for t, d in all_detail.items() 
                    if d.get("sector_etf") == etf and t not in rendered_tickers
                    and d.get("_display_status") == "ok"
                ]
                if sec_candidates:
                    top_gen = sorted(sec_candidates, key=lambda t: all_detail[t].get("proximity_score", 0), reverse=True)[:3]
                    gen_lines.append(f"• {etf}: " + ", ".join(f"<code>{t}</code>" for t in top_gen))
            
            if gen_lines:
                lines.append("\n🔭 <b>CANDIDATOS GENERALES POR FLOW</b>")
                lines.extend(gen_lines)

        nearest_flow = snapshot.get("nearest_flow") or {}
        flow_rows = nearest_flow.get("rows") or []
        if flow_rows:
            prev_date = html.escape(str(nearest_flow.get("previous_date", "previo")))
            lines.append(f"\n🔁 <b>NEAREST FLOW {prev_date} → {date_esc}</b>")
            state_map = {
                "SIGNAL": "Signal", "STILL_NEAR": "Sigue top", "DROPPED": "Cayo",
                "DATA_BAD": "Data mala", "OUT_OF_RADAR": "Fuera radar",
            }

            for row in flow_rows[:top_n]:
                ticker = row.get("ticker", "?")
                ticker_esc = html.escape(str(ticker))
                state = html.escape(state_map.get(row.get("state"), str(row.get("state", "-"))))
                drift = row.get("rank_drift", 0)
                if drift == "NEW": trend = "🆕 "
                elif drift == "OUT": trend = "❌ "
                else:
                    try:
                        dv = int(drift)
                        trend = f"⬆️{dv:+} " if dv > 0 else f"⬇️{dv:+} " if dv < 0 else "➡️ "
                    except: trend = "➡️ "
                
                prev_rank = row.get("previous_rank", "-")
                waiting = html.escape(str(row.get("current_waiting_for", "N/A")))
                px = row.get("price_delta_pct", "N/A")
                
                lines.append(f"• {trend}<b>{ticker_esc}</b> (Prev R{prev_rank}) | {state} | Wait: <code>{waiting}</code>")

    # Botones finales
    buttons.append([
        {"text": "🔄 Refresh", "callback_data": "refresh:market"},
        {"text": "⚡ Regen All", "callback_data": "regenerate:market"}
    ])

    return "\n".join(lines), buttons


if __name__ == "__main__":
    import sys

    # Permitir ejecutarlo directamente: python3 src/utils/terminal_gui.py path/to/snapshot.json
    if len(sys.argv) > 1:
        print_terminal_brief(sys.argv[1])
