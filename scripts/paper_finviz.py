#!/usr/bin/env python3
"""
PAPER TRADING - UNIVERSO FINVIZ (sistema paralelo, separado)
Usa Finviz como universo dinamico. NO mezclar con paper_local_db ni con backtest.
Objetivo: detectar si Finviz descubre oportunidades que el universo local no captura.
El drift gate esta desactivado aqui (bloque_on_high_drift=False).

Usage:
    python3 scripts/paper_finviz.py --phase pre
    python3 scripts/paper_finviz.py --phase pre --drift-override 100
    python3 scripts/paper_finviz.py --phase pre --rs-min 60   # aflojar RS threshold
Outputs -> outputs/paper_finviz/
"""

import argparse, copy, json, logging, sys, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.data.finviz_universe_provider import fetch_finviz_universe
from src.utils.market_context_live import get_market_context_live, apply_regime_override
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.data.ticker_cache import TickerCache
from src.config.dynamic_config import load_production_config, flatten_config
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS
from src.utils.terminal_gui import print_terminal_brief
from src.utils.data_quality import calculate_data_quality as shared_calculate_quality
from src.signals.thematic_logic import calculate_equal_weighted_index
from src.signals.signal_engine import calculate_dynamic_sizing_factor


def get_etf_dists(date_str: str, sma_period: int = 20) -> dict:
    """Calcula las distancias a la SMA20 para todos los ETFs directamente, para asegurar metadatos en auditoria."""
    import yfinance as yf

    dists = {}
    try:
        as_of = pd.Timestamp(date_str)
        start = (as_of - timedelta(days=sma_period * 2)).strftime("%Y-%m-%d")
        end_fetch = (as_of + timedelta(days=1)).strftime("%Y-%m-%d")

        etf_data = yf.download(SECTOR_ETFS, start=start, end=end_fetch, progress=False)["Close"]
        if isinstance(etf_data.columns, pd.MultiIndex):
            etf_data.columns = etf_data.columns.get_level_values(0)

        for etf in SECTOR_ETFS:
            if etf in etf_data.columns:
                s = etf_data[etf].ffill()
                if len(s) >= sma_period:
                    sma = s.rolling(sma_period).mean().iloc[-1]
                    dist = (s.iloc[-1] / sma) - 1.0
                    dists[etf] = dist
    except Exception as e:
        logger.warning(f"Error fetching ETF dists for audit: {e}")
    return dists


OUT_DIR = ROOT / "outputs" / "paper_finviz"
DB_PATH = ROOT / "data" / "ticker_cache.db"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR = ROOT / "config" / "combos"
OUT_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
ACTIVE_COMBOS = ["combo_pure_momentum", "combo_stage2_breakout"]
INITIAL_CAPITAL = 100_000


def pre_warm_cache(universe: list[str], date_str: str):
    """Refresca cache de forma inteligente: salta tickers que ya tienen data reciente."""
    logger.info(f"    [Pre-warm] Analizando frescura de cache para {len(universe)} tickers...")
    cache = TickerCache()
    as_of = pd.Timestamp(date_str)
    start = (as_of - timedelta(days=300)).strftime("%Y-%m-%d")

    # 1. Obtener estado actual de la DB para estos tickers
    conn = sqlite3.connect(cache.db_path)
    placeholders = ",".join(["?"] * len(universe))
    query = f"SELECT ticker, MAX(date) as last_date FROM ohlcv_cache WHERE ticker IN ({placeholders}) GROUP BY ticker"
    df_status = pd.read_sql_query(query, conn, params=universe)
    conn.close()

    last_dates = dict(zip(df_status["ticker"], df_status["last_date"]))

    # 2. Decidir cuales necesitan update
    to_update = []
    for t in universe:
        if t not in last_dates:
            to_update.append(t)
            continue

        last_ts = pd.to_datetime(last_dates[t])
        days_diff = (as_of - last_ts).days
        if days_diff >= 1:
            to_update.append(t)

    if not to_update:
        logger.info("    [Pre-warm] Todo el universo esta al dia. Saltando descargas.")
        return

    logger.info(f"    [Pre-warm] Refrescando {len(to_update)} tickers desactualizados usando descargas en lote...")
    try:
        cache.update_ohlcv_batch(to_update, start, date_str)
    except Exception as e:
        logger.error(f"Error during batch pre-warm: {e}")
    logger.info("    [Pre-warm] Cache de batch completado.")


def _nearest_candidates_from_snapshot(snapshot: dict, limit: int = 5) -> list[tuple[str, dict]]:
    """Replica el criterio visual de NEAREST TO SIGNAL para poder comparar dias."""
    items = []
    for ticker, detail in snapshot.get("watchlist_detail", {}).items():
        status, _ = shared_calculate_quality(detail)
        if status != "ok":
            continue
        items.append((ticker, detail))
    return sorted(items, key=lambda x: x[1].get("proximity_score", 0), reverse=True)[:limit]


def _find_previous_snapshot(trade_date: str) -> tuple[str | None, dict | None]:
    candidates = []
    for path in OUT_DIR.glob("*/snapshot.json"):
        day = path.parent.name
        if day >= trade_date:
            continue
        try:
            candidates.append((day, path))
        except Exception:
            continue

    for day, path in sorted(candidates, reverse=True):
        try:
            return day, json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"    [Flow] No se pudo leer snapshot previo {path}: {e}")
    return None, None


def _pct_change(curr, prev):
    try:
        curr_f = float(curr)
        prev_f = float(prev)
        if prev_f == 0:
            return None
        return round(((curr_f / prev_f) - 1.0) * 100, 2)
    except Exception:
        return None


def _build_nearest_flow(trade_date: str, current_snapshot: dict, limit: int = 5) -> dict:
    """Compara el top nearest previo contra el radar actual."""
    prev_date, previous_snapshot = _find_previous_snapshot(trade_date)
    if not previous_snapshot:
        return {}

    previous_nearest = _nearest_candidates_from_snapshot(previous_snapshot, limit=limit)
    current_watchlist = current_snapshot.get("watchlist_detail", {})

    # Rankings completos para calcular drift exacto
    current_nearest_all = _nearest_candidates_from_snapshot(current_snapshot, limit=100)
    current_rank_map = {t: i for i, (t, _) in enumerate(current_nearest_all)}

    prev_nearest_all = _nearest_candidates_from_snapshot(previous_snapshot, limit=100)
    prev_rank_map = {t: i for i, (t, _) in enumerate(prev_nearest_all)}

    signal_tickers = {s.get("ticker") for s in current_snapshot.get("signals", [])}

    rows = []
    for ticker, prev in previous_nearest:
        curr = current_watchlist.get(ticker)
        if ticker in signal_tickers:
            state = "SIGNAL"
            current_reason = "Confirmo signal"
            current_waiting = "OK"
        elif curr:
            curr_quality, _ = shared_calculate_quality(curr)
            if curr_quality == "bad":
                state = "DATA_BAD"
            elif ticker in current_rank_map and current_rank_map[ticker] < limit:
                state = "STILL_NEAR"
            else:
                state = "DROPPED"
            current_reason = (
                curr.get("primary_reason") or ", ".join(curr.get("reasons", [])[:2]) or "OK"
            )
            current_waiting = curr.get("waiting_for", "OK")
        else:
            state = "OUT_OF_RADAR"
            current_reason = "Salio del universo/watchlist Finviz"
            current_waiting = "N/A"

        row = {
            "ticker": ticker,
            "state": state,
            "previous_proximity": prev.get("proximity_score"),
            "current_proximity": curr.get("proximity_score") if curr else None,
            "proximity_delta": (
                round(
                    float(curr.get("proximity_score", 0)) - float(prev.get("proximity_score", 0)), 2
                )
                if curr
                else None
            ),
            "rank_drift": (
                (prev_rank_map[ticker] - current_rank_map[ticker])
                if ticker in current_rank_map and ticker in prev_rank_map
                else "NEW"
                if ticker in current_rank_map
                else "OUT"
            ),
            "previous_price": prev.get("price"),
            "current_price": curr.get("price") if curr else None,
            "price_delta_pct": _pct_change(curr.get("price") if curr else None, prev.get("price")),
            "previous_breakout_gap_pct": prev.get("breakout_gap_pct"),
            "current_breakout_gap_pct": curr.get("breakout_gap_pct") if curr else None,
            "previous_dist_sma20_pct": prev.get("dist_sma20_pct"),
            "current_dist_sma20_pct": curr.get("dist_sma20_pct") if curr else None,
            "previous_rvol": prev.get("rvol"),
            "current_rvol": curr.get("rvol") if curr else None,
            "previous_waiting_for": prev.get("waiting_for", "OK"),
            "current_waiting_for": current_waiting,
            "previous_reason": prev.get("primary_reason")
            or ", ".join(prev.get("reasons", [])[:2])
            or "OK",
            "current_reason": current_reason,
            "current_rank": current_rank_map.get(ticker, 999) + 1,
            "previous_rank": prev_rank_map.get(ticker, 999) + 1,
        }
        rows.append(row)

    # 3. Añadir los que son NUEVOS en el top actual (que no estaban en el anterior)
    current_nearest = _nearest_candidates_from_snapshot(current_snapshot, limit=limit)
    prev_top_tickers = {t for t, _ in previous_nearest}
    for ticker, curr in current_nearest:
        if ticker in prev_top_tickers:
            continue

        row = {
            "ticker": ticker,
            "state": "NEW_IN_TOP",
            "previous_proximity": None,
            "current_proximity": curr.get("proximity_score"),
            "proximity_delta": None,
            "rank_drift": "NEW",
            "previous_price": None,
            "current_price": curr.get("price"),
            "price_delta_pct": None,
            "previous_breakout_gap_pct": None,
            "current_breakout_gap_pct": curr.get("breakout_gap_pct"),
            "previous_dist_sma20_pct": None,
            "current_dist_sma20_pct": curr.get("dist_sma20_pct"),
            "previous_rvol": None,
            "current_rvol": curr.get("rvol"),
            "previous_waiting_for": "N/A",
            "current_waiting_for": curr.get("waiting_for", "OK"),
            "previous_reason": "N/A",
            "current_reason": curr.get("primary_reason")
            or ", ".join(curr.get("reasons", [])[:2])
            or "OK",
            "current_rank": current_rank_map.get(ticker, 999) + 1,
            "previous_rank": prev_rank_map.get(ticker) + 1 if ticker in prev_rank_map else "-",
        }
        rows.append(row)

    return {
        "previous_date": prev_date,
        "current_date": trade_date,
        "rows": rows,
    }


def _build_sector_flow(trade_date: str, current_hot_sectors: list) -> dict:
    """Compara la fuerza sectorial actual con el snapshot previo para detectar rotacion."""
    prev_date, previous_snapshot = _find_previous_snapshot(trade_date)
    if not previous_snapshot:
        return {}

    prev_hot = previous_snapshot.get("hot_sectors", [])
    if not prev_hot:
        return {}

    prev_map = {s["sector_etf"]: s for s in prev_hot}
    rows = []
    for curr in current_hot_sectors:
        etf = curr["sector_etf"]
        prev = prev_map.get(etf)

        drift = 0
        if prev:
            drift = prev.get("rank", 99) - curr.get("rank", 99)
            rs_change = (curr.get("rs", 0) or 0) - (prev.get("rs", 0) or 0)
        else:
            rs_change = 0

        rows.append(
            {
                "sector_etf": etf,
                "current_rank": curr.get("rank"),
                "previous_rank": prev.get("rank") if prev else None,
                "rank_drift": drift,
                "current_rs": curr.get("rs"),
                "previous_rs": prev.get("rs") if prev else None,
                "rs_drift": rs_change,
                "tradeable": curr.get("tradeable"),
            }
        )

    return {"previous_date": prev_date, "rows": rows}


def _e25_bucket(dist_sma20: float) -> str:
    if dist_sma20 <= 6.76:
        return "Z1"
    if dist_sma20 <= 10.0:
        return "Z2"
    if dist_sma20 <= 15.0:
        return "Z3"
    if dist_sma20 <= 25.0:
        return "Z4"
    if dist_sma20 <= 35.0:
        return "Z5"
    return "Z6"


def _e25_state(dist_sma20: float, sizing_factor: float, sizing_reason: str) -> str:
    if sizing_factor <= 0:
        return "BLOQUEADO"
    if dist_sma20 <= 6.76:
        return "SALUDABLE"
    if dist_sma20 <= 10.0:
        return "VALLE"
    if dist_sma20 <= 15.0:
        return "BREAKOUT"
    if dist_sma20 <= 25.0:
        return "EXTREMO"
    if dist_sma20 <= 50.0:
        return "EXTREMO"
    return "BLOQUEADO"


def _build_e25_summary(signals: list[dict], watchlist_details: dict) -> dict:
    buckets = {f"Z{i}": 0 for i in range(1, 7)}
    sizing_factors = []
    ultralight = 0
    blocked = 0
    for s in signals:
        dist = float(s.get("dist_sma20", s.get("dist_sma20_pct", 0)) or 0)
        factor = float(s.get("sizing_factor", 1.0) or 1.0)
        bucket = _e25_bucket(dist)
        buckets[bucket] += 1
        sizing_factors.append(factor)
        if factor <= 0.15:
            ultralight += 1
        if factor <= 0:
            blocked += 1

    watchlist_buckets = {f"Z{i}": 0 for i in range(1, 7)}
    for detail in (watchlist_details or {}).values():
        dist = float(detail.get("dist_sma20", detail.get("dist_sma20_pct", 0)) or 0)
        watchlist_buckets[_e25_bucket(dist)] += 1

    return {
        "bucket_counts": buckets,
        "watchlist_bucket_counts": watchlist_buckets,
        "signals_count": len(signals),
        "watchlist_count": len(watchlist_details or {}),
        "blocked_extreme_count": blocked,
        "ultralight_count": ultralight,
        "avg_sizing_factor": round(sum(sizing_factors) / len(sizing_factors), 2)
        if sizing_factors
        else 1.0,
    }


# ── RS FINVIZ MODE ──────────────────────────────────────────────────────────
RS_FINVIZ_MIN_PCT_DEFAULT = 60.0

FINVIZ_CFG = {
    "finviz": {
        "base_url": "https://finviz.com/screener.ashx",
        "filters": "cap_midover,sh_avgvol_o1000,sh_price_o10",
        "sort": "relativevolume",
        "max_pages": 30,
        "timeout_sec": 15,
        "retries": 3,
        "min_tickers": 80,
    }
}


def _fmt_price(value, default: str = "N/A"):
    try:
        if value is None or pd.isna(value):
            return default
        return f"{float(value):.2f}"
    except Exception:
        return default


def _get_latest_ohlcv_date(db_path: Path) -> str | None:
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT MAX(date) FROM ohlcv_cache").fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception as e:
        logger.warning(f"    [Date] No se pudo leer MAX(date) de ohlcv_cache: {e}")
        return None


def load_combo_params(name):
    """Carga parametros desde config/production_config.json (Source of Truth)"""
    try:
        config = load_production_config()
        params = {
            "tier1_strategy": config.get("tier1_strategy", {}),
            "tier2_filters": config.get("tier2_filters", {}),
            "tier3_risk": config.get("tier3_risk", {}),
        }
        logger.info(f"    [Config] Cargados parametros de produccion para {name}")
        return params
    except Exception as e:
        logger.warning(f"    [Config] Fallo carga production_config.json, usando fallback: {e}")
        f = RESULTS_DIR / f"{name}_config.json"
        if not f.exists():
            raise FileNotFoundError(f"Config no encontrado: {f}")
        return json.load(open(f))


def build_engine_kwargs(
    combo_name,
    params,
    rs_min_pct: float = RS_FINVIZ_MIN_PCT_DEFAULT,
    force_sector_off: bool = False,
):
    combo_cfg = json.load(open(COMBOS_DIR / f"{combo_name}.json"))
    tier2 = params.get("tier2_filters", {})
    tier1 = params.get("tier1_strategy", {})
    tier3 = params.get("tier3_risk", {})
    signal_type = combo_cfg.get("pattern", {}).get("signal_type", "any")
    screener_name = combo_cfg.get("screener", {}).get("name", "minervini_trend")
    risk_dollars = int(INITIAL_CAPITAL * tier3.get("risk_fraction", 0.005))
    tier3e = {}
    for k, v in tier3.items():
        k2 = {"max_stop_pct_hard": "max_stop_pct"}.get(k, k)
        if k2 in ("rvol_danger_size", "rvol_warning_size") and isinstance(v, float) and v <= 1.0:
            v = int(v * 100)
        if k2 == "max_stop_pct" and isinstance(v, float) and v <= 1.0:
            v = round(v * 100, 1)
        tier3e[k2] = v
    T2 = {
        "min_rvol",
        "min_adr",
        "max_dist_sma20",
        "min_dollar_volume",
        "min_volume",
        "min_consolidation_days",
        "use_rs_percentile",
        "min_rs_percentile",
        "rs_lookback_days",
        "require_positive_rs",
        "use_pattern_filter",
        "min_pattern_confidence",
        "pattern_cache_path",
        "use_sector_etf_filter",
        "sector_etf_dist_threshold",
        "sector_etf_sma_period",
    }

    t2_final = {k: v for k, v in tier2.items() if k in T2}
    if force_sector_off:
        t2_final["use_sector_etf_filter"] = False

    base = {
        **t2_final,
        **tier3e,
        **tier1,
        "signal_type": signal_type,
        "screener_name": screener_name,
        "screener_cache_path": None,
        "mode": "production",
        "risk_dollars": risk_dollars,
        "fees": 0.001,
        "slippage": 0.001,
        "offline_mode": False,
    }

    base["use_rs_percentile"] = False
    base["min_rs_percentile"] = rs_min_pct
    base["require_positive_rs"] = True
    base["screener_cache_path"] = None

    logger.info(
        f"  [RS-FINVIZ] use_rs_percentile=False | min_rs_percentile={rs_min_pct} | screener_cache desactivado"
    )
    return base


def _get_htf_candidate(ticker: str) -> int:
    """Fallback logic to get HTF status from candidate_state."""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT htf_candidate FROM candidate_state WHERE ticker=? ORDER BY date DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        conn.close()
        return int(row[0]) if row else 0
    except:
        return 0


def _enrich_watchlist_detail(engine, raw_detail: dict, fallback_detail: dict) -> dict:
    enriched = {}
    raw_detail = raw_detail or {}
    fallback_detail = fallback_detail or {}
    tickers = list(set(raw_detail) | set(fallback_detail))

    # Lookup robusto de sectores y temas desde DB/Taxonomy
    db_sectors = {}
    from src.data.theme_taxonomy import THEME_MAP

    try:
        conn = sqlite3.connect(DB_PATH)
        placeholders = ",".join(["?"] * len(tickers))
        query = f"SELECT ticker, sector_etf FROM candidate_state WHERE ticker IN ({placeholders}) ORDER BY date DESC"
        rows = conn.execute(query, tickers).fetchall()
        for t, s in rows:
            if t not in db_sectors:
                db_sectors[t] = s
        conn.close()
    except:
        pass

    # Cache for thematic indices to avoid redundant calculations
    theme_index_cache = {}

    # Get current date from engine or trade date
    as_of = engine.end_date if hasattr(engine, "end_date") else datetime.now().strftime("%Y-%m-%d")

    for ticker in tickers:
        detail = dict(raw_detail.get(ticker) or {})
        fallback = fallback_detail.get(ticker) or {}

        for key, value in fallback.items():
            if key not in detail or detail.get(key) in (None, ""):
                detail[key] = value

        # Cadena de fallback sectorial
        sec = detail.get("sector_etf")
        if not sec:
            sec = db_sectors.get(ticker)
        if not sec:
            sec = SECTOR_MAP.get(ticker)

        detail["sector_etf"] = sec or "OTHER"
        themes = THEME_MAP.get(ticker, [])
        detail["themes"] = themes

        # Calculate Theme RS if ticker has themes and a sector ETF
        theme_vs_sector = None
        best_theme_found = None
        if themes and sec and sec != "OTHER":
            try:
                max_rs = -999.0
                for theme_candidate in themes:
                    if theme_candidate not in theme_index_cache:
                        # Get all members
                        members = [t for t, ths in THEME_MAP.items() if theme_candidate in ths]
                        # Fetch price data for members + sector
                        conn = sqlite3.connect(DB_PATH)
                        all_req = members + [sec]
                        placeholders = ",".join(["?"] * len(all_req))
                        start_dt = (pd.Timestamp(as_of) - timedelta(days=60)).strftime("%Y-%m-%d")
                        query = f"SELECT ticker, date, close FROM ohlcv_cache WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?"
                        df_prices = pd.read_sql_query(
                            query, conn, params=all_req + [start_dt, as_of]
                        )
                        conn.close()

                        if not df_prices.empty:
                            pivot = df_prices.pivot(
                                index="date", columns="ticker", values="close"
                            ).sort_index()
                            t_idx = calculate_equal_weighted_index(pivot, members)
                            if not t_idx.empty:
                                theme_index_cache[theme_candidate] = (
                                    t_idx,
                                    pivot[sec] if sec in pivot.columns else None,
                                )

                    if theme_candidate in theme_index_cache:
                        t_idx, s_prices = theme_index_cache[theme_candidate]
                        if (
                            t_idx is not None
                            and s_prices is not None
                            and len(t_idx) >= 21
                            and len(s_prices) >= 21
                        ):
                            t_ret = (t_idx.iloc[-1] / t_idx.iloc[-21]) - 1
                            s_ret = (s_prices.iloc[-1] / s_prices.iloc[-21]) - 1
                            cand_rs = t_ret - s_ret
                            if cand_rs > max_rs:
                                max_rs = cand_rs
                                theme_vs_sector = cand_rs
                                best_theme_found = theme_candidate
            except Exception as e:
                logger.debug(f"Error calculating Theme RS for {ticker}: {e}")

        detail["theme_vs_sector"] = theme_vs_sector
        detail["best_theme"] = best_theme_found or (themes[0] if themes else None)

        if "max_dist_sma20" not in detail or detail.get("max_dist_sma20") is None:
            detail["max_dist_sma20"] = float(getattr(engine, "max_dist_sma20", 6.77))
        if "htf_candidate" not in detail:
            detail["htf_candidate"] = _get_htf_candidate(ticker)

        enriched[ticker] = detail

    return enriched


def calculate_breadth_from_engine(engine, date_str):
    try:
        close = engine.close
        if close is None or close.empty:
            return {}

        # FIX: A las 08:30 NY (premarket) yfinance no tiene el cierre de HOY todavía.
        # close.iloc[-1] es NaN para todos los tickers → sample_size = 0 → STALE.
        # Solución: encontrar las últimas 2 filas que SÍ tienen datos reales,
        # ignorando cualquier fila final que sea todo-NaN (la vela de hoy intraday).
        close_filled = close.dropna(how="all")  # elimina filas donde TODOS son NaN
        if len(close_filled) < 2:
            ctx = get_market_context_live(db_path=DB_PATH, as_of=date_str)
            return {
                "vix": round(ctx.get("vix"), 2) if ctx.get("vix") else None,
                "sample_size": 0,
                "data_status": "STALE",
                "verdict": "N/A",
            }

        # Tickers con al menos las últimas 2 velas válidas (sobre el close ya filtrado)
        valid_mask = close_filled.iloc[-2:].notna().all()
        valid_close = close_filled.loc[:, valid_mask]
        sample_size = int(valid_mask.sum())
        total_tickers = len(close.columns)

        # Umbral mínimo: necesitamos al menos 10% del universo para que sea significativo
        MIN_SAMPLE_RATIO = 0.10
        if sample_size == 0 or sample_size < total_tickers * MIN_SAMPLE_RATIO:
            ctx = get_market_context_live(db_path=DB_PATH, as_of=date_str)
            return {
                "vix": round(ctx.get("vix"), 2) if ctx.get("vix") else None,
                "sample_size": sample_size,
                "data_status": "STALE",
                "verdict": "N/A",
            }

        logger.info(
            f"    [Breadth] Usando {sample_size}/{total_tickers} tickers válidos "
            f"(última vela: {close_filled.index[-1]})"
        )

        # Advance/Decline sobre validos
        chg = valid_close.iloc[-1] / valid_close.iloc[-2] - 1
        advances = int((chg > 0).sum())
        declines = int((chg < 0).sum())

        # New Highs/Lows (252 bars)
        lookback = min(len(valid_close) - 1, 252)
        high_252 = valid_close.rolling(lookback, min_periods=lookback // 2).max().shift(1).iloc[-1]
        low_252 = valid_close.rolling(lookback, min_periods=lookback // 2).min().shift(1).iloc[-1]

        curr_price = valid_close.iloc[-1]
        new_highs = int((curr_price >= high_252).sum())
        new_lows = int((curr_price <= low_252).sum())

        # VIX
        ctx = get_market_context_live(db_path=DB_PATH, as_of=date_str)
        vix = ctx.get("vix")
        if vix:
            vix = round(float(vix), 2)

        # Verdict logic
        nh_nl_ratio = new_highs / (new_lows if new_lows > 0 else 1)
        ad_ratio = advances / (declines if declines > 0 else 1)

        green_score = 0
        if vix and vix < 20:
            green_score += 1
        if nh_nl_ratio > 1.5:
            green_score += 1
        if ad_ratio > 1.2:
            green_score += 1

        red_score = 0
        if vix and vix > 30:
            red_score += 1
        if nh_nl_ratio < 0.7:
            red_score += 1
        if ad_ratio < 0.8:
            red_score += 1

        verdict = "GREEN" if green_score >= 2 else "CAUTION" if red_score >= 1 else "NEUTRAL"

        return {
            "vix": vix,
            "new_highs": new_highs,
            "new_lows": new_lows,
            "advances": advances,
            "declines": declines,
            "verdict": verdict,
            "nh_nl_ratio": round(nh_nl_ratio, 2),
            "ad_ratio": round(ad_ratio, 2),
            "sample_size": sample_size,
            "data_status": "OK" if sample_size > total_tickers * 0.5 else "LOW_SAMPLE",
        }
    except Exception as e:
        logger.error(f"Error calculating breadth: {e}")
        return {}


def scan_signals(
    combo_name,
    universe,
    date_str,
    rs_min_pct: float = RS_FINVIZ_MIN_PCT_DEFAULT,
    force_sector_off: bool = False,
):
    params = load_combo_params(combo_name)
    kwargs = build_engine_kwargs(
        combo_name, params, rs_min_pct=rs_min_pct, force_sector_off=force_sector_off
    )
    as_of = pd.Timestamp(date_str)
    start = (as_of - pd.Timedelta(days=300)).strftime("%Y-%m-%d")
    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start,
        end_date=date_str,
        initial_capital=INITIAL_CAPITAL,
        **kwargs,
    )

    def _build_watchlist_detail(engine_obj, watchlist_scores, confirmed_signals):
        detail = {}
        if not watchlist_scores:
            return detail

        reason_priority = {
            "MA stack roto": 0,
            "Sector ETF bloqueado": 1,
            "Falta breakout": 2,
            "RVOL bajo": 3,
            "Extendido de SMA20": 4,
        }

        confirmed = {s.get("ticker") for s in confirmed_signals}
        for ticker, score in watchlist_scores.items():
            if ticker in confirmed:
                continue
            try:
                close = engine_obj.close[ticker]
                high = engine_obj.high[ticker]
                vol_series = engine_obj.volume[ticker]
                ema10 = engine_obj.ema_10[ticker]
                sma20 = engine_obj.sma_20[ticker]
                sma50 = engine_obj.sma_50[ticker]
                sma100 = engine_obj.sma_100[ticker]
                sma200 = engine_obj.sma_200[ticker]

                price = float(close.iloc[-1])
                e10 = float(ema10.iloc[-1])
                s20 = float(sma20.iloc[-1])
                s50 = float(sma50.iloc[-1])
                s100 = float(sma100.iloc[-1])
                s200 = float(sma200.iloc[-1])

                # Calcular RVOL directamente desde series raw para evitar
                # el default 1.0 cuando avg_volume_20 no esta precalculado en DB.
                rvol = 1.0
                try:
                    avg_vol_20 = vol_series.rolling(20, min_periods=5).mean().shift(1)
                    avg_last = float(avg_vol_20.iloc[-1])
                    vol_today = float(vol_series.iloc[-1])
                    if avg_last > 500 and vol_today > 0:
                        rvol = round(vol_today / avg_last, 2)
                except Exception:
                    # Fallback al atributo precalculado del engine
                    if (
                        hasattr(engine_obj, "rvol")
                        and engine_obj.rvol is not None
                        and ticker in engine_obj.rvol.columns
                    ):
                        rvol = float(engine_obj.rvol[ticker].iloc[-1])

                adr = 0.0
                if (
                    hasattr(engine_obj, "adr_pct")
                    and engine_obj.adr_pct is not None
                    and ticker in engine_obj.adr_pct.columns
                ):
                    adr = float(engine_obj.adr_pct[ticker].iloc[-1])

                dvol = 0.0
                if (
                    hasattr(engine_obj, "dollar_volume")
                    and engine_obj.dollar_volume is not None
                    and ticker in engine_obj.dollar_volume.columns
                ):
                    dvol = float(engine_obj.dollar_volume[ticker].iloc[-1])

                prev_high_20 = float(high.shift(1).rolling(20).max().iloc[-1])
                breakout = bool(price > prev_high_20)

                tol = 0.002
                ma_stack = bool(
                    price >= e10 * (1 - tol)
                    and e10 >= s20 * (1 - tol)
                    and s20 >= s50 * (1 - tol)
                    and s50 >= s100 * (1 - tol)
                    and s100 >= s200 * (1 - tol)
                )

                dist_sma20 = ((price / s20) - 1.0) * 100 if s20 > 0 else 0.0
                avg_vol_20 = float(vol_series.rolling(20).mean().iloc[-1])
                sizing_factor, sizing_reason = calculate_dynamic_sizing_factor(
                    dist_sma20, adr, load_production_config()
                )
                e25_bucket = _e25_bucket(dist_sma20)
                e25_state = _e25_state(dist_sma20, sizing_factor, sizing_reason)

                sector_etf = None
                sector_etf_dist = None
                sector_etf_ok = True

                # Intentar obtener sector desde el mapa manual si el engine falla
                if hasattr(engine_obj, "ticker_to_etf_map") and engine_obj.ticker_to_etf_map:
                    sector_etf = engine_obj.ticker_to_etf_map.get(ticker)

                if not sector_etf:
                    sector_etf = SECTOR_MAP.get(ticker)

                if (
                    sector_etf
                    and hasattr(engine_obj, "etf_dist_matrix")
                    and engine_obj.etf_dist_matrix is not None
                ):
                    if sector_etf in engine_obj.etf_dist_matrix.columns:
                        sector_etf_dist = float(engine_obj.etf_dist_matrix[sector_etf].iloc[-1])
                        sector_etf_ok = sector_etf_dist > 0.0

                max_dist_sma20 = float(getattr(engine_obj, "max_dist_sma20", 6.77))
                reasons = []
                if not breakout:
                    reasons.append("Falta breakout")
                if not ma_stack:
                    reasons.append("MA stack roto")
                if not sector_etf_ok:
                    reasons.append("Sector ETF bloqueado")
                if rvol < float(getattr(engine_obj, "min_rvol", 1.1)):
                    reasons.append("RVOL bajo")
                if abs(dist_sma20) > max_dist_sma20 and sizing_factor <= 0:
                    reasons.append("Extendido de SMA20")

                reasons = sorted(reasons, key=lambda r: reason_priority.get(r, 99))
                min_rvol = float(getattr(engine_obj, "min_rvol", 1.1))
                waiting_for = "OK"
                if not breakout:
                    waiting_for = f"Breakout > {prev_high_20:.2f}"
                elif not sector_etf_ok:
                    waiting_for = f"{sector_etf} > SMA20" if sector_etf else "Sector ETF > SMA20"
                elif not ma_stack:
                    waiting_for = "MA stack"
                elif rvol < min_rvol:
                    waiting_for = f"RVOL >= {min_rvol:.2f}"
                elif abs(dist_sma20) > max_dist_sma20 and sizing_factor <= 0:
                    waiting_for = f"Dist SMA20 penalizada: {max_dist_sma20:.2f}%"

                proximity_score = 100.0
                if not breakout:
                    proximity_score -= 40.0
                if not ma_stack:
                    proximity_score -= 30.0
                if not sector_etf_ok:
                    proximity_score -= 15.0
                if rvol < 1.0:
                    proximity_score -= 10.0
                if abs(dist_sma20) > max_dist_sma20:
                    proximity_score -= min(20.0, (abs(dist_sma20) - max_dist_sma20) * 2.5)
                if sizing_factor < 1.0:
                    proximity_score -= min(15.0, (1.0 - sizing_factor) * 20.0)
                proximity_score = max(0.0, min(100.0, proximity_score))

                raw_risk_budget_usd = float(kwargs.get("risk_dollars", INITIAL_CAPITAL * 0.005))
                risk_budget_usd = round(raw_risk_budget_usd * sizing_factor, 2)
                risk_per_share = max(price - stop, price * 0.005)
                initial_size = (
                    int(raw_risk_budget_usd / risk_per_share) if risk_per_share > 0 else 0
                )
                position_size = (
                    int(risk_budget_usd / risk_per_share)
                    if risk_per_share > 0 and sizing_factor > 0
                    else 0
                )

                detail[ticker] = {
                    "score": score,
                    "price": round(price, 2),
                    "breakout_level": round(prev_high_20, 2),
                    "avg_volume_20d": round(avg_vol_20, 0),
                    "rs_pct": round(score, 1),
                    "ema10": round(e10, 2),
                    "sma20": round(s20, 2),
                    "sma50": round(s50, 2),
                    "sma100": round(s100, 2),
                    "sma200": round(s200, 2),
                    "rvol": round(rvol, 2),
                    "adr": round(adr, 2),
                    "dollar_volume_m": round(dvol / 1e6, 2),
                    "dist_sma20_pct": round(dist_sma20, 2),
                    "max_dist_sma20": max_dist_sma20,
                    "breakout": breakout,
                    "ma_stack": ma_stack,
                    "sector_etf": sector_etf,
                    "sector_etf_dist": None
                    if sector_etf_dist is None
                    else round(sector_etf_dist * 100, 2),
                    "sector_etf_ok": sector_etf_ok,
                    "waiting_for": waiting_for,
                    "proximity_score": round(proximity_score, 2),
                    "primary_reason": reasons[0] if reasons else "OK",
                    "reasons": reasons,
                    "source_system": "finviz_vps",
                    "dist_sma20": round(dist_sma20, 2),
                    "adr_pct": round(adr, 2),
                    "sizing_factor": round(sizing_factor, 2),
                    "sizing_reason": sizing_reason,
                    "risk_budget_usd": risk_budget_usd,
                    "raw_risk_budget_usd": raw_risk_budget_usd,
                    "risk_per_share": round(risk_per_share, 4),
                    "initial_size": initial_size,
                    "position_size": position_size,
                    "extension_bucket": e25_bucket,
                    "e25_state": e25_state,
                    "htf_candidate": _get_htf_candidate(ticker),
                }
            except Exception as e:
                detail[ticker] = {
                    "score": score,
                    "reasons": [f"No se pudo calcular diagnóstico: {e}"],
                }
        return detail

    try:
        result = engine.run_backtest()

        rejected_short = result.get("rejected_tickers", [])
        if rejected_short:
            rejected_short = [str(t).split(" (")[0] for t in rejected_short]
            rejected_path = OUT_DIR / "rejected_short_history.json"
            current_rejected = set()
            if rejected_path.exists():
                try:
                    current_rejected = set(json.load(open(rejected_path)))
                except:
                    pass
            new_rejected = [t for t in rejected_short if t not in current_rejected]
            if new_rejected:
                current_rejected.update(new_rejected)
                with open(rejected_path, "w") as f:
                    json.dump(sorted(list(current_rejected)), f, indent=2)
                logger.info(
                    f"    [Cache] {len(new_rejected)} tickers nuevos marcados con historia insuficiente"
                )

        trades_df = result.get("trades_df", pd.DataFrame())
        setups = result.get("setups", [])
        signals = []

        if setups:
            logger.info(f"    [Setup] {len(setups)} candidatos detectados hoy para entrar mañana.")
            for s in setups:
                price = float(s["price"])
                stop = float(s["stop"])
                risk_per_share = price - stop if price - stop > 0 else price * 0.01
                risk_dollars = kwargs.get("risk_dollars", INITIAL_CAPITAL * 0.005)
                size = min(
                    max(int(risk_dollars / risk_per_share), 1),
                    int((INITIAL_CAPITAL * 0.25) / price),
                )

                signals.append(
                    {
                        "combo": combo_name,
                        "ticker": s["ticker"],
                        "signal_date": date_str,
                        "entry_price": price,
                        "stop_loss": stop,
                        "tp1_price": price + (risk_per_share * 1.25),
                        "tp2_price": price + (risk_per_share * 3.00),
                        "position_size": size,
                        "rvol": float(engine.rvol[s["ticker"]].iloc[-1])
                        if hasattr(engine, "rvol") and engine.rvol is not None
                        else 1.0,
                        "adr": float(engine.adr_pct[s["ticker"]].iloc[-1])
                        if hasattr(engine, "adr_pct") and engine.adr_pct is not None
                        else 0.0,
                        "dollar_volume_m": float(engine.dollar_volume[s["ticker"]].iloc[-1]) / 1e6
                        if hasattr(engine, "dollar_volume") and engine.dollar_volume is not None
                        else 0.0,
                        "score": result.get("eligible_watchlist", {}).get(s["ticker"], 0.5),
                        "rs_mode": "spy_fallback",
                        "source": "finviz_setup",
                        "sector_etf": s.get("sector_etf"),
                        "sector_etf_dist": s.get("sector_etf_dist"),
                    }
                )

        if not trades_df.empty:
            col = "entry_date" if "entry_date" in trades_df.columns else None
            if col:
                as_of = pd.Timestamp(date_str)
                lookback_dates = set(pd.bdate_range(end=as_of, periods=3).strftime("%Y-%m-%d"))
                mask = trades_df[col].astype(str).str[:10].isin(lookback_dates)
                today_t = trades_df[mask]
            else:
                today_t = trades_df.tail(5)

            for _, row in today_t.iterrows():
                ticker = str(row.get("ticker", row.get("symbol", "?")))
                if any(s["ticker"] == ticker for s in signals):
                    continue
                entry = float(row.get("entry_price", 0))
                stop = float(row.get("stop_loss", 0))
                risk = entry - stop
                signals.append(
                    {
                        "combo": combo_name,
                        "ticker": ticker,
                        "signal_date": str(row[col])[:10] if col else date_str,
                        "entry_price": entry,
                        "stop_loss": stop,
                        "tp1_price": float(row.get("tp1_price", entry + risk * 1.25)),
                        "tp2_price": float(row.get("tp2_price", entry + risk * 3.0)),
                        "position_size": float(row.get("shares", row.get("position_size", 0))),
                        "rs_mode": "spy_fallback",
                        "source": "backtest_trade",
                    }
                )

        fallback_detail = _build_watchlist_detail(
            engine, result.get("eligible_watchlist", {}), signals
        )

        return {
            "signals": signals,
            "watchlist": result.get("eligible_watchlist", {}),
            "watchlist_detail": _enrich_watchlist_detail(
                engine,
                result.get("watchlist_detail", {}),
                fallback_detail,
            ),
            "breadth": calculate_breadth_from_engine(engine, date_str),
        }
    except Exception as e:
        logger.error(f"Scan error ({combo_name}): {e}", exc_info=True)
        return {"signals": [], "watchlist": [], "watchlist_detail": {}, "breadth": {}}
    finally:
        engine.cleanup()


def run_pre(trade_date, drift_override, rs_min_pct=RS_FINVIZ_MIN_PCT_DEFAULT, top_n=5, hq_n=5):
    finviz_result = fetch_finviz_universe(FINVIZ_CFG)
    universe = finviz_result.tickers if finviz_result.ok else []

    # Apply exclusions from master config
    try:
        config = load_production_config()
        exclude_tickers = config.get("exclude_tickers", [])
        exclude_sectors = config.get("exclude_sectors", [])
        
        exclude_set = set()
        for x in exclude_tickers:
            if isinstance(x, str):
                for tok in x.split(","):
                    if tok.strip():
                        exclude_set.add(tok.upper().strip())
                        
        exclude_sectors_set = set()
        for x in exclude_sectors:
            if isinstance(x, str):
                for tok in x.split(","):
                    if tok.strip():
                        exclude_sectors_set.add(tok.upper().strip())

        if exclude_set or exclude_sectors_set:
            original_len = len(universe)
            universe = [
                t for t in universe
                if t.upper() not in exclude_set
                and SECTOR_MAP.get(t.upper(), "UNKNOWN") not in exclude_sectors_set
            ]
            logger.info(
                f"    [Universe] Exclusions applied: Excluded {original_len - len(universe)} tickers. "
                f"Remaining: {len(universe)} tickers. "
                f"Excluding Tickers: {sorted(list(exclude_set))}, Sectors: {sorted(list(exclude_sectors_set))}"
            )
    except Exception as e:
        logger.warning(f"    [Universe] Failed to apply exclusions from production_config: {e}")

    rejected_path = OUT_DIR / "rejected_short_history.json"
    if rejected_path.exists():
        try:
            rejected = set(json.load(open(rejected_path)))
            universe = [t for t in universe if t not in rejected]
        except:
            pass

    if not finviz_result.ok:
        logger.error("    [Universe] Fallo fetch de Finviz. Abortando.")
        return None

    # 1. Pre-warm with trade_date first to fetch latest available data
    pre_warm_cache(universe, trade_date)

    # 2. Now get the latest date from DB
    data_as_of = _get_latest_ohlcv_date(DB_PATH) or trade_date

    # Preflight stale check
    is_stale = False
    try:
        db_path = Path(DB_PATH)
        if not db_path.exists() or db_path.stat().st_size == 0:
            is_stale = True
        else:
            latest_date_str = _get_latest_ohlcv_date(DB_PATH)
            if latest_date_str:
                latest_ts = pd.to_datetime(latest_date_str)
                trade_ts = pd.to_datetime(trade_date)
                b_days = len(pd.bdate_range(start=latest_ts, end=trade_ts)) - 1
                if b_days > 3:
                    is_stale = True
            else:
                is_stale = True
    except Exception as e:
        logger.error(f"Error checking DB staleness: {e}")
        is_stale = True

    if is_stale:
        logger.warning("    [Preflight] DB is empty or stale. Sending Telegram Alert.")
        try:
            from src.utils.telegram_client import telegram_send
            telegram_send("⚠️ <b>DB desactualizada</b> — corriendo solo con Finviz live.")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")

    logger.info("=" * 60)
    logger.info(f"PAPER FINVIZ | Trade: {trade_date} | Data: {data_as_of}")
    logger.info("=" * 60)

    if data_as_of < trade_date:
        logger.warning(
            f"    [Date] WARNING: data_as_of ({data_as_of}) es anterior a trade_date ({trade_date}). yfinance podria no tener datos de hoy todavia."
        )

    # 3. Market Context con as_of
    ctx = get_market_context_live(require_spy_above_sma200=True, db_path=DB_PATH, as_of=data_as_of)
    regime = apply_regime_override(ctx, "none")
    reg_ok = regime.get("effective_regime_ok", False)

    signals, watchlist_scores, watchlist_details, first_breadth = [], {}, {}, None

    # 4. Scan Signals
    if reg_ok and universe:
        for combo_name in ACTIVE_COMBOS:
            res = scan_signals(combo_name, universe, data_as_of, rs_min_pct=rs_min_pct)
            signals.extend(res["signals"])
            if first_breadth is None:
                first_breadth = res.get("breadth")
            for t, score in res.get("watchlist", {}).items():
                if t not in watchlist_scores or score > watchlist_scores[t]:
                    watchlist_scores[t] = score
            for t, detail in res.get("watchlist_detail", {}).items():
                combo_lbl = (
                    "Qulla"
                    if combo_name == "combo_pure_momentum"
                    else "Minervini"
                    if combo_name == "combo_stage2_breakout"
                    else combo_name
                )
                if t not in watchlist_details:
                    watchlist_details[t] = detail
                    watchlist_details[t]["combos"] = [combo_lbl]
                else:
                    current_combos = watchlist_details[t].get("combos", [])
                    if combo_lbl not in current_combos:
                        current_combos.append(combo_lbl)

                    if detail.get("score", 0) > watchlist_details[t].get("score", 0):
                        # Keep the new detail but preserve and merge the combos list
                        watchlist_details[t] = detail

                    watchlist_details[t]["combos"] = current_combos

        seen = {}
        for s in signals:
            t = s["ticker"]
            if t not in seen or s.get("position_size", 0) > seen[t].get("position_size", 0):
                seen[t] = s
        signals = list(seen.values())

    # 5. Enriquecer con Calidad de Datos
    for ticker, detail in watchlist_details.items():
        q_status, q_reasons = shared_calculate_quality(detail)
        detail["data_quality_status"] = q_status
        detail["data_quality_reasons"] = q_reasons
        detail["is_promotable"] = q_status == "ok"

    # 6. Obtener Hot Sectors
    from src.utils.terminal_gui import _build_hot_sectors

    hot_sectors = _build_hot_sectors(data_as_of, top_n=11)

    scanner_uni_count = None
    try:
        summary_path = ROOT / "outputs" / "live_signals" / trade_date / "run_summary.json"
        if summary_path.exists():
            with open(summary_path, "r") as f:
                summary_data = json.load(f)
                scanner_uni_count = summary_data.get("universe_count")
    except Exception as e:
        logger.warning(f"Could not read run_summary.json for scanner_universe_count: {e}")

    day_dir = OUT_DIR / trade_date
    day_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "date": trade_date,
        "data_as_of": data_as_of,
        "source": "finviz",
        "universe_size": len(universe),
        "scanner_universe_count": scanner_uni_count,
        "regime_ok": reg_ok,
        "signals": signals,
        "signals_count": len(signals),
        "watchlist_detail": watchlist_details,
        "hot_sectors": hot_sectors,
        "breadth": first_breadth,
        "generated_at": datetime.now().isoformat(),
    }

    snap["e25_summary"] = _build_e25_summary(signals, watchlist_details)

    live_signals_path = ROOT / "outputs" / "live_signals" / trade_date / "combined.csv"
    if live_signals_path.exists():
        try:
            snap["live_signals_view"] = {
                "path": str(live_signals_path),
                "rows": int(pd.read_csv(live_signals_path).shape[0]),
            }
        except Exception:
            snap["live_signals_view"] = {"path": str(live_signals_path), "rows": None}

    # 7. Calcular Flows (Nearest y Sector)
    snap["nearest_flow"] = _build_nearest_flow(trade_date, snap, limit=30)
    snap["sector_flow"] = _build_sector_flow(trade_date, hot_sectors)

    # 8. Guardar y Mostrar
    with open(day_dir / "snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)

    print_terminal_brief(snap, top_n=top_n, hq_n=hq_n)
    return snap


def main():
    parser = argparse.ArgumentParser(description="Paper trading universo Finviz")
    parser.add_argument("--phase", choices=["pre"], default="pre")
    parser.add_argument("--date", default=None)
    parser.add_argument("--drift-override", type=float, default=100.0)
    parser.add_argument("--rs-min", type=float, default=RS_FINVIZ_MIN_PCT_DEFAULT)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--hq-n", type=int, default=5)
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.phase == "pre":
        run_pre(
            date_str, args.drift_override, rs_min_pct=args.rs_min, top_n=args.top_n, hq_n=args.hq_n
        )


if __name__ == "__main__":
    main()
