from __future__ import annotations

import json
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.dynamic_config import load_production_config
from src.paper.demo_portfolio import load_state
from src.data.theme_taxonomy import THEME_MAP, get_themes
from src.signals.thematic_logic import calculate_equal_weighted_index
from src.signals.signal_engine import calculate_dynamic_sizing_factor

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MONITOR_ROOT = PROJECT_ROOT / "outputs" / "telegram_monitor"
DEMO_ROOT = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"
LIVE_SIGNALS_ROOT = PROJECT_ROOT / "outputs" / "live_signals"
FINVIZ_DIR = PROJECT_ROOT / "outputs" / "paper_finviz"

WATCHLIST_PAGE_SIZE = 6

_E25_BUCKETS = [
    ("Z1", 6.76),
    ("Z2", 10.0),
    ("Z3", 15.0),
    ("Z4", 25.0),
    ("Z5", 35.0),
    ("Z6", 50.0),
]

GICS_TO_ETF = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

ETF_TO_NAME = {
    "XLK": "Tecnología",
    "XLF": "Financiero",
    "XLV": "Salud",
    "XLE": "Energía",
    "XLY": "Consumo Discr",
    "XLP": "Consumo Básico",
    "XLI": "Industrial",
    "XLB": "Materiales",
    "XLRE": "Inmobiliario",
    "XLU": "Utilities",
    "XLC": "Comunicaciones",
    "SPY": "Market",
}

_TICKER_TO_ETF = None


def _get_ticker_to_etf():
    global _TICKER_TO_ETF
    if _TICKER_TO_ETF is not None:
        return _TICKER_TO_ETF

    csv_path = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
    if not csv_path.exists():
        _TICKER_TO_ETF = {}
        return _TICKER_TO_ETF

    try:
        df = pd.read_csv(csv_path)
        ticker_to_gics = dict(zip(df["Symbol"], df["GICS Sector"]))
        _TICKER_TO_ETF = {t: GICS_TO_ETF[s] for t, s in ticker_to_gics.items() if s in GICS_TO_ETF}
    except Exception:
        _TICKER_TO_ETF = {}

    return _TICKER_TO_ETF


def _get_theme_rs_vs_etf(ticker: str, date: str, lookback: int = 20) -> float | None:
    etf = _get_ticker_to_etf().get(ticker)
    if not etf:
        return None

    themes = get_themes(ticker)
    if not themes:
        return None

    # Get all members of themes the ticker belongs to
    theme_members = set()
    for theme in themes:
        for t, th_list in THEME_MAP.items():
            if theme in th_list:
                theme_members.add(t)

    if not theme_members:
        return None

    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(db_path)
        all_tickers = list(theme_members) + [etf]
        placeholders = ",".join("?" * len(all_tickers))

        as_of_ts = pd.Timestamp(date)
        start_ts = as_of_ts - pd.Timedelta(days=lookback + 30)

        query = f"""
            SELECT ticker, date, close 
            FROM ohlcv_cache 
            WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?
        """
        df = pd.read_sql_query(
            query, conn, params=all_tickers + [start_ts.strftime("%Y-%m-%d"), date]
        )
        conn.close()

        if df.empty:
            return None

        pivot = df.pivot(index="date", columns="ticker", values="close").sort_index()
        member_cols = [c for c in pivot.columns if c in theme_members]
        if not member_cols:
            return None

        theme_index = calculate_equal_weighted_index(pivot, member_cols)
        if theme_index.empty:
            return None

        if etf not in pivot.columns:
            return None
        e_prices = pivot[etf].dropna()

        common_dates = theme_index.dropna().index.intersection(e_prices.index)
        if len(common_dates) < 2:
            return None

        end_idx = common_dates[-1]
        start_dt_idx = max(0, len(common_dates) - lookback - 1)
        start_idx = common_dates[start_dt_idx]

        t_ret = (theme_index.loc[end_idx] / theme_index.loc[start_idx]) - 1
        e_ret = (e_prices.loc[end_idx] / e_prices.loc[start_idx]) - 1

        return t_ret - e_ret
    except Exception as e:
        logger.error(f"Error in _get_theme_rs_vs_etf for {ticker}: {e}")
        return None


def _normalize_source_system(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"finviz", "finviz_vps", "vps"}:
        return "finviz_vps"
    return "local_pit"


def _source_badge(source_system: str) -> str:
    return "[FINVIZ]" if source_system == "finviz_vps" else "[LOCAL]"


def _e25_bucket(dist_sma20: float) -> str:
    try:
        value = float(dist_sma20)
    except Exception:
        return "Z1"
    for bucket, upper in _E25_BUCKETS:
        if value <= upper:
            return bucket
    return "Z6"


def _e25_state(
    dist_sma20: float, sizing_factor: float, sizing_reason: str, combo_cfg: dict | None = None
) -> str:
    t3 = (combo_cfg or {}).get("tier3_fixed", {})
    if not t3.get("use_dynamic_extension_sizing", False):
        return "DESACTIVADO"
    try:
        value = float(dist_sma20)
    except Exception:
        return "BLOQUEADO"
    comfort = float(t3.get("dynamic_extension_sizing", {}).get("comfort_pct", 6.76))
    valley = float(t3.get("dynamic_extension_sizing", {}).get("valley_pct", 10.0))
    mid = float(t3.get("dynamic_extension_sizing", {}).get("mid_pct", 15.0))
    high = float(t3.get("dynamic_extension_sizing", {}).get("high_pct", 25.0))
    extreme = float(t3.get("dynamic_extension_sizing", {}).get("extreme_pct", 35.0))
    max_pct = float(t3.get("dynamic_extension_sizing", {}).get("max_pct", 50.0))

    if sizing_factor <= 0:
        return "BLOQUEADO"
    if value <= comfort:
        return "SALUDABLE"
    if value <= valley:
        return "VALLE"
    if value <= mid:
        return "BREAKOUT"
    if value <= high:
        return "EXTREMO"
    if value <= max_pct:
        return "EXTREMO" if value <= extreme else "EXTREMO"
    return "BLOQUEADO"


def _e25_treatment(sizing_factor: float) -> str:
    if sizing_factor <= 0:
        return "BLOQUEADO"
    if sizing_factor <= 0.15:
        return "ULTRALIGHT"
    if sizing_factor < 1.0:
        return "PENALIZADO"
    return "NORMAL"


def _e25_fields(signal: dict[str, Any], combo_cfg: dict | None = None) -> dict[str, Any]:
    t3 = (combo_cfg or {}).get("tier3_fixed", {})
    dist = float(
        signal.get("dist_sma20", signal.get("dist_sma20_pct", signal.get("gate_dist_sma20", 0)))
        or 0
    )
    adr = float(signal.get("adr_pct", signal.get("gate_adr_pct", signal.get("adr", 0))) or 0)
    sizing_factor, sizing_reason = calculate_dynamic_sizing_factor(dist, adr, combo_cfg or {})
    risk_budget = float(signal.get("raw_risk_budget_usd", signal.get("risk_budget_usd", 0)) or 0)
    risk_budget = round(risk_budget, 2)
    if risk_budget <= 0 and signal.get("risk_budget_usd") is not None:
        risk_budget = float(signal.get("risk_budget_usd", 0) or 0)
    position_size = int(float(signal.get("position_size", signal.get("shares", 0)) or 0))
    initial_size = int(float(signal.get("initial_size", position_size) or position_size))
    if initial_size <= 0 and sizing_factor > 0:
        initial_size = position_size

    return {
        "dist_sma20": round(dist, 2),
        "adr_pct": round(adr, 2),
        "sizing_factor": round(float(sizing_factor), 2),
        "sizing_reason": sizing_reason,
        "risk_budget_usd": round(
            float(signal.get("risk_budget_usd", risk_budget) or risk_budget), 2
        ),
        "raw_risk_budget_usd": round(
            float(signal.get("raw_risk_budget_usd", risk_budget) or risk_budget), 2
        ),
        "risk_per_share": round(
            float(signal.get("risk_per_share", signal.get("stop_loss", 0)) or 0), 4
        ),
        "initial_size": initial_size,
        "position_size": position_size,
        "extension_bucket": _e25_bucket(dist),
        "e25_state": _e25_state(dist, sizing_factor, sizing_reason, combo_cfg),
        "e25_treatment": _e25_treatment(sizing_factor),
    }


def _annotate_source(
    signal: dict[str, Any], source_system: str, source_label: str
) -> dict[str, Any]:
    item = dict(signal)
    item["source_system"] = source_system
    item["source_label"] = source_label
    item["source_badge"] = _source_badge(source_system)
    return item


def _load_local_watchlist_signals(date: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    resolved = resolve_monitor_date(date)
    signals: list[dict[str, Any]] = []
    if resolved:
        status_path = MONITOR_ROOT / resolved / "market_status.json"
        data = _load_json(status_path)
        if data and "watchlist_detail" in data:
            for ticker, detail in data["watchlist_detail"].items():
                if _is_watchlist_candidate(detail):
                    signals.append(
                        _annotate_source(
                            _map_premarket_detail_to_signal(ticker, detail, resolved),
                            "local_pit",
                            "LOCAL/PIT",
                        )
                    )

        live_path = _resolve_live_signals_date(date)
        if live_path:
            csv_path = LIVE_SIGNALS_ROOT / live_path / "combined.csv"
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path).where(pd.notnull(pd.read_csv(csv_path)), None)
                    if not df.empty:
                        for row in df.to_dict(orient="records"):
                            ticker = str(row.get("ticker", "")).strip()
                            if not ticker:
                                continue
                            signals.append(_annotate_source(row, "local_pit", "LOCAL/PIT"))
                except Exception as e:
                    logger.warning(f"Error loading local combined.csv for {live_path}: {e}")

    return resolved, signals


def _load_finviz_watchlist_signals(date: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    resolved = date or latest_date(FINVIZ_DIR)
    if not resolved:
        return None, []
    snapshot = _load_json(FINVIZ_DIR / resolved / "snapshot.json") or {}
    signals: list[dict[str, Any]] = []

    for ticker, detail in (snapshot.get("watchlist_detail") or {}).items():
        if not ticker:
            continue
        enriched = dict(detail)
        enriched.setdefault("ticker", ticker)
        enriched.setdefault("entry_price", detail.get("price", detail.get("entry_price", 0)))
        enriched.setdefault("entry_score", detail.get("score", 0))
        enriched.setdefault("source_universe", "finviz")
        signals.append(_annotate_source(enriched, "finviz_vps", "FINVIZ/VPS"))

    for row in snapshot.get("signals", []):
        ticker = str(row.get("ticker", "")).strip()
        if not ticker:
            continue
        item = dict(row)
        item.setdefault("source_universe", "finviz")
        signals.append(_annotate_source(item, "finviz_vps", "FINVIZ/VPS"))

    return resolved, signals


def _merge_watchlist_sources(
    *groups: tuple[str | None, list[dict[str, Any]]],
) -> tuple[str | None, list[dict[str, Any]]]:
    resolved_dates = [resolved for resolved, rows in groups if resolved and rows]
    resolved = (
        max(resolved_dates)
        if resolved_dates
        else next((resolved for resolved, _ in groups if resolved), None)
    )
    merged: list[dict[str, Any]] = []
    for _, rows in groups:
        merged.extend(rows)
    return resolved, merged


def _aggregate_watchlist_signals(signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for signal in signals:
        ticker = str(signal.get("ticker", "")).upper()
        if not ticker:
            continue
        bucket = aggregated.setdefault(ticker, {"ticker": ticker, "sources": {}})
        source_system = _normalize_source_system(signal.get("source_system"))
        bucket["sources"][source_system] = signal
        if "best" not in bucket:
            bucket["best"] = signal
        else:
            best_score = float(bucket["best"].get("entry_score", 0) or 0)
            score = float(signal.get("entry_score", 0) or 0)
            if score > best_score:
                bucket["best"] = signal
    return aggregated


def _collapse_watchlist_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated = _aggregate_watchlist_signals(signals)
    collapsed: list[dict[str, Any]] = []
    for ticker, bucket in aggregated.items():
        best = dict(bucket["best"])
        systems = sorted(bucket["sources"].keys())
        badges = ["[LOCAL]" if s == "local_pit" else "[FINVIZ]" for s in systems]
        best["source_systems"] = systems
        best["source_badges"] = " ".join(badges)
        best["source_system"] = systems[0] if len(systems) == 1 else "dual"
        collapsed.append(best)
    return sorted(collapsed, key=lambda s: float(s.get("entry_score", 0) or 0), reverse=True)


def _render_signal_line(signal: dict[str, Any]) -> str:
    score = float(signal.get("entry_score", 0) or 0)
    dist = float(
        signal.get("dist_sma20", signal.get("dist_sma20_pct", signal.get("gate_dist_sma20", 0)))
        or 0
    )
    factor = float(signal.get("sizing_factor", 1.0) or 1.0)
    bucket = signal.get("extension_bucket", _e25_bucket(dist))
    badge = signal.get("source_badges") or signal.get(
        "source_badge", _source_badge(signal.get("source_system", "local_pit"))
    )
    return (
        f"{badge} ★{score:.0f} Dist:<code>{dist:+.1f}%</code> SF:<code>{factor:.2f}</code> {bucket}"
    )


def _dated_dirs(base: Path) -> list[Path]:
    import re

    if not base.exists():
        return []
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    return sorted(
        [p for p in base.iterdir() if p.is_dir() and pattern.match(p.name)], key=lambda p: p.name
    )


def latest_date(base: Path) -> str | None:
    dirs = _dated_dirs(base)
    return dirs[-1].name if dirs else None


def resolve_monitor_date(date: str | None = None) -> str | None:
    return date or latest_date(MONITOR_ROOT)


def resolve_demo_date(date: str | None = None) -> str | None:
    if date:
        return date
    state = load_state()
    if state.date:
        return state.date
    return latest_date(DEMO_ROOT)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def load_monitor_snapshot(date: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    resolved = resolve_monitor_date(date)
    if not resolved:
        return None, None
    payload = _load_json(MONITOR_ROOT / resolved / "market_status.json")
    return resolved, payload


def load_prealerts(date: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    resolved = resolve_monitor_date(date)
    if not resolved:
        return None, []
    payload = _load_json(MONITOR_ROOT / resolved / "prealerts.json") or {}
    return resolved, list(payload.get("signals", []))


def _resolve_live_signals_date(date: str | None = None) -> str | None:
    """Find latest date directory under live_signals/."""
    if date:
        if (LIVE_SIGNALS_ROOT / date).is_dir():
            return date
        return None
    return latest_date(LIVE_SIGNALS_ROOT)


def _map_premarket_detail_to_signal(ticker: str, detail: dict, date: str) -> dict[str, Any]:
    # El combo en pre-market es siempre "Pre-A→B" — la cascada corre en live
    combo_label = "Pre-A→B"

    reasons = detail.get("reasons", [])
    waiting = detail.get("waiting_for", "")
    primary_reason = detail.get("primary_reason", "")

    # Determine if really blocked or passed
    has_blockers = False
    if reasons:
        if any(r and r != "OK" for r in reasons):
            has_blockers = True
    if waiting and waiting != "OK":
        has_blockers = True
    if primary_reason and primary_reason != "OK":
        has_blockers = True

    gate_status = "BLOCKED" if has_blockers else "PASS"

    # Usar el motivo real del snapshot en lugar de hardcodear
    if reasons:
        gate_reason = "; ".join(reasons[:2]) if any(r and r != "OK" for r in reasons) else "OK"
    elif waiting and waiting != "OK":
        gate_reason = waiting
    elif primary_reason:
        gate_reason = primary_reason
    else:
        gate_reason = "OK" if not has_blockers else "screener_fail:qullamaggie_momentum=FAIL"

    if not primary_reason and reasons:
        primary_reason = reasons[0]

    return {
        "ticker": ticker.upper(),
        "agent_name": combo_label,
        "entry_score": detail.get("score", 0.0),
        "proximity_score": detail.get("proximity_score", 0.0),
        "entry_price": detail.get("price", 0.0),
        "breakout_level": detail.get("breakout_level", 0.0),
        "rvol": detail.get("rvol", 0.0),
        "live_volume": 0,
        "signal_date": date,
        "source_universe": "finviz",
        "decision_source": "finviz_premarket",
        "data_quality_status": detail.get("data_quality_status", "ok"),
        "sector_etf": detail.get("sector_etf", "OTHER"),
        "dollar_vol_M": detail.get("dollar_volume_m", 0.0),
        "dist_sma20": detail.get("dist_sma20_pct", 0.0),
        "waiting_for": waiting,
        "primary_reason": primary_reason,
        "live_trigger_status": "WAIT",
        "entry_gate_status": gate_status,
        "entry_gate_reason": gate_reason,
        "entry_gate_source": "premarket",
        "gate_rs_percentile": detail.get("rs_pct", detail.get("score")),
        "gate_adr_pct": detail.get("adr", 0.0),
        "gate_dollar_vol_M": detail.get("dollar_volume_m", 0.0),
        "gate_dist_sma20": detail.get("dist_sma20_pct", 0.0),
        "gate_sector_etf_dist": detail.get("sector_etf_dist_pct"),
        "combos": detail.get("combos", []),
        "sizing_factor": detail.get("sizing_factor", 1.0),
        "sizing_reason": detail.get("sizing_reason", ""),
        "risk_budget_usd": detail.get("risk_budget_usd"),
    }


def _is_watchlist_candidate(detail: dict) -> bool:
    """Filtra tickers del universo completo para quedarse solo con candidatos reales."""
    proximity = float(detail.get("proximity_score", 0) or 0)
    reasons = detail.get("reasons", [])
    rs_pct = float(detail.get("rs_pct", 0) or 0)
    waiting = detail.get("waiting_for", "OK")

    # Excluir errores de cálculo
    if any("No se pudo calcular" in r for r in reasons):
        return False

    # Excluir tickers con demasiados blockers — no son candidatos reales
    if len(reasons) >= 3:
        return False

    # Candidato real: alta proximidad al setup (máximo 1-2 blockers permitidos)
    if proximity >= 70:
        return True

    # RS elite + moderadamente cerca (máximo 2 blockers, ya garantizado arriba)
    if rs_pct >= 90 and proximity >= 50:
        return True

    return False


# Umbrales
_MAX_DIST_SMA20 = 6.77  # igual que producción
_DIST_MODERATE = 15.0  # sobre este valor = largo plazo


def _enrich_with_history(signals: list[dict], date: str) -> list[dict]:
    """
    Enriquece cada signal con datos históricos de candidate_state:
    setup_age, tendencia de dist_sma20, status histórico.
    Si no hay DB o el ticker no tiene historia, los campos quedan en None.
    """
    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    if not db_path.exists():
        return signals  # VPS sin DB — no enriquecer, no romper

    tickers = [s.get("ticker", "").upper() for s in signals if s.get("ticker")]
    if not tickers:
        return signals

    try:
        import sqlite3

        conn = sqlite3.connect(db_path)

        # Traer los últimos 10 días de cada ticker para calcular tendencia
        placeholders = ",".join(["?"] * len(tickers))
        df = pd.read_sql_query(
            f"""
            SELECT ticker, date, setup_age, dist_sma20_pct, status, near_breakout
            FROM candidate_state
            WHERE ticker IN ({placeholders})
              AND date <= ?
            ORDER BY ticker, date DESC
            """,
            conn,
            params=tickers + [date],
        )
        conn.close()
    except Exception as e:
        logger.warning(f"_enrich_with_history: error reading candidate_state: {e}")
        return signals

    if df.empty:
        return signals

    # Construir dict por ticker con los últimos N días
    history: dict[str, dict] = {}
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date", ascending=False)
        latest = grp.iloc[0]

        # Tendencia dist_sma20: comparar hoy vs hace 5 días
        dist_today = latest["dist_sma20_pct"]
        dist_5d_ago = grp.iloc[min(4, len(grp) - 1)]["dist_sma20_pct"]
        dist_trend = None
        if dist_today is not None and dist_5d_ago is not None:
            dist_trend = round(float(dist_today) - float(dist_5d_ago), 1)
            # Negativo = consolidando (bueno) | Positivo = extendiéndose (malo)

        history[ticker.upper()] = {
            "setup_age": int(latest["setup_age"]) if latest["setup_age"] else 0,
            "db_status": latest["status"],  # BUILDING|NEAR|CONFIRMED
            "near_breakout": bool(latest["near_breakout"]),
            "dist_trend_5d": dist_trend,  # None si sin historia
            "days_in_list": len(grp),  # cuántos días tiene data
        }

    # Enriquecer cada signal
    for s in signals:
        ticker = s.get("ticker", "").upper()
        h = history.get(ticker, {})
        s["_setup_age"] = h.get("setup_age", 0)
        s["_db_status"] = h.get("db_status")
        s["_near_breakout"] = h.get("near_breakout", False)
        s["_dist_trend_5d"] = h.get("dist_trend_5d")  # negativo = mejorando
        s["_days_in_list"] = h.get("days_in_list", 0)

    return signals


def _classify_urgency(signal: dict, system: str | None = None) -> tuple[str, str, str]:
    """
    Retorna (tier, badge_html, evolution_badge_html)
    tier       : "A" | "B" | "C"
    badge      : badge principal de urgencia
    evo_badge  : badge de evolución (vacío si sin historia o sin movimiento)

    Si system="B", se usa el umbral de la config E25 (comfort_pct) en vez del
    global _MAX_DIST_SMA20 para la clasificación por extensión.
    """
    reasons = signal.get("reasons") or []
    dist_sma = float(signal.get("dist_sma20", signal.get("gate_dist_sma20", 0)) or 0)
    gate = signal.get("entry_gate_status", "BLOCKED")

    # Datos históricos (pueden ser None si sin DB)
    setup_age = signal.get("_setup_age", 0) or 0
    db_status = signal.get("_db_status")
    dist_trend = signal.get("_dist_trend_5d")  # negativo = consolidando
    near_bo = signal.get("_near_breakout", False)

    # ── Umbral de extensión según sistema ─────────────────────────────────
    # System B (E25) permite hasta 35.0% (extensión mitigada por sizing).
    # System A (Padre) usa _MAX_DIST_SMA20 (6.77%).
    if system == "B":
        max_dist = 35.0
    else:
        max_dist = _MAX_DIST_SMA20

    has_dist  = dist_sma > max_dist
    has_ma    = any("MA stack" in r or "MA Stack" in r for r in reasons)
    has_bkout = any("breakout" in r.lower() for r in reasons)
    has_rvol = any("RVOL" in r for r in reasons)

    # ── Badge de evolución ────────────────────────────────────────────────
    evo_badge = ""

    if setup_age >= 3:
        if dist_trend is not None and dist_trend <= -5.0:
            # Consolidando activamente — dist bajó ≥5% en 5 días
            evo_badge = f"📈 <i>Consolidando {abs(dist_trend):.1f}% en 5d</i>"
        elif near_bo or db_status == "NEAR":
            evo_badge = f"⚡ <i>Cerca del trigger ({setup_age}d en lista)</i>"
        elif db_status == "CONFIRMED":
            evo_badge = f"🏆 <i>Confirmado ({setup_age}d)</i>"
        elif setup_age >= 7:
            # Lleva mucho tiempo sin moverse — puede estar perdiendo momentum
            evo_badge = f"⏳ <i>{setup_age}d en lista</i>"

    # ── Clasificación principal ───────────────────────────────────────────
    if gate == "PASS":
        return "A", "🟢 <b>ACTIVO</b>", evo_badge

    if has_rvol and not has_dist and not has_ma and not has_bkout:
        return "A", "🟢 <b>RVOL pendiente</b>", evo_badge

    if has_bkout and not has_dist and not has_ma:
        return "A", "🟡 <b>Esperar breakout</b>", evo_badge

    if has_dist and not has_ma and dist_sma <= _DIST_MODERATE:
        badge = "🟡 <b>Consolidar + RVOL</b>" if has_rvol else "🟡 <b>Consolidar</b>"
        return "B", badge, evo_badge

    if has_rvol and dist_sma <= _DIST_MODERATE and not has_ma:
        return "B", "🟡 <b>Consolidar + RVOL</b>", evo_badge

    return "C", "🔴 <b>Radar largo plazo</b>", evo_badge


def load_watchlist_signals(date: str | None = None) -> tuple[str | None, list[dict[str, Any]]]:
    """Load watchlist candidates from pre-market snapshots and merge live triggers on top."""
    local_signals: list[dict[str, Any]] = []
    finviz_signals: list[dict[str, Any]] = []

    resolved_local = date or resolve_monitor_date()
    if resolved_local:
        status_path = MONITOR_ROOT / resolved_local / "market_status.json"
        data = _load_json(status_path)
        if data and "watchlist_detail" in data:
            for ticker, detail in data["watchlist_detail"].items():
                if _is_watchlist_candidate(detail):
                    local_signals.append(
                        _annotate_source(
                            _map_premarket_detail_to_signal(ticker, detail, resolved_local),
                            "local_pit",
                            "LOCAL/PIT",
                        )
                    )

        resolved_live = _resolve_live_signals_date(date)
        if resolved_live:
            csv_path = LIVE_SIGNALS_ROOT / resolved_live / "combined.csv"
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)
                    df = df.where(pd.notnull(df), None)
                    if not df.empty:
                        for row in df.to_dict(orient="records"):
                            ticker = str(row.get("ticker", "")).strip()
                            if ticker:
                                local_signals.append(
                                    _annotate_source(row, "local_pit", "LOCAL/PIT")
                                )
                except Exception as e:
                    logger.warning(f"Error loading combined.csv for {resolved_live}: {e}")

    resolved_finviz = date or latest_date(FINVIZ_DIR)
    if resolved_finviz:
        snapshot = _load_json(FINVIZ_DIR / resolved_finviz / "snapshot.json") or {}
        for ticker, detail in (snapshot.get("watchlist_detail") or {}).items():
            if ticker:
                finviz_signals.append(
                    _annotate_source(
                        {**detail, "ticker": ticker},
                        "finviz_vps",
                        "FINVIZ/VPS",
                    )
                )
        for row in snapshot.get("signals", []):
            ticker = str(row.get("ticker", "")).strip()
            if ticker:
                finviz_signals.append(_annotate_source(row, "finviz_vps", "FINVIZ/VPS"))

    if not local_signals and not finviz_signals:
        resolved_pre_fallback, pre_signals = load_prealerts(date)
        if pre_signals:
            resolved_local = resolved_pre_fallback
            local_signals = [
                _annotate_source(ps, "local_pit", "LOCAL/PIT")
                for ps in pre_signals
                if ps.get("ticker")
            ]

    resolved_date = resolved_finviz or resolved_local or date
    return resolved_date, _collapse_watchlist_signals(local_signals + finviz_signals)


def load_demo_context(date: str | None = None) -> tuple[str | None, dict[str, Any]]:
    resolved = resolve_demo_date(date)
    if not resolved:
        return None, {}
    day_dir = DEMO_ROOT / resolved
    return resolved, {
        "portfolio_state": _load_json(day_dir / "portfolio_state.json") or {},
        "run_report": _load_json(day_dir / "run_report.json") or {},
        "positions": _load_csv(day_dir / "positions.csv"),
        "intents": _load_csv(day_dir / "execution_intents.csv"),
        "orders": _load_csv(day_dir / "orders.csv"),
        "fills": _load_csv(day_dir / "fills.csv"),
    }


def load_monitor_brief(date: str | None = None) -> tuple[str | None, dict[str, Any] | None]:
    resolved = resolve_monitor_date(date)
    if not resolved:
        return None, None
    payload = _load_json(MONITOR_ROOT / resolved / "premarket_brief.json")
    return resolved, payload


def build_market_message(date: str | None = None) -> tuple[str, list]:
    resolved, brief_data = load_monitor_brief(date)
    state = load_state()

    if resolved and brief_data and "brief" in brief_data:
        # Si existe el brief enriquecido (generado por finviz_monitor), lo usamos
        brief_text = brief_data["brief"]
        buttons = brief_data.get("buttons", [])
        return brief_text, buttons

    # Fallback al mensaje corto si no hay brief
    resolved, snapshot = load_monitor_snapshot(date)
    if not resolved or not snapshot:
        return "⚠️ <b>MARKET</b>\nNo monitor data available yet.", []

    warnings = snapshot.get("finviz_warnings") or []
    signals = snapshot.get("signals") or []
    top = signals[:5]

    status_icon = "🟢" if snapshot.get("regime_ok") else "🔴"

    lines = [
        f"🌐 <b>MARKET OVERVIEW | {resolved}</b>",
        "🧪 <b>SHADOW / E25</b>",
        f"STATUS: <code>SHADOW</code>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"{status_icon} <b>Regime Status:</b> {'<b>OK</b>' if snapshot.get('regime_ok') else '<b>BLOCKED</b>'}",
        f"📊 Universe Size: <code>{snapshot.get('universe_size', 0)}</code>",
        f"🛰 Monitor Signals: <code>{len(signals)}</code>",
        f"🛑 Demo Kill Switch: <code>{'ON' if state.kill_switch else 'OFF'}</code>",
    ]
    if warnings:
        lines.append("\n⚠️ <b>Warnings:</b>")
        for warning in warnings[:3]:
            lines.append(f"• {warning}")
    if top:
        lines.append("\n🔥 <b>Top Candidates:</b>")
        lines.append("<pre>")
        lines.append(f"{'Ticker':<7} {'Combo':<12} {'Entry':<8} {'Stop'}")
        lines.append(f"{'-' * 7} {'-' * 12} {'-' * 8} {'-' * 6}")
        for signal in top:
            ticker = signal.get("ticker", "?")
            combo = signal.get("combo", signal.get("combo_name", "n/a"))[:12]
            entry = float(signal.get("entry_price", 0) or 0)
            stop = float(signal.get("stop_loss", signal.get("stop_price", 0)) or 0)
            lines.append(f"{ticker:<7} {combo:<12} {entry:<8.2f} {stop:.2f}")
        lines.append("</pre>")

    e25_audit = snapshot.get("e25_audit") or {}
    if e25_audit:
        systems = e25_audit.get("systems", {})
        finviz = systems.get("finviz_vps", {})
        local = systems.get("local_pit", {})
        lines.append("\n🧪 <b>SHADOW / E25 AUDIT</b>")
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
    return "\n".join(lines), []


def _get_sector_status(etf: str, date: str) -> tuple[bool, float] | None:
    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT close FROM ohlcv_cache WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 40"
        df = pd.read_sql_query(query, conn, params=(etf, date))
        conn.close()
        if len(df) < 20:
            return None
        # Must sort ASC for rolling() to work correctly
        df = df.sort_values("date")
        sma = df["close"].rolling(20).mean().iloc[-1]
        curr = df["close"].iloc[-1]
        return curr > sma, (curr / sma) - 1
    except Exception:
        return None


def _build_grouped_signals_lines(signals: list, date: str, limit: int = 15) -> list[str]:
    ticker_to_etf = _get_ticker_to_etf()
    groups: dict[str, list[dict]] = {}
    no_etf = []

    for s in signals:
        ticker = s.get("ticker")
        etf = ticker_to_etf.get(ticker)
        if etf:
            if etf not in groups:
                groups[etf] = []
            groups[etf].append(s)
        else:
            no_etf.append(s)

    lines = []
    # Sort groups by ETF name
    for etf in sorted(groups.keys()):
        sector_name = ETF_TO_NAME.get(etf, etf)

        # Sector status
        s_status = _get_sector_status(etf, date)
        s_icon = ""
        s_dist_text = ""
        if s_status is not None:
            ok, dist = s_status
            s_icon = " 🟢" if ok else " 🔴"
            s_dist_text = f" ({dist:+.1%})"

        lines.append(f"<b>{etf} — {sector_name}</b>{s_icon}{s_dist_text}")

        for s in groups[etf][:limit]:
            ticker = s["ticker"]
            themes = get_themes(ticker)
            theme_str = f"Temas: {', '.join(themes)}" if themes else "(no theme)"
            rs_val = s.get("rs_rating", s.get("rs_20d", "??"))

            theme_rs = _get_theme_rs_vs_etf(ticker, date)
            rs_icon = ""
            rs_text = ""
            if theme_rs is not None:
                # Theme RS is vs Sector ETF
                rs_icon = " ✅" if theme_rs > 0 else " ⚠️"
                rs_text = f" | RS vs Sector: {theme_rs:+.1%}"

            lines.append(f"  <code>{ticker:<5}</code> RS:{rs_val} | {theme_str}{rs_text}{rs_icon}")
        lines.append("")

    if no_etf:
        lines.append("<b>Sin sector mapeado</b>")
        for s in no_etf[:limit]:
            ticker = s["ticker"]
            themes = get_themes(ticker)
            theme_str = f"Temas: {', '.join(themes)}" if themes else "(no theme)"
            lines.append(f"  <code>{ticker:<5}</code> {theme_str}")

    return lines

def build_watchlist_message(date: str | None = None, page: int = 1, system: str | None = None) -> tuple[str, list]:
    """Build paginated watchlist message. Returns (text, buttons)."""
    resolved, signals = load_watchlist_signals(date)
    if not resolved:
        return "⚠️ <b>WATCHLIST</b>\nNo signal data available yet.", []

    if system is not None:
        filtered_signals = []
        for s in signals:
            combos = s.get("combos") or []
            agent_name = s.get("agent_name") or ""
            combos_str = str(combos)
            if system == "A":
                if "Qulla" in combos_str or "combo_pure_momentum" in agent_name or agent_name == "A":
                    filtered_signals.append(s)
            elif system == "B":
                if "Minervini" in combos_str or "combo_stage2_breakout" in agent_name or agent_name == "B":
                    filtered_signals.append(s)
        signals = filtered_signals

    if not signals:
        sys_prefix = "[SISTEMA A] " if system == "A" else "[SISTEMA B] " if system == "B" else ""
        return (
            f"🧭 <b>{sys_prefix}WATCHLIST | {resolved}</b>\n"
            f"<i>(Manual Review)</i>\n\n"
            f"No watchlist candidates for this date.",
            [],
        )

    signals = [dict(s, **_e25_fields(s)) for s in signals]
    signals = _enrich_with_history(signals, resolved)

    for s in signals:
        tier, badge, evo_badge = _classify_urgency(s, system=system)
        s["_urgency_tier"]  = tier
        s["_urgency_badge"] = badge
        s["_evo_badge"] = evo_badge  # ← NUEVO

    cnt = {"A": 0, "B": 0, "C": 0}
    for s in signals:
        cnt[s["_urgency_tier"]] += 1

    tier_order = {"A": 0, "B": 1, "C": 2}
    signals = sorted(
        signals,
        key=lambda s: (
            tier_order.get(s.get("_urgency_tier", "C"), 2),
            -float(s.get("entry_score", 0) or 0),
        ),
    )

    total = len(signals)
    total_pages = max(1, (total + WATCHLIST_PAGE_SIZE - 1) // WATCHLIST_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * WATCHLIST_PAGE_SIZE
    end_idx = start_idx + WATCHLIST_PAGE_SIZE
    page_signals = signals[start_idx:end_idx]

    # Header enriquecido con conteo por tier
    sys_prefix = "[SISTEMA A] " if system == "A" else "[SISTEMA B] " if system == "B" else ""
    lines = [
        f"🧭 <b>{sys_prefix}WATCHLIST | {resolved}</b>",
        f"<i>Grouped by Sector · Page {page}/{total_pages}</i>\n",
        f"🔍 Candidates: <code>{total}</code>  "
        f"🟢<code>{cnt['A']}</code> 🟡<code>{cnt['B']}</code> 🔴<code>{cnt['C']}</code>\n",
    ]
    lines = _build_shadow_audit_lines(resolved) + lines

    # Group page signals by sector ETF
    lines.extend(_build_watchlist_grouped_lines(page_signals, resolved, system=system))

    # Footer stats
    scores = [float(s.get("entry_score", 0) or 0) for s in signals]
    if scores:
        lines.append(
            f"\n📊 Top: <code>{max(scores):.0f}</code> | "
            f"Avg: <code>{sum(scores) / len(scores):.0f}</code> | "
            f"Showing {start_idx + 1}-{min(end_idx, total)} of {total}"
        )

    # Pagination buttons
    buttons = _watchlist_pagination_buttons(page, total_pages)
    return "\n".join(lines), buttons


def _build_watchlist_grouped_lines(signals: list, date: str, system: str | None = None) -> list[str]:
    """Build enriched watchlist lines grouped by sector ETF."""
    ticker_to_etf = _get_ticker_to_etf()
    groups: dict[str, list[dict]] = {}
    no_etf: list[dict] = []

    for s in signals:
        ticker = s.get("ticker", "")
        # Try sector_etf from CSV first, then lookup
        etf = s.get("sector_etf") or ticker_to_etf.get(ticker)
        if etf:
            groups.setdefault(etf, []).append(s)
        else:
            no_etf.append(s)

    lines: list[str] = []
    for etf in sorted(groups.keys()):
        sector_name = ETF_TO_NAME.get(etf, etf)
        s_status = _get_sector_status(etf, date)
        s_icon = ""
        s_dist_text = ""
        if s_status is not None:
            ok, dist = s_status
            s_icon = " 🟢" if ok else " 🔴"
            s_dist_text = f" ({dist:+.1%})"

        lines.append(f"<b>{etf} — {sector_name}</b>{s_icon}{s_dist_text}")

        for s in groups[etf]:
            ticker = s.get("ticker", "?")
            score = float(s.get("entry_score", 0) or 0)
            entry = float(s.get("entry_price", 0) or 0)
            adr = float(s.get("gate_adr_pct", 0) or 0)
            gate_status = s.get("entry_gate_status", "")
            gate_icon = "✅" if gate_status == "PASS" else "⛔"
            urgency_badge = s.get("_urgency_badge", "")
            evo_badge = s.get("_evo_badge", "")

            # Theme RS enrichment
            themes = get_themes(ticker)
            theme_rs = _get_theme_rs_vs_etf(ticker, date)
            theme_line = ""
            if themes:
                theme_names = ", ".join(themes[:2])
                rs_part = ""
                if theme_rs is not None:
                    rs_icon = "✅" if theme_rs > 0 else "⚠️"
                    rs_part = f" {rs_icon} RS:{theme_rs:+.1%}"
                theme_line = f"\n         └ {theme_names}{rs_part}"

            # Badge de sizing para el Sistema B
            sizing_lbl = ""
            if system == "B":
                sf = s.get("sizing_factor")
                dist = s.get("dist_sma20", s.get("gate_dist_sma20", 0.0))
                dist_val = float(dist) if dist is not None else 0.0
                if sf is not None and float(sf) < 1.0:
                    sizing_lbl = f" <code>(Size: {float(sf):.0%} [Ext: {dist_val:.1f}%])</code>"
                elif dist_val > 6.76:
                    sizing_lbl = f" <code>(Ext: {dist_val:.1f}%)</code>"

            # Badge de urgencia en línea separada si no es PASS (no saturar los verdes)
            urgency_line = ""
            if gate_status != "PASS" and urgency_badge:
                urgency_line = f"\n         {urgency_badge}"

            evo_line = ""
            if evo_badge:
                evo_line = f"\n         {evo_badge}"

            lines.append(
                f"  <code>{ticker:<5}</code> ★{score:.0f}  "
                f"Entry:<code>{entry:.2f}</code>{sizing_lbl}  "
                f"ADR:<code>{adr:.1f}%</code> {gate_icon}"
                f"{theme_line}"
                f"{urgency_line}"
                f"{evo_line}"
            )
        lines.append("")

    if no_etf:
        lines.append("<b>Sin sector mapeado</b>")
        for s in no_etf:
            ticker = s.get("ticker", "?")
            score = float(s.get("entry_score", 0) or 0)
            entry = float(s.get("entry_price", 0) or 0)
            lines.append(f"  <code>{ticker:<5}</code> ★{score:.0f}  Entry:<code>{entry:.2f}</code>")
        lines.append("")

    return lines


def _build_dual_watchlist_header(signals: list[dict[str, Any]], resolved: str) -> list[str]:
    local = {
        str(s.get("ticker", "")).upper()
        for s in signals
        if _normalize_source_system(s.get("source_system")) == "local_pit"
    }
    finviz = {
        str(s.get("ticker", "")).upper()
        for s in signals
        if _normalize_source_system(s.get("source_system")) == "finviz_vps"
    }
    overlap = sorted(local & finviz)
    local_only = sorted(local - finviz)
    finviz_only = sorted(finviz - local)
    lines = [
        f"🧭 <b>DUAL VIEW | {resolved}</b>",
        f"LOCAL/PIT: <code>{len(local)}</code> | FINVIZ/VPS: <code>{len(finviz)}</code>",
        f"Overlap: <code>{len(overlap)}</code> | Local-only: <code>{len(local_only)}</code> | Finviz-only: <code>{len(finviz_only)}</code>",
        f"Badges: [LOCAL] [FINVIZ]",
    ]
    if overlap:
        lines.append(f"Overlap tickers: <code>{', '.join(overlap[:8])}</code>")
    if local_only:
        lines.append(f"Local divergences: <code>{', '.join(local_only[:6])}</code>")
    if finviz_only:
        lines.append(f"Finviz divergences: <code>{', '.join(finviz_only[:6])}</code>")
    return lines


def _build_shadow_audit_lines(date: str | None) -> list[str]:
    resolved, snapshot = load_monitor_snapshot(date)
    if not resolved or not snapshot:
        return []
    e25_audit = snapshot.get("e25_audit") or {}
    if not e25_audit:
        return []
    systems = e25_audit.get("systems", {})
    finviz = systems.get("finviz_vps", {})
    local = systems.get("local_pit", {})
    overlap = e25_audit.get("overlap_tickers") or []
    lines = [
        "🧪 <b>SHADOW / E25 AUDIT</b>",
        f"FINVIZ/VPS: <code>{finviz.get('signals', 0)}</code> | SF <code>{finviz.get('avg_sizing_factor', 1.0):.2f}</code> | blocked <code>{finviz.get('blocked_extremes', 0)}</code> | ultra <code>{finviz.get('ultralight', 0)}</code>",
        f"LOCAL/PIT: <code>{local.get('signals', 0)}</code> | SF <code>{local.get('avg_sizing_factor', 1.0):.2f}</code> | blocked <code>{local.get('blocked_extremes', 0)}</code> | ultra <code>{local.get('ultralight', 0)}</code>",
    ]
    if overlap:
        lines.append(f"Overlap: <code>{', '.join(overlap[:8])}</code>")
    return lines


def _watchlist_pagination_buttons(page: int, total_pages: int) -> list[list[dict]]:
    """Build pagination buttons for watchlist."""
    if total_pages <= 1:
        return [[{"text": "🔄 Refresh", "callback_data": "refresh:watchlist"}]]

    nav_row: list[dict] = []
    if page > 1:
        nav_row.append({"text": "◀️", "callback_data": f"watchlist_page:{page - 1}"})
    nav_row.append({"text": f"{page}/{total_pages}", "callback_data": "noop"})
    if page < total_pages:
        nav_row.append({"text": "▶️", "callback_data": f"watchlist_page:{page + 1}"})
    nav_row.append({"text": "🔄", "callback_data": "refresh:watchlist"})
    return [nav_row]


def build_watchlist_detail(ticker: str, date: str | None = None) -> str:
    """Build detailed card for a single ticker from watchlist signals."""
    resolved, signals = load_watchlist_signals(date)
    if not resolved or not signals:
        return f"⚠️ <b>WATCHLIST</b>\nNo data for <code>{ticker.upper()}</code>."

    # Find the ticker in signals
    match = None
    for s in signals:
        if s.get("ticker", "").upper() == ticker.upper():
            match = s
            break

    if not match:
        return (
            f"⚠️ <b>WATCHLIST | {resolved}</b>\n"
            f"<code>{ticker.upper()}</code> not found in today's candidates."
        )

    local_match = None
    finviz_match = None
    for s in signals:
        if s.get("ticker", "").upper() != ticker.upper():
            continue
        system = _normalize_source_system(s.get("source_system"))
        if system == "local_pit":
            local_match = s
        elif system == "finviz_vps":
            finviz_match = s

    score = float(match.get("entry_score", 0) or 0)
    proximity = float(match.get("proximity_score", 0) or 0)
    entry = float(match.get("entry_price", 0) or 0)
    breakout = float(match.get("breakout_level", 0) or 0)
    combo = match.get("agent_name", "n/a")
    rvol = float(match.get("rvol", 0) or 0)
    adr = float(match.get("gate_adr_pct", 0) or 0)
    rs = float(match.get("gate_rs_percentile", 0) or 0)
    dist_sma = float(match.get("dist_sma20", 0) or 0)
    dvol = float(match.get("gate_dollar_vol_M", match.get("dollar_vol_M", 0)) or 0)
    etf = match.get("sector_etf", "n/a")
    gate = match.get("entry_gate_status", "n/a")
    import html

    gate_reason = html.escape(match.get("entry_gate_reason", ""))
    waiting = html.escape(match.get("waiting_for", ""))
    primary_reason = html.escape(match.get("primary_reason", ""))
    gate_sector_dist = match.get("gate_sector_etf_dist", "")

    gate_icon = "✅" if gate == "PASS" else "⛔"
    local_panel = (
        f"[LOCAL] {_render_signal_line(dict(local_match, **_e25_fields(local_match)))}"
        if local_match
        else ""
    )
    finviz_panel = (
        f"[FINVIZ] {_render_signal_line(dict(finviz_match, **_e25_fields(finviz_match)))}"
        if finviz_match
        else ""
    )

    # Sector status
    sector_line = f"Sector: <code>{etf}</code>"
    if etf and etf != "n/a":
        s_status = _get_sector_status(etf, resolved)
        if s_status is not None:
            ok, dist = s_status
            s_ico = "🟢" if ok else "🔴"
            sector_line = f"Sector: <code>{etf}</code> {s_ico} ({dist:+.1%})"

    # Theme info
    themes = get_themes(ticker.upper())
    theme_rs = _get_theme_rs_vs_etf(ticker.upper(), resolved)
    theme_line = "Theme: <i>(no theme)</i>"
    if themes:
        theme_names = ", ".join(themes[:3])
        theme_line = f"Theme: <code>{theme_names}</code>"
        if theme_rs is not None:
            rs_ico = "✅" if theme_rs > 0 else "⚠️"
            theme_line += f" {rs_ico} RS:{theme_rs:+.1%}"
            # Variant E check
            if etf and etf != "n/a":
                s_status_e = _get_sector_status(etf, resolved)
                if s_status_e is not None and theme_rs > 0 and not s_status_e[0]:
                    theme_line += "\nVariant E: <b>✅ Theme OK, Sector NO</b>"

    lines = [
        f"📋 <b>WATCHLIST DETAIL | {ticker.upper()}</b>",
        f"<i>{resolved}</i>\n",
        f"{'─' * 28}",
        local_panel,
        finviz_panel,
        f"{'─' * 28}",
        f"Score:  ★ <code>{score:.0f}</code>",
        f"Prox:   ★ <code>{proximity:.0f}</code>",
        f"Combo:  <code>{combo}</code>",
        f"Entry:  <code>${entry:.2f}</code>",
        f"Brkout: <code>${breakout:.2f}</code>",
        f"{'─' * 28}",
        f"ADR:    <code>{adr:.1f}%</code>",
        f"RVOL:   <code>{rvol:.1f}x</code>",
        f"RS:     <code>P{rs:.0f}</code>",
        f"Dist%:  <code>{dist_sma:+.1f}%</code>",
        f"E25:    <code>{match.get('e25_state', _e25_state(dist_sma, float(match.get('sizing_factor', 1.0) or 1.0), match.get('sizing_reason', '')))}</code>",
        f"Bucket: <code>{match.get('extension_bucket', _e25_bucket(dist_sma))}</code>",
        f"SF:     <code>{float(match.get('sizing_factor', 1.0) or 1.0):.2f}</code>",
        f"Risk:   <code>${float(match.get('risk_budget_usd', 0) or 0):.2f}</code>",
        f"InitSz: <code>{int(float(match.get('initial_size', match.get('position_size', 0)) or 0))}</code>",
        f"$Vol:   <code>${dvol:.1f}M</code>",
        f"{'─' * 28}",
        sector_line,
        theme_line,
        f"{'─' * 28}",
        f"Gate:   {gate_icon} <code>{gate}</code>",
    ]
    if gate_reason:
        if len(gate_reason) > 60:
            lines.append(f"Reason: <code>{gate_reason[:60]}</code>")
            lines.append(f"        <code>{gate_reason[60:120]}</code>")
        else:
            lines.append(f"Reason: <code>{gate_reason}</code>")
    if waiting:
        lines.append(f"Wait:   <code>{waiting[:60]}</code>")
    if primary_reason:
        lines.append(f"Setup:  <code>{primary_reason[:60]}</code>")

    tv_url = f"https://www.tradingview.com/symbols/{ticker.upper()}/"
    lines.append(f'\n📈 <a href="{tv_url}">Ver en TradingView</a>')

    return "\n".join(lines)


def build_monitor_signals_message(date: str | None = None, limit: int = 10) -> str:
    resolved, signals = load_prealerts(date)
    if not resolved:
        return "⚠️ <b>SIGNALS</b>\nNo monitor signals available yet."

    lines = [
        f"🧭 <b>MONITOR SIGNALS | {resolved}</b>",
        f"<i>(Observation Mode - Grouped by Sector)</i>\n",
        f"📡 Candidates: <code>{len(signals)}</code>\n",
    ]

    if not signals:
        lines.append("No monitor candidates available.")
        return "\n".join(lines)

    lines.extend(_build_grouped_signals_lines(signals, resolved, limit))
    return "\n".join(lines)


def build_signals_message(date: str | None = None, limit: int = 5) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>SIGNALS</b>\nNo demo candidates available yet."
    intents = ctx.get("intents", pd.DataFrame())
    if intents.empty:
        return f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>\nNo demo candidates available."
    pending = intents[intents["status"].astype(str).isin(["pending", "snoozed"])].copy()
    if pending.empty:
        return f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>\nNo pending demo candidates."

    lines = [
        f"🎯 <b>PENDING SIGNALS (DEMO) | {resolved}</b>",
        "🧪 <b>SHADOW / E25</b>",
        f"STATUS: <code>SHADOW</code>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"⏱ Pending: <code>{len(pending)}</code>",
    ]

    shadow_lines = _build_shadow_audit_lines(resolved)
    if shadow_lines:
        lines.extend([""] + shadow_lines + [""])

    lines.append("\n<pre>")
    lines.append(f"{'Ticker':<7} {'Status':<8} {'Entry':<8} {'Stop'}")
    lines.append(f"{'-' * 7} {'-' * 8} {'-' * 8} {'-' * 6}")
    for _, row in pending.head(limit).iterrows():
        ticker = row["ticker"]
        status = row.get("status", "pending")[:8]
        entry = float(row.get("entry_price_ref", 0) or 0)
        stop = float(row.get("stop_price", 0) or 0)
        dist = float(row.get("dist_sma20", row.get("dist_sma20_pct", 0)) or 0)
        adr = float(row.get("adr_pct", row.get("gate_adr_pct", 0)) or 0)
        factor, reason = calculate_dynamic_sizing_factor(dist, adr, load_production_config())
        lines.append(
            f"{ticker:<7} {status:<8} {entry:<8.2f} {stop:.2f} Dist:{dist:+.1f}% SF:{factor:.2f} {reason}"
        )
    lines.append("</pre>")
    return "\n".join(lines)


def build_portfolio_message(date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>PORTFOLIO</b>\nNo demo portfolio state available yet."
    state = ctx.get("portfolio_state") or {}
    metrics = state.get("metrics") or {}
    positions = ctx.get("positions", pd.DataFrame())
    open_positions = (
        positions[positions["status"].astype(str) == "open"]
        if not positions.empty
        else pd.DataFrame()
    )

    pnl = float(metrics.get("realized_pnl", 0) or 0)
    pnl_icon = "🟢" if pnl >= 0 else "🔴"

    lines = [
        f"💼 <b>PORTFOLIO STATUS | {resolved}</b>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"🔹 Status: <code>{state.get('status', 'idle')}</code>",
        f"🛑 Kill switch: <code>{'ON' if state.get('kill_switch') else 'OFF'}</code>",
        f"⏸ Entries paused: <code>{'ON' if state.get('entries_paused') else 'OFF'}</code>\n",
        f"📂 Open: <code>{metrics.get('open_positions', 0)}</code> | "
        f"🔒 Closed: <code>{metrics.get('closed_positions', 0)}</code>",
        f"⏱ Pending: <code>{metrics.get('pending_intents', 0)}</code> | "
        f"💤 Snoozed: <code>{metrics.get('snoozed_intents', 0)}</code>",
        f"{pnl_icon} Realized PnL: <b>${pnl:.2f}</b>",
    ]
    if not open_positions.empty:
        lines.append("\n📈 <b>Open Positions:</b>")
        lines.append("<pre>")
        lines.append(f"{'Ticker':<7} {'Qty':<4} {'Entry':<8} {'Stop'}")
        lines.append(f"{'-' * 7} {'-' * 4} {'-' * 8} {'-' * 6}")
        for _, row in open_positions.head(5).iterrows():
            ticker = row["ticker"]
            qty = int(float(row.get("qty", 0) or 0))
            entry = float(row.get("entry_price", 0) or 0)
            stop = float(row.get("stop_price", 0) or 0)
            lines.append(f"{ticker:<7} {qty:<4} {entry:<8.2f} {stop:.2f}")
        lines.append("</pre>")
    return "\n".join(lines)


def build_position_message(ticker: str, date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return f"⚠️ <b>POSITION</b>\nNo portfolio data for <code>{ticker}</code>."
    positions = ctx.get("positions", pd.DataFrame())
    if positions.empty:
        return f"⚠️ <b>POSITION | {resolved}</b>\nNo positions for <code>{ticker}</code>."
    mask = positions["ticker"].astype(str).str.upper() == ticker.upper()
    if not mask.any():
        return f"⚠️ <b>POSITION | {resolved}</b>\nNo positions for <code>{ticker}</code>."
    row = positions[mask].iloc[0]

    status_icon = "🟢" if row.get("status", "") == "open" else "🔒"

    lines = [
        f"📊 <b>POSITION DETAILS | {resolved}</b>",
        f"Ticker: <b>{row['ticker']}</b>",
        f"Status: {status_icon} <code>{row.get('status', 'unknown')}</code>",
        f"Qty: <code>{int(float(row.get('qty', 0) or 0))}</code>\n",
        f"Entry: <code>{float(row.get('entry_price', 0) or 0):.2f}</code>",
        f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>",
        f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code>",
        f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>\n",
        f"Entry trigger: <code>{row.get('entry_trigger', 'n/a')}</code>",
        f"Exit trigger: <code>{row.get('exit_trigger', 'n/a')}</code>",
        f"Confirmed by: <code>{row.get('confirmed_by', 'n/a')}</code>",
    ]
    return "\n".join(lines)


def build_paper_run_message(date: str | None = None) -> str:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return "⚠️ <b>PAPER RUN</b>\nNo demo run available yet."
    report = ctx.get("run_report") or {}
    metrics = report.get("metrics") or {}

    pnl = float(metrics.get("realized_pnl", 0) or 0)
    pnl_icon = "🟢" if pnl >= 0 else "🔴"

    lines = [
        f"📝 <b>PAPER RUN REPORT | {resolved}</b>",
        "🧪 <b>SHADOW / E25</b>",
        f"STATUS: <code>SHADOW</code>",
        f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>\n",
        f"🔹 Status: <code>{report.get('status', 'idle')}</code>",
        f"✅ Approved intents: <code>{report.get('approved_intents', 0)}</code>",
        f"❌ Rejected intents: <code>{report.get('rejected_intents', 0)}</code>",
        f"💤 Snoozed intents: <code>{report.get('snoozed_intents', 0)}</code>\n",
        f"📂 Open positions: <code>{report.get('open_positions', 0)}</code>",
        f"🔒 Closed positions: <code>{report.get('closed_positions', 0)}</code>",
        f"🛒 Orders: <code>{metrics.get('orders', 0)}</code> | 🔄 Fills: <code>{metrics.get('fills', 0)}</code>",
        f"{pnl_icon} Realized PnL: <b>${pnl:.2f}</b>",
    ]

    shadow_lines = _build_shadow_audit_lines(resolved)
    if shadow_lines:
        lines.append("\n")
        lines.extend(shadow_lines)

    return "\n".join(lines)


def build_signal_cards(date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return []
    intents = ctx.get("intents", pd.DataFrame())
    if intents.empty:
        return []
    pending = intents[intents["status"].astype(str).isin(["pending", "snoozed"])].copy()
    cards: list[dict[str, Any]] = []
    for _, row in pending.head(limit).iterrows():
        signal_id = str(row["signal_id"])
        dist = float(row.get("dist_sma20", row.get("dist_sma20_pct", 0)) or 0)
        adr = float(row.get("adr_pct", row.get("gate_adr_pct", 0)) or 0)
        factor, reason = calculate_dynamic_sizing_factor(dist, adr, load_production_config())
        text = (
            f"🎯 <b>{row['ticker']}</b> | {row['strategy_id']}\n"
            f"Entry: <code>{float(row.get('entry_price_ref', 0) or 0):.2f}</code>\n"
            f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>\n"
            f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code> | "
            f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>\n"
            f"Dist: <code>{dist:+.1f}%</code> | ADR: <code>{adr:.1f}%</code>\n"
            f"SF: <code>{factor:.2f}</code> | Reason: <code>{reason}</code>\n"
            f"Status: <code>{row.get('status', 'pending')}</code>"
        )
        cards.append(
            {
                "text": text,
                "buttons": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve_trade:{signal_id}"},
                        {"text": "❌ Reject", "callback_data": f"reject_trade:{signal_id}"},
                    ],
                    [
                        {"text": "💤 Snooze", "callback_data": f"snooze_trade:{signal_id}"},
                        {"text": "🔄 Refresh", "callback_data": "refresh:signals"},
                    ],
                ],
            }
        )
    return cards


def build_position_cards(date: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    resolved, ctx = load_demo_context(date)
    if not resolved:
        return []
    positions = ctx.get("positions", pd.DataFrame())
    if positions.empty:
        return []
    open_positions = positions[positions["status"].astype(str) == "open"].copy()
    cards: list[dict[str, Any]] = []
    for _, row in open_positions.head(limit).iterrows():
        position_id = str(row["position_id"])
        text = (
            f"📈 <b>{row['ticker']}</b>\n"
            f"Qty: <code>{int(float(row.get('qty', 0) or 0))}</code>\n"
            f"Entry: <code>{float(row.get('entry_price', 0) or 0):.2f}</code>\n"
            f"Stop: <code>{float(row.get('stop_price', 0) or 0):.2f}</code>\n"
            f"TP1: <code>{float(row.get('tp1_price', 0) or 0):.2f}</code> | "
            f"TP2: <code>{float(row.get('tp2_price', 0) or 0):.2f}</code>"
        )
        cards.append(
            {
                "text": text,
                "buttons": [
                    [
                        {"text": "🔒 Close", "callback_data": f"close_position:{position_id}"},
                        {"text": "🔄 Refresh", "callback_data": "refresh:portfolio"},
                    ]
                ],
            }
        )
    return cards
