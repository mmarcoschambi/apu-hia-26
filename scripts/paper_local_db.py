#!/usr/bin/env python3
"""
PAPER TRADING - UNIVERSO LOCAL (DB)
Variante del runbook que usa DB local como universo, sin Finviz.
- Universo identico al backtest -> convergencia medible
- Sin dependencia externa, 100% reproducible
- Si no corriste un dia, podes reconstruirlo exactamente con --date
- Scorecard IC semanal comparable con WF 2022-2025
Usage:
    python3 scripts/paper_local_db.py --phase pre
    python3 scripts/paper_local_db.py --phase eod
    python3 scripts/paper_local_db.py --phase pre --universe-size 400
    python3 scripts/paper_local_db.py --phase pre --date 2025-03-15
Outputs -> outputs/paper_local/
"""
import argparse, json, logging, sys, sqlite3
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from src.utils.market_context_live import get_market_context_live, apply_regime_override
from src.signals.signal_engine import evaluate_ticker
from src.integration.combo_loader import load_combo_merged
OUT_DIR     = ROOT / "outputs" / "paper_local"
DB_PATH     = ROOT / "data" / "ticker_cache.db"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR  = ROOT / "config" / "combos"
OUT_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
ACTIVE_COMBOS   = ["combo_pure_momentum", "combo_stage2_breakout"]
UNIVERSE_SIZE   = 200
INITIAL_CAPITAL = 100_000
SCORECARD_TARGETS = {"min_trades_6w": 25, "min_win_rate": 45.0, "min_pf": 1.40, "max_dd_pct": 15.0}

def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
        (ticker, start, end),
    ).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)

def get_universe_from_db(as_of_date, lookback_days=252, limit=UNIVERSE_SIZE):
    as_of = pd.Timestamp(as_of_date)
    start = (as_of - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        conn = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql_query(
            "SELECT ticker, COUNT(*) as cnt FROM ohlcv_cache WHERE date >= ? AND date <= ? GROUP BY ticker ORDER BY cnt DESC LIMIT ?",
            conn, params=(start, as_of_date, limit))
        conn.close()
        if not df.empty:
            return df["ticker"].tolist()
    except Exception as e:
        logger.error(f"DB error: {e}")
    return []

def load_journal():
    jf = OUT_DIR / "journal.json"
    return json.load(open(jf)) if jf.exists() else []

def save_journal(entries):
    with open(OUT_DIR / "journal.json", "w") as f:
        json.dump(entries, f, indent=2, default=str)

def compute_scorecard(journal):
    sigs  = [s for e in journal for s in e.get("signals",[])]
    total = len(sigs)
    days  = len(journal)
    return {"days_run": days, "signals_total": total,
            "signals_per_day": round(total/max(days,1),1),
            "target_25_ok": total >= SCORECARD_TARGETS["min_trades_6w"],
            "remaining": max(0, SCORECARD_TARGETS["min_trades_6w"]-total)}

def run_pre(date_str, universe_size):
    logger.info("=" * 60)
    logger.info("PAPER LOCAL DB - PRE-MARKET (PRO)")
    logger.info("=" * 60)
    logger.info(f"  Fecha:   {date_str}")
    logger.info(f"  Modo:    DB local (Hibrido A + B)")
    logger.info(f"  Combos:  {ACTIVE_COMBOS}")
    logger.info(f"  Capital: ${INITIAL_CAPITAL:,}")
    
    logger.info("\n  [1/3] Regime check (SPY > SMA200, VIX < 35)...")
    ctx    = get_market_context_live(
        require_spy_above_sma200=True, 
        spy_lookback_days=300, 
        max_vix=35.0, 
        db_path=DB_PATH
    )
    regime = apply_regime_override(ctx, "none")
    spy_ok = regime.get("effective_spy_ok", False)
    vix_ok = regime.get("effective_vix_ok", False)
    reg_ok = regime.get("effective_regime_ok", False)
    
    logger.info(f"    SPY: ${ctx.get('spy_price',0):.2f}  SMA200: ${ctx.get('spy_sma200',0):.2f}  {'OK' if spy_ok else 'BLOCKED'}")
    logger.info(f"    VIX: {ctx.get('vix','N/A')}  {'OK' if vix_ok else 'BLOCKED'}")
    logger.info(f"    Regime: {'PASS' if reg_ok else 'BLOCKED'}")
    
    logger.info(f"\n  [2/3] Universo DB ({universe_size} tickers)...")
    universe = get_universe_from_db(date_str, limit=universe_size)
    logger.info(f"    Tickers: {len(universe)}")
    
    signals = []
    if reg_ok and universe:
        logger.info(f"\n  [3/3] Scanning usando daily_scan.py (A_BOTH)...")
        from scripts.daily_scan import run_daily_scan
        try:
            # run_daily_scan ya filtra internamente, lee universo, etc.
            daily_sigs = run_daily_scan(date_str, max_tickers=universe_size)
            
            for s in daily_sigs:
                signals.append({
                    "combo": s.get("combo_name", "A_BOTH_PRO"),
                    "ticker": s["ticker"],
                    "signal_date": date_str,
                    "entry_price": s.get("entry_price", 0.0),
                    "stop_loss": float(s.get("tier1_metrics", {}).get("stop_price", 0.0)),
                    "position_size": float(s.get("tier1_metrics", {}).get("shares", 0.0)),
                    "source": "local_db"
                })
            logger.info(f"    Senales totales: {len(signals)}")
        except Exception as e:
            logger.error(f"Error en daily_scan: {e}")
        
        for s in signals:
            logger.info(f"      {s['ticker']:6s} ({s['combo']}) entrada=${s['entry_price']:.2f}  stop=${s['stop_loss']:.2f}")
    elif not reg_ok:
        logger.warning("  [3/3] SKIP - regime bloqueado")
    else:
        logger.warning("  [3/3] SKIP - universo vacio")
    day_dir = OUT_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    snap = {"date": date_str, "source": "local_db", "universe_size": len(universe),
            "universe_sample": universe[:20],
            "regime": {"spy_ok": spy_ok, "vix_ok": vix_ok, "pass": reg_ok},
            "signals": signals, "signals_count": len(signals),
            "generated_at": datetime.now().isoformat()}
    with open(day_dir / "snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)
    journal = [e for e in load_journal() if e.get("date") != date_str]
    journal.append({"date": date_str, "phase": "pre", "universe_size": len(universe),
                    "regime_ok": reg_ok, "signals": signals})
    save_journal(journal)
    sc = compute_scorecard(journal)
    logger.info(f"\n  SCORECARD ACUMULADO (meta 6 semanas):")
    logger.info(f"    Dias corridos:   {sc['days_run']}")
    logger.info(f"    Senales totales: {sc['signals_total']}")
    logger.info(f"    Promedio/dia:    {sc['signals_per_day']}")
    if sc["target_25_ok"]:
        logger.info(f"    Meta 25 trades:  ALCANZADA")
    else:
        logger.info(f"    Meta 25 trades:  faltan {sc['remaining']}")
    logger.info(f"\n  Snapshot: {day_dir / 'snapshot.json'}")
    logger.info("PRE-MARKET LOCAL COMPLETE")
    return snap

def run_eod(date_str):
    logger.info("=" * 60)
    logger.info("PAPER LOCAL DB - END OF DAY")
    logger.info("=" * 60)
    snap_file = OUT_DIR / date_str / "snapshot.json"
    if not snap_file.exists():
        logger.warning(f"  Sin snapshot para {date_str}. Corre --phase pre primero.")
        return
    snap    = json.load(open(snap_file))
    signals = snap.get("signals", [])
    logger.info(f"  Senales del dia: {len(signals)}")
    if signals:
        tickers = list(set(s["ticker"] for s in signals))
        try:
            end_dt = (pd.Timestamp(date_str) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            data   = yf.download(tickers, start=date_str, end=end_dt, progress=False, auto_adjust=True)
            closes = {}
            if not data.empty and "Close" in data.columns:
                row = data["Close"].iloc[-1]
                closes = row.to_dict() if hasattr(row,"to_dict") else {tickers[0]: float(row)}
        except Exception as e:
            logger.warning(f"  yfinance: {e}")
            closes = {}
        pnl_total = 0.0
        for s in signals:
            eod = float(closes.get(s["ticker"], s["entry_price"]))
            pnl = (eod - s["entry_price"]) * s.get("position_size", 0)
            pnl_total += pnl
            logger.info(f"    {s['ticker']:6s}  entry={s['entry_price']:.2f}  eod={eod:.2f}  pnl={pnl:+.0f}$")
        logger.info(f"\n  P&L dia: ${pnl_total:+,.0f}")
        snap["eod_pnl"] = round(pnl_total, 2)
        with open(snap_file, "w") as f:
            json.dump(snap, f, indent=2)
    logger.info("EOD LOCAL COMPLETE")

def main():
    parser = argparse.ArgumentParser(description="Paper trading DB local (sin Finviz)")
    parser.add_argument("--phase", choices=["pre","eod","all"], default="pre")
    parser.add_argument("--date", default=None)
    parser.add_argument("--universe-size", type=int, default=UNIVERSE_SIZE)
    args     = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.phase in ("pre","all"):
        run_pre(date_str, args.universe_size)
    if args.phase in ("eod","all"):
        run_eod(date_str)

if __name__ == "__main__":
    main()
