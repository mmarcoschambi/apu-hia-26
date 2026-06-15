#!/usr/bin/env python3
"""
live_auto_trader.py - Automated & Managed Live Paper Trading Bot.

Este script tiene dos funciones principales:
1. FLOW AUTOMÁTICO: Auto-aprueba las señales del día y las gestiona (TP1/TP2/SL).
2. FLOW MANUAL (DEMO): Gestiona automáticamente las posiciones que el usuario aprueba en Telegram.

Directorio de datos:
- Auto: outputs/live_paper_auto/runs/YYYY-MM-DD/
- Demo: outputs/paper_demo_telegram/runs/YYYY-MM-DD/

Usage:
    python3 scripts/live_auto_trader.py --monitor --interval 1
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

try:
    import pytz
except ImportError:
    pytz = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

AUTO_LEDGER_ROOT = PROJECT_ROOT / "outputs" / "live_paper_auto" / "runs"
DEMO_LEDGER_ROOT = PROJECT_ROOT / "outputs" / "paper_demo_telegram" / "runs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | LIVE-AUTO | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# --- UTILS ---

def today_ny() -> str:
    """Retorna fecha actual en formato YYYY-MM-DD usando timezone de NY."""
    if pytz:
        tz = pytz.timezone("America/New_York")
        return datetime.now(tz).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")

def load_live_signals(date: str) -> pd.DataFrame:
    """Lee señales confirmadas desde combined.csv con validación robusta."""
    path = PROJECT_ROOT / "outputs" / "live_signals" / date / "combined.csv"
    if not path.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(path)
        if df.empty:
            return pd.DataFrame()
            
        required = ["ticker", "entry_price", "source_universe", "decision_source"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            logger.warning(f"Combined.csv incompleto. Faltan columnas: {missing}")
            return pd.DataFrame()
        return df
    except Exception as e:
        logger.error(f"Error leyendo {path}: {e}")
        return pd.DataFrame()

def load_config():
    """Carga configuración de producción para parámetros de riesgo."""
    path = PROJECT_ROOT / "config" / "production_config.json"
    if not path.exists():
        logger.warning(f"Config no encontrada en {path}, usando defaults.")
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        logger.error(f"Error parsing config: {e}")
        return {}

def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)

def save_csv(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)

def log_action(ledger_name: str, date: str, action: str, ticker: str, price: float, reason: str = ""):
    root = AUTO_LEDGER_ROOT if ledger_name == "AUTO" else DEMO_LEDGER_ROOT
    path = root / date / "trade_log.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] {action} | {ticker} @ {price:.2f} | {reason}\n")
    logger.info(f"[{ledger_name}] {action} | {ticker} @ {price:.2f} | {reason}")

# --- EXECUTION ---

def is_auto_enabled() -> bool:
    """Check if auto-trading is explicitly enabled via environment or config."""
    # 1. Check environment
    env_val = os.getenv("LIVE_AUTO_TRADER_ENABLED", "0").lower()
    if env_val in ("1", "true", "yes"):
        return True
        
    # 2. Check config file
    config = load_config()
    cfg_val = str(config.get("LIVE_AUTO_TRADER_ENABLED", "0")).lower()
    return cfg_val in ("1", "true", "yes")

def auto_approve_signals(date: str):
    """FLOW AUTO: Auto-aprueba señales confirmadas por finviz_live_promoter."""
    if not is_auto_enabled():
        logger.info("Auto-trading is DISABLED (LIVE_AUTO_TRADER_ENABLED != 1). Skipping signal approval.")
        return

    signals_df = load_live_signals(date)
    if signals_df.empty:
        return

    # Filtrar solo señales de finviz_live_promoter
    mask = (signals_df.get("source_universe") == "finviz") & \
           (signals_df.get("decision_source") == "finviz_live_promoter")
    
    signals_df = signals_df[mask].copy()
    if signals_df.empty:
        return

    signals_df = signals_df.sort_values("entry_price", ascending=False).drop_duplicates("ticker")
    
    config = load_config()
    risk_cfg = config.get("tier3_risk", {})
    strat_cfg = config.get("tier1_strategy", {})
    ui_cfg = config.get("ui_defaults", {})
    
    # Parámetros de Riesgo
    capital = ui_cfg.get("initial_capital", 100000)
    risk_fraction = risk_cfg.get("risk_fraction", 0.02878)
    max_pos_pct = risk_cfg.get("max_position_pct", 0.25)
    max_stop_hard = risk_cfg.get("max_stop_pct_hard", 0.08)
    
    tp1_r_mult = strat_cfg.get("tp1_r", 1.25)
    tp2_r_mult = strat_cfg.get("tp2_r", 3.0)

    risk_dollars = capital * risk_fraction
    max_pos_val = capital * max_pos_pct

    path = AUTO_LEDGER_ROOT / date / "positions.csv"
    positions_df = load_csv(path)
    existing = set(positions_df["ticker"].tolist()) if not positions_df.empty else set()

    new_rows = []
    for _, row in signals_df.iterrows():
        ticker = row["ticker"]
        if ticker in existing:
            continue
            
        entry = float(row.get("entry_price", 0) or 0)
        if entry <= 0:
            logger.warning(f"Skipping {ticker}: Invalid entry price {entry}")
            continue
            
        # Stop Loss logic
        stop_source = "signal"
        stop = float(row.get("stop_price", row.get("stop_loss", 0)) or 0)
        if stop <= 0 or stop >= entry:
            stop = entry * (1 - max_stop_hard)
            stop_source = "fallback_hard"
        
        risk_per_share = entry - stop
        if risk_per_share <= 0:
            logger.warning(f"Skipping {ticker}: Invalid risk per share (Entry: {entry}, Stop: {stop})")
            continue
            
        # Sizing (read shares from row if present and valid)
        qty = int(row.get("shares", 0) or 0)
        if qty <= 0:
            qty_risk = risk_dollars / risk_per_share
            qty_cap = max_pos_val / entry
            qty = int(min(qty_risk, qty_cap))
            sizing_source = "calculated_fallback"
        else:
            sizing_source = "signal_shares"
        
        if qty <= 0:
            logger.warning(f"Skipping {ticker}: Calculated Qty is 0 for {ticker}")
            continue

        # TPs
        tp1 = float(row.get("tp1_price", 0) or 0)
        if tp1 <= 0 or tp1 <= entry:
            tp1 = entry + (tp1_r_mult * risk_per_share)
            
        tp2 = float(row.get("tp2_price", 0) or 0)
        if tp2 <= 0 or tp2 <= entry:
            tp2 = entry + (tp2_r_mult * risk_per_share)
            
        new_rows.append({
            "position_id": f"pos_auto_{ticker}_{date}",
            "ticker": ticker,
            "status": "open",
            "entry_price": entry,
            "stop_price": stop,
            "tp1_price": tp1,
            "tp2_price": tp2,
            "qty": qty,
            "qty_remaining": qty,
            "tp1_hit": False,
            "tp2_hit": False,
            "realized_pnl": 0.0,
            "exited": False,
            "risk_fraction": risk_fraction,
            "risk_dollars": risk_dollars,
            "risk_per_share": risk_per_share,
            "stop_source": stop_source
        })
        log_action("AUTO", date, "ENTER", ticker, entry, f"from live_signals ({stop_source} stop, {sizing_source} sizing)")

    if new_rows:
        df = pd.DataFrame(new_rows)
        save_csv(path, pd.concat([positions_df, df], ignore_index=True) if not positions_df.empty else df)

def fetch_prices(tickers: list) -> dict:
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False)
        if data.empty:
            return {}
        res = {}
        for t in tickers:
            try:
                df = data.xs(t, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data
                if df.empty: continue
                res[t] = {"high": float(df["High"].max()), "low": float(df["Low"].min()), "last": float(df["Close"].iloc[-1])}
            except: pass
        return res
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        return {}

def manage_ledger(ledger_name: str, date: str):
    """Revisa TPs y SLs para un ledger específico."""
    root = AUTO_LEDGER_ROOT if ledger_name == "AUTO" else DEMO_LEDGER_ROOT
    path = root / date / "positions.csv"
    df = load_csv(path)
    if df.empty:
        return

    # Nos interesan posiciones abiertas y que no tengan 'exited' True
    # Algunos CSVs usan status='open', otros usan exited=False.
    open_mask = (df["status"] == "open") & (~df.get("exited", False))
    open_pos = df[open_mask]
    if open_pos.empty:
        return

    tickers = open_pos["ticker"].tolist()
    prices = fetch_prices(tickers)
    updated = False

    for idx, row in open_pos.iterrows():
        t = row["ticker"]
        if t not in prices: continue
        
        m = prices[t]
        high, low = m["high"], m["low"]
        entry, stop, tp1, tp2 = row["entry_price"], row["stop_price"], row.get("tp1_price"), row.get("tp2_price")
        qty_rem = row["qty_remaining"] if "qty_remaining" in row else row["qty"]

        # 1. STOP LOSS
        if low <= stop:
            pnl = (stop - entry) * qty_rem
            df.at[idx, "status"] = "closed"
            df.at[idx, "exited"] = True
            df.at[idx, "exit_price"] = stop
            df.at[idx, "realized_pnl"] = (df.at[idx, "realized_pnl"] if "realized_pnl" in df.columns else 0) + pnl
            df.at[idx, "qty_remaining"] = 0
            log_action(ledger_name, date, "STOP", t, stop, f"Hit SL (Low: {low:.2f})")
            updated = True
            continue

        # 2. TP1
        if tp1 and tp1 > 0 and not row.get("tp1_hit", False) and high >= tp1:
            exit_qty = int(row["qty"] * 0.33)
            if 0 < exit_qty <= qty_rem:
                pnl = (tp1 - entry) * exit_qty
                df.at[idx, "realized_pnl"] = (df.at[idx, "realized_pnl"] if "realized_pnl" in df.columns else 0) + pnl
                df.at[idx, "qty_remaining"] = qty_rem - exit_qty
                df.at[idx, "tp1_hit"] = True
                df.at[idx, "stop_price"] = entry # Breakeven
                log_action(ledger_name, date, "TP1", t, tp1, "Moved Stop to BE")
                updated = True
                qty_rem -= exit_qty

        # 3. TP2
        if tp2 and tp2 > 0 and not row.get("tp2_hit", False) and high >= tp2 and qty_rem > 0:
            exit_qty = int(row["qty"] * 0.33)
            if 0 < exit_qty <= qty_rem:
                pnl = (tp2 - entry) * exit_qty
                df.at[idx, "realized_pnl"] = (df.at[idx, "realized_pnl"] if "realized_pnl" in df.columns else 0) + pnl
                df.at[idx, "qty_remaining"] = qty_rem - exit_qty
                df.at[idx, "tp2_hit"] = True
                log_action(ledger_name, date, "TP2", t, tp2, "Secured TP2")
                updated = True

    if updated:
        save_csv(path, df)

from src.utils.telegram_client import telegram_send as shared_telegram_send

def send_portfolio_summary(date: str):
    """Envía un resumen del portafolio automático a Telegram."""
    if not is_auto_enabled():
        return
        
    path = AUTO_LEDGER_ROOT / date / "positions.csv"
    df = load_csv(path)
    if df.empty:
        return
        
    open_mask = (df["status"] == "open") & (~df.get("exited", False))
    open_pos = df[open_mask]
    
    msg = f"🤖 <b>AUTO PAPER PORTFOLIO | {date}</b>\n"
    if open_pos.empty:
        msg += "<i>No hay posiciones abiertas.</i>"
    else:
        msg += f"📦 Posiciones activas: <b>{len(open_pos)}</b>\n\n"
        tickers = open_pos["ticker"].tolist()
        prices = fetch_prices(tickers)
        
        for _, row in open_pos.iterrows():
            t = row["ticker"]
            entry = row["entry_price"]
            last = prices.get(t, {}).get("last", entry)
            pnl_pct = (last / entry - 1) * 100
            pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
            
            msg += (
                f"• <b>{t}</b>: ${last:.2f} ({pnl_emoji} {pnl_pct:+.2f}%)\n"
                f"  Entry: ${entry:.2f} | SL: ${row['stop_price']:.2f}\n"
            )
            
    shared_telegram_send(msg)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--interval", type=int, default=1)
    parser.add_argument("--telegram", action="store_true", help="Enviar resumen de portafolio")
    args = parser.parse_args()

    date = args.date or today_ny()
    
    logger.info(f"--- LIVE AUTO-TRADER START ({date}) ---")
    if not pytz:
        logger.warning("pytz no instalado. Usando fecha local del sistema.")

    last_summary_time = 0
    summary_interval = 60 * 60 # 1 hora por defecto para el resumen

    while True:
        try:
            # 1. Flujo Automático
            auto_approve_signals(date)
            manage_ledger("AUTO", date)
            
            # 2. Gestión del Flujo Manual (Demo Telegram)
            manage_ledger("DEMO", date)
            
            # 3. Resumen Periódico
            if args.telegram and (time.time() - last_summary_time > summary_interval):
                send_portfolio_summary(date)
                last_summary_time = time.time()
            
        except Exception as e:
            logger.error(f"Loop error: {e}")

        if not args.monitor:
            break
            
        time.sleep(args.interval * 60)

if __name__ == "__main__":
    main()
