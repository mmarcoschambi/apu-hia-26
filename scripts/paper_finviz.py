#!/usr/bin/env python3
"""
PAPER TRADING - UNIVERSO FINVIZ (sistema paralelo, separado)
Usa Finviz como universo dinamico. NO mezclar con paper_local_db ni con backtest.
Objetivo: detectar si Finviz descubre oportunidades que el universo local no captura.
El drift gate esta desactivado aqui (bloque_on_high_drift=False).
Usage:
    python3 scripts/paper_finviz.py --phase pre
    python3 scripts/paper_finviz.py --phase pre --drift-override 100
Outputs -> outputs/paper_finviz/
"""
import argparse, json, logging, sys, sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.data.finviz_universe_provider import fetch_finviz_universe
from src.utils.market_context_live import get_market_context_live, apply_regime_override
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
OUT_DIR     = ROOT / "outputs" / "paper_finviz"
DB_PATH     = ROOT / "data" / "ticker_cache.db"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR  = ROOT / "config" / "combos"
OUT_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
ACTIVE_COMBOS    = ["combo_pure_momentum", "combo_stage2_breakout"]
INITIAL_CAPITAL = 100_000
FINVIZ_CFG = {
    "finviz": {"base_url": "https://finviz.com/screener.ashx",
               "filters": "cap_midover,sh_avgvol_o1000,sh_price_o10",
               "sort": "relativevolume", "max_pages": 20,
               "timeout_sec": 15, "retries": 3, "min_tickers": 80}}

def load_combo_params(name):
    f = RESULTS_DIR / f"{name}_config.json"
    if not f.exists():
        raise FileNotFoundError(f"Config no encontrado: {f}")
    return json.load(open(f))

def build_engine_kwargs(combo_name, params):
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
    return {**{k:v for k,v in tier2.items() if k in T2}, **tier3e, **tier1,
            "signal_type": signal_type, "screener_name": screener_name,
            "screener_cache_path": str(ROOT / "data" / "screener_cache"),
            "mode": "production", "risk_dollars": risk_dollars,
            "fees": 0.001, "slippage": 0.001}

def scan_signals(combo_name, universe, date_str):
    params  = load_combo_params(combo_name)
    kwargs  = build_engine_kwargs(combo_name, params)
    as_of   = pd.Timestamp(date_str)
    start   = (as_of - pd.Timedelta(days=300)).strftime("%Y-%m-%d")
    engine  = AdvancedVectorBTEngine(universe=universe, start_date=start, end_date=date_str,
                                     initial_capital=INITIAL_CAPITAL, **kwargs)
    try:
        result    = engine.run_backtest()
        trades_df = result.get("trades_df", pd.DataFrame())
        signals   = []
        if not trades_df.empty:
            col = "entry_date" if "entry_date" in trades_df.columns else None
            today_t = (trades_df[trades_df[col].astype(str).str.startswith(date_str)]
                       if col else trades_df.tail(5))
            for _, row in today_t.iterrows():
                signals.append({"combo": combo_name,
                                 "ticker": str(row.get("ticker", row.get("symbol","?"))),
                                 "signal_date": date_str,
                                 "entry_price": float(row.get("entry_price",0)),
                                 "stop_loss":   float(row.get("stop_loss",0)),
                                 "position_size": float(row.get("size", row.get("position_size",0))),
                                 "source": "finviz"})
        return signals
    except Exception as e:
        logger.error(f"Scan error: {e}")
        return []
    finally:
        engine.cleanup()

def load_journal():
    jf = OUT_DIR / "journal.json"
    return json.load(open(jf)) if jf.exists() else []

def save_journal(entries):
    with open(OUT_DIR / "journal.json", "w") as f:
        json.dump(entries, f, indent=2, default=str)

def run_pre(date_str, drift_override):
    logger.info("=" * 60)
    logger.info("PAPER FINVIZ - PRE-MARKET  [sistema separado, NO comparar con backtest]")
    logger.info("=" * 60)
    logger.info(f"  Fecha:  {date_str}")
    logger.info(f"  Combos: {ACTIVE_COMBOS}")
    logger.info(f"  AVISO:  Universo Finviz dinamico - resultados NO comparables con WF/backtest")
    logger.info("\n  [1/3] Regime check...")
    ctx    = get_market_context_live(require_spy_above_sma200=True, spy_lookback_days=300, max_vix=35.0, db_path=DB_PATH)
    regime = apply_regime_override(ctx, "none")
    reg_ok = regime.get("effective_regime_ok", False)
    logger.info(f"    SPY: ${ctx.get('spy_price',0):.2f}  SMA200: ${ctx.get('spy_sma200',0):.2f}  VIX: {ctx.get('vix','N/A')}  Regime: {'PASS' if reg_ok else 'BLOCKED'}")
    logger.info("\n  [2/3] Cargando universo Finviz (drift gate desactivado)...")
    finviz_result = fetch_finviz_universe(FINVIZ_CFG)
    universe = finviz_result.tickers if finviz_result.ok else []
    logger.info(f"    Finviz ok={finviz_result.ok}  tickers={len(universe)}  pages={finviz_result.pages_ok}")
    if finviz_result.error:
        logger.warning(f"    Finviz error: {finviz_result.error}")
    if not finviz_result.ok:
        logger.warning("    Finviz fetch fallido - abortando pre")
        return None
    logger.info(f"    Sample: {universe[:10]}")
    signals = []
    if reg_ok and universe:
        for combo_name in ACTIVE_COMBOS:
            logger.info(f"\n  [3/3] Scanning {combo_name} sobre universo Finviz...")
            combo_sigs = scan_signals(combo_name, universe, date_str)
            signals.extend(combo_sigs)
            logger.info(f"    Senales {combo_name}: {len(combo_sigs)}")
            
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
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.phase == "pre":
        run_pre(date_str, args.drift_override)

if __name__ == "__main__":
    main()
