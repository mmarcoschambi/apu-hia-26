#!/usr/bin/env python3
"""
PAPER TRADING DAILY RUNBOOK — CHECKLIST OPERATIVO
================================================
Workflow diario para ejecución de paper trading:
- Pre-market (AM): Health checks + signal generation + charts
- Intraday: Monitoring + execution (simulated)
- End-of-day (PM): Reconciliation + KPIs + alerts

Usage:
    python3 scripts/paper_trading_runbook.py --phase pre           # Morning + signals
    python3 scripts/paper_trading_runbook.py --phase pre --charts  # Morning + generate charts
    python3 scripts/paper_trading_runbook.py --phase intra         # Intraday
    python3 scripts/paper_trading_runbook.py --phase eod           # End of day
    python3 scripts/paper_trading_runbook.py --phase all           # Full day (default)
    python3 scripts/paper_trading_runbook.py --phase eod --select AAPL,NVDA  # Track selected
"""

import argparse
import json
import logging
import sys
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.data.finviz_universe_provider import fetch_finviz_universe
from src.paper.universe_snapshot_service import save_universe_snapshot
from src.paper.universe_drift_audit import run_drift_audit, save_drift_audit
from src.utils.market_context_live import (
    get_market_context_live,
    apply_regime_override,
    _to_bool,
)
from src.analytics.paper_analytics_engine import compute_daily_analytics
from src.analytics.simulation_pack import run_simulation_pack
from src.paper.analytics_io import build_analytics_inputs, save_daily_analytics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            f"logs/paper_trading_{datetime.now().strftime('%Y%m%d')}.log"
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

PAPER_CONFIG = ROOT / "config" / "paper_portfolio_config.json"
OUTPUTS_DIR = ROOT / "outputs" / "paper_trading"
CHARTS_DIR = OUTPUTS_DIR / "charts"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = ROOT / "data" / "ticker_cache.db"
COMBOS_DIR = ROOT / "config" / "combos"

UNIVERSE_SIZE = 200
LOOKBACK_DAYS = 130
MIN_HISTORY = 65


def load_paper_config():
    if PAPER_CONFIG.exists():
        return json.load(open(PAPER_CONFIG))
    logger.warning(f"Paper config not found: {PAPER_CONFIG}, using defaults")
    return {
        "portfolio": {
            "strategies": [
                {"combo": "combo_pure_momentum", "allocation_pct": 100},
            ],
            "shadow": [
                {"combo": "combo_pullback_entry"},
                {"combo": "combo_aggressive_momentum"},
                {"combo": "combo_stage2_breakout"},
            ],
        }
    }


def load_combo_config(combo_name: str) -> dict:
    """Load combo configuration."""
    path = COMBOS_DIR / f"{combo_name}.json"
    if path.exists():
        return json.load(open(path))
    return {}


def get_universe_from_db(start_date: str, end_date: str, limit: int = UNIVERSE_SIZE):
    """Load top tickers by liquidity from DB."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        df = pd.read_sql_query(
            """
            SELECT ticker, COUNT(*) as cnt
            FROM ohlcv_cache
            WHERE date >= ? AND date <= ?
            GROUP BY ticker
            ORDER BY cnt DESC
            LIMIT ?
        """,
            conn,
            params=(start_date, end_date, limit),
        )
        conn.close()
        if not df.empty:
            return df["ticker"].tolist()
    except Exception as e:
        logger.error(f"Error loading universe: {e}")
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM", "V", "UNH"]


def load_ohlcv(ticker: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    """Load OHLCV data for ticker from DB."""
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
    except Exception:
        return pd.DataFrame()
    return df.set_index("date").astype(float)


def log_combo_validation_status(combo_name: str):
    """Loguea estado de validación del combo (approved, production_passed, rejection_reasons)."""
    cfg_path = ROOT / "outputs" / "best_combos_run" / f"{combo_name}_config.json"
    if not cfg_path.exists():
        logger.warning(f"      ⚠️ {combo_name}: validation snapshot missing")
        return

    data = json.load(open(cfg_path))
    val = data.get("validation", {})
    approved = bool(val.get("approved", False))
    prod_passed = _to_bool(val.get("production_passed", False))
    reasons = val.get("rejection_reasons", [])

    logger.info(
        f"      {combo_name}: approved={approved} production_passed={prod_passed} rejection_reasons={len(reasons)}"
    )
    for r in reasons[:3]:
        logger.info(f"        - {r}")


def scan_combo_signals(combo_name: str, universe: list) -> list:
    """
    Scan universe for combo signals using production logic.
    Replicates the signal generation from daily_signal_scanner.py
    """
    combo = load_combo_config(combo_name)
    if not combo:
        return []

    screener_name = combo.get("screener", {}).get("name", "")
    signal_type = combo.get("pattern", {}).get("signal_type", "breakout")
    tier2 = combo.get("tier2_filters", {})

    logger.info(
        f"  Scanning {combo_name}: screener={screener_name}, signal={signal_type}"
    )

    config_path = ROOT / "config" / "production_config.json"
    if config_path.exists():
        prod_cfg = json.load(open(config_path))
    else:
        prod_cfg = {}

    T1 = prod_cfg.get("tier1_strategy", {})
    T2 = prod_cfg.get("tier2_filters", {})
    MR = prod_cfg.get("market_regime", {})

    MIN_RVOL = tier2.get("min_rvol", T2.get("min_rvol", 0.7))
    MIN_ADR = tier2.get("min_adr", T2.get("min_adr", 1.5))
    MAX_DIST_SMA20 = tier2.get("max_dist_sma20", T2.get("max_dist_sma20", 12.0))
    MIN_CONSOL = tier2.get(
        "min_consolidation_days", T2.get("min_consolidation_days", 3)
    )
    MIN_DV = tier2.get("min_dollar_volume", T2.get("min_dollar_volume", 10_000_000))
    MIN_VOL = tier2.get("min_volume", T2.get("min_volume", 100_000))
    MIN_RS = T2.get("min_rs_percentile", 70.0)
    RS_LB = T2.get("rs_lookback_days", 60)
    MAX_VIX = MR.get("max_vix", 35.0)
    REQ_SPY = MR.get("require_spy_above_sma50", True)

    logger.info(
        f"    Filters: RVOL>={MIN_RVOL}, ADR>={MIN_ADR}, Dist<={MAX_DIST_SMA20}, DV>={MIN_DV / 1e6:.0f}M"
    )

    all_closes = {}
    for ticker in universe:
        df = load_ohlcv(ticker)
        if len(df) >= MIN_HISTORY:
            all_closes[ticker] = df["close"].pct_change(RS_LB, fill_method=None)
    rs_df = pd.DataFrame(all_closes)

    signals = []
    for ticker in universe:
        df = load_ohlcv(ticker)
        if df.empty or len(df) < MIN_HISTORY:
            continue

        try:
            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]

            sma20 = close.rolling(20).mean()
            sma50 = close.rolling(50).mean()
            avg_vol_20 = volume.rolling(20).mean().replace(0, np.nan)
            rvol = volume / avg_vol_20

            daily_range = (high - low) / close * 100
            adr_val = float(daily_range.rolling(20).mean().iloc[-1])

            dist_sma20 = (close - sma20) / sma20.replace(0, np.nan) * 100
            dollar_vol = float(close.iloc[-1] * avg_vol_20.iloc[-1])

            bb_std = close.rolling(20).std()
            inside_bb = (close >= sma20 - bb_std * 2) & (close <= sma20 + bb_std * 2)
            consol_days = int(inside_bb.rolling(20).sum().iloc[-1])

            last_close = float(close.iloc[-1])
            last_sma20 = float(sma20.iloc[-1]) if not np.isnan(sma20.iloc[-1]) else 0.0
            last_sma50 = float(sma50.iloc[-1]) if not np.isnan(sma50.iloc[-1]) else 0.0
            last_rvol = float(rvol.iloc[-1]) if not np.isnan(rvol.iloc[-1]) else 0.0
            last_dist = (
                float(dist_sma20.iloc[-1])
                if not np.isnan(dist_sma20.iloc[-1])
                else 999.0
            )

            if last_close <= last_sma20:
                continue

            if last_rvol < MIN_RVOL:
                continue
            if adr_val < MIN_ADR:
                continue
            if last_dist > MAX_DIST_SMA20:
                continue
            if dollar_vol < MIN_DV:
                continue
            if consol_days < MIN_CONSOL:
                continue
            if float(volume.iloc[-1]) < MIN_VOL:
                continue

            rs_pct = 50.0
            if not rs_df.empty and ticker in rs_df.columns:
                last_row = rs_df.iloc[-1].dropna()
                ticker_val = last_row.get(ticker, np.nan)
                if not np.isnan(ticker_val):
                    rs_pct = float((last_row < ticker_val).mean() * 100)

            if rs_pct < MIN_RS:
                continue

            rs_score = rs_pct / 100.0
            high_52w = float(high.rolling(min(252, len(high))).max().iloc[-1])
            prox_52w = last_close / high_52w if high_52w > 0 else 0.5
            entry_score = round(1.0 * rs_score + 0.0 * prox_52w, 3)

            stop_dist = last_close * T1.get("max_stop_pct", 0.08)
            stop_price = round(last_close - stop_dist, 4)
            tp1_price = round(last_close + stop_dist * T1.get("tp1_r", 1.75), 4)
            tp2_price = round(last_close + stop_dist * T1.get("tp2_r", 3.75), 4)

            signals.append(
                {
                    "ticker": ticker,
                    "combo": combo_name,
                    "signal_date": str(df.index[-1].date()),
                    "signal_price": round(last_close, 4),
                    "entry_score": entry_score,
                    "rs_percentile": round(rs_pct, 1),
                    "rvol": round(last_rvol, 2),
                    "adr_pct": round(adr_val, 2),
                    "dist_sma20": round(last_dist, 2),
                    "dollar_vol_M": round(dollar_vol / 1e6, 2),
                    "consol_days": consol_days,
                    "above_sma50": last_close > last_sma50,
                    "stop_price": stop_price,
                    "tp1": tp1_price,
                    "tp2": tp2_price,
                    "risk_$": T1.get("risk_dollars", 1000),
                    "screener": screener_name,
                    "signal_type": signal_type,
                }
            )
        except Exception as e:
            logger.debug(f"  Error scanning {ticker}: {e}")
            continue

    return signals


def generate_charts(signals: list, date_str: str):
    """Generate charts for top signals."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib not available - skipping charts")
        return

    top_signals = sorted(signals, key=lambda x: x["entry_score"], reverse=True)[:10]

    for sig in top_signals:
        ticker = sig["ticker"]
        combo = sig["combo"]

        chart_dir = CHARTS_DIR / date_str / combo
        chart_dir.mkdir(parents=True, exist_ok=True)

        df = load_ohlcv(ticker)
        if df.empty or len(df) < 50:
            continue

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

        ax1.plot(df.index, df["close"], linewidth=1.5, label="Close")
        ax1.plot(
            df.index,
            df["close"].rolling(20).mean(),
            linewidth=1,
            label="SMA20",
            alpha=0.7,
        )
        ax1.plot(
            df.index,
            df["close"].rolling(50).mean(),
            linewidth=1,
            label="SMA50",
            alpha=0.7,
        )

        if sig.get("stop_price"):
            ax1.axhline(
                y=sig["stop_price"],
                color="red",
                linestyle="--",
                alpha=0.5,
                label=f"Stop ${sig['stop_price']:.2f}",
            )
        if sig.get("tp1"):
            ax1.axhline(
                y=sig["tp1"],
                color="green",
                linestyle="--",
                alpha=0.5,
                label=f"TP1 ${sig['tp1']:.2f}",
            )

        ax1.set_title(
            f"{ticker} - {combo}\nScore: {sig['entry_score']:.3f}, RS: {sig['rs_percentile']:.1f}%, RVOL: {sig['rvol']:.2f}"
        )
        ax1.legend(loc="upper left", fontsize=8)
        ax1.grid(True, alpha=0.3)

        ax2.bar(df.index, df["volume"], alpha=0.5)
        ax2.set_ylabel("Volume")
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        output_path = chart_dir / f"{ticker}.png"
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close()

        logger.info(f"    📊 Chart: {output_path}")


def generate_watchlist_alerts(universe: list, today: str) -> list:
    """
    Escanea el universe y para cada ticker que NO pasó los filtros tier2,
    calcula la distancia porcentual a cada umbral que falta cruzar.

    Umbrales chequeados:
        - close > SMA20           (entry gate)
        - RVOL >= MIN_RVOL
        - ADR  >= MIN_ADR
        - Dist SMA20 <= MAX_DIST
        - DV   >= MIN_DV
        - RS   >= MIN_RS_PCT

    Exporta:
        outputs/paper_trading/watchlist_alerts_YYYYMMDD.csv

    Campos clave del CSV:
        ticker, close, gap_to_sma20_pct, rvol, gap_rvol,
        adr, gap_adr, dist_sma20, gap_dist, dv_M, gap_dv_M,
        rs_pct, gap_rs, blockers (lista de filtros fallidos),
        proximity_score (menor = más cerca de pasar todos los filtros)
    """
    import json, numpy as np, pandas as pd, sqlite3
    from pathlib import Path

    ROOT_A = Path(__file__).parent.parent
    DB_PATH_A = ROOT_A / "data" / "ticker_cache.db"
    prod_cfg = json.load(open(ROOT_A / "config" / "production_config.json"))

    T2_A = prod_cfg.get("tier2_filters", {})
    MIN_RVOL_A = T2_A.get("min_rvol", 0.7)
    MIN_ADR_A = T2_A.get("min_adr", 1.5)
    MAX_DIST_A = T2_A.get("max_dist_sma20", 12.0)
    MIN_DV_A = T2_A.get("min_dollar_volume", 10_000_000)
    MIN_VOL_A = T2_A.get("min_volume", 100_000)
    MIN_RS_A = T2_A.get("min_rs_percentile", 70.0)
    RS_LB_A = T2_A.get("rs_lookback_days", 60)
    LOOKBACK_A = 130
    MIN_HIST_A = 65

    conn = sqlite3.connect(str(DB_PATH_A))
    cutoff_a = (datetime.now() - timedelta(days=LOOKBACK_A)).strftime("%Y-%m-%d")

    # construir RS cross-sectional usando último retorno disponible por ticker
    rs_last_returns = {}
    for t in universe:
        rows = conn.execute(
            "SELECT date,close FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
            (t, cutoff_a),
        ).fetchall()
        if len(rows) >= MIN_HIST_A:
            s = pd.Series([r[1] for r in rows], dtype=float)
            rs_series = s.pct_change(RS_LB_A, fill_method=None).dropna()
            if not rs_series.empty:
                rs_last_returns[t] = float(rs_series.iloc[-1])

    rs_cross_values = pd.Series(rs_last_returns, dtype=float)

    alerts = []

    for ticker in universe:
        rows = conn.execute(
            "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
            "WHERE ticker=? AND date>=? ORDER BY date",
            (ticker, cutoff_a),
        ).fetchall()
        if len(rows) < MIN_HIST_A:
            continue

        try:
            df_a = pd.DataFrame(
                rows, columns=["date", "open", "high", "low", "close", "volume"]
            )
            df_a = df_a.set_index("date")
            c_a = df_a["close"].astype(float)
            h_a = df_a["high"].astype(float)
            l_a = df_a["low"].astype(float)
            v_a = df_a["volume"].astype(float)

            sma20_a = c_a.rolling(20).mean()
            avg_vol_a = v_a.rolling(20).mean().replace(0, np.nan)
            rvol_a = (
                float((v_a / avg_vol_a).iloc[-1])
                if not np.isnan((v_a / avg_vol_a).iloc[-1])
                else 0.0
            )
            adr_a = float(((h_a - l_a) / c_a * 100).rolling(20).mean().iloc[-1])
            dist_a = (
                float(((c_a - sma20_a) / sma20_a * 100).iloc[-1])
                if not np.isnan(((c_a - sma20_a) / sma20_a * 100).iloc[-1])
                else 999.0
            )
            dv_a = float(c_a.iloc[-1] * avg_vol_a.iloc[-1])
            last_a = float(c_a.iloc[-1])
            lsma20_a = (
                float(sma20_a.iloc[-1]) if not np.isnan(sma20_a.iloc[-1]) else 0.0
            )

            # RS percentil
            rs_pct_a = 50.0
            if not rs_cross_values.empty and ticker in rs_last_returns:
                tv = rs_last_returns[ticker]
                rs_pct_a = float((rs_cross_values < tv).mean() * 100)

            # distancias a umbral (% que falta para pasar; negativo = ya pasó)
            gap_sma20 = (
                ((lsma20_a - last_a) / lsma20_a * 100) if lsma20_a > 0 else 0.0
            )  # >0 = debajo de SMA20
            gap_rvol = max(0.0, MIN_RVOL_A - rvol_a)
            gap_adr = max(0.0, MIN_ADR_A - adr_a)
            gap_dist = max(0.0, dist_a - MAX_DIST_A)  # >0 = demasiado extendido
            gap_dv_M = max(0.0, (MIN_DV_A - dv_a) / 1e6)
            gap_rs = max(0.0, MIN_RS_A - rs_pct_a)

            blockers = []
            if last_a <= lsma20_a:
                blockers.append(f"below_SMA20({gap_sma20:.1f}%)")
            if rvol_a < MIN_RVOL_A:
                blockers.append(f"rvol({rvol_a:.2f}<{MIN_RVOL_A})")
            if adr_a < MIN_ADR_A:
                blockers.append(f"adr({adr_a:.2f}<{MIN_ADR_A})")
            if dist_a > MAX_DIST_A:
                blockers.append(f"dist({dist_a:.1f}>{MAX_DIST_A})")
            if dv_a < MIN_DV_A:
                blockers.append(f"dv({dv_a / 1e6:.0f}M<{MIN_DV_A / 1e6:.0f}M)")
            if rs_pct_a < MIN_RS_A:
                blockers.append(f"rs({rs_pct_a:.0f}%<{MIN_RS_A:.0f}%)")

            if not blockers:
                continue  # ya pasaría — está en signals, no en alerts

            # proximity_score: promedio normalizado de brechas (0 = a punto de pasar)
            # SMA20 gap lo ponderamos más porque es el gate principal
            prox = (
                abs(gap_sma20) * 2.0
                + gap_rvol * 10.0
                + gap_adr * 20.0
                + gap_dist * 1.0
                + gap_dv_M * 0.1
                + gap_rs * 0.5
            )

            alerts.append(
                {
                    "ticker": ticker,
                    "close": round(last_a, 2),
                    "sma20": round(lsma20_a, 2),
                    "gap_to_sma20_pct": round(gap_sma20, 2),
                    "rvol": round(rvol_a, 2),
                    "gap_rvol": round(gap_rvol, 2),
                    "adr": round(adr_a, 2),
                    "gap_adr": round(gap_adr, 2),
                    "dist_sma20": round(dist_a, 2),
                    "gap_dist": round(gap_dist, 2),
                    "dv_M": round(dv_a / 1e6, 1),
                    "gap_dv_M": round(gap_dv_M, 1),
                    "rs_pct": round(rs_pct_a, 1),
                    "gap_rs": round(gap_rs, 1),
                    "n_blockers": len(blockers),
                    "blockers": " | ".join(blockers),
                    "proximity_score": round(prox, 3),
                }
            )
        except Exception as e:
            logger.debug(f"  Alert scan error {ticker}: {e}")
            continue

    conn.close()

    alert_columns = [
        "ticker",
        "close",
        "sma20",
        "gap_to_sma20_pct",
        "rvol",
        "gap_rvol",
        "adr",
        "gap_adr",
        "dist_sma20",
        "gap_dist",
        "dv_M",
        "gap_dv_M",
        "rs_pct",
        "gap_rs",
        "n_blockers",
        "blockers",
        "proximity_score",
    ]

    if alerts:
        alerts.sort(key=lambda x: (x["n_blockers"], x["proximity_score"]))
        alerts_df = pd.DataFrame(alerts)
    else:
        alerts_df = pd.DataFrame(columns=alert_columns)

    alerts_path = OUTPUTS_DIR / f"watchlist_alerts_{today}.csv"
    alerts_df.to_csv(alerts_path, index=False)
    logger.info(f"      ✅ Alerts watchlist: {alerts_path} ({len(alerts)} tickers)")

    # log top 10 más cercanos a pasar
    logger.info(
        f"      Top candidatos en vigilancia (proximity_score = menor es mejor):"
    )
    for a in alerts[:10]:
        logger.info(
            f"        {a['ticker']:<8} n_block={a['n_blockers']}  prox={a['proximity_score']:.2f} "
            f"| {a['blockers']}"
        )

    return alerts


def log_universe_diagnostics(tickers: list[str], db_path: Path, top_n: int = 15):
    """Log observability metrics for fetched universe."""
    if not tickers:
        logger.info("      Universe diagnostics: no tickers fetched")
        return

    preview = tickers[: max(0, top_n)]
    logger.info(
        f"      Universe diagnostics: fetched={len(tickers)} top_{len(preview)}={preview}"
    )

    try:
        conn = sqlite3.connect(str(db_path))
        placeholders = ",".join(["?"] * len(tickers))
        q = f"SELECT COUNT(DISTINCT ticker) FROM ohlcv_cache WHERE ticker IN ({placeholders})"
        rows_in_cache = conn.execute(q, tickers).fetchone()[0]
        conn.close()
        coverage = (rows_in_cache / len(tickers)) * 100 if tickers else 0.0
        logger.info(
            f"      Universe diagnostics: DB coverage={rows_in_cache}/{len(tickers)} ({coverage:.1f}%)"
        )
    except Exception as e:
        logger.warning(f"      Universe diagnostics failed: {e}")


def run_pre_market(
    generate_charts_flag: bool = False,
    override_regime: str = "none",
    override_reason: str = "manual_override",
    drift_max_divergence_pct: float | None = None,
    diagnostics_top_n: int = 15,
):
    """PRE-MARKET: Health checks + regime validation + signal generation."""
    logger.info("=" * 60)
    logger.info("PRE-MARKET CHECKS")
    logger.info("=" * 60)

    config = load_paper_config()
    strategies = config.get("portfolio", {}).get("strategies", [])

    today = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"📅 Date: {today}")
    logger.info(f"🎯 Active strategies: {[s['combo'] for s in strategies]}")

    logger.info("  [1/6] Checking data cache...")
    cache_status = {"db": False, "screener": False}
    db_path = ROOT / "data" / "ticker_cache.db"
    if db_path.exists():
        cache_status["db"] = True
        logger.info(f"      ✅ DB cache exists")
    else:
        logger.warning(f"      ⚠️ DB cache missing")

    screener_cache_dir = ROOT / "data" / "screener_cache"
    if screener_cache_dir.exists():
        cache_status["screener"] = True
        logger.info(f"      ✅ Screener cache exists")
    else:
        logger.warning(f"      ⚠️ Screener cache missing")

    logger.info("  [2/6] Validating regime filter (SPY>SMA50)...")
    ctx = get_market_context_live(
        require_spy_above_sma50=True,
        max_vix=35.0,
        db_path=DB_PATH,
    )
    reg = apply_regime_override(ctx, override_regime)

    spy_status = "OK" if reg["effective_spy_ok"] else "BLOCKED"
    vix_status = "OK" if reg["effective_vix_ok"] else "BLOCKED"
    raw_status = "✅ PASS" if reg["raw_regime_ok"] else "❌ BLOCK"
    eff_status = "✅ PASS" if reg["effective_regime_ok"] else "❌ BLOCK"
    quality = ctx.get("regime_quality", "OK")

    logger.info(
        f"      SPY: ${ctx['spy_price']:.2f} (SMA50 ${ctx['spy_sma50']:.2f}) [{spy_status}]"
    )
    vix_src = ctx.get("vix_source", "N/A")
    logger.info(
        f"      VIX: {ctx['vix'] if ctx['vix'] else 'N/A'} [{vix_status}] [{quality}] [{vix_src}]"
    )
    logger.info(
        f"      Regime raw: {raw_status} | effective: {eff_status} (override={reg['override_mode']})"
    )

    if reg["override_applied"]:
        logger.warning(f"      ⚠️ Override applied: {override_reason}")

    regime_ok = reg["effective_regime_ok"]

    if not regime_ok:
        logger.warning("  ⚠️ Market blocked by regime filter - no new entries today")

    logger.info("  [3/6] Loading universe from Finviz...")

    prod_cfg_path = ROOT / "config" / "production_config.json"
    if prod_cfg_path.exists():
        prod_cfg = json.load(open(prod_cfg_path))
    else:
        prod_cfg = {}

    universe_source_cfg = prod_cfg.get("universe_source", {})
    configured_max_divergence = universe_source_cfg.get("drift", {}).get(
        "max_divergence_pct", 15.0
    )
    effective_max_divergence = (
        drift_max_divergence_pct
        if drift_max_divergence_pct is not None
        else configured_max_divergence
    )

    if drift_max_divergence_pct is not None:
        logger.warning(
            "      ⚠️ Drift threshold override active: "
            f"{configured_max_divergence}% -> {effective_max_divergence}%"
        )

    universe_gate_ok = True
    universe_block_reason = None
    snapshot_info = {}
    drift_info = {}

    UNIVERSE_SNAPSHOT_DIR = OUTPUTS_DIR / "universe_snapshots"
    UNIVERSE_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    finviz_result = fetch_finviz_universe(universe_source_cfg)

    if not finviz_result.ok:
        universe_gate_ok = False
        universe_block_reason = f"finviz_fetch_error:{finviz_result.error}"
        logger.warning(f"  🚫 Universe gate BLOCKED: {universe_block_reason}")
        log_universe_diagnostics(finviz_result.tickers, DB_PATH, diagnostics_top_n)
        universe = []
    else:
        meta = {
            "provider": finviz_result.provider,
            "fetched_at": finviz_result.fetched_at,
            "pages_ok": finviz_result.pages_ok,
            "raw_rows": finviz_result.raw_rows,
            "warnings": finviz_result.parse_warnings,
        }
        snapshot = save_universe_snapshot(
            today, finviz_result.tickers, meta, UNIVERSE_SNAPSHOT_DIR
        )
        snapshot_info = {
            "provider": finviz_result.provider,
            "snapshot_path": str(snapshot.snapshot_path)
            if snapshot.snapshot_path
            else None,
            "hash": snapshot.hash,
            "tickers_count": snapshot.tickers_count,
        }
        logger.info(
            f"      Universe snapshot: {snapshot.tickers_count} tickers, hash={snapshot.hash[:12]}..."
        )
        log_universe_diagnostics(finviz_result.tickers, DB_PATH, diagnostics_top_n)

        drift = run_drift_audit(
            finviz_result.tickers,
            DB_PATH,
            max_divergence_pct=effective_max_divergence,
            reference_limit=200,
        )
        drift_info = {
            "divergence_pct": drift.divergence_pct,
            "live_coverage_pct": drift.live_coverage_pct,
            "live_extra_pct": drift.live_extra_pct,
            "gate_passed": drift.gate_passed,
            "max_divergence_pct": effective_max_divergence,
            "configured_max_divergence_pct": configured_max_divergence,
        }
        save_drift_audit(today, drift, finviz_result.tickers, UNIVERSE_SNAPSHOT_DIR)

        if not drift.gate_passed:
            universe_gate_ok = False
            universe_block_reason = drift.block_reason
            logger.warning(
                f"  🚫 Universe gate BLOCKED: high_drift {drift.divergence_pct}%"
            )
            universe = []
        else:
            universe = finviz_result.tickers

    logger.info(f"      Universe: {len(universe)} tickers (gate_ok={universe_gate_ok})")

    logger.info("  [4/6] Checking combo configs & validation status...")
    for strat in strategies:
        combo = strat["combo"]
        cfg_path = ROOT / "outputs" / "best_combos_run" / f"{combo}_config.json"
        combo_path = COMBOS_DIR / f"{combo}.json"
        if combo_path.exists():
            logger.info(f"      ✅ {combo}: combo config OK")
            log_combo_validation_status(combo)
        else:
            logger.warning(f"      ⚠️ {combo}: config MISSING")

    logger.info("  [5/6] Generating signals...")
    all_signals = []
    override_was_used = reg.get("override_applied", False)

    if regime_ok:
        if override_was_used:
            logger.warning(
                f"      ⚠️  Override activo ({reg['override_mode']}) — régimen forzado PASS, "
                f"scanner ejecutándose de todas formas"
            )
        for strat in strategies:
            combo = strat["combo"]
            signals = scan_combo_signals(combo, universe)
            logger.info(f"      {combo}: {len(signals)} signals")
            all_signals.extend(signals)
    else:
        logger.info("      Skipping signal generation (market blocked)")

    if not universe_gate_ok:
        all_signals = []
        logger.warning(f"      🚫 Universe gate blocked - no signals generated")
        logger.warning(f"      🚫 Reason: {universe_block_reason}")

    all_signals.sort(key=lambda x: x["entry_score"], reverse=True)
    logger.info(f"      Total signals: {len(all_signals)}")

    if all_signals:
        logger.info(f"\n  Top 5 signals:")
        for s in all_signals[:5]:
            logger.info(
                f"    {s['ticker']:<8} {s['combo']:<30} score={s['entry_score']:.3f} RS={s['rs_percentile']:.0f}%"
            )
    elif regime_ok and override_was_used:
        logger.warning(
            "      → Scanner corrió con override activo y NO encontró setups válidos."
        )
        logger.warning(
            "      → Esto es normal en mercado en distribución: los filtros tier2/RS son "
            "correctos, no hay candidatos hoy."
        )
        logger.info(
            "      → Ver watchlist_alerts para tickers que están cerca de los umbrales."
        )
    elif regime_ok and not override_was_used:
        logger.info(
            "      → Scanner corrió normalmente: no hay setups que cumplan criterios hoy."
        )

    logger.info("  [6/6] Saving watchlist...")
    if all_signals:
        daily_watchlist = pd.DataFrame(all_signals[:30])
        daily_path = OUTPUTS_DIR / f"watchlist_daily_{today}.csv"
        daily_watchlist.to_csv(daily_path, index=False)
        logger.info(
            f"      ✅ Daily watchlist: {daily_path} ({len(all_signals)} signals)"
        )

        weekly_path = OUTPUTS_DIR / f"watchlist_weekly_{today}.csv"
        daily_watchlist.to_csv(weekly_path, index=False)
        logger.info(f"      ✅ Weekly watchlist: {weekly_path}")
    else:
        logger.info("      ℹ️  No signals generated")

    # --- Watchlist de vigilancia: siempre se genera, tenga o no señales ---
    logger.info("      Scanning universe for near-threshold candidates...")
    alerts = generate_watchlist_alerts(universe, today)

    pre_report = {
        "date": today,
        "regime": {
            "spy_ok": ctx["spy_ok"],
            "spy_price": ctx.get("spy_price"),
            "spy_sma50": ctx.get("spy_sma50"),
            "vix": ctx["vix"],
            "vix_ok": ctx["vix_ok"],
            "vix_source": ctx.get("vix_source"),
            "regime_quality": quality,
            "warnings": ctx.get("warnings", []),
            "raw_regime_ok": reg["raw_regime_ok"],
            "effective_regime_ok": reg["effective_regime_ok"],
        },
        "override": {
            "mode": reg["override_mode"],
            "applied": reg["override_applied"],
            "reason": override_reason,
        },
        "universe": {
            "provider": snapshot_info.get("provider", "db"),
            "snapshot_path": snapshot_info.get("snapshot_path"),
            "hash": snapshot_info.get("hash"),
            "tickers_count": len(universe),
            "drift_metrics": drift_info,
            "gate_passed": universe_gate_ok,
            "block_reason": universe_block_reason,
        },
        "signals": len(all_signals),
        "top_signals": all_signals[:10] if all_signals else [],
        "alerts": {
            "count": len(alerts),
            "top_near_threshold": alerts[:5] if alerts else [],
        },
    }
    pre_report_path = OUTPUTS_DIR / f"pre_report_{today}.json"
    with open(pre_report_path, "w") as f:
        json.dump(pre_report, f, indent=2, default=str)
    logger.info(f"      ✅ Pre-report: {pre_report_path}")

    if generate_charts_flag and all_signals:
        logger.info("  [EXTRA] Generating charts...")
        generate_charts(all_signals, today)

    logger.info("✅ PRE-MARKET COMPLETE")
    return {
        "cache": cache_status,
        "regime_ok": regime_ok,
        "regime_ctx": ctx,
        "signals": all_signals,
        "universe": len(universe),
    }


def run_intraday():
    """INTRADAY: Monitoring + simulated execution."""
    logger.info("=" * 60)
    logger.info("INTRADAY MONITORING")
    logger.info("=" * 60)

    config = load_paper_config()
    strategies = config.get("portfolio", {}).get("strategies", [])

    logger.info("  [1/3] Monitoring open positions...")
    positions = []
    logger.info(f"      Open positions: {len(positions)}")

    logger.info("  [2/3] Checking exposure limits...")
    max_exposure = 0.65
    current_exposure = 0.0
    logger.info(
        f"      Current: {current_exposure * 100:.1f}% / Max: {max_exposure * 100:.1f}%"
    )
    if current_exposure > max_exposure:
        logger.warning("      ⚠️ EXPOSURE EXCEEDED")
    else:
        logger.info("      ✅ Within limits")

    logger.info("  [3/3] Simulating signal execution...")
    for strat in strategies:
        combo = strat["combo"]
        alloc = strat.get("allocation_pct", 0)
        logger.info(f"      {combo}: {alloc}% allocation (SIMULATED)")

    logger.info("✅ INTRADAY COMPLETE")
    return {"positions": positions, "exposure": current_exposure}


def run_eod(selected_tickers: list = None):
    """END-OF-DAY: Reconciliation + KPIs + reporting."""
    logger.info("=" * 60)
    logger.info("END-OF-DAY RECONCILIATION")
    logger.info("=" * 60)

    config = load_paper_config()
    strategies = config.get("portfolio", {}).get("strategies", [])
    shadow = config.get("portfolio", {}).get("shadow", [])

    today = datetime.now().strftime("%Y-%m-%d")
    pre_report_path = OUTPUTS_DIR / f"pre_report_{today}.json"

    pre_signals = []
    if pre_report_path.exists():
        with open(pre_report_path) as f:
            pre_data = json.load(f)
            pre_signals = pre_data.get("top_signals", [])

    selected = selected_tickers or []
    if not selected and pre_signals:
        logger.info(f"  [1/5] No selected tickers provided.")
        logger.info(
            f"      Available from pre-market: {[s['ticker'] for s in pre_signals[:5]]}"
        )
        logger.info(f"      Use --select TICKER1,TICKER2 to track specific ones")

    logger.info("  [2/5] Reconciling trades...")

    daily_summary = {
        "date": today,
        "strategies": {},
        "shadow": {},
        "selected": selected,
        "tracked": 0,
    }

    for strat in strategies:
        combo = strat["combo"]

        selected_for_combo = [
            t
            for t in selected
            if any(s["ticker"] == t and s["combo"] == combo for s in pre_signals)
        ]

        daily_summary["strategies"][combo] = {
            "signals_generated": len([s for s in pre_signals if s["combo"] == combo]),
            "selected_to_track": len(selected_for_combo),
            "orders_sent": len(selected_for_combo),
            "fills": 0,
            "pnl_r": 0.0,
            "sharpe_rolling": 0.0,
            "pf_rolling": 0.0,
        }
        logger.info(f"      {combo}: {len(selected_for_combo)} selected to track")

    for sh in shadow:
        combo = sh["combo"]
        daily_summary["shadow"][combo] = {
            "signals_generated": 0,
            "selected_to_track": 0,
            "pnl_r": 0.0,
        }
        logger.info(f"      {combo} (SHADOW): 0 selected")

    daily_summary["tracked"] = len(selected)

    logger.info("  [3/5] Computing daily KPIs...")
    max_daily_loss_r = 3.0
    daily_risk_used = 0.0
    logger.info(f"      Daily R used: {daily_risk_used:.2f} / {max_daily_loss_r:.2f}")
    if daily_risk_used >= max_daily_loss_r:
        logger.warning("      ⚠️ DAILY LOSS LIMIT REACHED")
    else:
        logger.info("      ✅ Within daily loss limit")

    logger.info("  [4/5] Rolling metrics (placeholder for now)...")
    for combo in daily_summary["strategies"]:
        logger.info(f"      {combo}: Sharpe rolling=0.00, PF rolling=0.00")

    logger.info("  [5/5] Saving daily report...")
    report_path = OUTPUTS_DIR / f"daily_pnl_{today}.json"
    with open(report_path, "w") as f:
        json.dump(daily_summary, f, indent=2, default=str)
    logger.info(f"      ✅ Saved: {report_path}")

    # === [6/5] Compute and save analytics ===
    logger.info("  [6/5] Computing daily analytics...")
    try:
        inputs = build_analytics_inputs(today)
        analytics = compute_daily_analytics(
            date=today,
            trades=inputs["trades"],
            equity_curve=inputs["equity_curve"],
            market_score=inputs["market_score"],
            regime_quality=inputs["regime_quality"],
            actual_snapshot=inputs["actual_snapshot"],
            initial_capital=inputs["initial_capital"],
        )
        save_daily_analytics(today, analytics)

        # Log key metrics
        ps = analytics.get("position_sizing", {})
        rs = analytics.get("trade_stats", {})
        oq = analytics.get("overall_quality", {})
        mc = analytics.get("simulation", {})
        flags = analytics.get("meta", {}).get("data_quality_flags", [])

        logger.info(
            f"      📊 Kelly: {ps.get('kelly_tier')} ({ps.get('kelly_fraction')})"
        )
        logger.info(
            f"      📊 Deployed: {ps.get('deployed_pct') * 100:.1f}% | Cash reserve: {ps.get('cash_reserve_usd', 0):.0f}"
        )
        logger.info(
            f"      📊 Trades: {rs.get('trades')} | WR: {rs.get('win_rate')}% | RR: {rs.get('rr')}"
        )
        logger.info(
            f"      📊 PF: {oq.get('profit_factor')} | Calmar: {oq.get('calmar')} | Sharpe: {oq.get('sharpe')}"
        )
        logger.info(
            f"      📊 Expected 1Y growth: {mc.get('expected_growth_1y', 0) * 100:.1f}%"
        )
        if flags:
            logger.warning(f"      ⚠️ Quality flags: {flags}")

        # === [7/5] Run simulation pack ===
        logger.info("  [7/5] Running simulation pack...")
        try:
            equity_curve = inputs.get("equity_curve")
            if equity_curve is not None and len(equity_curve) >= 10:
                sim_pack = run_simulation_pack(
                    equity_series=equity_curve,
                    trades=inputs.get("trades", []),
                    regime_cards=None,  # Not available in daily
                    n_sims=1000,
                    store_full_paths=False,  # Compact mode
                )
                analytics["simulation_pack"] = sim_pack
                save_daily_analytics(today, analytics)  # Re-save with simulation pack

                # Log simulation key metrics
                mc_full = sim_pack.get("mc_full", {})
                summary = mc_full.get("summary", {})
                if summary:
                    logger.info(
                        f"      🎲 Sim: median=${summary.get('median_outcome', 0):,.0f} "
                        f"risk_loss={summary.get('risk_of_loss', 0) * 100:.1f}% "
                        f"conf_low={mc_full.get('confidence_low', False)}"
                    )
                if sim_pack.get("cash_constraint_curves", {}).get("note"):
                    logger.debug(
                        f"      🎲 Cash constraints: {sim_pack['cash_constraint_curves']['note']}"
                    )
            else:
                logger.info("      🎲 Skipping (insufficient equity history)")
        except Exception as e:
            logger.warning(f"      🎲 Simulation pack failed: {e}")

        # Risk alerts
        risk_checks = analytics.get("risk_checks", {})
        soft_ruin = risk_checks.get("soft_ruin_30", 0)
        hard_ruin = risk_checks.get("hard_ruin_50", 0)
        if hard_ruin > 0.05:
            logger.warning(
                f"      🚨 ALERT: Hard ruin probability {hard_ruin * 100:.1f}% exceeds 5% threshold!"
            )
        elif soft_ruin > 0.10:
            logger.warning(
                f"      ⚠️ ALERT: Soft ruin probability {soft_ruin * 100:.1f}% exceeds 10%"
            )
    except Exception as e:
        logger.error(f"      ❌ Analytics failed: {e}")

    logger.info("✅ END-OF-DAY COMPLETE")
    return daily_summary


def run_full_day():
    """Run complete daily cycle."""
    logger.info("🚀 STARTING FULL DAILY CYCLE")
    pre = run_pre_market(generate_charts_flag=False)
    intra = run_intraday()
    eod = run_eod()
    logger.info("✅ FULL DAILY CYCLE COMPLETE")
    return {"pre": pre, "intra": intra, "eod": eod}


def main():
    parser = argparse.ArgumentParser(description="Paper Trading Daily Runbook")
    parser.add_argument(
        "--phase",
        type=str,
        choices=["pre", "intra", "eod", "all"],
        default="all",
        help="Phase to run",
    )
    parser.add_argument(
        "--charts", action="store_true", help="Generate charts in pre-market"
    )
    parser.add_argument(
        "--select",
        type=str,
        default="",
        help="Comma-separated tickers selected for EOD tracking",
    )
    parser.add_argument(
        "--override-regime",
        type=str,
        choices=["none", "spy", "vix", "all"],
        default="none",
        help="Override regime gate for paper trading (audited)",
    )
    parser.add_argument(
        "--override-reason",
        type=str,
        default="manual_override",
        help="Reason stored in logs/pre_report when override is used",
    )
    parser.add_argument(
        "--drift-max-divergence-pct",
        type=float,
        default=None,
        help="Override drift gate max divergence pct (diagnostic/testing)",
    )
    parser.add_argument(
        "--diag-top-universe",
        type=int,
        default=15,
        help="Top N Finviz tickers to log for universe diagnostics",
    )
    args = parser.parse_args()

    selected = None
    if args.select:
        selected = [t.strip().upper() for t in args.select.split(",") if t.strip()]

    if args.phase == "pre":
        run_pre_market(
            generate_charts_flag=args.charts,
            override_regime=args.override_regime,
            override_reason=args.override_reason,
            drift_max_divergence_pct=args.drift_max_divergence_pct,
            diagnostics_top_n=args.diag_top_universe,
        )
    elif args.phase == "intra":
        run_intraday()
    elif args.phase == "eod":
        run_eod(selected_tickers=selected)
    else:
        run_full_day()


if __name__ == "__main__":
    main()
