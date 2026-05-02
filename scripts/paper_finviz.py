#!/usr/bin/env python3
"""
PAPER TRADING - UNIVERSO FINVIZ (sistema paralelo, separado)
Usa Finviz como universo dinamico. NO mezclar con paper_local_db ni con backtest.
Objetivo: detectar si Finviz descubre oportunidades que el universo local no captura.
El drift gate esta desactivado aqui (bloque_on_high_drift=False).

RS FIX (2026-04-29):
  El motor usa use_rs_percentile=True por defecto, lo que hace que consulte
  daily_rs_rankings (DB local). Para tickers fuera de la DB devuelve None y
  cae a rs_pct=50, fallando el umbral min_rs_percentile=85 -> 0 senales.
  Solucion: en modo Finviz desactivamos use_rs_percentile y bajamos
  min_rs_percentile a un umbral operativo bajo (RS_FINVIZ_MIN_PCT).
  El screener Qullamaggie calcula el RS relativo vs SPY on-the-fly con los
  precios descargados de Yahoo (rs_fallback_spy=True), sin tocar la DB local.
  Esto hace el sistema 100% independiente de daily_rs_rankings.

Usage:
    python3 scripts/paper_finviz.py --phase pre
    python3 scripts/paper_finviz.py --phase pre --drift-override 100
    python3 scripts/paper_finviz.py --phase pre --rs-min 60   # aflojar RS threshold
Outputs -> outputs/paper_finviz/
"""
import argparse, json, logging, sys, sqlite3
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
OUT_DIR     = ROOT / "outputs" / "paper_finviz"
DB_PATH     = ROOT / "data" / "ticker_cache.db"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR  = ROOT / "config" / "combos"
OUT_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
ACTIVE_COMBOS    = ["combo_pure_momentum"]
INITIAL_CAPITAL = 100_000


def pre_warm_cache(universe: list[str], date_str: str):
    """Refresca los últimos 300 días para todo el universo en paralelo.
    Esto asegura que tras un cleanup o para tickers nuevos tengamos historia 
    suficiente para los indicadores (SMA200)."""
    logger.info(f"    [Pre-warm] Refrescando cache (300d) para {len(universe)} tickers...")
    as_of = pd.Timestamp(date_str)
    start = (as_of - timedelta(days=300)).strftime("%Y-%m-%d")
    cache = TickerCache()
    
    def _fetch(t):
        try:
            cache.get_ohlcv(t, start, date_str)
        except: pass

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(_fetch, universe)
    logger.info("    [Pre-warm] Cache actualizado.")

# ── RS FINVIZ MODE ──────────────────────────────────────────────────────────
# Umbral de RS relativo-vs-SPY para el modo exploración Finviz.
# El screener Qullamaggie calcula esto on-the-fly (sin DB local).
# 60 = ligeramente mejor que el mercado (suficiente para scouting).
# Subir a 70-80 para señales mas selectivas; bajar a 40-50 para maximo flujo.
RS_FINVIZ_MIN_PCT_DEFAULT = 60.0

FINVIZ_CFG = {
    "finviz": {"base_url": "https://finviz.com/screener.ashx",
               "filters": "cap_midover,sh_avgvol_o1000,sh_price_o10",
               "sort": "relativevolume", "max_pages": 30,
               "timeout_sec": 15, "retries": 3, "min_tickers": 80}}


def _fmt_price(value, default: str = "N/A"):
    try:
        if value is None or pd.isna(value):
            return default
        return f"{float(value):.2f}"
    except Exception:
        return default

def load_combo_params(name):
    f = RESULTS_DIR / f"{name}_config.json"
    if not f.exists():
        raise FileNotFoundError(f"Config no encontrado: {f}")
    return json.load(open(f))

def build_engine_kwargs(combo_name, params, rs_min_pct: float = RS_FINVIZ_MIN_PCT_DEFAULT):
    combo_cfg = json.load(open(COMBOS_DIR / f"{combo_name}.json"))
    tier2 = params.get("tier2_filters", {})
    tier1 = params.get("tier1_strategy", {})
    tier3 = params.get("tier3_risk", {})
    signal_type   = combo_cfg.get("pattern", {}).get("signal_type", "any")
    screener_name = combo_cfg.get("screener", {}).get("name", "minervini_trend")
    risk_dollars  = int(INITIAL_CAPITAL * tier3.get("risk_fraction", 0.005))
    tier3e = {}
    for k, v in tier3.items():
        k2 = {"max_stop_pct_hard": "max_stop_pct"}.get(k, k)
        if k2 in ("rvol_danger_size","rvol_warning_size") and isinstance(v,float) and v<=1.0:
            v = int(v*100)
        if k2 == "max_stop_pct" and isinstance(v,float) and v<=1.0:
            v = round(v*100, 1)
        tier3e[k2] = v
    T2 = {"min_rvol","min_adr","max_dist_sma20","min_dollar_volume","min_volume",
          "min_consolidation_days","use_rs_percentile","min_rs_percentile",
          "rs_lookback_days","require_positive_rs","use_pattern_filter",
          "min_pattern_confidence","pattern_cache_path"}
    base = {**{k:v for k,v in tier2.items() if k in T2}, **tier3e, **tier1,
            "signal_type": signal_type, "screener_name": screener_name,
            "screener_cache_path": None,
            "mode": "production", "risk_dollars": risk_dollars,
            "fees": 0.001, "slippage": 0.001, "offline_mode": False}

    # ── FINVIZ RS OVERRIDE ──────────────────────────────────────────────────
    # Desactivar el filtro de RS basado en DB local (daily_rs_rankings).
    # Para tickers fuera de la DB, get_rs_percentile() devuelve None y el
    # screener Qullamaggie aplica fallback SPY automaticamente (rs_fallback_spy=True).
    # Usamos min_rs_percentile reducido para no bloquear buenos candidatos nuevos.
    base["use_rs_percentile"] = False          # no filtrar via DB -> usa fallback SPY
    base["min_rs_percentile"] = rs_min_pct     # umbral operativo para el fallback
    base["require_positive_rs"] = True         # mantener: exigir RS > 0 vs SPY
    # Desactivar screener cache: estos tickers no estan en el cache historico local
    base["screener_cache_path"] = None

    logger.info(
        f"  [RS-FINVIZ] use_rs_percentile=False | "
        f"min_rs_percentile={rs_min_pct} (fallback SPY) | "
        f"screener_cache desactivado"
    )
    return base

def scan_signals(combo_name, universe, date_str, rs_min_pct: float = RS_FINVIZ_MIN_PCT_DEFAULT):
    params  = load_combo_params(combo_name)
    kwargs  = build_engine_kwargs(combo_name, params, rs_min_pct=rs_min_pct)
    as_of   = pd.Timestamp(date_str)
    start   = (as_of - pd.Timedelta(days=300)).strftime("%Y-%m-%d")
    engine  = AdvancedVectorBTEngine(universe=universe, start_date=start, end_date=date_str,
                                     initial_capital=INITIAL_CAPITAL, **kwargs)
    try:
        result    = engine.run_backtest()
        
        # ── TRACKING DE TICKERS RECHAZADOS POR HISTORIA ─────────────────────
        rejected_short = result.get("rejected_tickers", [])
        if rejected_short:
            # Extraer solo el ticker de strings como "TICKER (len=...)"
            rejected_short = [str(t).split(" (")[0] for t in rejected_short]
            
            rejected_path = OUT_DIR / "rejected_short_history.json"
            current_rejected = set()
            if rejected_path.exists():
                try:
                    current_rejected = set(json.load(open(rejected_path)))
                except: pass
            
            new_rejected = [t for t in rejected_short if t not in current_rejected]
            if new_rejected:
                current_rejected.update(new_rejected)
                with open(rejected_path, "w") as f:
                    json.dump(sorted(list(current_rejected)), f, indent=2)
                logger.info(f"    [Cache] {len(new_rejected)} tickers nuevos marcados con historia insuficiente")

        trades_df = result.get("trades_df", pd.DataFrame())
        setups    = result.get("setups", [])
        signals   = []

        # 1. ── SETUPS FRESCOS (Detectados hoy para entrar mañana) ───────────
        if setups:
            logger.info(f"    [Setup] {len(setups)} candidatos detectados hoy para entrar mañana.")
            for s in setups:
                signals.append({
                    "combo": combo_name,
                    "ticker": s["ticker"],
                    "signal_date": date_str,
                    "entry_price": s["price"],
                    "stop_loss": s["stop"],
                    "position_size": 0,
                    "rs_mode": "spy_fallback",
                    "source": "finviz_setup"
                })

        # 2. ── TRADES RECIENTES (Ejecutados en los últimos días) ────────────
        if not trades_df.empty:
            col = "entry_date" if "entry_date" in trades_df.columns else None
            if col:
                # Intentar primero con la ventana de 3 días (señales frescas)
                as_of = pd.Timestamp(date_str)
                lookback_dates = set(pd.bdate_range(end=as_of, periods=3).strftime("%Y-%m-%d"))
                mask = trades_df[col].astype(str).str[:10].isin(lookback_dates)
                today_t = trades_df[mask]

                # Si no hay nada reciente, tomar el último día que generó actividad
                if today_t.empty and not signals:
                    last_date = trades_df[col].max()
                    today_t = trades_df[trades_df[col] == last_date]
                    logger.info(f"    [Aviso] No hay señales hoy. Usando último día con actividad: {str(last_date)[:10]}")
            else:
                today_t = trades_df.tail(5)

            if not today_t.empty:
                for _, row in today_t.iterrows():
                    ticker = str(row.get("ticker", row.get("symbol","?")))
                    # Evitar duplicados si ya está en setups
                    if any(s["ticker"] == ticker for s in signals):
                        continue
                        
                    signals.append({
                        "combo": combo_name,
                        "ticker": ticker,
                        "signal_date": str(row[col])[:10] if col else date_str,
                        "entry_price": float(row.get("entry_price", 0)),
                        "stop_loss": float(row.get("stop_loss", 0)),
                        "position_size": float(row.get("shares", row.get("position_size", 0))),
                        "rs_mode": "spy_fallback",
                        "source": "backtest_trade"
                    })
        return signals
    except Exception as e:
        logger.error(f"Scan error ({combo_name}): {e}", exc_info=True)
        return []
    finally:
        engine.cleanup()

def load_journal():
    jf = OUT_DIR / "journal.json"
    return json.load(open(jf)) if jf.exists() else []

def save_journal(entries):
    with open(OUT_DIR / "journal.json", "w") as f:
        json.dump(entries, f, indent=2, default=str)

def run_pre(date_str, drift_override, rs_min_pct: float = RS_FINVIZ_MIN_PCT_DEFAULT):
    logger.info("=" * 60)
    logger.info("PAPER FINVIZ - PRE-MARKET  [sistema separado, NO comparar con backtest]")
    logger.info("=" * 60)
    logger.info(f"  Fecha:  {date_str}")
    logger.info(f"  Combos: {ACTIVE_COMBOS}")
    logger.info(f"  RS min (fallback SPY): {rs_min_pct}")
    logger.info(f"  AVISO:  Universo Finviz dinamico - resultados NO comparables con WF/backtest")
    logger.info("\n  [1/3] Regime check...")
    ctx    = get_market_context_live(require_spy_above_sma200=True, spy_lookback_days=300, max_vix=35.0, db_path=DB_PATH)
    regime = apply_regime_override(ctx, "none")
    reg_ok = regime.get("effective_regime_ok", False)
    logger.info(
        f"    SPY: ${_fmt_price(ctx.get('spy_price'))}  SMA200: ${_fmt_price(ctx.get('spy_sma200'))}  "
        f"VIX: {_fmt_price(ctx.get('vix'))}  Regime: {'PASS' if reg_ok else 'BLOCKED'}"
    )
    logger.info("\n  [2/3] Cargando universo Finviz (drift gate desactivado)...")
    finviz_result = fetch_finviz_universe(FINVIZ_CFG)
    universe = finviz_result.tickers if finviz_result.ok else []
    logger.info(f"    Finviz ok={finviz_result.ok}  tickers={len(universe)}  pages={finviz_result.pages_ok}")
    
    # ── PRE-FILTRO: Tickers con historia insuficiente ──────────────────────
    rejected_path = OUT_DIR / "rejected_short_history.json"
    if rejected_path.exists():
        try:
            rejected = set(json.load(open(rejected_path)))
            before = len(universe)
            universe = [t for t in universe if t not in rejected]
            if len(universe) < before:
                logger.info(f"    Pre-filtro: {before - len(universe)} tickers con historia insuficiente excluidos")
        except Exception as e:
            logger.warning(f"    Error cargando pre-filtro: {e}")

    if finviz_result.error:
        logger.warning(f"    Finviz error: {finviz_result.error}")
    if not finviz_result.ok:
        logger.warning("    Finviz fetch fallido - abortando pre")
        return None
    logger.info(f"    Sample: {universe[:10]}")
    
    # ── [PRE-WARM] ──────────────────────────────────────────────────────────
    # Descargar los últimos 30 días para todos los tickers del universo.
    # El motor necesita data fresca para detectar setups de 'hoy'.
    pre_warm_cache(universe, date_str)

    signals = []
    if reg_ok and universe:
        for combo_name in ACTIVE_COMBOS:
            logger.info(f"\n  [3/3] Scanning {combo_name} sobre universo Finviz...")
            combo_sigs = scan_signals(combo_name, universe, date_str, rs_min_pct=rs_min_pct)
            signals.extend(combo_sigs)
            logger.info(f"    Senales {combo_name}: {len(combo_sigs)}")
            
        # Deduplicar por ticker, preferir el combo con mayor position_size
        seen = {}
        for s in signals:
            t = s["ticker"]
            if t not in seen or s.get("position_size", 0) > seen[t].get("position_size", 0):
                seen[t] = s
        signals = list(seen.values())

        for s in signals:
            logger.info(f"      {s['ticker']:6s} ({s['combo']}) entrada=${s['entry_price']:.2f}  stop=${s['stop_loss']:.2f}")
    elif not reg_ok:
        logger.warning("  [3/3] SKIP - regime bloqueado")
    day_dir = OUT_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    snap = {"date": date_str, "source": "finviz",
            "universe_size": len(universe), "universe_sample": universe[:30],
            "finviz_pages_ok": finviz_result.pages_ok,
            "finviz_warnings": finviz_result.parse_warnings,
            "regime_ok": reg_ok, "signals": signals, "signals_count": len(signals),
            "rs_mode": "spy_fallback", "rs_min_pct": rs_min_pct,
            "drift_gate": "disabled", "generated_at": datetime.now().isoformat()}
    with open(day_dir / "snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)
    journal = [e for e in load_journal() if e.get("date") != date_str]
    journal.append({"date": date_str, "universe_size": len(universe),
                    "regime_ok": reg_ok, "signals": signals})
    save_journal(journal)
    all_sigs = [s for e in journal for s in e.get("signals",[])]
    logger.info(f"\n  Journal acumulado: {len(journal)} dias / {len(all_sigs)} senales totales")
    logger.info(f"  Snapshot: {day_dir / 'snapshot.json'}")
    logger.info("PRE-MARKET FINVIZ COMPLETE")
    return snap

def main():
    parser = argparse.ArgumentParser(description="Paper trading universo Finviz (separado del pipeline local)")
    parser.add_argument("--phase", choices=["pre"], default="pre")
    parser.add_argument("--date", default=None)
    parser.add_argument("--drift-override", type=float, default=100.0,
                        help="Max drift%% permitido (default 100 = sin restriccion)")
    parser.add_argument("--rs-min", type=float, default=RS_FINVIZ_MIN_PCT_DEFAULT,
                        help=f"Umbral minimo de RS relativo vs SPY para modo Finviz (default: {RS_FINVIZ_MIN_PCT_DEFAULT})")
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.phase == "pre":
        run_pre(date_str, args.drift_override, rs_min_pct=args.rs_min)

if __name__ == "__main__":
    main()
