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

    # 2. Pre-fetch ETF and Theme data si los filtros están activos
    etf_dists = {}
    theme_metrics_map = {}
    
    use_theme_filter = t2_master.get("use_theme_group_filter", False)

    if use_sector_filter or use_theme_filter:
        import yfinance as yf
        from src.data.theme_taxonomy import THEME_MAP, get_themes
        
        logger.info("Fetching Market Data for Filters (Sector + Theme)...")
        etf_start = (today - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # Recolectar todos los tickers necesarios
        tickers_to_fetch = set(SECTOR_ETFS)
        if use_theme_filter:
            for t in THEME_MAP:
                tickers_to_fetch.add(t)
        
        try:
            market_data = yf.download(list(tickers_to_fetch), start=etf_start, end=date_str, progress=False)["Close"]
            if isinstance(market_data, pd.Series):
                # Caso un solo ticker
                ticker = list(tickers_to_fetch)[0]
                market_data = market_data.to_frame()
                market_data.columns = [ticker]
            elif isinstance(market_data.columns, pd.MultiIndex):
                market_data.columns = market_data.columns.get_level_values(0)
            
            market_data = market_data.ffill()
            
            # 2a. Calcular ETF Dists
            sma_period = t2_master.get("sector_etf_sma_period", 20)
            for etf in SECTOR_ETFS:
                if etf in market_data.columns:
                    series = market_data[etf]
                    if len(series) >= sma_period:
                        sma = series.rolling(sma_period).mean().iloc[-1]
                        current = series.iloc[-1]
                        etf_dists[etf] = (current / sma) - 1
            
            # 2b. Calcular Theme Metrics
            if use_theme_filter:
                theme_to_tickers = {}
                for t, themes in THEME_MAP.items():
                    for theme in themes:
                        theme_to_tickers.setdefault(theme, []).append(t)
                
                theme_indices = {}
                for theme, members in theme_to_tickers.items():
                    avail = [m for m in members if m in market_data.columns]
                    if len(avail) < 2: continue
                    
                    # Equal-weighted: average of returns
                    m_rets = market_data[avail].pct_change()
                    # Min 5 members or all if < 5 total
                    min_m = min(5, len(avail))
                    valid = market_data[avail].notna().sum(axis=1) >= min_m
                    
                    t_rets = m_rets.mean(axis=1)
                    t_rets[~valid] = np.nan
                    t_idx = (1 + t_rets.fillna(0)).cumprod()
                    t_idx[t_rets.isna()] = np.nan
                    theme_indices[theme] = t_idx
                
                df_themes = pd.DataFrame(theme_indices)
                theme_sma20 = df_themes.rolling(20).mean()
                
                # Theme Metrics for each ticker
                for ticker in THEME_MAP:
                    ticker_themes = get_themes(ticker)
                    etf_sym = SECTOR_MAP.get(ticker)
                    
                    best_theme = None
                    best_theme_vs_sector = -999
                    
                    metrics_found = False
                    
                    for theme in ticker_themes:
                        if theme not in df_themes.columns: continue
                        
                        try:
                            t_price = df_themes[theme].iloc[-1]
                            t_sma = theme_sma20[theme].iloc[-1]
                            if pd.isna(t_price) or pd.isna(t_sma): continue
                            
                            t_dist = (t_price / t_sma) - 1
                            t_ret_20d = df_themes[theme].pct_change(20).iloc[-1]
                            
                            vs_sector = 0.0
                            if etf_sym and etf_sym in market_data.columns:
                                etf_ret_20d = market_data[etf_sym].pct_change(20).iloc[-1]
                                vs_sector = t_ret_20d - etf_ret_20d
                            
                            if vs_sector > best_theme_vs_sector:
                                best_theme_vs_sector = vs_sector
                                best_theme = theme
                                
                            theme_metrics_map[ticker] = {
                                "theme_dist": t_dist,
                                "theme_vs_sector": vs_sector,
                                "theme_rank_pct": 0.0 # simplified rank for live
                            }
                            metrics_found = True
                        except:
                            continue
            
            logger.info(f"  ETF Dists: {len(etf_dists)} | Theme Metrics: {len(theme_metrics_map)} calculated.")
        except Exception as e:
            logger.error(f"Error fetching market data: {e}. Filters might fail.")

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
            
            # Obtener metrics temáticas
            t_m = theme_metrics_map.get(ticker, {})
            t_dist = t_m.get("theme_dist")
            t_vs_sec = t_m.get("theme_vs_sector")
            t_rank = t_m.get("theme_rank_pct")

            # Evaluar ambos modos
            da = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_a,
                mode="A",
                scan_date=date_str,
                sector_etf_dist=dist,
                theme_dist=t_dist,
                theme_vs_sector=t_vs_sec,
                theme_rank_pct=t_rank
            )
            da_no_sector = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_a_no_sector,
                mode="A",
                scan_date=date_str,
                sector_etf_dist=dist,
                theme_dist=t_dist,
                theme_vs_sector=t_vs_sec,
                theme_rank_pct=t_rank
            )
            db = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_b,
                mode="B",
                scan_date=date_str,
                sector_etf_dist=dist,
                theme_dist=t_dist,
                theme_vs_sector=t_vs_sec,
                theme_rank_pct=t_rank
            )
            db_no_sector = evaluate_ticker(
                ticker=ticker,
                df=df,
                spy_df=spy_df,
                combo_cfg=cfg_b_no_sector,
                mode="B",
                scan_date=date_str,
                sector_etf_dist=dist,
                theme_dist=t_dist,
                theme_vs_sector=t_vs_sec,
                theme_rank_pct=t_rank
            )

            # Auditoria contrafactual: mismo ticker/mode con filtro ON vs OFF.
            for with_theme, without_theme in [(da, da_no_sector), (db, db_no_sector)]:
                blocked_by_theme = (
                    without_theme.passed
                    and not with_theme.passed
                    and "theme_group" in with_theme.reject_reason
                )
                blocked_by_sector = (
                    without_theme.passed
                    and not with_theme.passed
                    and "sector_etf" in with_theme.reject_reason
                )
                rejection_audit.append({
                    "ticker": ticker,
                    "mode": with_theme.mode,
                    "sector_etf": etf_symbol,
                    "best_theme": t_m.get("best_theme"),
                    "theme_vs_sector": t_vs_sec,
                    "passed_with_filter": with_theme.passed,
                    "reject_reason": with_theme.reject_reason,
                    "passed_without_filter": without_theme.passed,
                    "blocked_by_theme": blocked_by_theme,
                    "blocked_by_sector": blocked_by_sector,
                    "target_hold_days": with_theme.target_hold_days
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
        df_audit = pd.DataFrame(rejection_audit)
        df_audit.to_csv(out_dir / "rejection_audit.csv", index=False)
        logger.info(f"Saved {len(rejection_audit)} rejection records to {out_dir / 'rejection_audit.csv'}")
        
        # Summary for Thematic Divergence (Fase 2.3)
        theme_blocked = df_audit["blocked_by_theme"].sum()
        theme_passed = (df_audit["passed_with_filter"] & df_audit["best_theme"].notna()).sum()
        logger.info("=" * 40)
        logger.info("THEMATIC FILTER SUMMARY (Divergence Mode)")
        logger.info(f"  Allowed: {theme_passed} | Blocked: {theme_blocked}")
        logger.info("=" * 40)
        
        # Weekly floor alert (Fase 2.3)
        floor = t2_master.get("theme_monthly_signal_floor", 15) / 4.0
        eligible_signals = (df_audit["passed_without_filter"] & (df_audit["target_hold_days"] >= 10)).sum()
        if eligible_signals < floor:
            logger.warning(f"ALERT: Weekly signal floor risk! Eligible signals today: {eligible_signals} (Floor target: {floor:.1f})")

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
