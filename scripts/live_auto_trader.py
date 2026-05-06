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

def load_snapshot(date: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "outputs" / "paper_finviz" / date / "snapshot.json"
    if not path.exists():
        return pd.DataFrame()
    data = json.loads(path.read_text())
    return pd.DataFrame(data.get("signals", []))

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

def auto_approve_signals(date: str):
    """FLOW AUTO: Auto-aprueba señales si no existen en el ledger AUTO."""
    signals_df = load_snapshot(date)
    if signals_df.empty:
        return

    signals_df = signals_df.sort_values("position_size", ascending=False).drop_duplicates("ticker")
    
    path = AUTO_LEDGER_ROOT / date / "positions.csv"
    positions_df = load_csv(path)
    existing = set(positions_df["ticker"].tolist()) if not positions_df.empty else set()

    new_rows = []
    for _, row in signals_df.iterrows():
        ticker = row["ticker"]
        if ticker in existing:
            continue
            
        entry = float(row.get("entry_price", 0) or 0)
        size = float(row.get("position_size", 0) or 0)
        if entry <= 0 or size <= 0:
            continue
            
        new_rows.append({
            "position_id": f"pos_auto_{ticker}_{date}",
            "ticker": ticker,
            "status": "open",
            "entry_price": entry,
            "stop_price": float(row.get("stop_loss", row.get("stop_price", 0)) or 0),
            "tp1_price": float(row.get("tp1_price", 0) or 0),
            "tp2_price": float(row.get("tp2_price", 0) or 0),
            "qty": size,
            "qty_remaining": size,
            "tp1_hit": False,
            "tp2_hit": False,
            "realized_pnl": 0.0,
            "exited": False
        })
        log_action("AUTO", date, "ENTER", ticker, entry, "Auto-approve from snapshot")

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--interval", type=int, default=1)
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"--- LIVE AUTO-TRADER START ({date}) ---")

    while True:
        try:
            # 1. Flujo Automático
            auto_approve_signals(date)
            manage_ledger("AUTO", date)
            
            # 2. Gestión del Flujo Manual (Demo Telegram)
            manage_ledger("DEMO", date)
            
        except Exception as e:
            logger.error(f"Loop error: {e}")

        if not args.monitor:
            break
            
        time.sleep(args.interval * 60)

if __name__ == "__main__":
    main()
