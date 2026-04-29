#!/usr/bin/env python3
"""
scripts/daily_scan.py
Scanner diario PRO usando el motor validado del Walk-Forward.

- Universo idéntico al backtest (Top 200 ADV).
- Motor de señal canónico (signal_engine.py).
- Régimen de mercado SMA200 (lookback 400d).
- Soporta múltiples agentes (A + B).
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.signals.signal_engine import evaluate_ticker, merge_ab_signals
from src.integration.combo_loader import load_combo_merged
from src.integration.universe_builder import build_universe_for_fold

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"


def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
        (ticker, start, end),
    ).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)


def run_daily_scan(date_str: str, max_tickers: int = 200):
    logger.info("=" * 60)
    logger.info(f"DAILY SCAN PRO - {date_str}")
    logger.info("=" * 60)

    today = pd.Timestamp(date_str)
    
    # 1. Construir universo idéntico al WF
    logger.info(f"Building universe (limit={max_tickers})...")
    universe_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    snap = build_universe_for_fold(DB_PATH, date_str, universe_start, max_tickers=max_tickers)
    tickers = snap.tickers
    logger.info(f"Universe: {len(tickers)} tickers selected.")

    # 2. Cargar SPY para régimen de mercado (SMA200 real)
    logger.info("Checking Market Regime (SMA200)...")
    spy_start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
    spy_df = load_ohlcv("SPY", spy_start, date_str)
    
    # 3. Cargar configuraciones de combos
    logger.info("Loading combo configurations...")
    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")

    # Después de cargar los combos, aplicar overrides validados:
    VALIDATED_OVERRIDES = {
        "min_rs_percentile": 75,
        "min_trend_intensity": 104,
        "require_ma_stack": True,
        "min_adr_pct": 1.2,
        "require_spy_above_sma200": True,
    }
    
    # En cfg_a y cfg_b, inyectar en tier2_filters y screener.params
    for k, v in VALIDATED_OVERRIDES.items():
        cfg_a.setdefault("tier2_filters", {})[k] = v
        cfg_b.setdefault("tier2_filters", {})[k] = v
        
        cfg_a.setdefault("screener", {}).setdefault("params", {})[k] = v
        cfg_b.setdefault("screener", {}).setdefault("params", {})[k] = v
        
        if k in ["min_adr_pct"]:
            cfg_a.setdefault("screener", {})[k] = v
            cfg_b.setdefault("screener", {})[k] = v

    # 4. Scan
    all_signals = []
    logger.info(f"Scanning {len(tickers)} tickers with A+B modes...")
    
    for ticker in tickers:
        df = pd.DataFrame()
        try:
            # Lookback de seguridad para medias móviles
            df_start = (today - timedelta(days=300)).strftime("%Y-%m-%d")
            df = load_ohlcv(ticker, df_start, date_str)
            
            if df.empty or len(df) < 65:
                continue

            # Evaluar ambos modos
            da = evaluate_ticker(ticker=ticker, df=df, spy_df=spy_df, combo_cfg=cfg_a, mode="A", scan_date=date_str)
            db = evaluate_ticker(ticker=ticker, df=df, spy_df=spy_df, combo_cfg=cfg_b, mode="B", scan_date=date_str)
            
            # Mergear señales
            merged = merge_ab_signals([da] if da.passed else [], [db] if db.passed else [])
            for sig in merged:
                # Calcular Stop Loss y Position Size basados en el capital de papel
                entry_price = float(df.iloc[-1]["close"])
                
                # Regla de Stop base (8% por defecto)
                stop_pct = 0.08 
                stop_price = entry_price * (1 - stop_pct)
                
                # Sizing basado en riesgo de $1000 por trade
                risk_dollars = 1000.0
                shares = risk_dollars / max((entry_price - stop_price), 0.01)

                s_dict = sig.to_dict()
                s_dict["signal_date"] = date_str
                s_dict["agent_name"] = "A_BOTH"
                s_dict["combo_name"] = "A_BOTH_PRO"
                s_dict["entry_price"] = entry_price
                
                # Inyectar métricas de ejecución falsificando tier1_metrics
                if "tier1_metrics" not in s_dict:
                    s_dict["tier1_metrics"] = {}
                s_dict["tier1_metrics"]["stop_price"] = stop_price
                s_dict["tier1_metrics"]["shares"] = int(shares)
                
                all_signals.append(s_dict)
                logger.info(f"  ★ SIGNAL: {ticker:6s} | Mode: {sig.mode:6s} | Score: {sig.entry_score:.3f}")
        
        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")

    # 5. Persistir resultados
    out_dir = OUTPUT_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    
    df_results = pd.DataFrame(all_signals)
    if not df_results.empty:
        df_results.to_csv(out_dir / "combined.csv", index=False)
        logger.info(f"\nSaved {len(all_signals)} signals to {out_dir / 'combined.csv'}")
    else:
        logger.warning("\nNo signals found today.")

    return all_signals


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Scan date (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--max-tickers", type=int, default=200)
    args = parser.parse_args()
    
    run_daily_scan(args.date, args.max_tickers)
