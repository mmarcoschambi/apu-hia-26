#!/usr/bin/env python3
"""
finviz_live_promoter.py - Monitor de mercado live para universo Finviz con RVOL dinámico.
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv()

from src.utils.telegram_client import telegram_send as shared_telegram_send
from src.utils.data_quality import calculate_data_quality, is_monitor_eligible

OUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
FINVIZ_DIR = PROJECT_ROOT / "outputs" / "paper_finviz"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_session_fraction() -> float:
    """Calcula la fracción transcurrida de la sesión NYSE (9:30 - 16:00 EST)."""
    try:
        import pytz
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz)
    except ImportError:
        now = datetime.now()
    
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if now < start:
        return 0.01
    if now > end:
        return 1.0
        
    elapsed = (now - start).total_seconds()
    total = (end - start).total_seconds()
    return min(max(elapsed / total, 0.01), 1.0)


def fetch_live_data(tickers: list[str]) -> pd.DataFrame:
    """Obtiene precio actual y volumen acumulado usando yfinance."""
    if not tickers:
        return pd.DataFrame()
    
    import requests
    session = requests.Session()
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False, group_by="ticker", session=session)
        results = []
        for ticker in tickers:
            try:
                df = data if len(tickers) == 1 else data[ticker]
                if df.empty:
                    results.append({"ticker": ticker, "live_price": None, "live_vol": None})
                    continue
                
                last_row = df.iloc[-1]
                results.append({
                    "ticker": ticker,
                    "live_price": float(last_row["Close"]),
                    "live_vol": float(df["Volume"].sum())
                })
            except Exception:
                results.append({"ticker": ticker, "live_price": None, "live_vol": None})
        return pd.DataFrame(results)
    except Exception as e:
        logger.error(f"Error fetching live data: {e}")
        return pd.DataFrame()
    finally:
        session.close()


from src.utils.sector_rotation import get_ticker_sector_mapping

def promote_candidates(
    date: str, 
    min_rvol: float = 1.5, 
    send_telegram: bool = False
):
    snapshot_path = FINVIZ_DIR / date / "snapshot.json"
    if not snapshot_path.exists():
        logger.warning(f"Snapshot no encontrado: {snapshot_path}")
        return

    with open(snapshot_path, "r") as f:
        snapshot = json.load(f)

    watchlist = snapshot.get("watchlist_detail", {})
    if not watchlist:
        return

    # Resolve sectors for all tickers in watchlist
    sector_map = get_ticker_sector_mapping(list(watchlist.keys()))

    # 1. Filtrar candidatos elegibles para monitoreo (OK + WARN)
    candidates = []
    stats = {"ok": 0, "warn": 0, "bad": 0, "skipped_baseline": 0, "promoted": 0, "already_sent": 0}
    
    for ticker, detail in watchlist.items():
        status, reasons = calculate_data_quality(detail)
        detail["data_quality_status"] = status
        detail["data_quality_reasons"] = reasons
        
        if is_monitor_eligible(detail):
            candidates.append(ticker)
            stats[status] += 1
        else:
            stats["bad"] += 1

    if not candidates:
        logger.info(f"Ciclo completo: ok={stats['ok']} warn={stats['warn']} bad={stats['bad']} -> Nada que monitorear.")
        return

    # 2. Obtener data live
    logger.info(f"Monitorizando {len(candidates)} tickers (ok={stats['ok']}, warn={stats['warn']})...")
    live_df = fetch_live_data(candidates)
    if live_df.empty:
        return

    session_fraction = get_session_fraction()
    
    # 3. Cargar existentes para evitar duplicados
    combined_dir = OUT_DIR / date
    combined_dir.mkdir(parents=True, exist_ok=True)
    combined_path = combined_dir / "combined.csv"
    existing_tickers = set()
    if combined_path.exists():
        try:
            df_existing = pd.read_csv(combined_path)
            existing_tickers = set(df_existing["ticker"].tolist())
        except: pass

    new_signals = []
    for _, row in live_df.iterrows():
        ticker = row["ticker"]
        if ticker in existing_tickers:
            stats["already_sent"] += 1
            continue
            
        price = row["live_price"]
        vol = row["live_vol"]
        if price is None or vol is None:
            continue
            
        detail = watchlist[ticker]
        breakout_lvl = detail.get("breakout_level", 999999)
        avg_vol_20d = detail.get("avg_volume_20d")
        status = detail.get("data_quality_status", "ok")

        # 4. Cálculo de RVOL Live
        live_rvol = 0
        if avg_vol_20d and avg_vol_20d > 0:
            expected_vol = avg_vol_20d * session_fraction
            live_rvol = vol / expected_vol if expected_vol > 0 else 0
        else:
            # Si no hay baseline, solo permitimos si el status era OK
            if status == "ok":
                live_rvol = detail.get("rvol", 0)
            else:
                stats["skipped_baseline"] += 1
                continue

        # 5. Validación final de promoción
        if price >= breakout_lvl and live_rvol >= min_rvol:
            logger.info(f"🚀 PROMOVIENDO {ticker}: Price={price:.2f} (Break={breakout_lvl}), RVOL={live_rvol:.1f} [{status}]")
            stats["promoted"] += 1
            
            # Metadata extra para el reporte enriquecido
            sec = sector_map.get(ticker, "OTHER")
            dv = (price * (avg_vol_20d or 0)) / 1e6
            dist_sma20 = detail.get("dist_sma20_pct", 0)
            waiting = detail.get("waiting_for", "OK")
            blocker = detail.get("primary_reason", "")
            if not blocker and waiting != "OK":
                blocker = waiting
            
            # Alerta de precio sospechoso
            snapshot_price = detail.get("price", 0)
            price_flag = ""
            if snapshot_price > 0:
                diff = abs(price - snapshot_price) / snapshot_price
                if diff > 0.15: # > 15% diff
                    price_flag = " ⚠️"

            signal = {
                "ticker": ticker,
                "agent_name": detail.get("combo", "finviz_live"),
                "entry_score": detail.get("score", 0.5),
                "entry_price": price,
                "breakout_level": breakout_lvl,
                "rvol": round(live_rvol, 2),
                "live_volume": int(vol),
                "signal_date": date,
                "source_universe": "finviz",
                "decision_source": "finviz_live_promoter",
                "data_quality_status": status,
                "sector_etf": sec,
                "dollar_vol_M": dv,
                "dist_sma20": dist_sma20,
                "waiting_for": waiting,
                "primary_reason": blocker
            }
            new_signals.append(signal)
            
            if send_telegram:
                msg = (
                    f"🧭 <b>MANUAL REVIEW: {ticker}</b> ({sec})\n"
                    f"<i>(NO AUTO ENTRY - Validate Radar first)</i>\n\n"
                    f"Price: <b>${price:.2f}</b>{price_flag} (Break: ${breakout_lvl:.2f})\n"
                    f"Live RVOL: <b>{live_rvol:.1f}x</b> | Dist20: {dist_sma20:.1f}%\n"
                    f"DV: {dv:.0f}M | Quality: {status.upper()}\n"
                    f"Status: <b>{waiting}</b> | Blocker: <i>{blocker}</i>"
                )
                shared_telegram_send(msg)

    # Resumen Operativo
    logger.info(
        f"RESUMEN CICLO: ok={stats['ok']} warn={stats['warn']} | "
        f"promoted={stats['promoted']} skipped_no_baseline={stats['skipped_baseline']} "
        f"already_active={stats['already_sent']}"
    )

    if new_signals:
        df_new = pd.DataFrame(new_signals)
        if combined_path.exists():
            df_existing = pd.read_csv(combined_path)
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = df_new
        df_final.to_csv(combined_path, index=False)
        logger.info(f"Guardadas {len(new_signals)} nuevas señales en {combined_path}")


def main():
    parser = argparse.ArgumentParser(description="Finviz Live Promoter")
    parser.add_argument("--date", type=str, default=None, help="Fecha YYYY-MM-DD")
    parser.add_argument("--monitor", action="store_true", help="Loop continuo")
    parser.add_argument("--interval", type=int, default=1, help="Minutos entre chequeos")
    parser.add_argument("--rvol", type=float, default=1.5, help="Umbral RVOL")
    parser.add_argument("--telegram", action="store_true", help="Enviar alertas")
    args = parser.parse_args()

    while True:
        try:
            current_date = args.date or datetime.now().strftime("%Y-%m-%d")
            promote_candidates(current_date, min_rvol=args.rvol, send_telegram=args.telegram)
        except Exception as e:
            logger.error(f"Error: {e}")
        if not args.monitor:
            break
        time.sleep(args.interval * 60)

if __name__ == "__main__":
    main()
