import html
import json
from pathlib import Path

import pandas as pd
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.utils.data_quality import calculate_data_quality
from src.utils.gamma_scraper import fetch_gamma_data
from src.utils.sector_rotation import SectorRotationAnalyzer, get_ticker_sector_mapping

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
                "[green][U+2713][/green]" if data.get("breakout") else "[red][U+2717][/red]",
                _fmt_num(data.get("breakout_level")),
                "[green][U+2713][/green]" if data.get("ma_stack") else "[red][U+2717][/red]",
                str(data.get("ma_trigger", "OK")),
                _fmt_num(data.get("rvol")),
                _fmt_num(data.get("dist_sma20_pct"), "%"),
                "[green][U+2713][/green]" if data.get("sector_etf_ok", True) else "[red][U+2717][/red]",
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
                        except (TypeError, ValueError):
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
                    except (TypeError, ValueError):
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
            except (TypeError, ValueError):
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


# ── Constantes narrativas del brief ─────────────────────────────────────────
# Umbrales de interpretación del VIX (zonas de volatilidad)
VIX_CALM_THRESHOLD = 20.0
VIX_STRESS_THRESHOLD = 30.0

# Umbrales de interpretación del DIX (compra oculta institucional)
DIX_STRONG_THRESHOLD = 0.40
DIX_MODERATE_THRESHOLD = 0.35

# Tamaños del formato narrativo
NARRATIVE_HOT_SECTORS = 4
MAX_CANDIDATES_PER_SECTOR = 3
TOP_GLOBAL_NARRATIVE_SIZE = 3

# Parámetros técnicos por defecto
DEFAULT_MAX_DIST_SMA20 = 6.77
RVOL_MINIMO_TRIGGER = 1.0
GEX_TO_BILLIONS = 1e9

# Estados narrativos de los candidatos
ESTADO_TRIGGER_LISTO = "Trigger listo"
ESTADO_CONSOLIDAR = "Consolidar - no comprar aún"
ESTADO_ESPERANDO_RUPTURA = "Esperando ruptura"
ESTADO_ESPERANDO_VOLUMEN = "Esperando volumen"
ESTADO_DATOS_INCOMPLETOS = "Datos incompletos"

EMOJI_ESTADO = {
    ESTADO_TRIGGER_LISTO: "✅",
    ESTADO_CONSOLIDAR: "⏸",
    ESTADO_ESPERANDO_RUPTURA: "⏳",
    ESTADO_ESPERANDO_VOLUMEN: "📉",
    ESTADO_DATOS_INCOMPLETOS: "⚠️",
}

SEM_FAVORABLE = "ENTORNO FAVORABLE"
SEM_CAUTELA = "ENTORNO DE CAUTELA"
SEM_BLOQUEADO = "ENTORNO BLOQUEADO"


def _to_float(value, default=None):
    """Convierte un valor a float de forma tolerante.

    Propósito: evitar excepciones con datos faltantes o corruptos del snapshot.
    Parámetros: value (valor a convertir), default (retorno si no es convertible).
    Retorna: float o default.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _semaphore_state(regime_ok: bool, breadth: dict) -> str:
    """Determina la etiqueta del semáforo de entorno.

    Propósito: resumir el régimen en favorable/cautela/bloqueado para humanos.
    Parámetros: regime_ok (gate del sistema), breadth (diccionario con 'vix').
    Retorna: etiqueta del semáforo (str).
    """
    vix = _to_float((breadth or {}).get("vix"))
    if not regime_ok or (vix is not None and vix >= VIX_STRESS_THRESHOLD):
        return SEM_BLOQUEADO
    if vix is None:
        return SEM_CAUTELA
    if vix < VIX_CALM_THRESHOLD:
        return SEM_FAVORABLE
    return SEM_CAUTELA


def _narrativa_vix(vix) -> str:
    """Traduce el valor del VIX a una interpretación narrativa.

    Propósito: que el lector entienda el entorno sin conocer el indicador.
    Parámetros: vix (valor numérico o None).
    Retorna: frase explicativa (str).
    """
    if vix is None:
        return "Sin datos de VIX hoy: el radar de volatilidad está apagado, se recomienda cautela."
    if vix < VIX_CALM_THRESHOLD:
        return (
            f"VIX en {vix:.2f} (zona tranquila): el mercado opera sin miedo y deja buscar "
            "oportunidades con comodidad."
        )
    if vix < VIX_STRESS_THRESHOLD:
        return (
            f"VIX en {vix:.2f} (zona nerviosa): hay tensión en el mercado; conviene operar "
            "liviano y solo los mejores setups."
        )
    return (
        f"VIX en {vix:.2f} (zona de pánico): el mercado está defendiéndose; prioridad en "
        "proteger capital y esperar a que pase la tormenta."
    )


def _narrativa_gex(gex_raw) -> str:
    """Traduce el Gamma Exposure a una interpretación narrativa.

    Propósito: explicar si el GEX actúa como piso o techo para el mercado.
    Parámetros: gex_raw (GEX en dólares crudos).
    Retorna: frase explicativa (str).
    """
    gex_b = float(gex_raw) / GEX_TO_BILLIONS
    if gex_b > 0:
        return (
            f"GEX de <b>${gex_b:.1f}B</b> positivo: las caídas encuentran compradores rápido; "
            "actúa como un <b>piso de soporte</b> para el mercado."
        )
    return (
        f"GEX de <b>${gex_b:.1f}B</b> negativo: los movimientos se amplifican en ambas "
        "direcciones; actúa como un <b>techo de volatilidad</b> que frena los rebotes."
    )


def _narrativa_dix(dix: float) -> str:
    """Traduce el DIX (Dark Pool IndicateX) a una interpretación narrativa.

    Propósito: explicar qué está haciendo el dinero institucional oculto.
    Parámetros: dix (proporción de compra oculta, 0-1).
    Retorna: frase explicativa (str).
    """
    pct = dix * 100.0
    if dix >= DIX_STRONG_THRESHOLD:
        return (
            f"{pct:.1f}% del volumen fue compra oculta en Dark Pool: hay <b>acumulación "
            "institucional activa</b>; el smart money sigue posicionado."
        )
    if dix >= DIX_MODERATE_THRESHOLD:
        return (
            f"{pct:.1f}% del volumen fue compra oculta en Dark Pool: acumulación moderada; "
            "el dinero institucional observa sin comprometerse."
        )
    return (
        f"Solo {pct:.1f}% del volumen fue compra oculta en Dark Pool: el smart money está "
        "mayormente esperando; poca convicción institucional."
    )


def _estado_narrativo(data: dict) -> tuple[str, str, str]:
    """Clasifica un candidato en un estado narrativo accionable.

    Propósito: reemplazar estados técnicos por lenguaje natural con motivo numérico.
    Parámetros: data (diccionario de watchlist_detail del candidato).
    Retorna: tupla (estado, motivo, acción sugerida), todas en texto natural.
    """
    dist = _to_float(data.get("dist_sma20_pct"))
    max_dist = _to_float(data.get("max_dist_sma20"), DEFAULT_MAX_DIST_SMA20)
    nivel = _to_float(data.get("breakout_level"), 0.0)
    precio = _to_float(data.get("price"), 0.0)
    rvol = _to_float(data.get("rvol"))
    reason = str(data.get("primary_reason") or "").lower()

    if data.get("_display_status") == "warn":
        return (
            ESTADO_DATOS_INCOMPLETOS,
            "faltan datos clave para validar el setup",
            "Revisar datos antes de operar",
        )

    # Extendido sobre su media: dejar enfriar antes de comprar
    if (dist is not None and abs(dist) > max_dist) or "extendido" in reason:
        extension = abs(dist) if dist is not None else 0.0
        return (
            ESTADO_CONSOLIDAR,
            f"precio extendido {extension:.2f}% sobre su media, límite sano: {max_dist:.2f}%",
            "Esperar que se enfríe hacia la media antes de re-evaluar",
        )

    gap = ((nivel / precio) - 1.0) * 100.0 if precio > 0 and nivel > 0 else 0.0

    # Aún no rompió su nivel clave
    if not data.get("breakout"):
        return (
            ESTADO_ESPERANDO_RUPTURA,
            f"a {gap:.2f}% de romper {nivel:.2f}",
            f"Vigilar ruptura de {nivel:.2f} con volumen",
        )

    # Ruptura confirmada pero sin volumen suficiente
    if rvol is not None and rvol < RVOL_MINIMO_TRIGGER:
        return (
            ESTADO_ESPERANDO_VOLUMEN,
            (
                f"rompió {nivel:.2f} pero el volumen relativo es {rvol:.2f} "
                f"(mínimo sano: {RVOL_MINIMO_TRIGGER:.2f})"
            ),
            "Esperar entrada de volumen que confirme la ruptura",
        )

    # Setup completo: listo para disparar
    rvol_txt = f"{rvol:.2f}" if rvol is not None else "n/d"
    return (
        ESTADO_TRIGGER_LISTO,
        f"a {gap:.2f}% de su nivel clave {nivel:.2f}, con volumen relativo {rvol_txt}",
        f"Entrada al romper {nivel:.2f} con volumen",
    )


def _join_natural(nombres: list) -> str:
    """Une nombres en formato natural en español ('A y B', 'A, B y C').

    Propósito: listar tickers legibles dentro de frases narrativas.
    Parámetros: nombres (lista de strings).
    Retorna: string unido de forma natural.
    """
    if len(nombres) <= 1:
        return ", ".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def build_telegram_brief(snapshot: dict, top_n: int = 5, hq_n: int = 5) -> tuple[str, list]:
    """Construye un brief pre-market narrativo para Telegram (parse_mode=HTML).

    Propósito: reemplazar el reporte técnico por un relato human-friendly con 8
    secciones: Header, Semáforo, Rastro Institucional, Sectores en Rotación,
    Candidatos del Día, Alerta Prioritaria, Top Global y Footer.

    Parámetros:
        snapshot: dict del pipeline con date/breadth/watchlist_detail/etc.
        top_n: presupuesto máximo de candidatos a mostrar.
        hq_n: se mantiene por compatibilidad con callers existentes (sin uso).

    Retorna: tupla (texto_html, botones_inline) para el cliente de Telegram.
    """
    date = snapshot.get("date", "n/a")
    data_as_of = snapshot.get("data_as_of")
    regime_ok = snapshot.get("regime_ok", False)
    watchlist_detail = snapshot.get("watchlist_detail", {})
    breadth = snapshot.get("breadth") or {}
    universe_size = snapshot.get("universe_size", 0)

    date_esc = html.escape(str(date))
    lines: list = []

    # ── 1. Header ────────────────────────────────────────────────────────
    header = f"🚀 <b>MOMENTUM SIGNALS</b> | {date_esc}"
    if data_as_of and data_as_of != date:
        header += (
            f"\n<i>Datos al cierre del {html.escape(str(data_as_of))} · "
            f"Universo: {universe_size} activos</i>"
        )
    else:
        header += f"\n<i>Universo: {universe_size} activos</i>"
    lines.append(header)

    # ── 2. Semáforo de entorno ───────────────────────────────────────────
    semaphore = _semaphore_state(regime_ok, breadth)
    vix = _to_float(breadth.get("vix")) if breadth else None
    accion_entorno = {
        SEM_FAVORABLE: "Momento de <b>buscar breakouts</b>, no de quedarse mirando.",
        SEM_CAUTELA: "Entorno exigente: <b>operar liviano</b> y solo lo mejor del radar.",
        SEM_BLOQUEADO: (
            "El sistema está <b>bloqueado</b>: prioridad en proteger capital, no en entrar."
        ),
    }[semaphore]
    lines.append(
        f"\n🚦 <b>SEMÁFORO: {semaphore}</b>\n"
        f"{_narrativa_vix(vix)}\n"
        f"{accion_entorno}"
    )

    # ── Datos externos: Gamma/Dark Pool y sectores calientes ────────────
    gamma_data = fetch_gamma_data()
    hot_sectors = _build_hot_sectors(str(date), top_n=NARRATIVE_HOT_SECTORS)
    hot_etfs = {row["sector_etf"] for row in hot_sectors}
    hot_sector_order = {row["sector_etf"]: idx for idx, row in enumerate(hot_sectors)}

    # ── 3. Rastro Institucional ──────────────────────────────────────────
    if gamma_data:
        dix_line = _narrativa_dix(float(gamma_data["dix"]))
        gex_line = _narrativa_gex(float(gamma_data["gex"]))
        lines.append(f"\n🏛 <b>RASTRO INSTITUCIONAL</b>\n{gex_line}\n{dix_line}")
    else:
        lines.append(
            "\n🏛 <b>RASTRO INSTITUCIONAL</b>\nSin datos de Gamma/Dark Pool disponibles hoy."
        )

    # ── 4. Sectores en Rotación ──────────────────────────────────────────
    if hot_sectors:
        rotacion = ["\n📊 <b>SECTORES EN ROTACIÓN</b>"]
        for idx, row in enumerate(hot_sectors, 1):
            etf = row["sector_etf"]
            nombre = SECTOR_NAMES.get(etf, etf)
            fuego = " 🔥" if row.get("tradeable") else ""
            rotacion.append(f"{idx}. {nombre} ({etf}) → Fuerza {row.get('rs', 0):.0%}{fuego}")
        lines.append("\n".join(rotacion))
    else:
        lines.append("\n📊 <b>SECTORES EN ROTACIÓN</b>\nSin datos de rotación sectorial hoy.")

    # ── Clasificación de calidad y resolución de sectores ───────────────
    nearest_ok = []
    nearest_warn = []
    for ticker, data in watchlist_detail.items():
        status, _ = calculate_data_quality(data)
        if status == "bad":
            continue
        data["_display_status"] = status
        (nearest_warn if status == "warn" else nearest_ok).append((ticker, data))

    nearest_ok.sort(key=lambda x: x[1].get("proximity_score", 0), reverse=True)

    # Resolución de sectores perezosa: solo consultar el mapeo si falta dato
    sin_sector = [t for t, d in watchlist_detail.items() if not d.get("sector_etf")]
    resolved_sectors = get_ticker_sector_mapping(sin_sector) if sin_sector else {}

    def _get_sec(ticker, data):
        return data.get("sector_etf") or resolved_sectors.get(ticker) or "OTHER"

    # ── 5. Candidatos del Día (agrupados por sector caliente) ───────────
    lines.append("\n🎯 <b>CANDIDATOS DEL DÍA</b>")
    rendered_tickers = []
    presupuesto = top_n
    if nearest_ok and hot_sectors:
        by_sector = {}
        for ticker, data in nearest_ok:
            by_sector.setdefault(_get_sec(ticker, data), []).append((ticker, data))

        # Solo sectores calientes: los líderes fuera de la rotación van a Top Global
        for sec in [h["sector_etf"] for h in hot_sectors]:
            if presupuesto <= 0:
                break
            sec_cands = by_sector.get(sec)
            if not sec_cands:
                continue
            sec_info = next((h for h in hot_sectors if h["sector_etf"] == sec), None)
            sec_nombre = SECTOR_NAMES.get(sec, sec)
            fuego = " 🔥" if (sec_info or {}).get("tradeable") else ""
            lines.append(f"\n→ <b>Sector {sec_nombre}{fuego}</b>")

            sec_cands = sorted(
                by_sector[sec], key=lambda x: x[1].get("proximity_score", 0), reverse=True
            )[:MAX_CANDIDATES_PER_SECTOR]
            for ticker, data in sec_cands:
                if presupuesto <= 0:
                    break
                presupuesto -= 1
                rendered_tickers.append(ticker)
                estado, motivo, accion = _estado_narrativo(data)
                emoji = EMOJI_ESTADO.get(estado, "•")
                rs = _to_float(data.get("rs_pct", data.get("score", 0)), 0.0)
                nivel = _to_float(data.get("breakout_level"), 0.0)
                precio = _to_float(data.get("price"), 0.0)
                themes = data.get("themes") or []
                tema_txt = f" ({', '.join(themes)})" if themes else ""
                ticker_esc = html.escape(str(ticker))
                motivo_esc = html.escape(motivo)
                accion_esc = html.escape(accion)
                lines.append(
                    f"• <b>{ticker_esc}</b>{tema_txt} · Fuerza Relativa {rs:.0f}/100\n"
                    f"{emoji} <b>Estado: {estado}</b>\n"
                    f"→ Motivo: {motivo_esc}\n"
                    f"→ Nivel de ruptura: {nivel:.2f} | Precio actual: {precio:.2f}\n"
                    f"→ Acción sugerida: {accion_esc}"
                )
    if len(rendered_tickers) == 0:
        lines.append("Sin candidatos validados hoy; el radar sigue trabajando.")

    # ── 6. Alerta Prioritaria ────────────────────────────────────────────
    lines.append("\n🚨 <b>ALERTA PRIORITARIA</b>")
    if rendered_tickers and hot_sectors:
        rendered_set = set(rendered_tickers)
        sec_top = min(
            (_get_sec(t, watchlist_detail[t]) for t in rendered_tickers),
            key=lambda s: (hot_sector_order.get(s, 99), s),
        )
        foco = [
            t
            for t in rendered_tickers
            if _get_sec(t, watchlist_detail[t]) == sec_top
        ]
        resto = [t for t in rendered_tickers if t not in rendered_set]
        nombres_foco = _join_natural([html.escape(t) for t in foco])
        sec_nombre = SECTOR_NAMES.get(sec_top, sec_top)
        detalle_resto = ""
        if resto:
            detalle_resto = f"\n<i>En espera: {_join_natural(resto)} aún no tienen trigger.</i>"
        lines.append(
            f"Sector {sec_nombre} concentra el mejor momentum del mercado hoy.\n"
            f"→ <b>Acción:</b> vigilar {nombres_foco} → si rompen su nivel clave "
            f"<b>con volumen</b>, son los primeros en gatillar señal de entrada."
            f"{detalle_resto}"
        )
    elif hot_sectors:
        sec_nombre = SECTOR_NAMES.get(hot_sectors[0]["sector_etf"], hot_sectors[0]["sector_etf"])
        lines.append(
            f"Sector {sec_nombre} lidera la rotación, pero ningún candidato pasó el filtro.\n"
            f"→ <b>Acción:</b> vigilar el sector sin apurar entradas."
        )
    else:
        lines.append(
            "Mercado sin rotación clara hoy.\n"
            "→ <b>Acción:</b> mantener la pólvora seca hasta que aparezcan líderes."
        )

    # ── 7. Top Global (fuera de sectores calientes) ──────────────────────
    lines.append("\n🏆 <b>TOP GLOBAL (fuera de sectores calientes)</b>")
    globales = (
        [(t, d) for t, d in nearest_ok if _get_sec(t, d) not in hot_etfs]
        if hot_sectors
        else list(nearest_ok)
    )
    globales.sort(key=lambda x: x[1].get("rs_pct", x[1].get("score", 0)), reverse=True)
    globales = globales[:TOP_GLOBAL_NARRATIVE_SIZE]
    if globales:
        for ticker, data in globales:
            rs = _to_float(data.get("rs_pct", data.get("score", 0)), 0.0)
            sec = _get_sec(ticker, data)
            sec_nombre = SECTOR_NAMES.get(sec, sec)
            ticker_esc = html.escape(str(ticker))
            lines.append(f"• <b>{ticker_esc}</b> ({sec_nombre}) → Fuerza {rs:.0f}/100")
        lines.append("<i>Fuerzas altas fuera de la rotación principal: vigilar sin apurar.</i>")
    else:
        lines.append("Sin líderes relevantes fuera de la rotación por ahora.")

    # ── 8. Footer ────────────────────────────────────────────────────────
    lines.append(
        "\n<i>Reporte informativo, no es asesoría de inversión.</i>\n"
        "\n📖 <b>CÓMO LEER ESTE REPORTE</b>\n"
        "• <b>Fuerza Relativa (RS)</b>: performance del ticker vs el mercado; 90+ = liderazgo.\n"
        "• <b>RVOL</b>: volumen relativo vs su promedio; 1.00+ confirma interés real.\n"
        "• <b>Nivel de ruptura</b>: precio clave que, al superarse con volumen, dispara señal.\n"
        "• <b>DIX/GEX</b>: huella del dinero institucional (Dark Pool) y del mercado de opciones."
    )

    # Botones inline con emojis reales (contrato preservado para el caller)
    buttons: list = []
    fila_detalle = []
    for ticker in rendered_tickers[:6]:
        fila_detalle.append({"text": f"🔎 {ticker}", "callback_data": f"detail:{ticker}"})
        if len(fila_detalle) == 2:
            buttons.append(fila_detalle)
            fila_detalle = []
    if fila_detalle:
        buttons.append(fila_detalle)
    buttons.append(
        [
            {"text": "🔄 Refresh", "callback_data": "refresh:market"},
            {"text": "♻️ Regen All", "callback_data": "regenerate:market"},
            {"text": "🧪 Shadow Audit", "callback_data": "shadow_audit:market"},
        ]
    )

    return "\n".join(lines), buttons



if __name__ == "__main__":
    import sys

    # Permitir ejecutarlo directamente: python3 src/utils/terminal_gui.py path/to/snapshot.json
    if len(sys.argv) > 1:
        print_terminal_brief(sys.argv[1])
