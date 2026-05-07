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
ACTIVE_COMBOS = ["combo_pure_momentum"]
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
        if days_diff > 3:
            to_update.append(t)

    if not to_update:
        logger.info("    [Pre-warm] Todo el universo esta al dia. Saltando descargas.")
        return

    logger.info(f"    [Pre-warm] Refrescando {len(to_update)} tickers desactualizados...")

    def _fetch(t):
        try:
            cache.get_ohlcv(t, start, date_str)
        except:
            pass

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_fetch, to_update)
    logger.info("    [Pre-warm] Cache actualizado.")


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
        "min_rvol", "min_adr", "max_dist_sma20", "min_dollar_volume", "min_volume",
        "min_consolidation_days", "use_rs_percentile", "min_rs_percentile",
        "rs_lookback_days", "require_positive_rs", "use_pattern_filter",
        "min_pattern_confidence", "pattern_cache_path", "use_sector_etf_filter",
        "sector_etf_dist_threshold", "sector_etf_sma_period",
    }

    t2_final = {k: v for k, v in tier2.items() if k in T2}
    if force_sector_off:
        t2_final["use_sector_etf_filter"] = False

    base = {
        **t2_final, **tier3e, **tier1,
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

                rvol = 1.0
                if (hasattr(engine_obj, "rvol") and engine_obj.rvol is not None 
                    and ticker in engine_obj.rvol.columns):
                    rvol = float(engine_obj.rvol[ticker].iloc[-1])

                adr = 0.0
                if (hasattr(engine_obj, "adr_pct") and engine_obj.adr_pct is not None 
                    and ticker in engine_obj.adr_pct.columns):
                    adr = float(engine_obj.adr_pct[ticker].iloc[-1])

                dvol = 0.0
                if (hasattr(engine_obj, "dollar_volume") and engine_obj.dollar_volume is not None 
                    and ticker in engine_obj.dollar_volume.columns):
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

                sector_etf = None
                sector_etf_dist = None
                sector_etf_ok = True
                if hasattr(engine_obj, "ticker_to_etf_map") and engine_obj.ticker_to_etf_map:
                    sector_etf = engine_obj.ticker_to_etf_map.get(ticker)
                if (sector_etf and hasattr(engine_obj, "etf_dist_matrix") 
                    and engine_obj.etf_dist_matrix is not None):
                    if sector_etf in engine_obj.etf_dist_matrix.columns:
                        sector_etf_dist = float(engine_obj.etf_dist_matrix[sector_etf].iloc[-1])
                        sector_etf_ok = sector_etf_dist > 0.0

                reasons = []
                if not breakout: reasons.append("Falta breakout")
                if not ma_stack: reasons.append("MA stack roto")
                if not sector_etf_ok: reasons.append("Sector ETF bloqueado")
                if rvol < float(getattr(engine_obj, "min_rvol", 1.1)): reasons.append("RVOL bajo")
                if abs(dist_sma20) > float(getattr(engine_obj, "max_dist_sma20", 6.77)): reasons.append("Extendido de SMA20")

                reasons = sorted(reasons, key=lambda r: reason_priority.get(r, 99))

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
                    "breakout": breakout,
                    "ma_stack": ma_stack,
                    "sector_etf": sector_etf,
                    "sector_etf_dist": None if sector_etf_dist is None else round(sector_etf_dist * 100, 2),
                    "sector_etf_ok": sector_etf_ok,
                    "primary_reason": reasons[0] if reasons else "OK",
                    "reasons": reasons,
                }
            except Exception as e:
                detail[ticker] = {"score": score, "reasons": [f"No se pudo calcular diagnóstico: {e}"]}
        return detail

    try:
        result = engine.run_backtest()
        
        rejected_short = result.get("rejected_tickers", [])
        if rejected_short:
            rejected_short = [str(t).split(" (")[0] for t in rejected_short]
            rejected_path = OUT_DIR / "rejected_short_history.json"
            current_rejected = set()
            if rejected_path.exists():
                try: current_rejected = set(json.load(open(rejected_path)))
                except: pass
            new_rejected = [t for t in rejected_short if t not in current_rejected]
            if new_rejected:
                current_rejected.update(new_rejected)
                with open(rejected_path, "w") as f: json.dump(sorted(list(current_rejected)), f, indent=2)
                logger.info(f"    [Cache] {len(new_rejected)} tickers nuevos marcados con historia insuficiente")

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
                size = min(max(int(risk_dollars / risk_per_share), 1), int((INITIAL_CAPITAL * 0.25) / price))
                
                signals.append({
                    "combo": combo_name, "ticker": s["ticker"], "signal_date": date_str,
                    "entry_price": price, "stop_loss": stop, "tp1_price": price + (risk_per_share * 1.25),
                    "tp2_price": price + (risk_per_share * 3.00), "position_size": size,
                    "rvol": float(engine.rvol[s["ticker"]].iloc[-1]) if hasattr(engine, "rvol") and engine.rvol is not None else 1.0,
                    "adr": float(engine.adr_pct[s["ticker"]].iloc[-1]) if hasattr(engine, "adr_pct") and engine.adr_pct is not None else 0.0,
                    "dollar_volume_m": float(engine.dollar_volume[s["ticker"]].iloc[-1]) / 1e6 if hasattr(engine, "dollar_volume") and engine.dollar_volume is not None else 0.0,
                    "score": result.get("eligible_watchlist", {}).get(s["ticker"], 0.5),
                    "rs_mode": "spy_fallback", "source": "finviz_setup",
                    "sector_etf": s.get("sector_etf"), "sector_etf_dist": s.get("sector_etf_dist"),
                })

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
                if any(s["ticker"] == ticker for s in signals): continue
                entry = float(row.get("entry_price", 0))
                stop = float(row.get("stop_loss", 0))
                risk = entry - stop
                signals.append({
                    "combo": combo_name, "ticker": ticker, "signal_date": str(row[col])[:10] if col else date_str,
                    "entry_price": entry, "stop_loss": stop, "tp1_price": float(row.get("tp1_price", entry + risk * 1.25)),
                    "tp2_price": float(row.get("tp2_price", entry + risk * 3.0)),
                    "position_size": float(row.get("shares", row.get("position_size", 0))),
                    "rs_mode": "spy_fallback", "source": "backtest_trade",
                })

        return {
            "signals": signals,
            "watchlist": result.get("eligible_watchlist", {}),
            "watchlist_detail": result.get("watchlist_detail", {}),
        }
    except Exception as e:
        logger.error(f"Scan error ({combo_name}): {e}", exc_info=True)
        return {"signals": [], "watchlist": [], "watchlist_detail": {}}
    finally:
        engine.cleanup()


def run_pre(date_str, drift_override, rs_min_pct=RS_FINVIZ_MIN_PCT_DEFAULT, top_n=5, hq_n=5):
    logger.info("=" * 60)
    logger.info("PAPER FINVIZ - PRE-MARKET")
    logger.info("=" * 60)
    
    latest_db_date = _get_latest_ohlcv_date(DB_PATH)
    if latest_db_date: date_str = latest_db_date
    
    ctx = get_market_context_live(require_spy_above_sma200=True, db_path=DB_PATH)
    regime = apply_regime_override(ctx, "none")
    reg_ok = regime.get("effective_regime_ok", False)
    
    finviz_result = fetch_finviz_universe(FINVIZ_CFG)
    universe = finviz_result.tickers if finviz_result.ok else []
    
    rejected_path = OUT_DIR / "rejected_short_history.json"
    if rejected_path.exists():
        try:
            rejected = set(json.load(open(rejected_path)))
            universe = [t for t in universe if t not in rejected]
        except: pass

    if not finviz_result.ok: return None
    pre_warm_cache(universe, date_str)

    signals, watchlist_scores, watchlist_details, audit_data = [], {}, {}, []

    if reg_ok and universe:
        for combo_name in ACTIVE_COMBOS:
            res = scan_signals(combo_name, universe, date_str, rs_min_pct=rs_min_pct)
            signals.extend(res["signals"])
            for t, score in res.get("watchlist", {}).items():
                if t not in watchlist_scores or score > watchlist_scores[t]: watchlist_scores[t] = score
            for t, detail in res.get("watchlist_detail", {}).items():
                if t not in watchlist_details or detail.get("score", 0) > watchlist_details[t].get("score", 0):
                    watchlist_details[t] = detail

        seen = {}
        for s in signals:
            t = s["ticker"]
            if t not in seen or s.get("position_size", 0) > seen[t].get("position_size", 0): seen[t] = s
        signals = list(seen.values())

    # 4. Enriquecer con Calidad de Datos
    for ticker, detail in watchlist_details.items():
        q_status, q_reasons = shared_calculate_quality(detail)
        detail["data_quality_status"] = q_status
        detail["data_quality_reasons"] = q_reasons
        detail["is_promotable"] = q_status == "ok"

    day_dir = OUT_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "date": date_str, "source": "finviz", "universe_size": len(universe),
        "regime_ok": reg_ok, "signals": signals, "signals_count": len(signals),
        "watchlist_detail": watchlist_details, "generated_at": datetime.now().isoformat(),
    }
    with open(day_dir / "snapshot.json", "w") as f: json.dump(snap, f, indent=2)
    
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
        run_pre(date_str, args.drift_override, rs_min_pct=args.rs_min, top_n=args.top_n, hq_n=args.hq_n)

if __name__ == "__main__":
    main()
