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

import argparse, json, logging, sys, sqlite3, os
from datetime import datetime
from pathlib import Path
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv()
from src.utils.market_context_live import get_market_context_live, apply_regime_override
from src.signals.signal_engine import evaluate_ticker
from src.integration.combo_loader import load_combo_merged
from scripts.execution_intents import build_intents
from scripts.paper_execution_loop import simulate_run

OUT_DIR = ROOT / "outputs" / "paper_local"
DB_PATH = ROOT / "data" / "ticker_cache.db"
RESULTS_DIR = ROOT / "outputs" / "best_combos_run"
COMBOS_DIR = ROOT / "config" / "combos"
INTENTS_DIR = ROOT / "outputs" / "execution_intents"
OUT_DIR.mkdir(parents=True, exist_ok=True)
(ROOT / "logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
ACTIVE_COMBOS = ["combo_pure_momentum", "combo_stage2_breakout"]
UNIVERSE_SIZE = 200
INITIAL_CAPITAL = 100_000
SCORECARD_TARGETS = {
    "min_trades_6w": 25,
    "min_win_rate": 45.0,
    "min_pf": 1.40,
    "max_dd_pct": 15.0,
}


def _fmt_price(value, default: str = "N/A") -> str:
    try:
        if value is None or pd.isna(value):
            return default
        return f"{float(value):.2f}"
    except Exception:
        return default


def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
        (ticker, start, end),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
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
            conn,
            params=(start, as_of_date, limit),
        )
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
    sigs = [s for e in journal for s in e.get("signals", [])]
    total = len(sigs)
    days = len(journal)
    return {
        "days_run": days,
        "signals_total": total,
        "signals_per_day": round(total / max(days, 1), 1),
        "target_25_ok": total >= SCORECARD_TARGETS["min_trades_6w"],
        "remaining": max(0, SCORECARD_TARGETS["min_trades_6w"] - total),
    }


def telegram_send(text: str, parse_mode: str = "HTML") -> bool:
    import httpx, os

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            return r.status_code == 200
    except:
        return False


def build_paper_alert_html(snap):
    date = snap["date"]
    regime = snap["regime"]

    status_icon = "🟢" if regime["pass"] else "🔴"
    spy_icon = "✅" if regime["spy_ok"] else "❌"
    vix_icon = "✅" if regime["vix_ok"] else "❌"

    header = f"📋 <b>PAPER LOCAL | {date}</b>\n"
    regime_text = (
        f"\n{status_icon} <b>Regime Check:</b>\n"
        f"• SPY > SMA200: {spy_icon}\n"
        f"• VIX &lt; 35: {vix_icon}\n"
        f"• Status: {'<b>PASS</b>' if regime['pass'] else '<b>BLOCKED</b>'}\n"
    )

    signals = snap.get("signals", [])
    signals_text = f"\n🛰 <b>Signals Found: {len(signals)}</b>\n"
    if signals:
        signals_text += "<pre>"
        signals_text += f"{'Ticker':<7} {'Entry':<8} {'Agent':<10}\n"
        signals_text += f"{'-' * 7} {'-' * 8} {'-' * 10}\n"
        # Mostrar top 10
        for s in signals[:10]:
            signals_text += (
                f"{s['ticker']:<7} {s['entry_price']:<8.2f} {s['combo'][:10]:<10}\n"
            )
        if len(signals) > 10:
            signals_text += f"... and {len(signals) - 10} more\n"
        signals_text += "</pre>"

    return header + regime_text + signals_text


def run_pre(date_str, universe_size, send_telegram=False):
    logger.info("=" * 60)
    logger.info("PAPER LOCAL DB - PRE-MARKET (PRO)")
    logger.info("=" * 60)
    logger.info(f"  Fecha:   {date_str}")
    logger.info(f"  Modo:    DB local (Hibrido A + B)")
    logger.info(f"  Combos:  {ACTIVE_COMBOS}")
    logger.info(f"  Capital: ${INITIAL_CAPITAL:,}")

    logger.info("\n  [1/3] Regime check (SPY > SMA200, VIX < 35)...")
    ctx = get_market_context_live(
        require_spy_above_sma200=True,
        spy_lookback_days=300,
        max_vix=35.0,
        db_path=DB_PATH,
    )
    regime = apply_regime_override(ctx, "none")
    spy_ok = regime.get("effective_spy_ok", False)
    vix_ok = regime.get("effective_vix_ok", False)
    reg_ok = regime.get("effective_regime_ok", False)

    logger.info(
        f"    SPY: ${_fmt_price(ctx.get('spy_price'))}  SMA200: ${_fmt_price(ctx.get('spy_sma200'))}  {'OK' if spy_ok else 'BLOCKED'}"
    )
    logger.info(f"    VIX: {_fmt_price(ctx.get('vix'))}  {'OK' if vix_ok else 'BLOCKED'}")
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
                tier1 = s.get("tier1_metrics", {})
                signals.append(
                    {
                        "combo": s.get("combo_name", "A_BOTH_PRO"),
                        "ticker": s["ticker"],
                        "signal_date": date_str,
                        "entry_price": s.get("entry_price", 0.0),
                        "stop_loss": float(tier1.get("stop_price", 0.0)),
                        "position_size": float(tier1.get("shares", 0.0)),
                        "risk_budget_usd": float(tier1.get("risk_budget_usd", 0.0)),
                        "risk_per_share": float(tier1.get("risk_per_share", 0.0)),
                        "tp1_price": float(tier1.get("tp1_price", 0.0)),
                        "tp2_price": float(tier1.get("tp2_price", 0.0)),
                        "tp1_pct": float(tier1.get("tp1_pct", 0.0)),
                        "tp2_pct": float(tier1.get("tp2_pct", 0.0)),
                        "runner_pct": float(tier1.get("runner_pct", 0.0)),
                        "source": "local_db",
                    }
                )
            logger.info(f"    Senales totales: {len(signals)}")
        except Exception as e:
            logger.error(f"Error en daily_scan: {e}")

        for s in signals:
            logger.info(
                f"      {s['ticker']:6s} ({s['combo']}) entrada=${s['entry_price']:.2f}  stop=${s['stop_loss']:.2f}"
            )
    elif not reg_ok:
        logger.warning("  [3/3] SKIP - regime bloqueado")
    else:
        logger.warning("  [3/3] SKIP - universo vacio")
    day_dir = OUT_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "date": date_str,
        "source": "local_db",
        "universe_size": len(universe),
        "universe_sample": universe[:20],
        "regime": {"spy_ok": spy_ok, "vix_ok": vix_ok, "pass": reg_ok},
        "signals": signals,
        "signals_count": len(signals),
        "generated_at": datetime.now().isoformat(),
    }
    with open(day_dir / "snapshot.json", "w") as f:
        json.dump(snap, f, indent=2)
    journal = [e for e in load_journal() if e.get("date") != date_str]
    journal.append(
        {
            "date": date_str,
            "phase": "pre",
            "universe_size": len(universe),
            "regime_ok": reg_ok,
            "signals": signals,
        }
    )
    save_journal(journal)

    intents = build_intents(date_str, source_universe="local_db")
    day_intents = INTENTS_DIR / date_str
    day_intents.mkdir(parents=True, exist_ok=True)
    from src.integration.execution_ledger import write_jsonl, write_csv

    write_jsonl(day_intents / "execution_intents.jsonl", intents)
    write_csv(day_intents / "execution_intents.csv", intents)
    with open(day_intents / "execution_intents_meta.json", "w") as f:
        json.dump(
            {"date": date_str, "count": len(intents), "source_universe": "local_db"},
            f,
            indent=2,
        )

    paper_result = simulate_run(
        pd.DataFrame([i.metadata for i in intents]) if intents else pd.DataFrame(),
        date_str,
        dry_run=True,
    )
    with open(day_dir / "paper_preview.json", "w") as f:
        json.dump(paper_result, f, indent=2, default=str)

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

    if send_telegram:
        msg = build_paper_alert_html(snap)
        ok = telegram_send(msg)
        logger.info(f"  Telegram: {'✓ enviado' if ok else '✗ error'}")

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
    snap = json.load(open(snap_file))
    signals = snap.get("signals", [])
    logger.info(f"  Senales del dia: {len(signals)}")
    intents_path = INTENTS_DIR / date_str / "execution_intents.csv"
    if intents_path.exists():
        logger.info(f"  Intents detectados: {intents_path}")
    if signals:
        tickers = list(set(s["ticker"] for s in signals))
        try:
            end_dt = (pd.Timestamp(date_str) + pd.Timedelta(days=1)).strftime(
                "%Y-%m-%d"
            )
            data = yf.download(
                tickers, start=date_str, end=end_dt, progress=False, auto_adjust=True
            )
            closes = {}
            if not data.empty and "Close" in data.columns:
                row = data["Close"].iloc[-1]
                closes = (
                    row.to_dict()
                    if hasattr(row, "to_dict")
                    else {tickers[0]: float(row)}
                )
        except Exception as e:
            logger.warning(f"  yfinance: {e}")
            closes = {}
        pnl_total = 0.0
        for s in signals:
            eod = float(closes.get(s["ticker"], s["entry_price"]))
            pnl = (eod - s["entry_price"]) * s.get("position_size", 0)
            pnl_total += pnl
            logger.info(
                f"    {s['ticker']:6s}  entry={s['entry_price']:.2f}  eod={eod:.2f}  pnl={pnl:+.0f}$"
            )
        logger.info(f"\n  P&L dia: ${pnl_total:+,.0f}")
        snap["eod_pnl"] = round(pnl_total, 2)
        with open(snap_file, "w") as f:
            json.dump(snap, f, indent=2)
    logger.info("EOD LOCAL COMPLETE")


def main():
    parser = argparse.ArgumentParser(description="Paper trading DB local (sin Finviz)")
    parser.add_argument("--phase", choices=["pre", "eod", "all"], default="pre")
    parser.add_argument("--date", default=None)
    parser.add_argument("--universe-size", type=int, default=UNIVERSE_SIZE)
    parser.add_argument("--telegram", action="store_true", help="Send Telegram alert")
    args = parser.parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    if args.phase in ("pre", "all"):
        run_pre(date_str, args.universe_size, send_telegram=args.telegram)
    if args.phase in ("eod", "all"):
        run_eod(date_str)


if __name__ == "__main__":
    main()
