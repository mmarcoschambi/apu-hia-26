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

from src.utils.sector_rotation import SectorRotationAnalyzer, get_ticker_sector_mapping

from src.utils.data_quality import calculate_data_quality
from src.utils.gamma_scraper import fetch_gamma_data

console = Console()

SECTOR_NAMES = {
    "XLK": "Tecnología",
    "XLY": "Consumo discrecional",
    "XLRE": "Real Estate",
    "XLC": "Comunicaciones",
    "XLI": "Industriales",
    "XLF": "Financieras",
    "XLE": "Energía",
    "XLV": "Salud",
    "XLP": "Consumo defensivo",
    "XLU": "Utilities",
    "XLB": "Materiales",
}


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

    universe_size = snapshot.get("universe_size", 0)
    scanner_uni_count = snapshot.get("scanner_universe_count")
    if scanner_uni_count is not None and abs(universe_size - scanner_uni_count) > 50:
        universe_val = f"{universe_size} (Finviz) | {scanner_uni_count} (Scanner DB)\n"
    else:
        universe_val = f"{universe_size}\n"

    stats_text = Text.assemble(
        ("Date: ", "cyan"),
        (f"{date}\n", "white"),
        ("Regime: ", "cyan"),
        (f"{regime_str}\n", "white"),
        ("Universe: ", "cyan"),
        (universe_val, "white"),
        ("Signals: ", "cyan"),
        (f"{len(signals)}\n\n", "white"),
        ("[WARN]  ", "yellow"),
        ("MANUAL REVIEW - NO AUTO ENTRY", "bold yellow"),
    )

    console.print("\n")
    console.print(
        Panel(
            stats_text,
            title="[bold magenta][U+1F680] MOMENTUM V2 - DAILY BRIEF[/bold magenta]",
            border_style="bright_blue",
            box=box.ROUNDED,
        )
    )

    # 2. Signals Table
    if signals:
        table = Table(
            title="\n[bold fire][U+1F525] TOP CONFIRMED SIGNALS[/bold fire]",
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
        console.print("\n[bold cyan][U+1F525] HOT SECTORS[/bold cyan]")
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
                "[U+2713]" if row.get("tradeable") else "[U+2717]",
            )

        console.print(hs)

    # 3. Watchlist
    if watchlist_scored:
        sig_tickers = {s.get("ticker") for s in signals}
        watchlist = [(t, score) for t, score in watchlist_scored.items() if t not in sig_tickers]
        watchlist.sort(key=lambda x: x[1], reverse=True)

        if watchlist:
            console.print("\n[bold cyan][U+1F52D] WATCHLIST (NEAR-ENTRIES - TOP RS)[/bold cyan]")

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
        console.print("\n[bold cyan][U+1F9EA] WATCHLIST DIAGNOSTIC[/bold cyan]")
        diag = Table(box=box.SIMPLE_HEAD, title_justify="left")
        diag.add_column("Ticker", style="bold yellow")
        diag.add_column("RS", justify="right")
        diag.add_column("Breakout")
        diag.add_column("Break lvl")
        diag.add_column("MA Stack")
        diag.add_column("MA trig")
        diag.add_column("RVOL")
        diag.add_column("Dist SMA20", justify="right")
        diag.add_column("Sector", justify="center")
        diag.add_column("Theme RS", justify="right")
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
            t_rs = data.get("theme_vs_sector")
            t_rs_txt = f"{t_rs:+.1%}" if t_rs is not None else "N/A"

            diag.add_row(
                ticker,
                f"[bold]{data.get('rs_pct', data.get('score', 0)):.1f}[/bold]",
                f"[green][U+2713][/green]" if data.get("breakout") else "[red][U+2717][/red]",
                _fmt_num(data.get("breakout_level")),
                f"[green][U+2713][/green]" if data.get("ma_stack") else "[red][U+2717][/red]",
                str(data.get("ma_trigger", "OK")),
                _fmt_num(data.get("rvol")),
                _fmt_num(data.get("dist_sma20_pct"), "%"),
                f"[green][U+2713][/green]" if data.get("sector_etf_ok", True) else "[red][U+2717][/red]",
                t_rs_txt,
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

        nearest_ok = sorted(nearest_ok, key=lambda x: x[1].get("proximity_score", 0), reverse=True)[
            :top_n
        ]

        nearest_warn = sorted(
            nearest_warn, key=lambda x: x[1].get("proximity_score", 0), reverse=True
        )[:top_n]

        # Resolve all sectors for efficiency
        all_tickers = list(watchlist_detail.keys())
        resolved_sectors = get_ticker_sector_mapping(all_tickers)

        def _get_sec(ticker, data):
            return data.get("sector_etf") or resolved_sectors.get(ticker) or "OTHER"

        def _estado(data):
            if data.get("_display_status") == "warn":
                return "[yellow][WARN] Data incompleta[/yellow]"

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
                    return "[HOURGLASS] Breakout"
            if data.get("breakout") and data.get("dist_sma20_pct") is not None:
                try:
                    if abs(float(data.get("dist_sma20_pct"))) > max_dist:
                        return "[U+1F4C9] Consolidar"
                except Exception:
                    pass
            return "[U+1F527] Setup incompleto"

        if nearest_ok:
            console.print("\n[bold cyan][U+1F3AF] SECTORES CON CANDIDATOS (NEAREST TO SIGNAL)[/bold cyan]")

            # Agrupar por sector
            by_sector = {}
            for t, d in nearest_ok:
                sec = _get_sec(t, d)
                by_sector.setdefault(sec, []).append((t, d))

            # Mapa de flujo para inyectar en la tabla principal
            nearest_flow = snapshot.get("nearest_flow") or {}
            flow_data = {r.get("ticker"): r for r in nearest_flow.get("rows", [])}

            # Obtener orden de sectores hot para el sorting
            hot_sector_order = (
                {s["sector_etf"]: i for i, s in enumerate(hot_sectors)} if hot_sectors else {}
            )
            hot_sector_map = {s["sector_etf"]: s for s in hot_sectors} if hot_sectors else {}

            def _sector_sort_key(sec):
                cands = by_sector.get(sec, [])
                best_prox = max((d.get("proximity_score", 0) for _, d in cands), default=0)
                return (hot_sector_order.get(sec, 99), -best_prox, sec)

            # Ordenar sectores por importancia/fuerza
            for sec in sorted(by_sector.keys(), key=_sector_sort_key):
                sec_cands = by_sector[sec]

                # Metadata del sector para el header
                hs_info = hot_sector_map.get(sec, {})
                rs_txt = f" | RS {hs_info.get('rs', 0):.1%}" if "rs" in hs_info else ""
                s1_txt = (
                    " | S1 [U+2713]"
                    if hs_info.get("tradeable")
                    else " | S1 [U+2717]"
                    if "tradeable" in hs_info
                    else ""
                )

                console.print(
                    f"\n[bold yellow]-- [ {sec} {SECTOR_NAMES.get(sec, '')}{rs_txt}{s1_txt} ] --------------------------------[/bold yellow]"
                )

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

                # Ordenar candidatos dentro del sector por proximidad
                sec_cands.sort(key=lambda x: x[1].get("proximity_score", 0), reverse=True)

                for idx, (ticker, data) in enumerate(sec_cands, 1):
                    prox = float(data.get("proximity_score", 0))
                    prox_style = "green" if prox >= 80 else "yellow" if prox >= 50 else "red"

                    # Obtener info de flujo si existe
                    f_row = flow_data.get(ticker, {})
                    drift = f_row.get("rank_drift", 0)
                    if drift == "NEW":
                        trend = "[U+1F195]"
                    else:
                        try:
                            dv = int(drift)
                            trend = "[UP]" if dv > 0 else "[DOWN]" if dv < 0 else "[RIGHT]"
                        except:
                            trend = "[RIGHT]"

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
            console.print(
                "\n[bold yellow][U+1F4E1] DATA INCOMPLETE RADAR (VIGILANCIA - REVISAR MANAL)[/bold yellow]"
            )
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
            console.print(f"\n[bold cyan][U+1F501] NEAREST FLOW ({prev_date} -> {date})[/bold cyan]")
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
                    trend = "[U+1F195]"
                elif drift == "OUT":
                    trend = "[FAIL]"
                else:
                    try:
                        drift_val = int(drift)
                        if drift_val > 0:
                            trend = f"[UP]{drift_val:+} "
                        elif drift_val < 0:
                            trend = f"[DOWN]{drift_val:+} "
                        else:
                            trend = "[RIGHT]  "
                    except:
                        trend = "[RIGHT]  "

                ticker_txt = f"{trend}{row.get('ticker', '?')} (R{row.get('previous_rank', '-')})"

                prox_txt = (
                    f"{_fmt_num(row.get('previous_proximity'))}"
                    f"->{_fmt_num(row.get('current_proximity'))}"
                )
                gap_txt = (
                    f"{_fmt_delta(row.get('previous_breakout_gap_pct'), '%')}"
                    f"->{_fmt_delta(row.get('current_breakout_gap_pct'), '%')}"
                )
                dist_txt = (
                    f"{_fmt_delta(row.get('previous_dist_sma20_pct'), '%')}"
                    f"->{_fmt_delta(row.get('current_dist_sma20_pct'), '%')}"
                )
                rvol_txt = (
                    f"{_fmt_num(row.get('previous_rvol'))}->{_fmt_num(row.get('current_rvol'))}"
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
            console.print("\n[bold cyan][U+1F3DB] SECTOR MONEY FLOW (DINERO INSTITUCIONAL)[/bold cyan]")
            sf = Table(box=box.SIMPLE_HEAD, title_justify="left")
            sf.add_column("ETF", style="bold yellow")
            sf.add_column("Tendencia", justify="center")
            sf.add_column("Rank", justify="center")
            sf.add_column("RS Flow", justify="right")
            sf.add_column("Estado")

            for row in sf_rows:
                drift = row.get("rank_drift", 0)
                trend = "[U+1F525] [UP]" if drift > 0 else "[SNOW] [DOWN]" if drift < 0 else "[RIGHT]"
                rs_drift = row.get("rs_drift", 0)
                rs_txt = f"{rs_drift:+.2%}" if rs_drift != 0 else "="

                sf.add_row(
                    row["sector_etf"],
                    trend,
                    f"{row.get('previous_rank') or '-'}->{row.get('current_rank') or '-'}",
                    rs_txt,
                    "[OK] Tradeable" if row.get("tradeable") else "[WARN] Blocked",
                )
            console.print(sf)

        high_quality = []
        for t, d in watchlist_detail.items():
            status, _ = calculate_data_quality(d)
            if status != "ok":
                continue

            max_dist = 6.77
            try:
                max_dist = float(d.get("max_dist_sma20", max_dist))
            except:
                pass

            dist = d.get("dist_sma20_pct")
            if (
                d.get("rs_pct", d.get("score", 0)) >= 90
                and d.get("ma_stack")
                and d.get("sector_etf_ok", True)
                and (dist is not None and abs(float(dist)) <= max_dist)
            ):
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
            console.print("\n[bold cyan][U+1F3C6] HIGH QUALITY SETUPS[/bold cyan]")
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
                    "[U+2713]" if data.get("breakout") else "[U+2717]",
                    _fmt_num(data.get("breakout_level")),
                    _fmt_num(data.get("dist_sma20_pct"), "%"),
                    _fmt_num(data.get("rvol")),
                    str(data.get("waiting_for", "OK")),
                )

            console.print(hq)

    console.print("\n" + "-" * console.width + "\n", style="dim")


def build_telegram_brief(snapshot: dict, top_n: int = 5, hq_n: int = 5) -> tuple[str, list]:
    """Construye un brief operativo para Telegram con formato visual 'tipo GUI' y botones inline."""
    date = snapshot.get("date", "n/a")
    data_as_of = snapshot.get("data_as_of")
    regime_ok = snapshot.get("regime_ok", False)
    signals = snapshot.get("signals", [])
    watchlist_detail = snapshot.get("watchlist_detail", {})
    breadth = snapshot.get("breadth", {})

    date_esc = html.escape(str(date))
    header_date = f"[U+1F680] <b>MOMENTUM V2 | {date_esc}</b>"
    if data_as_of and data_as_of != date:
        data_as_of_esc = html.escape(str(data_as_of))
        header_date += f" (Data: {data_as_of_esc})"

    # 1. Breadth Health Section
    breadth_lines = []
    if breadth:
        data_status = breadth.get("data_status", "OK")
        vix = breadth.get("vix")
        vix_status = "[U+1F7E2]" if (vix and vix < 20) else "[U+1F7E1]" if (vix and vix < 30) else "[U+1F534]"

        if data_status == "STALE" or breadth.get("sample_size", 0) == 0:
            breadth_lines = [
                f"\n[U+1F4CA] <b>BREADTH HEALTH: [CIRCLE-W] N/A</b>",
                f"• VIX: <code>{vix if vix else 'N/A'}</code> {vix_status}",
                f"• Status: <code>DATA STALE (0/0)</code> [WARN]",
            ]
        else:
            nh = breadth.get("new_highs", 0)
            nl = breadth.get("new_lows", 0)
            nh_nl_ratio = nh / (nl if nl > 0 else 1)
            nh_status = "[U+1F7E2]" if nh_nl_ratio > 1.5 else "[U+1F7E1]" if nh_nl_ratio > 0.7 else "[U+1F534]"

            adv = breadth.get("advances", 0)
            dec = breadth.get("declines", 0)
            ad_ratio = adv / (dec if dec > 0 else 1)
            ad_status = "[U+1F7E2]" if ad_ratio > 1.2 else "[U+1F7E1]" if ad_ratio > 0.8 else "[U+1F534]"

            verdict = breadth.get("verdict", "NEUTRAL")
            v_emoji = (
                "[OK] GREEN"
                if verdict == "GREEN"
                else "[WARN] CAUTION"
                if verdict == "CAUTION"
                else "[SCALE] NEUTRAL"
            )
            sample = breadth.get("sample_size", 0)

            breadth_lines = [
                f"\n[U+1F4CA] <b>BREADTH HEALTH: {v_emoji}</b>",
                f"• VIX: <code>{vix if vix else 'N/A'}</code> {vix_status}",
                f"• NH/NL: <code>{nh}/{nl}</code> {nh_status} | A/D: <code>{adv}/{dec}</code> {ad_status}",
                f"• Sample: <code>{sample} tickers</code>",
            ]
            pc = breadth.get("put_call")
            if pc:
                breadth_lines[-1] += f" | P/C: <code>{pc:.2f}</code>"

    # Intentar obtener datos de Gamma/DarkPools
    gamma_data = fetch_gamma_data()
    gamma_str = ""
    if gamma_data:
        dix = gamma_data["dix"]
        gex = gamma_data["gex"] / 1e9  # Convertir a Billones para legibilidad
        dix_status = "[U+1F525]" if dix > 0.45 else "[SNOW]"
        gex_status = "[OK]" if gex > 0 else "[WARN]"
        gamma_str = (
            f"\n[U+1F48E] <b>MARKET ALPHA (Gamma/DIX)</b>\n"
            f"• DIX: <code>{dix:.1%}</code> {dix_status} (Dark Pool Buy %)\n"
            f"• GEX: <code>${gex:.1f}B</code> {gex_status} (Gamma Exposure)\n"
        )

    universe_size = snapshot.get("universe_size", 0)
    scanner_uni_count = snapshot.get("scanner_universe_count")
    if scanner_uni_count is not None and abs(universe_size - scanner_uni_count) > 50:
        universe_str = f"• Universe (Finviz): <code>{universe_size}</code> | Scanner DB: <code>{scanner_uni_count}</code>"
    else:
        universe_str = f"• Universe: <code>{universe_size}</code>"

    lines = [
        header_date,
        f"• Regime: <b>{'PASS' if regime_ok else 'BLOCKED'}</b>",
        universe_str,
        f"• Signals: <code>{len(signals)}</code>",
    ]

    if breadth_lines:
        lines.extend(breadth_lines)

    if gamma_str:
        lines.append(gamma_str)

    e25_audit = snapshot.get("e25_audit") or {}
    if e25_audit:
        systems = e25_audit.get("systems", {})
        finviz = systems.get("finviz_vps", {})
        local = systems.get("local_pit", {})
        lines.append("\n[U+1F9EA] <b>SHADOW / E25 AUDIT</b>")
        lines.append(
            f"• FINVIZ/VPS: <code>{finviz.get('signals', 0)}</code> | avg SF <code>{finviz.get('avg_sizing_factor', 1.0):.2f}</code> | blocked <code>{finviz.get('blocked_extremes', 0)}</code> | ultra <code>{finviz.get('ultralight', 0)}</code>"
        )
        lines.append(
            f"• LOCAL/PIT: <code>{local.get('signals', 0)}</code> | avg SF <code>{local.get('avg_sizing_factor', 1.0):.2f}</code> | blocked <code>{local.get('blocked_extremes', 0)}</code> | ultra <code>{local.get('ultralight', 0)}</code>"
        )
        overlap = e25_audit.get("overlap_tickers") or []
        local_only = e25_audit.get("local_only_tickers") or []
        finviz_only = e25_audit.get("finviz_only_tickers") or []
        if overlap:
            lines.append(f"• Overlap: <code>{', '.join(overlap[:8])}</code>")
        if local_only:
            lines.append(f"• Local only: <code>{', '.join(local_only[:6])}</code>")
        if finviz_only:
            lines.append(f"• Finviz only: <code>{', '.join(finviz_only[:6])}</code>")

    hot_sectors = _build_hot_sectors(date, top_n=5)
    hot_sector_order = {}
    if hot_sectors:
        lines.append("\n[U+1F525] <b>HOT SECTORS</b>")
        for idx, row in enumerate(hot_sectors):
            etf = row["sector_etf"]
            hot_sector_order[etf] = idx
            name = html.escape(SECTOR_NAMES.get(etf, ""))
            lines.append(
                f"• <b>{etf} {name}</b> | RS {row.get('rs', 0):.1%} | S1 {'[U+2713]' if row.get('tradeable') else '[U+2717]'}"
            )

    # Resolve all sectors at once for efficiency
    all_tickers_for_sec = list(watchlist_detail.keys())
    nearest_flow_data = snapshot.get("nearest_flow") or {}
    all_tickers_for_sec.extend(
        [r.get("ticker") for r in nearest_flow_data.get("rows", []) if r.get("ticker")]
    )
    all_tickers_for_sec = list(set(all_tickers_for_sec))
    resolved_sectors = get_ticker_sector_mapping(all_tickers_for_sec)

    def _get_sec(ticker, data):
        return data.get("sector_etf") or resolved_sectors.get(ticker) or "OTHER"

    def _fmt_val(v, suffix="", default="N/A"):
        if v is None:
            return default
        try:
            return f"{float(v):.2f}{suffix}"
        except:
            return default

    def _get_tv_link(ticker):
        ticker_esc = html.escape(str(ticker))
        return f'<a href="https://www.tradingview.com/symbols/{ticker_esc}/">TradingView</a>'

    def _estado_simple(data):
        if data.get("_display_status") == "warn":
            return "[WARN] Data incompleta"

        # Calculate sizing factor for E25_v2
        dist = data.get("dist_sma20_pct")
        adr = data.get("adr", 0.0)
        try:
            from src.signals.signal_engine import calculate_dynamic_sizing_factor
            from src.config.dynamic_config import load_production_config
            cfg = load_production_config()
            sf_val, _ = calculate_dynamic_sizing_factor(float(dist or 0.0), float(adr or 0.0), cfg)
        except:
            sf_val = 1.0

        waiting = data.get("waiting_for", "OK")
        reason = data.get("primary_reason", "OK")
        breakout = data.get("breakout", False)
        rvol = data.get("rvol")

        max_dist = 6.77
        try:
            max_dist = float(data.get("max_dist_sma20", max_dist))
        except:
            pass

        # Si E25 está activo y sf_val > 0, quitamos el bloqueo de distancia
        is_extendido = (dist is not None and abs(float(dist)) > max_dist)
        if is_extendido and sf_val > 0:
            if reason == "Extendido de SMA20":
                reasons = [r for r in data.get("reasons", []) if "extendido" not in r.lower()]
                reason = reasons[0] if reasons else "OK"
            if "dist" in waiting.lower() or "sma20" in waiting.lower():
                reasons = [r for r in data.get("reasons", []) if "extendido" not in r.lower()]
                waiting = "OK" if not reasons else reasons[0]

        # Lógica mejorada según plan
        if waiting == "OK" and reason == "OK":
            return "[OK] Trigger listo"
        if reason == "Extendido de SMA20" or (is_extendido and sf_val <= 0):
            return "[U+1F4C9] Consolidar"
        if reason == "Falta breakout" or not breakout:
            return "[HOURGLASS] Esperar breakout"
        if reason == "RVOL bajo" or (rvol is not None and float(rvol) < 1.0):
            return "[U+1F4E1] Esperar volumen"

        return "[U+1F527] Setup incompleto"

    buttons = []

    if watchlist_detail:
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

        # Mapa de flujo para inyectar tendencias en el reporte principal
        nearest_flow = snapshot.get("nearest_flow") or {}
        flow_data = {r.get("ticker"): r for r in nearest_flow.get("rows", [])}

        nearest_ok = sorted(nearest_ok, key=lambda x: x[1].get("proximity_score", 0), reverse=True)
        rendered_tickers = []

        if nearest_ok:
            lines.append("\n[U+1F3AF] <b>SECTORES CON CANDIDATOS</b>")

            # Agrupar por SECTOR primero
            by_sector = {}
            for t, d in nearest_ok:
                sec = _get_sec(t, d)
                by_sector.setdefault(sec, []).append((t, d))

            def _sector_sort_key(sec):
                cands = by_sector.get(sec, [])
                best_prox = max((d.get("proximity_score", 0) for _, d in cands), default=0)
                return (hot_sector_order.get(sec, 99), -best_prox, sec)

            total_shown = 0
            shown_tickers = set()

            for sec in sorted(by_sector.keys(), key=_sector_sort_key):
                if total_shown >= top_n:
                    break

                # Header del Sector con metadata de RS/Flow
                # Intentar encontrar datos del sector en hot_sectors o sector_flow
                sec_name = SECTOR_NAMES.get(sec, sec)

                # Buscar RS del sector en hot_sectors
                sec_rs_txt = ""
                for hs in hot_sectors:
                    if hs["sector_etf"] == sec:
                        sec_rs_txt = (
                            f" | RS {hs.get('rs', 0):.1%} {'[U+1F525]' if hs.get('tradeable') else ''}"
                        )
                        break

                lines.append(f"<b>[{sec} {sec_name}{sec_rs_txt}]</b>")

                # Dentro del sector, opcionalmente agrupar por temas
                sec_cands = sorted(
                    by_sector[sec], key=lambda x: x[1].get("proximity_score", 0), reverse=True
                )

                # Detectar temas en este sector
                themes_in_sec = {}
                for t, d in sec_cands:
                    for theme in d.get("themes", []):
                        themes_in_sec.setdefault(theme, []).append(t)

                # Renderizar candidatos
                for ticker, data in sec_cands:
                    if total_shown >= top_n:
                        break
                    total_shown += 1
                    rendered_tickers.append(ticker)
                    shown_tickers.add(ticker)

                    ticker_esc = html.escape(str(ticker))
                    rs = data.get("rs_pct", data.get("score", 0))
                    prox = data.get("proximity_score", 0)
                    brk = data.get("breakout_level", 0)
                    rvol = _fmt_val(data.get("rvol"))
                    dist_val = data.get("dist_sma20_pct", 0)
                    dist = _fmt_val(dist_val, "%")
                    max_dist = _fmt_val(data.get("max_dist_sma20", 6.77), "%")
                    htf_badge = " [U+1F525] HTF" if data.get("htf_candidate") else ""

                    themes = data.get("themes", [])
                    theme_txt = f" [Tema: {', '.join(themes).upper()}]" if themes else ""

                    entry = float(brk) if brk else data.get("price", 0)
                    f_row = flow_data.get(ticker, {})
                    drift = f_row.get("rank_drift", 0)
                    if drift == "NEW":
                        trend = "[U+1F195] "
                    elif drift == "OUT":
                        trend = "[FAIL] "
                    else:
                        try:
                            dv = int(drift)
                            trend = "[UP] " if dv > 0 else "[DOWN] " if dv < 0 else "[RIGHT] "
                        except:
                            trend = "[RIGHT] "

                    # Calculate sizing factor for E25_v2 shadow
                    try:
                        from src.signals.signal_engine import calculate_dynamic_sizing_factor
                        from src.config.dynamic_config import load_production_config
                        cfg = load_production_config()
                        sf_val, _ = calculate_dynamic_sizing_factor(float(dist_val or 0.0), float(data.get("adr", 0.0) or 0.0), cfg)
                    except:
                        sf_val = 1.0

                    bucket = "Z1"
                    if dist_val <= 6.76:
                        bucket = "Z1"
                    elif dist_val <= 10.0:
                        bucket = "Z2"
                    elif dist_val <= 15.0:
                        bucket = "Z3"
                    elif dist_val <= 25.0:
                        bucket = "Z4"
                    elif dist_val <= 35.0:
                        bucket = "Z5"
                    else:
                        bucket = "Z6"

                    if sf_val is not None:
                        dist_sma20_line = f"Dist SMA20: {dist} / E25 Sizing: {sf_val:.2f} ({bucket})"
                    else:
                        dist_sma20_line = f"Dist SMA20: {dist} / max {max_dist}"

                    reasons = data.get("reasons", [])
                    trigger = html.escape(str(data.get("waiting_for", "OK")))

                    if sf_val > 0:
                        reasons = [r for r in reasons if "extendido" not in r.lower()]
                        if "dist" in trigger.lower() or "sma20" in trigger.lower():
                            trigger = "OK" if not reasons else reasons[0]

                    falta = ", ".join(reasons[:2]) if reasons else "OK"

                    combos = data.get("combos", [])
                    combo_badge = ""
                    if combos:
                        if len(combos) > 1:
                            combo_badge = " <b>[Ambos]</b>"
                        else:
                            combo_badge = f" <b>[{combos[0]}]</b>"

                    lines.append(
                        f"• {trend}<code>{ticker_esc}</code>{combo_badge}{htf_badge}{theme_txt}\n"
                        f"  RS: <b>{rs:.0f}</b> | Prox: <b>{prox:.0f}</b> | {_get_tv_link(ticker)}\n"
                        f"  Estado: <b>{html.escape(_estado_simple(data))}</b>\n"
                        f"  {dist_sma20_line}\n"
                        f"  RVOL: {rvol} | Break: <code>{entry:.2f}</code>\n"
                        f"  Bloqueos: {html.escape(str(falta))} | Live: <code>{trigger}</code>\n"
                    )

        # 2. TOP GLOBAL (TOTAL RANKING) - Absolute leaders regardless of sector
        if nearest_ok:
            lines.append("\n[U+1F3C6] <b>TOP GLOBAL (TOTAL RANKING)</b>")
            for ticker, data in nearest_ok[:5]:
                ticker_esc = html.escape(str(ticker))
                rs = data.get("rs_pct", data.get("score", 0))
                prox = data.get("proximity_score", 0)
                sec = _get_sec(ticker, data)
                lines.append(
                    f"• <code>{ticker_esc}</code> ({sec}) | Prox: <b>{prox:.0f}</b> | RS: <b>{rs:.0f}</b>"
                )

        # 3. VARIANTE E (DIVERGENCIA TEMÁTICA)
        variant_e_candidates = []
        for ticker, data in nearest_ok:
            # Variante E: Tema fuerte (Theme vs Sector > 2%) pero Sector débil (sector_etf_ok = False)
            if not data.get("sector_etf_ok", True) and (data.get("theme_vs_sector") or 0) > 0.02:
                variant_e_candidates.append((ticker, data))

        if variant_e_candidates:
            lines.append("\n[U+1F6E1] <b>VARIANTE E (DIVERGENCIA TEMÁTICA)</b>")
            lines.append("<i>Temas fuertes en sectores débiles (Plan E11)</i>")
            for ticker, data in sorted(
                variant_e_candidates, key=lambda x: x[1].get("theme_vs_sector", 0), reverse=True
            )[:3]:
                ticker_esc = html.escape(str(ticker))
                rs_divergence = data.get("theme_vs_sector", 0)
                sec = _get_sec(ticker, data)
                theme = data.get("best_theme", "N/A")
                lines.append(
                    f"• <code>{ticker_esc}</code> ({theme}) | Div: <b>{rs_divergence:+.1%}</b> vs {sec}"
                )

            # Crear el teclado inline
            row = []
            for ticker in rendered_tickers[:6]:
                row.append({"text": f"[U+1F50E] {ticker}", "callback_data": f"detail:{ticker}"})
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

        if nearest_warn:
            lines.append("\n[U+1F4E1] <b>DATA INCOMPLETE RADAR</b>")
            quality_map = {
                "rvol_1.0_default": "RVOL premarket no confiable",
                "adr_0": "ADR faltante",
                "zero_dollar_vol": "Dollar volume faltante",
                "missing_avg_volume_20d": "sin baseline volumen 20d",
                "dist_sma20_zero_suspect": "SMA20 suspect (0.0)",
            }

            for ticker, data in nearest_warn[:3]:
                ticker_esc = html.escape(str(ticker))
                sec = _get_sec(ticker, data)
                q_reasons = data.get("data_quality_reasons", [])
                if q_reasons:
                    motivo = ", ".join([quality_map.get(r, r) for r in q_reasons[:2]])
                else:
                    motivo = ", ".join(data.get("reasons", [])[:2]) or "Incompleto"

                motivo = html.escape(str(motivo))
                lines.append(
                    f"• <b>{ticker_esc}</b> ({sec}) | RS {data.get('rs_pct', 0):.0f} | {motivo}"
                )

        # 2. ALERTA TOP Section (basada solo en lo renderizado)
        if rendered_tickers:
            rendered_data = [(t, watchlist_detail[t]) for t in rendered_tickers]
            grouped_rendered = {}
            for t, d in rendered_data:
                grouped_rendered.setdefault(_get_sec(t, d), []).append((t, d))

            top_sec = sorted(
                grouped_rendered.keys(),
                key=lambda sec: (
                    hot_sector_order.get(sec, 99),
                    -max(
                        (d.get("proximity_score", 0) for _, d in grouped_rendered.get(sec, [])),
                        default=0,
                    ),
                    sec,
                ),
            )[0]
            top_sector_candidates = sorted(
                grouped_rendered[top_sec],
                key=lambda x: x[1].get("proximity_score", 0),
                reverse=True,
            )
            top_names = " / ".join(t for t, _ in top_sector_candidates[:3])

            # Blocker predominante y notas secundarias
            blocker_counts = {}
            rvol_notes = []
            sma20_notes = []
            for t, data in top_sector_candidates[:3]:
                blocker = data.get("primary_reason") or "OK"
                blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1

                # Notas específicas
                if "RVOL bajo" in data.get("reasons", []):
                    rvol_notes.append(t)
                if "Extendido de SMA20" in data.get("reasons", []):
                    sma20_notes.append(t)

            main_blocker = max(blocker_counts, key=blocker_counts.get)

            # Construir accion coherente
            if sma20_notes and rvol_notes:
                max_d = top_sector_candidates[0][1].get("max_dist_sma20", 6.77)
                action = f"Esperar Dist SMA20 <= {max_d:.2f}%"
                if rvol_notes:
                    action += f"; {', '.join(rvol_notes)} además RVOL >= 1.10"
            elif sma20_notes:
                max_d = top_sector_candidates[0][1].get("max_dist_sma20", 6.77)
                action = f"Esperar Dist SMA20 <= {max_d:.2f}%"
            elif rvol_notes:
                action = "Esperar RVOL >= 1.10"
            elif main_blocker == "Falta breakout":
                action = "Esperar Breakout"
            else:
                wait_msg = top_sector_candidates[0][1].get("waiting_for", "trigger live")
                action = (
                    f"Esperar {wait_msg}"
                    if main_blocker != "OK"
                    else "Monitorear Breakout live + RVOL"
                )

            lines.append(
                f"\n[U+1F6A8] <b>ALERTA TOP: Sector {top_sec}</b>\n"
                f"Candidatos: <code>{html.escape(top_names)}</code>\n"
                f"Blocker: <b>{html.escape(str(main_blocker))}</b>\n"
                f"Acción: <b>{html.escape(str(action))}</b>"
            )

        sector_flow = snapshot.get("sector_flow") or {}
        sf_rows = sector_flow.get("rows") or []
        if sf_rows:
            lines.append("\n[U+1F3DB] <b>SECTOR MONEY FLOW</b>")
            flow_secs = []
            for row in sf_rows[:5]:
                etf = row["sector_etf"]
                flow_secs.append(etf)
                name = html.escape(SECTOR_NAMES.get(etf, ""))
                drift = row.get("rank_drift", 0)
                trend = "[U+1F525] [UP]" if drift > 0 else "[SNOW] [DOWN]" if drift < 0 else "[RIGHT]"
                rs_drift = row.get("rs_drift", 0)
                rs_txt = f"{rs_drift:+.2%}" if rs_drift != 0 else "="
                lines.append(f"• <b>{etf} {name}</b> | {trend} | RS {rs_txt}")

            # Bloque compacto: TOP WATCHLIST POR FLOW
            all_detail = watchlist_detail
            gen_lines = []
            for etf in flow_secs:
                sec_candidates = [
                    t
                    for t, d in all_detail.items()
                    if _get_sec(t, d) == etf
                    and t not in rendered_tickers
                    and d.get("_display_status") == "ok"
                ]
                if sec_candidates:
                    top_gen = sorted(
                        sec_candidates,
                        key=lambda t: all_detail[t].get("proximity_score", 0),
                        reverse=True,
                    )[:3]
                    formatted_gen = []
                    for t in top_gen:
                        prox = all_detail[t].get("proximity_score", 0)
                        formatted_gen.append(f"<code>{t}</code> ({prox:.0f})")
                    gen_lines.append(f"• {etf}: " + ", ".join(formatted_gen))

            if gen_lines:
                lines.append("\n[U+1F52D] <b>TOP WATCHLIST POR FLOW</b>")
                lines.append(
                    "<i>Top por score sectorial; no necesariamente listos para trigger.</i>"
                )
                lines.extend(gen_lines)

        nearest_flow = snapshot.get("nearest_flow") or {}
        flow_rows = nearest_flow.get("rows") or []
        if flow_rows:
            prev_date = html.escape(str(nearest_flow.get("previous_date", "previo")))
            lines.append(f"\n[U+1F501] <b>NEAREST FLOW {prev_date} -> {date_esc}</b>")
            state_map = {
                "SIGNAL": "Signal",
                "STILL_NEAR": "Sigue top",
                "DROPPED": "Cayo",
                "DATA_BAD": "Data mala",
                "OUT_OF_RADAR": "Fuera radar",
            }

            for row in flow_rows[:top_n]:
                ticker = row.get("ticker", "?")
                ticker_esc = html.escape(str(ticker))
                state = html.escape(state_map.get(row.get("state"), str(row.get("state", "-"))))
                drift = row.get("rank_drift", 0)
                if drift == "NEW":
                    trend = "[U+1F195] "
                elif drift == "OUT":
                    trend = "[FAIL] "
                else:
                    try:
                        dv = int(drift)
                        trend = f"[UP]{dv:+} " if dv > 0 else f"[DOWN]{dv:+} " if dv < 0 else "[RIGHT] "
                    except:
                        trend = "[RIGHT] "

                prev_rank = row.get("previous_rank", "-")
                waiting = html.escape(str(row.get("current_waiting_for", "N/A")))
                px = row.get("price_delta_pct", "N/A")

                lines.append(
                    f"• {trend}<b>{ticker_esc}</b> (Prev R{prev_rank}) | {state} | Wait: <code>{waiting}</code>"
                )

    # PIPELINE STATUS Block
    scanner_uni_count = snapshot.get("scanner_universe_count")
    is_stale = False
    try:
        from src.scanner.universe_loader import DB_PATH
        import pandas as pd
        from pathlib import Path

        db_path = Path(DB_PATH)
        if not db_path.exists() or db_path.stat().st_size == 0:
            is_stale = True
        else:
            # Simple query to get latest date
            import sqlite3

            conn = sqlite3.connect(db_path)
            res = conn.execute("SELECT MAX(date) FROM ohlcv_cache").fetchone()
            latest_date_str = res[0] if res else None
            conn.close()
            if latest_date_str:
                latest_ts = pd.to_datetime(latest_date_str)
                trade_ts = pd.to_datetime(snapshot.get("date"))
                b_days = len(pd.bdate_range(start=latest_ts, end=trade_ts)) - 1
                if b_days > 3:
                    is_stale = True
            else:
                is_stale = True
    except:
        pass

    status_parts = []
    status_parts.append(f"{snapshot.get('universe_size', 0)} Finviz")
    if scanner_uni_count is not None:
        status_parts.append(f"{scanner_uni_count} DB")
    if is_stale:
        status_parts.append("[WARN] DB stale")

    status_line = " | ".join(status_parts)
    lines.append(f"\n[U+1F527] <b>PIPELINE STATUS</b>\nScanner: {status_line}")

    # Botones finales
    buttons.append(
        [
            {"text": "[U+1F504] Refresh", "callback_data": "refresh:market"},
            {"text": "[BOLT] Regen All", "callback_data": "regenerate:market"},
            {"text": "[U+1F9EA] Shadow Audit", "callback_data": "shadow_audit:market"},
        ]
    )

    return "\n".join(lines), buttons


if __name__ == "__main__":
    import sys

    # Permitir ejecutarlo directamente: python3 src/utils/terminal_gui.py path/to/snapshot.json
    if len(sys.argv) > 1:
        print_terminal_brief(sys.argv[1])
