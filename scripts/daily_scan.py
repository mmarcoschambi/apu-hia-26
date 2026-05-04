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
import copy
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
from src.config.dynamic_config import load_production_config
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

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
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)


def run_daily_scan(date_str: str, max_tickers: int = 200):
    logger.info("=" * 60)
    logger.info(f"DAILY SCAN PRO - {date_str}")
    logger.info("=" * 60)

    today = pd.Timestamp(date_str)

    # 1. Cargar Master Config (production_config.json)
    try:
        master_cfg = load_production_config()
        t2_master = master_cfg.get("tier2_filters", {})
        use_sector_filter = t2_master.get("use_sector_etf_filter", False)
        logger.info(f"Master Config loaded. Sector Filter: {'ENABLED' if use_sector_filter else 'DISABLED'}")
    except Exception as e:
        logger.warning(f"Failed to load master config: {e}. Sector filter will be disabled.")
        t2_master = {}
        use_sector_filter = False

    # 2. Pre-fetch ETF data si el filtro está activo
    etf_dists = {}
    if use_sector_filter:
        import yfinance as yf
        logger.info("Fetching Sector ETF data for filter...")
        etf_start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
        try:
            etf_data = yf.download(SECTOR_ETFS, start=etf_start, end=date_str, progress=False)["Close"]
            if isinstance(etf_data.columns, pd.MultiIndex):
                etf_data.columns = etf_data.columns.get_level_values(0)
            
            sma_period = t2_master.get("sector_etf_sma_period", 20)
            for etf in SECTOR_ETFS:
                if etf in etf_data.columns:
                    series = etf_data[etf].ffill()
                    if len(series) >= sma_period:
                        sma = series.rolling(sma_period).mean().iloc[-1]
                        current = series.iloc[-1]
                        etf_dists[etf] = (current / sma) - 1
            logger.info(f"  ETF Dists calculated for {len(etf_dists)} sectors.")
        except Exception as e:
            logger.error(f"Error fetching ETF data: {e}. Filter might fail for some tickers.")

    # 3. Construir universo idéntico al WF
    logger.info(f"Building universe (limit={max_tickers})...")
    universe_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    snap = build_universe_for_fold(
        DB_PATH, date_str, universe_start, max_tickers=max_tickers
    )
    tickers = snap.tickers
    logger.info(f"Universe: {len(tickers)} tickers selected.")

    # 4. Cargar SPY para régimen de mercado (SMA200 real)
    logger.info("Checking Market Regime (SMA200)...")
    spy_start = (today - timedelta(days=400)).strftime("%Y-%m-%d")
    spy_df = load_ohlcv("SPY", spy_start, date_str)

    # 5. Cargar configuraciones de combos
    logger.info("Loading combo configurations...")
    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")

    # Aplicar Overrides: Master Config gana, luego VALIDATED_OVERRIDES como fallback/legacy
    VALIDATED_OVERRIDES = {
        "min_rs_percentile": 75,
        "min_trend_intensity": 104,
        "require_ma_stack": True,
        "min_adr_pct": 1.2,
        "require_spy_above_sma200": True,
    }

    # Combinar t2_master con VALIDATED_OVERRIDES
    final_t2 = {**VALIDATED_OVERRIDES, **t2_master}

    # En cfg_a y cfg_b, inyectar en tier2_filters y screener.params
    for k, v in final_t2.items():
        cfg_a.setdefault("tier2_filters", {})[k] = v
        cfg_b.setdefault("tier2_filters", {})[k] = v

        cfg_a.setdefault("screener", {}).setdefault("params", {})[k] = v
        cfg_b.setdefault("screener", {}).setdefault("params", {})[k] = v

        if k in ["min_adr_pct"]:
            cfg_a.setdefault("screener", {})[k] = v
            cfg_b.setdefault("screener", {})[k] = v

    # Configs contrafactuales para medir impacto marginal del filtro sectorial.
    cfg_a_no_sector = copy.deepcopy(cfg_a)
    cfg_b_no_sector = copy.deepcopy(cfg_b)
    cfg_a_no_sector.setdefault("tier2_filters", {})["use_sector_etf_filter"] = False
    cfg_b_no_sector.setdefault("tier2_filters", {})["use_sector_etf_filter"] = False

    # 6. Scan
    all_signals = []
    rejection_audit = []
    logger.info(f"Scanning {len(tickers)} tickers with A+B modes...")

    for ticker in tickers:
        df = pd.DataFrame()
        try:
            # Lookback de seguridad para medias móviles
            df_start = (today - timedelta(days=300)).strftime("%Y-%m-%d")
            df = load_ohlcv(ticker, df_start, date_str)

            if df.empty or len(df) < 65:
                continue

            # Obtener dist del ETF para este ticker
            etf_symbol = SECTOR_MAP.get(ticker)
            dist = etf_dists.get(etf_symbol) if etf_symbol else None

            # Evaluar ambos modos
            da = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_a,
                mode="A",
                scan_date=date_str,
                sector_etf_dist=dist
            )
            da_no_sector = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_a_no_sector,
                mode="A",
                scan_date=date_str,
                sector_etf_dist=dist
            )
            db = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_b,
                mode="B",
                scan_date=date_str,
                sector_etf_dist=dist
            )
            db_no_sector = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_b_no_sector,
                mode="B",
                scan_date=date_str,
                sector_etf_dist=dist
            )

            # Auditoria contrafactual: mismo ticker/mode con filtro ON vs OFF.
            for with_sector, without_sector in [(da, da_no_sector), (db, db_no_sector)]:
                blocked_by_sector = (
                    without_sector.passed
                    and not with_sector.passed
                    and "sector_etf" in with_sector.reject_reason
                )
                rejection_audit.append({
                    "ticker": ticker,
                    "mode": with_sector.mode,
                    "sector_etf": etf_symbol,
                    "sector_etf_dist": dist,
                    "passed_with_sector": with_sector.passed,
                    "reject_reason_with_sector": with_sector.reject_reason,
                    "passed_without_sector": without_sector.passed,
                    "reject_reason_without_sector": without_sector.reject_reason,
                    "blocked_by_sector": blocked_by_sector,
                })

            # Mergear señales
            merged = merge_ab_signals(
                [da] if da.passed else [], [db] if db.passed else []
            )
            for sig in merged:
                s_dict = sig.to_dict()
                s_dict["signal_date"] = date_str
                s_dict["agent_name"] = "A_BOTH"
                s_dict["combo_name"] = "A_BOTH_PRO"
                s_dict["entry_price"] = sig.tier2_metrics.close

                # Inyectar métricas de ejecución al primer nivel (ya resueltas por el engine canónico)
                # Esto incluye ATR-based stops si el combo lo pide.
                s_dict["stop_price"] = sig.stop_price
                s_dict["shares"] = sig.shares
                s_dict["risk_budget_usd"] = sig.risk_budget_usd
                s_dict["risk_per_share"] = sig.risk_per_share
                s_dict["tp1_price"] = sig.tp1_price
                s_dict["tp2_price"] = sig.tp2_price
                s_dict["tp1_pct"] = sig.tp1_pct
                s_dict["tp2_pct"] = sig.tp2_pct
                s_dict["runner_pct"] = sig.runner_pct
                
                # Mantener compatibilidad retroactiva si alguien lee tier1_metrics
                if "tier1_metrics" not in s_dict:
                    s_dict["tier1_metrics"] = {}
                s_dict["tier1_metrics"].update({
                    "stop_price": sig.stop_price,
                    "shares": sig.shares,
                    "risk_budget_usd": sig.risk_budget_usd,
                    "risk_per_share": sig.risk_per_share,
                    "tp1_price": sig.tp1_price,
                    "tp2_price": sig.tp2_price,
                    "tp1_pct": sig.tp1_pct,
                    "tp2_pct": sig.tp2_pct,
                    "runner_pct": sig.runner_pct
                })

                s_dict["rvol"] = round(sig.tier2_metrics.rvol, 2)
                s_dict["adr_pct"] = round(sig.tier2_metrics.adr_pct, 2)
                s_dict["dist_sma20"] = round(sig.tier2_metrics.dist_sma20, 2)
                s_dict["consol_days"] = sig.tier2_metrics.consol_days
                s_dict["volume"] = int(sig.tier2_metrics.volume)
                s_dict["dollar_vol_M"] = round(sig.tier2_metrics.dollar_vol_M, 1)
                s_dict["rs_ret"] = (
                    round(sig.tier2_metrics.rs_ret, 4)
                    if sig.tier2_metrics.rs_ret is not None
                    else None
                )
                s_dict["rs_percentile"] = (
                    round(sig.tier2_metrics.rs_percentile, 1)
                    if sig.tier2_metrics.rs_percentile is not None
                    else None
                )
                s_dict["close"] = round(sig.tier2_metrics.close, 4)
                s_dict["spy_above_sma50"] = sig.tier2_metrics.spy_above_sma50
                s_dict["spy_above_sma200"] = sig.tier2_metrics.spy_above_sma200

                all_signals.append(s_dict)
                logger.info(
                    f"  ★ SIGNAL: {ticker:6s} | Mode: {sig.mode:6s} | Score: {sig.entry_score:.3f}"
                )

        except Exception as e:
            logger.error(f"Error scanning {ticker}: {e}")

    # 5. Persistir resultados
    out_dir = OUTPUT_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    if rejection_audit:
        pd.DataFrame(rejection_audit).to_csv(out_dir / "rejection_audit.csv", index=False)
        logger.info(f"Saved {len(rejection_audit)} rejection records to {out_dir / 'rejection_audit.csv'}")

    df_results = pd.DataFrame(all_signals)
    if not df_results.empty:
        df_results.to_csv(out_dir / "combined.csv", index=False)
        logger.info(f"\nSaved {len(all_signals)} signals to {out_dir / 'combined.csv'}")
    else:
        logger.warning("\nNo signals found today.")

    return all_signals


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        help="Scan date (YYYY-MM-DD)",
        default=datetime.now().strftime("%Y-%m-%d"),
    )
    parser.add_argument("--max-tickers", type=int, default=200)
    args = parser.parse_args()

    run_daily_scan(args.date, args.max_tickers)
