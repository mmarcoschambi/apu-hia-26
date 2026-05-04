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
    
    # 2. Intentar cargar auditoria real (rejection_audit.csv)
    audit_file = SIGNALS_DIR / date_str / "rejection_audit.csv"
    signal_file = SIGNALS_DIR / date_str / "combined.csv"
    
    if audit_file.exists():
        logger.info(f"Usando auditoría real desde {audit_file.name}")
        df_rej = pd.read_csv(audit_file)
        # Filtrar solo rechazos por sector_etf
        df_sector_rej = df_rej[df_rej["reject_reason"].str.contains("sector_etf", na=False)]
        
        # Cargar señales exitosas para el total
        df_passed = pd.read_csv(signal_file) if signal_file.exists() else pd.DataFrame()
        
        total_candidates = len(df_passed) + len(df_sector_rej)
        blocked = len(df_sector_rej)
        pct = (blocked / total_candidates * 100) if total_candidates > 0 else 0
        
        print("\n" + "="*60)
        print(f"AUDITORIA SECTORIAL REAL - {date_str}")
        print("="*60)
        print(f"Config: use_sector_etf_filter={enabled} | threshold={threshold}")
        print(f"Total Candidatos Post-Screener: {total_candidates}")
        print(f"Bloqueados por Sector ETF:      {blocked} ({pct:.1f}%)")
        print("-" * 60)
        if blocked > 0:
            print("TICKERS BLOQUEADOS REALMENTE:")
            # Mostrar ticker y la razon específica (que contiene la dist)
            print(df_sector_rej[["ticker", "mode", "reject_reason"]].to_string(index=False))
        else:
            print("Ningún ticker bloqueado realmente por el filtro sectorial.")
        print("="*60 + "\n")
        return

    # 3. Fallback: Auditoria Teórica (REEVALUACIÓN)
    logger.warning("No se encontró rejection_audit.csv. Realizando auditoría teórica sobre supervivientes...")
    if not signal_file.exists():
        logger.error(f"No se encontró archivo de señales para {date_str}")
        return

    df_signals = pd.read_csv(signal_file)
    if df_signals.empty:
        logger.info("No hay señales para auditar.")
        return

    # Fetch ETF data (mismo código que antes...)
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
            if len(series) >= sma_period:
                sma = series.rolling(sma_period).mean().iloc[-1]
                current = series.iloc[-1]
                dist = (current / sma) - 1
                etf_metrics[etf] = {"dist": dist}

    audit_rows = []
    for _, row in df_signals.iterrows():
        ticker = row["ticker"]
        etf = SECTOR_MAP.get(ticker)
        m = etf_metrics.get(etf)
        if m:
            passed = m["dist"] > threshold
            audit_rows.append({"ticker": ticker, "sector_etf": etf, "dist": m["dist"], "passed": passed})

    df_audit = pd.DataFrame(audit_rows)
    blocked = len(df_audit[~df_audit["passed"]])
    print(f"Bloqueados (teórico sobre supervivientes): {blocked}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    run_audit(args.date)
