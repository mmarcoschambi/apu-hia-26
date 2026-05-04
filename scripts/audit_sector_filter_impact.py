import json
import logging
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.dynamic_config import load_production_config
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SIGNALS_DIR = PROJECT_ROOT / "outputs" / "live_signals"

def run_audit(date_str):
    logger.info(f"Auditando impacto del Sector ETF Filter para la fecha: {date_str}")
    
    # 1. Cargar Config
    cfg = load_production_config()
    t2 = cfg.get("tier2_filters", {})
    enabled = t2.get("use_sector_etf_filter", False)
    threshold = float(t2.get("sector_etf_dist_threshold", 0.0))
    
    if not enabled:
        logger.warning("El filtro sectorial está DESACTIVADO en config. Auditando impacto teórico.")
    
    # 2. Cargar Señales (Combined)
    signal_path = SIGNALS_DIR / date_str / "combined.csv"
    if not signal_path.exists():
        logger.error(f"No se encontró archivo de señales para {date_str} en {signal_path}")
        return

    df_signals = pd.read_csv(signal_path)
    if df_signals.empty:
        logger.info("No hay señales para auditar.")
        return

    # 3. Fetch ETF data
    logger.info("Descargando data de ETFs...")
    as_of = pd.Timestamp(date_str)
    start = (as_of - timedelta(days=60)).strftime("%Y-%m-%d")
    etf_data = yf.download(SECTOR_ETFS, start=start, end=date_str, progress=False)["Close"]
    if isinstance(etf_data.columns, pd.MultiIndex):
        etf_data.columns = etf_data.columns.get_level_values(0)
    
    sma_period = t2.get("sector_etf_sma_period", 20)
    etf_metrics = {}
    for etf in SECTOR_ETFS:
        if etf in etf_data.columns:
            series = etf_data[etf].ffill()
            sma = series.rolling(sma_period).mean().iloc[-1]
            current = series.iloc[-1]
            dist = (current / sma) - 1
            etf_metrics[etf] = {"price": current, "sma": sma, "dist": dist}

    # 4. Analizar impacto
    audit_rows = []
    for _, row in df_signals.iterrows():
        ticker = row["ticker"]
        etf = SECTOR_MAP.get(ticker)
        
        m = etf_metrics.get(etf)
        if not m:
            audit_rows.append({
                "ticker": ticker, "sector_etf": etf, "dist": None, 
                "passed": True, "reason": "no_etf_data"
            })
            continue
            
        passed = m["dist"] > threshold
        audit_rows.append({
            "ticker": ticker,
            "sector_etf": etf,
            "etf_price": round(m["price"], 2),
            "etf_sma20": round(m["sma"], 2),
            "dist": round(m["dist"], 4),
            "passed": passed,
            "reason": "" if passed else "sector_below_sma"
        })

    df_audit = pd.DataFrame(audit_rows)
    
    # 5. Reporte
    total = len(df_audit)
    blocked = len(df_audit[~df_audit["passed"]])
    
    print("\n" + "="*60)
    print(f"AUDITORIA SECTORIAL - {date_str}")
    print("="*60)
    print(f"Config: use_sector_etf_filter={enabled} | threshold={threshold}")
    print(f"Total Tickers Analizados: {total}")
    print(f"Bloqueados (teórico):     {blocked} ({blocked/total*100:.1f}%)")
    print("-" * 60)
    if blocked > 0:
        print("TICKERS BLOQUEADOS POR SECTOR:")
        print(df_audit[~df_audit["passed"]][["ticker", "sector_etf", "dist"]].to_string(index=False))
    else:
        print("Ningún ticker bloqueado por el filtro sectorial.")
    print("="*60 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_audit(args.date)
