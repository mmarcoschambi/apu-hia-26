#!/usr/bin/env python3
"""
finviz_live_promoter.py - Monitor de mercado live para universo Finviz con RVOL dinámico.
"""

import argparse
import html
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import suppress

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

        tz = pytz.timezone("US/Eastern")
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


def today_ny() -> str:
    """Return current date in New York timezone."""
    try:
        import pytz

        tz = pytz.timezone("America/New_York")
        return datetime.now(tz).strftime("%Y-%m-%d")
    except ImportError:
        return datetime.now().strftime("%Y-%m-%d")


def is_rth() -> bool:
    """Check if current time is within Regular Trading Hours (9:30 AM - 4:00 PM EST)."""
    try:
        import pytz
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
    except ImportError:
        now = datetime.now()
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return start <= now <= end


def fetch_live_data(tickers: list[str]) -> pd.DataFrame:
    """Obtiene precio actual y volumen acumulado usando yfinance con fallbacks robustos."""
    if not tickers:
        return pd.DataFrame()

    try:
        data = yf.download(
            tickers,
            period="1d",
            interval="1m",
            progress=False,
            group_by="ticker",
            threads=False,
            timeout=15,
        )
    except Exception as e:
        logger.warning(f"Batch download failed: {e}. Retrying tickers individually.")
        data = pd.DataFrame()

    results = []
    for ticker in tickers:
        try:
            df = pd.DataFrame()
            if not data.empty:
                df = data if len(tickers) == 1 else data.get(ticker, pd.DataFrame())

            # 1. Verificar si el batch download funcionó para este ticker
            has_valid_data = (
                not df.empty 
                and "Close" in df.columns 
                and not df["Close"].dropna().empty
            )

            # Fallback 1: Intento individual a 1m
            if not has_valid_data:
                logger.info(f"Retrying individual 1m download for {ticker}...")
                with suppress(Exception):
                    df = yf.download(ticker, period="1d", interval="1m", progress=False, timeout=10)
                has_valid_data = (
                    not df.empty 
                    and "Close" in df.columns 
                    and not df["Close"].dropna().empty
                )

            # Fallback 2: Intento individual diario (muy robusto frente a rate limits)
            if not has_valid_data:
                logger.info(f"Retrying individual daily download for {ticker}...")
                with suppress(Exception):
                    df = yf.download(ticker, period="1d", progress=False, timeout=10)
                has_valid_data = (
                    not df.empty 
                    and "Close" in df.columns 
                    and not df["Close"].dropna().empty
                )

            # Fallback 3: Ticker.history diario
            if not has_valid_data:
                logger.info(f"Retrying Ticker.history daily for {ticker}...")
                with suppress(Exception):
                    t_obj = yf.Ticker(ticker)
                    df = t_obj.history(period="1d")
                has_valid_data = (
                    not df.empty 
                    and "Close" in df.columns 
                    and not df["Close"].dropna().empty
                )

            if not has_valid_data:
                logger.error(f"Failed to fetch live data for {ticker} after all fallbacks.")
                results.append({"ticker": ticker, "live_price": None, "live_vol": None})
                continue

            df_clean = df.dropna(subset=["Close"])
            last_row = df_clean.iloc[-1]
            live_price = float(last_row["Close"])
            live_vol = float(df_clean["Volume"].sum()) if "Volume" in df_clean.columns else 0.0

            results.append(
                {
                    "ticker": ticker,
                    "live_price": live_price,
                    "live_vol": live_vol,
                }
            )
        except Exception as ex:
            logger.error(f"Unexpected error processing ticker {ticker}: {ex}")
            results.append({"ticker": ticker, "live_price": None, "live_vol": None})

    return pd.DataFrame(results)


from src.utils.sector_rotation import get_ticker_sector_mapping
import sqlite3
from src.config.dynamic_config import load_production_config
from src.integration.combo_loader import load_combo_merged
from src.signals.signal_engine import evaluate_ticker, Tier2Metrics, resolve_canonical_risk

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"


def load_historical_ohlcv(ticker: str, days: int = 150) -> pd.DataFrame:
    """Loads up to 'days' of daily bars for a ticker from SQLite database."""
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        logger.debug(f"Database not found or empty at {DB_PATH}")
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_cache
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
        """
        df = pd.read_sql(query, conn, params=(ticker, days))
        conn.close()
        if df.empty:
            return pd.DataFrame()
        df["date_parsed"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
        df = df.sort_values("date_parsed").drop_duplicates(subset=["date_parsed"], keep="last")
        df = df.rename(columns={"date_parsed": "date"}).set_index("date")
        df.columns = [c.lower() for c in df.columns]
        return df.astype(float)
    except Exception as e:
        logger.error(f"Error loading historical ohlcv for {ticker}: {e}")
        return pd.DataFrame()


def check_snapshot_gate_partial(detail: dict, config: dict) -> tuple[bool, str]:
    """Manually evaluates gate criteria against config parameters when DB is not available."""
    t2 = config.get("tier2_filters", {})
    
    # 1. RS Percentile
    if t2.get("use_rs_percentile", True):
        rs_val = detail.get("rs_pct")
        min_rs = t2.get("min_rs_percentile", 58.01)
        if rs_val is None:
            return False, "missing_rs_percentile"
        if rs_val < min_rs:
            return False, f"tier2_fail:rs_percentile:{rs_val:.2f}<{min_rs:.2f}"
            
    # 2. ADR
    min_adr = t2.get("min_adr", 1.8714)
    adr_val = detail.get("adr")
    if adr_val is None:
        return False, "missing_adr"
    if adr_val < min_adr:
        return False, f"tier2_fail:adr:{adr_val:.2f}<{min_adr:.2f}"
        
    # 3. Dollar Volume
    min_dv = t2.get("min_dollar_volume", 20000000)
    dv_val = detail.get("dollar_volume_m", 0) * 1e6
    if dv_val < min_dv:
        return False, f"tier2_fail:dollar_volume:{dv_val/1e6:.1f}M<{min_dv/1e6:.1f}M"
        
    # 4. Distance to SMA20
    t3 = config.get("tier3_fixed", config.get("tier3_risk", {}))
    use_dyn = t3.get("use_dynamic_extension_sizing", False)
    max_dist = 50.0 if use_dyn else t2.get("max_dist_sma20", 6.768)
    dist_val = detail.get("dist_sma20_pct")
    if dist_val is None:
        return False, "missing_dist_sma20"
    if dist_val > max_dist:
        return False, f"tier2_fail:dist_sma20:{dist_val:.2f}>{max_dist:.2f}"
        
    # 5. Sector ETF Filter
    if t2.get("use_sector_etf_filter", True):
        if not detail.get("sector_etf_ok", True):
            dist_pct = detail.get("sector_etf_dist_pct")
            dist_str = f" ({dist_pct:.2f}%)" if dist_pct is not None else ""
            return False, f"tier2_fail:sector_etf{dist_str}"
            
    return True, "passed"


def _load_watchlist_tickers(date: str) -> set[str]:
    """Carga los tickers candidatos oficiales (de la watchlist pre-market) del día."""
    watchlist_tickers = set()
    
    # 1. Cargar desde snapshot.json usando el filtro de candidato
    snapshot_path = FINVIZ_DIR / date / "snapshot.json"
    if snapshot_path.exists():
        try:
            with open(snapshot_path, "r") as f:
                snapshot = json.load(f)
            watchlist = snapshot.get("watchlist_detail", {})
            for ticker, detail in watchlist.items():
                proximity = float(detail.get("proximity_score", 0) or 0)
                reasons = detail.get("reasons", [])
                rs_pct = float(detail.get("rs_pct", 0) or 0)
                
                # Excluir errores de cálculo
                if any("No se pudo calcular" in r for r in reasons):
                    continue
                # Excluir tickers con demasiados blockers
                if len(reasons) >= 3:
                    continue
                # Criterios del candidato real
                if proximity >= 70:
                    watchlist_tickers.add(ticker.upper())
                elif rs_pct >= 90 and proximity >= 50:
                    watchlist_tickers.add(ticker.upper())
        except Exception as e:
            logger.warning(f"Error loading watchlist from snapshot: {e}")
            
    # 2. Cargar desde combined.csv al inicio del día (si existía, p.ej. de daily_scan en lab)
    combined_path = OUT_DIR / date / "combined.csv"
    if combined_path.exists():
        try:
            df = pd.read_csv(combined_path)
            if not df.empty and "ticker" in df.columns:
                for ticker in df["ticker"].tolist():
                    watchlist_tickers.add(str(ticker).upper())
        except Exception as e:
            logger.warning(f"Error loading watchlist from combined.csv: {e}")
            
    return watchlist_tickers


def promote_candidates(date: str, min_rvol: float = 1.5, send_telegram: bool = False):
    snapshot_path = FINVIZ_DIR / date / "snapshot.json"
    if not snapshot_path.exists():
        logger.warning(f"Snapshot no encontrado: {snapshot_path}")
        return

    logger.info(f"Promoter cycle start | date={date} | snapshot={snapshot_path}")
    with open(snapshot_path, "r") as f:
        snapshot = json.load(f)

    watchlist_tickers = _load_watchlist_tickers(date)

    watchlist = snapshot.get("watchlist_detail", {})
    if not watchlist:
        logger.info(f"Ciclo {date}: watchlist_detail vacío en {snapshot_path}")
        return

    # Resolve sectors for all tickers in watchlist
    sector_map = get_ticker_sector_mapping(list(watchlist.keys()))

    # Load production config and define active combos/modes
    prod_config = load_production_config(PROJECT_ROOT / "config" / "production_config.json")
    ACTIVE_COMBOS = [
        ("combo_pure_momentum", "A"),
        ("combo_stage2_breakout", "B"),
    ]

    # 1. Filtrar candidatos elegibles para monitoreo (OK + WARN)
    candidates = []
    stats = {"ok": 0, "warn": 0, "bad": 0, "skipped_baseline": 0, "promoted": 0, "already_sent": 0}
    audit_rows = []

    for ticker, detail in watchlist.items():
        status, reasons = calculate_data_quality(detail)
        detail["data_quality_status"] = status
        detail["data_quality_reasons"] = reasons

        if is_monitor_eligible(detail):
            candidates.append(ticker)
            stats[status] += 1
            audit_rows.append(
                {
                    "ticker": ticker,
                    "status": status,
                    "eligible": True,
                    "reason": "; ".join(reasons) if reasons else "eligible",
                }
            )
        else:
            stats["bad"] += 1
            audit_rows.append(
                {
                    "ticker": ticker,
                    "status": status,
                    "eligible": False,
                    "reason": "; ".join(reasons) if reasons else "not_monitor_eligible",
                }
            )

    if not candidates:
        logger.info(
            f"Ciclo completo {date}: ok={stats['ok']} warn={stats['warn']} bad={stats['bad']} -> Nada que monitorear."
        )
        audit_dir = OUT_DIR / date
        audit_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(audit_rows).to_csv(audit_dir / "rejection_audit.csv", index=False)
        return

    # 2. Obtener data live (including SPY in a single batch request)
    logger.info(
        f"Monitorizando {len(candidates)} tickers (ok={stats['ok']}, warn={stats['warn']}) + SPY..."
    )
    download_tickers = list(set(candidates + ["SPY"]))
    live_df = fetch_live_data(download_tickers)
    if live_df.empty:
        logger.warning(f"Ciclo {date}: live_df vacío al consultar {len(download_tickers)} tickers.")
        return

    # Extract SPY live data
    spy_row = live_df[live_df["ticker"] == "SPY"]
    if not spy_row.empty:
        spy_price = spy_row.iloc[0]["live_price"]
        spy_vol = spy_row.iloc[0]["live_vol"]
    else:
        spy_price, spy_vol = None, None

    session_fraction = get_session_fraction()

    # 3. Cargar existentes para evitar duplicados
    combined_dir = OUT_DIR / date
    combined_dir.mkdir(parents=True, exist_ok=True)
    combined_path = combined_dir / "combined.csv"
    existing_signals = set()
    if combined_path.exists():
        try:
            df_existing = pd.read_csv(combined_path)
            if not df_existing.empty and "ticker" in df_existing.columns and "agent_name" in df_existing.columns:
                for _, r in df_existing.iterrows():
                    existing_signals.add((str(r["ticker"]).upper(), str(r["agent_name"])))
        except Exception as e:
            logger.warning(f"No se pudo leer combined.csv existente {combined_path}: {e}")

    new_signals = []
    for _, row in live_df.iterrows():
        ticker = row["ticker"]
        # Skip SPY from being evaluated as a candidate
        if ticker == "SPY":
            continue

        price = row["live_price"]
        vol = row["live_vol"]
        if price is None or vol is None:
            audit_rows.append(
                {
                    "ticker": ticker,
                    "status": "live_missing",
                    "eligible": False,
                    "reason": "missing_price_or_volume",
                }
            )
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
                audit_rows.append(
                    {
                        "ticker": ticker,
                        "status": status,
                        "eligible": False,
                        "reason": "missing_avg_volume_20d",
                    }
                )
                continue

        # 5. Validación final de promoción
        if price >= breakout_lvl and live_rvol >= min_rvol:
            logger.info(
                f"🚀 PROMOVIENDO TRIGGER {ticker}: Price={price:.2f} (Break={breakout_lvl}), RVOL={live_rvol:.1f} [{status}]"
            )

            # Metadata extra
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
                if diff > 0.15:  # > 15% diff
                    price_flag = " ⚠️"

            # Precalculated metrics for gating
            rs_pct = detail.get("rs_pct", detail.get("score"))
            sector_etf_dist = detail.get("sector_etf_dist_pct")
            if sector_etf_dist is not None:
                sector_etf_dist = sector_etf_dist / 100.0

            premarket_combos = detail.get("combos", [])
            combos_to_eval = []
            for combo_name, mode in ACTIVE_COMBOS:
                lbl = "Qulla" if combo_name == "combo_pure_momentum" else "Minervini"
                if not premarket_combos or lbl in premarket_combos:
                    combos_to_eval.append((combo_name, mode))
            if not combos_to_eval:
                combos_to_eval = ACTIVE_COMBOS

            for combo_name, mode in combos_to_eval:
                if (ticker.upper(), combo_name) in existing_signals:
                    stats["already_sent"] += 1
                    audit_rows.append(
                        {
                            "ticker": ticker,
                            "status": "existing",
                            "eligible": False,
                            "reason": f"already_sent:{combo_name}",
                        }
                    )
                    continue

                passed_eval = False
                reject_reason = ""
                risk_info = {}
                decision = None
                
                # Dual-Gate Evaluation
                entry_gate_status = "UNKNOWN"
                entry_gate_reason = "not_evaluated"
                entry_gate_source = "none"
                
                gate_rs_percentile = rs_pct
                gate_adr_pct = detail.get("adr")
                gate_dollar_vol_M = detail.get("dollar_volume_m")
                gate_dist_sma20 = detail.get("dist_sma20_pct")
                gate_sector_etf_dist = detail.get("sector_etf_dist_pct")

                if DB_PATH.exists():
                    # Laboratory Environment: Run canonical evaluate_ticker
                    hist_df = load_historical_ohlcv(ticker, days=150)
                    spy_hist_df = load_historical_ohlcv("SPY", days=150)
                    today_dt = pd.to_datetime(date).normalize()

                    # Hydrate latest row with live intraday data
                    if not hist_df.empty:
                        if today_dt in hist_df.index:
                            hist_df.loc[today_dt, "close"] = price
                            hist_df.loc[today_dt, "high"] = max(hist_df.loc[today_dt, "high"], price)
                            hist_df.loc[today_dt, "low"] = min(hist_df.loc[today_dt, "low"], price)
                            hist_df.loc[today_dt, "volume"] = vol
                        else:
                            new_row = pd.DataFrame(
                                {"open": price, "high": price, "low": price, "close": price, "volume": vol},
                                index=[today_dt]
                            )
                            hist_df = pd.concat([hist_df, new_row])

                    if not spy_hist_df.empty and spy_price is not None:
                        if today_dt in spy_hist_df.index:
                            spy_hist_df.loc[today_dt, "close"] = spy_price
                            spy_hist_df.loc[today_dt, "high"] = max(spy_hist_df.loc[today_dt, "high"], spy_price)
                            spy_hist_df.loc[today_dt, "low"] = min(spy_hist_df.loc[today_dt, "low"], spy_price)
                            spy_hist_df.loc[today_dt, "volume"] = spy_vol or 0.0
                        else:
                            new_row = pd.DataFrame(
                                {"open": spy_price, "high": spy_price, "low": spy_price, "close": spy_price, "volume": spy_vol or 0.0},
                                index=[today_dt]
                            )
                            spy_hist_df = pd.concat([spy_hist_df, new_row])

                    if len(hist_df) >= 65:
                        try:
                            # Load combo_cfg
                            combo_cfg, _ = load_combo_merged(combo_name)
                            if "tier1_strategy" not in combo_cfg:
                                combo_cfg["tier1_strategy"] = {}
                            if "tier2_filters" not in combo_cfg:
                                combo_cfg["tier2_filters"] = {}
                            
                            # Merge with production overrides
                            combo_cfg["tier1_strategy"].update(prod_config.get("tier1_strategy", {}))
                            
                            if combo_name == "combo_pure_momentum":
                                prod_t2 = prod_config.get("tier2_filters", {}).copy()
                                if not combo_cfg["tier2_filters"].get("use_rs_percentile", False):
                                    prod_t2["use_rs_percentile"] = False
                                combo_cfg["tier2_filters"].update(prod_t2)
                            
                            if combo_name == "combo_stage2_breakout":
                                if "tier3_fixed" not in combo_cfg:
                                    combo_cfg["tier3_fixed"] = {}
                                combo_cfg["tier3_fixed"].update(prod_config.get("tier3_fixed", {}))
                            
                            decision = evaluate_ticker(
                                ticker=ticker,
                                df=hist_df,
                                spy_df=spy_hist_df,
                                combo_cfg=combo_cfg,
                                mode=mode,
                                rs_percentile=rs_pct,
                                scan_date=date,
                                sector_etf_dist=sector_etf_dist
                            )
                            passed_eval = decision.passed
                            reject_reason = decision.reject_reason if not passed_eval else "passed"
                            if passed_eval:
                                risk_info = {
                                    "stop_price": decision.stop_price,
                                    "tp1_price": decision.tp1_price,
                                    "tp2_price": decision.tp2_price,
                                    "shares": decision.shares,
                                    "risk_budget_usd": decision.risk_budget_usd,
                                    "sizing_factor": decision.sizing_factor,
                                    "sizing_reason": decision.sizing_reason,
                                }
                        except Exception as e:
                            logger.error(f"Error calling canonical evaluate_ticker for {ticker} with {combo_name}: {e}")
                            passed_eval = False
                            reject_reason = f"error:{e}"
                        
                        entry_gate_status = "PASS" if passed_eval else "BLOCKED"
                        entry_gate_reason = reject_reason
                        entry_gate_source = f"canonical_signal_engine:{combo_name}"

                        if decision:
                            if decision.tier2_metrics and decision.tier2_metrics.adr_pct > 0:
                                gate_rs_percentile = decision.tier2_metrics.rs_percentile
                                gate_adr_pct = decision.tier2_metrics.adr_pct
                                gate_dollar_vol_M = decision.tier2_metrics.dollar_vol_M
                                gate_dist_sma20 = decision.tier2_metrics.dist_sma20
                                gate_sector_etf_dist = (
                                    decision.tier2_metrics.sector_etf_dist * 100.0 
                                    if decision.tier2_metrics.sector_etf_dist is not None else None
                                )
                    else:
                        entry_gate_status = "UNKNOWN"
                        entry_gate_reason = "insufficient_historical_bars"
                else:
                    # VPS fallback: evaluar combos filtrados por premarket_combos con sus configs nativas
                    try:
                        combo_cfg_vps, _ = load_combo_merged(combo_name)
                        if combo_name == "combo_pure_momentum":
                            combo_cfg_vps["tier2_filters"].update(prod_config.get("tier2_filters", {}))
                        if combo_name == "combo_stage2_breakout":
                            if "tier3_fixed" not in combo_cfg_vps:
                                combo_cfg_vps["tier3_fixed"] = {}
                            combo_cfg_vps["tier3_fixed"].update(prod_config.get("tier3_fixed", {}))
                            
                        passed_eval, reject_reason = check_snapshot_gate_partial(detail, combo_cfg_vps)
                        if passed_eval:
                            metrics_vps = Tier2Metrics(
                                rvol=live_rvol,
                                adr_pct=detail.get("adr", 0.0),
                                atr=detail.get("atr", 0.0),
                                dist_sma20=detail.get("dist_sma20_pct", 0.0),
                                dollar_vol_M=detail.get("dollar_volume_m", 0.0),
                                rs_percentile=rs_pct,
                                sector_etf_dist=sector_etf_dist
                            )
                            t1_cfg = combo_cfg_vps.get("tier1_strategy", {})
                            risk_res = resolve_canonical_risk(
                                entry_price=price,
                                metrics=metrics_vps,
                                combo_cfg=combo_cfg_vps,
                                risk_dollars=float(t1_cfg.get("risk_dollars", 2878.0)),
                            )
                            risk_info = {
                                "stop_price": risk_res["stop_price"],
                                "tp1_price": risk_res["tp1_price"],
                                "tp2_price": risk_res["tp2_price"],
                                "shares": risk_res["shares"],
                                "risk_budget_usd": risk_res["risk_budget_usd"],
                                "sizing_factor": risk_res["sizing_factor"],
                                "sizing_reason": risk_res["sizing_reason"],
                            }
                    except Exception as e:
                        logger.error(f"Error calculating risk for {ticker} (VPS fallback) with {combo_name}: {e}")
                        passed_eval = False
                        reject_reason = f"risk_calc_error:{e}"
                    
                    entry_gate_status = "PASS" if passed_eval else "BLOCKED"
                    entry_gate_reason = reject_reason
                    entry_gate_source = f"snapshot_partial:{combo_name}"
                    
                    gate_rs_percentile = rs_pct
                    gate_adr_pct = detail.get("adr")
                    gate_dollar_vol_M = detail.get("dollar_volume_m")
                    gate_dist_sma20 = detail.get("dist_sma20_pct")
                    gate_sector_etf_dist = detail.get("sector_etf_dist_pct")

                if passed_eval:
                    stats["promoted"] += 1
                    signal = {
                        "ticker": ticker,
                        "agent_name": combo_name,
                        "entry_score": detail.get("score", 0.5),
                        "proximity_score": detail.get("proximity_score", 0.0),
                        "entry_price": price,
                        "breakout_level": breakout_lvl,
                        "rvol": round(live_rvol, 2),
                        "live_volume": int(vol),
                        "signal_date": date,
                        "source_universe": "finviz",
                        "decision_source": f"finviz_live_promoter:{combo_name}",
                        "data_quality_status": status,
                        "sector_etf": sec,
                        "dollar_vol_M": dv,
                        "dist_sma20": dist_sma20,
                        "waiting_for": waiting,
                        "primary_reason": blocker,
                        
                        # Risk parameters
                        "stop_price": risk_info.get("stop_price"),
                        "tp1_price": risk_info.get("tp1_price"),
                        "tp2_price": risk_info.get("tp2_price"),
                        "shares": risk_info.get("shares"),
                        "risk_budget_usd": risk_info.get("risk_budget_usd"),
                        "sizing_factor": risk_info.get("sizing_factor"),
                        "sizing_reason": risk_info.get("sizing_reason"),
                        
                        # Telegram fields
                        "live_trigger_status": "PASS",
                        "entry_gate_status": entry_gate_status,
                        "entry_gate_reason": entry_gate_reason,
                        "entry_gate_source": entry_gate_source,
                        "gate_rs_percentile": gate_rs_percentile,
                        "gate_adr_pct": gate_adr_pct,
                        "gate_dollar_vol_M": gate_dollar_vol_M,
                        "gate_dist_sma20": gate_dist_sma20,
                        "gate_sector_etf_dist": gate_sector_etf_dist,
                    }
                    new_signals.append(signal)
                    
                    audit_rows.append(
                        {
                            "ticker": ticker,
                            "status": status,
                            "eligible": True,
                            "reason": f"promoted:{combo_name} price>={breakout_lvl:.4f} rvol>={min_rvol:.2f}",
                            "price": price,
                            "breakout_level": breakout_lvl,
                            "live_rvol": round(live_rvol, 2),
                            "entry_gate_status": entry_gate_status,
                            "entry_gate_reason": entry_gate_reason,
                        }
                    )

                    if send_telegram:
                        safe_ticker = html.escape(str(ticker), quote=False)
                        safe_sector = html.escape(str(sec), quote=False)
                        
                        in_watchlist = ticker.upper() in watchlist_tickers
                        watchlist_badge = "📋 <b>EN WATCHLIST</b>" if in_watchlist else "🆕 <b>NUEVO TICKER</b>"

                        # Determine icon and instruction for gate status
                        if entry_gate_status == "PASS":
                            gate_icon = "🟢"
                            action_text = "🟢 Trigger validado. Elegible para entrada swing manual."
                        elif entry_gate_status == "BLOCKED":
                            gate_icon = "🔴"
                            blockers = []
                            reason_lower = entry_gate_reason.lower()
                            if "adr" in reason_lower:
                                blockers.append("ADR bajo")
                            if "dist_sma20" in reason_lower or "dist_sma" in reason_lower:
                                blockers.append("Extendido de SMA20")
                            if "rs_percentile" in reason_lower or "rs_pct" in reason_lower:
                                blockers.append("RS bajo")
                            if "dollar_volume" in reason_lower or "dollar_vol" in reason_lower:
                                blockers.append("DVol bajo")
                            if "sector_etf" in reason_lower:
                                blockers.append("Sector ETF bajista")
                            
                            if blockers:
                                action_text = f"🔴 Evitar entrada: bloqueado por {', '.join(blockers)}."
                            else:
                                action_text = "🔴 Evitar entrada: no cumple criterios de validación cascada."
                        else:
                            gate_icon = "🟡"
                            action_text = "🟡 Requiere verificación manual de filtros."
                        
                        rs_str = f"{gate_rs_percentile:.1f}%" if gate_rs_percentile is not None else "N/A"
                        adr_str = f"{gate_adr_pct:.2f}%" if gate_adr_pct is not None else "N/A"
                        dv_str = f"${gate_dollar_vol_M:.1f}M" if gate_dollar_vol_M is not None else "N/A"
                        dist20_str = f"{gate_dist_sma20:.2f}%" if gate_dist_sma20 is not None else "N/A"
                        sec_dist_str = f"{gate_sector_etf_dist:.2f}%" if gate_sector_etf_dist is not None else "N/A"
                        
                        if sec == "XLK":
                            header_title = f"⚡ <b>[SHADOW: XLK-Only] {safe_ticker}</b>"
                        elif sec == "XLC":
                            header_title = f"👁️ <b>[OBSERVATION: XLC] {safe_ticker}</b>"
                        else:
                            header_title = f"🧭 <b>LIVE SIGNAL: {safe_ticker}</b> ({safe_sector})"
                        
                        prefix = "<b>[SISTEMA A]</b> " if combo_name == "combo_pure_momentum" else "<b>[SISTEMA B]</b> "
                        header_title = prefix + header_title
                        
                        msg = (
                            f"{header_title}\n"
                            f"{watchlist_badge}\n\n"
                            f"⚡ <b>TRIGGER DETAILS:</b>\n"
                            f"• Live Trigger: <b>PASS</b>\n"
                            f"• Price: <b>${price:.2f}</b>{price_flag} (Break: ${breakout_lvl:.2f})\n"
                            f"• Live RVOL: <b>{live_rvol:.2f}x</b>\n\n"
                            f"{gate_icon} <b>ENTRY GATE STATUS: {entry_gate_status}</b>\n"
                            f"• Gate Reason: <code>{html.escape(entry_gate_reason, quote=False)}</code>\n"
                            f"• Source: <i>{entry_gate_source}</i>\n\n"
                            f"📊 <b>GATE METRICS:</b>\n"
                            f"• RS Percentile: <b>{rs_str}</b>\n"
                            f"• ADR %: <b>{adr_str}</b>\n"
                            f"• Dollar Volume: <b>{dv_str}</b>\n"
                            f"• Dist SMA20: <b>{dist20_str}</b>\n"
                            f"• Sector ETF Dist: <b>{sec_dist_str}</b>\n\n"
                            f"📈 <a href=\"https://www.tradingview.com/symbols/{safe_ticker}/\">Ver en TradingView</a>\n\n"
                            f"📢 <b>ACTION:</b>\n"
                            f"<b>{action_text}</b>"
                        )
                        
                        # Si está definido el canal live unificado, enviamos allí.
                        # De lo contrario, se envía al canal específico de cada sistema.
                        chat_id_to_send = os.getenv("TELEGRAM_CHAT_ID_LIVE")
                        if not chat_id_to_send:
                            chat_id_to_send = os.getenv("TELEGRAM_CHAT_ID_SYSTEM_B") if combo_name == "combo_stage2_breakout" else None
                        if not chat_id_to_send:
                            chat_id_to_send = os.getenv("TELEGRAM_CHAT_ID")
                            
                        shared_telegram_send(msg, chat_id=chat_id_to_send)
                else:
                    audit_rows.append(
                        {
                            "ticker": ticker,
                            "status": status,
                            "eligible": False,
                            "reason": f"rejected:{combo_name} {entry_gate_reason}",
                            "price": price,
                            "breakout_level": breakout_lvl,
                            "live_rvol": round(live_rvol, 2),
                            "entry_gate_status": entry_gate_status,
                            "entry_gate_reason": entry_gate_reason,
                        }
                    )
        else:
            reason = []
            if price < breakout_lvl:
                reason.append(f"price<{breakout_lvl:.4f}")
            if live_rvol < min_rvol:
                reason.append(f"rvol<{min_rvol:.2f}")
            audit_rows.append(
                {
                    "ticker": ticker,
                    "status": status,
                    "eligible": False,
                    "reason": "; ".join(reason) if reason else "not_promoted",
                    "price": price,
                    "breakout_level": breakout_lvl,
                    "live_rvol": round(live_rvol, 2),
                }
            )

    # Resumen Operativo
    logger.info(
        f"RESUMEN CICLO {date}: ok={stats['ok']} warn={stats['warn']} bad={stats['bad']} | "
        f"promoted={stats['promoted']} skipped_no_baseline={stats['skipped_baseline']} "
        f"already_active={stats['already_sent']}"
    )

    audit_dir = OUT_DIR / date
    audit_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(audit_rows).to_csv(audit_dir / "rejection_audit.csv", index=False)

    if new_signals:
        df_new = pd.DataFrame(new_signals)
        if combined_path.exists():
            df_existing = pd.read_csv(combined_path)
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            df_final = df_new
        df_final.to_csv(combined_path, index=False)
        logger.info(f"Guardadas {len(new_signals)} nuevas señales en {combined_path}")
    else:
        logger.info(f"Ciclo {date}: no hubo nuevas señales para persistir.")


def main():
    parser = argparse.ArgumentParser(description="Finviz Live Promoter")
    parser.add_argument("--date", type=str, default=None, help="Fecha YYYY-MM-DD")
    parser.add_argument("--monitor", action="store_true", help="Loop continuo")
    parser.add_argument("--interval", type=int, default=1, help="Minutos entre chequeos")
    parser.add_argument("--rvol", type=float, default=1.5, help="Umbral RVOL")
    parser.add_argument("--telegram", action="store_true", help="Enviar alertas")
    args = parser.parse_args()

    last_date = None
    while True:
        try:
            current_date = args.date or today_ny()
            
            # Guardia de horario US Regular Trading Hours (RTH: 9:30 AM - 4:00 PM EST)
            if args.monitor and not is_rth():
                logger.info("Outside US Regular Trading Hours (RTH). Sleeping 60s...")
                time.sleep(60)
                continue
            if args.monitor and last_date and current_date != last_date and args.date is None:
                logger.info(
                    f"Date rollover detected ({last_date} -> {current_date}). Exiting for clean restart."
                )
                return
            promote_candidates(current_date, min_rvol=args.rvol, send_telegram=args.telegram)
            last_date = current_date
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            with suppress(Exception):
                import gc

                gc.collect()
        if not args.monitor:
            break
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
