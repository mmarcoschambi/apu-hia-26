import os
import sys
import json
import sqlite3
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.signals.signal_engine import evaluate_ticker, merge_ab_signals
from src.integration.combo_loader import load_combo_merged
from src.integration.universe_builder import build_universe_for_fold
from src.config.dynamic_config import load_production_config
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS
from src.signals.thematic_logic import calculate_equal_weighted_index
from src.data.theme_taxonomy import THEME_MAP, get_themes, get_theme_map_for_date

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "backtests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Constants
MAX_POSITIONS = 6
MAX_PER_SECTOR = 2
RISK_PCT_BY_REGIME = {
    "ATTACK": 0.028 * 1.30,
    "DEFENSE_PARTIAL": 0.028 * 1.00,
    "DEFENSE_FULL": 0.028 * 0.60,
}
HOLDING_DAYS_LIMIT = 10
FEE_BPS = 1.0  # 1 bps
SLIPPAGE_BPS = 5.0  # 5 bps

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)


def get_trading_dates(start_date: str, end_date: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT DISTINCT date FROM ohlcv_cache WHERE ticker='SPY' AND date >= ? AND date <= ? || ' 23:59:59' ORDER BY date"
    df = pd.read_sql(query, conn, params=(start_date, end_date))
    conn.close()
    if df.empty:
        return []
    dates = pd.to_datetime(df["date"], format="mixed").dt.strftime("%Y-%m-%d").unique().tolist()
    return sorted(dates)


def load_ohlcv_batch_memory(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    if not tickers:
        return {}
    conn = sqlite3.connect(DB_PATH)
    res = {}
    for i in range(0, len(tickers), 500):
        chunk = tickers[i : i + 500]
        placeholders = ",".join(["?"] * len(chunk))
        query = f"SELECT ticker, date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? || ' 23:59:59'"
        df_all = pd.read_sql(query, conn, params=chunk + [start, end])
        for ticker, group in df_all.groupby("ticker"):
            df = group.drop(columns=["ticker"]).copy()
            df["date_parsed"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
            df["date_len"] = df["date"].str.len()
            df = df.sort_values(["date_parsed", "date_len"]).drop_duplicates(
                subset=["date_parsed"], keep="last"
            )
            res[ticker] = (
                df.drop(columns=["date", "date_len"])
                .rename(columns={"date_parsed": "date"})
                .set_index("date")
                .astype(float)
            )
    conn.close()
    return res


def calculate_backtest_metrics(trades_df, equity_curve_df, rs_coverage_pct=100.0):
    if trades_df.empty:
        initial = 100000.0
        final = initial
        if not equity_curve_df.empty:
            final = equity_curve_df["equity"].iloc[-1]
        return {
            "total_return": round(float((final / initial - 1) * 100), 2),
            "total_trades": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "rs_coverage_pct": rs_coverage_pct,
        }

    pnl = trades_df["pnl"]
    win_rate = (pnl > 0).mean() * 100
    pos_pnl, neg_pnl = pnl[pnl > 0].sum(), abs(pnl[pnl < 0].sum())
    profit_factor = pos_pnl / neg_pnl if neg_pnl > 0 else float("inf")

    equity = pd.to_numeric(equity_curve_df["equity"], errors="coerce").dropna()
    equity = equity[equity > 0]

    if not equity.empty:
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max * 100
        max_dd = drawdown.min()
        initial, final = equity.iloc[0], equity.iloc[-1]
        n_days = (
            pd.to_datetime(equity_curve_df["date"].iloc[-1])
            - pd.to_datetime(equity_curve_df["date"].iloc[0])
        ).days
        ann_ret = ((final / initial) ** (365.0 / max(1, n_days)) - 1) * 100 if n_days > 0 else 0
        rets = equity.pct_change().dropna()
        sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
    else:
        max_dd, initial, final, ann_ret, sharpe = 0, 1, 1, 0, 0

    return {
        "sharpe_ratio": round(float(sharpe), 3),
        "win_rate": round(float(win_rate), 2),
        "profit_factor": round(float(profit_factor), 2),
        "max_drawdown": round(float(max_dd), 2),
        "annualized_return": round(float(ann_ret), 2),
        "total_return": round(float((final / initial - 1) * 100), 2),
        "total_trades": len(trades_df),
        "rs_coverage_pct": rs_coverage_pct,
    }


def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float,
    max_tickers: int,
    tag: str,
    use_variant_e: bool = False,
    index_name: str = "SP500",
    use_e25_sizing: bool = False,
    e25_version: str = "v1_monotonic",
    exclude_tickers: list[str] | None = None,
    exclude_sectors: list[str] | None = None,
    use_pit: bool = True,
    ticker_cap: float | None = None,
    sector_cap: float | None = None,
    universe_source: str = "pit",
):
    # Support both space-separated (--exclude-tickers NVDA AMD) and
    # comma-separated (--exclude-tickers NVDA,AMD) formats.
    exclude_set = {
        tok.upper()
        for raw in (exclude_tickers or [])
        for tok in raw.split(",")
        if tok.strip()
    }
    exclude_sectors_set = {
        tok.upper()
        for raw in (exclude_sectors or [])
        for tok in raw.split(",")
        if tok.strip()
    }
    logger.info(
        f"[BACKTEST] BACKTEST (PARITY{' + VAR-E' if use_variant_e else ''}{' + E25-SIZING (' + e25_version + ')' if use_e25_sizing else ''}) | Index: {index_name} | Range: {start_date} -> {end_date}"
        f"{' | Excluding Tickers: ' + ','.join(sorted(exclude_set)) if exclude_set else ''}"
        f"{' | Excluding Sectors: ' + ','.join(sorted(exclude_sectors_set)) if exclude_sectors_set else ''}"
    )
    dates_str = get_trading_dates(start_date, end_date)
    if not dates_str:
        return

    # --- FASE 1: PRE-CARGA Y CONFIGURACIÓN ---
    logger.info("[LOADING] Loading configs and pre-loading superset...")

    # Load production config for backtest constants and E25 dynamic extension sizing
    prod_cfg = load_production_config()
    bt_cfg = prod_cfg.get("backtest", {})

    max_positions = bt_cfg.get("max_positions", 8)
    max_per_sector = bt_cfg.get("max_per_sector", 2)
    holding_days_limit = bt_cfg.get("holding_days_limit", 10)
    fee_bps = bt_cfg.get("fee_bps", 1.0)
    slippage_bps = bt_cfg.get("slippage_bps", 5.0)
    risk_pct_by_regime = bt_cfg.get("risk_pct_by_regime", {
        "ATTACK": 0.0364,
        "DEFENSE_PARTIAL": 0.028,
        "DEFENSE_FULL": 0.0168
    })

    # For Issue #21 RS Coverage metric tracking
    missing_rs_count = {}
    evaluated_rs_total = 0
    available_rs_count = 0

    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")

    if use_variant_e:
        for cfg in [cfg_a, cfg_b]:
            cfg["tier2_filters"]["use_theme_group_filter"] = True
            cfg["tier2_filters"]["theme_filter_mode"] = "divergence"
            # CRITICAL: We need sector data for divergence, but we MUST NOT block if sector is weak!
            cfg["tier2_filters"]["use_sector_etf_filter"] = False

    if use_e25_sizing:
        # Load from config, falling back to safe defaults if not found
        prod_dynamic_sizing = prod_cfg.get("tier3_fixed", {}).get("dynamic_extension_sizing", {
            "version": e25_version,
            "comfort_pct": 6.76,
            "valley_pct": 10.0,
            "mid_pct": 15.0,
            "high_pct": 25.0,
            "extreme_pct": 35.0,
            "max_pct": 50.0,
            "min_factor": 0.5,
            "extreme_factor": 0.2,
            "adr_exception_pct": 8.0,
        })
        # Override version from CLI if it's passed explicitly
        prod_dynamic_sizing["version"] = e25_version

        for cfg in [cfg_a, cfg_b]:
            # Activar el feature flag del sizing dinámico en tier3_fixed
            cfg["tier3_fixed"] = {
                "use_dynamic_extension_sizing": True,
                "dynamic_extension_sizing": prod_dynamic_sizing,
            }
            # Reemplazar el bloqueo de max_dist_sma20 en tier2_filters (Experimento 2 de E25)
            cfg["tier2_filters"]["use_dynamic_extension"] = True

    logger.info(f"[SCANNING] Building PIT universes for each date (Index: {index_name})...")
    
    # Load disk cache for universe builder to speed up consecutive backtest runs
    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"universes_{index_name}_{max_tickers}.json"
    universe_cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                universe_cache = json.load(f)
            logger.info(f"Loaded {len(universe_cache)} cached universes from {cache_file}")
        except Exception as e:
            logger.warning(f"Error loading universe cache: {e}")

    universe_by_date = {}
    superset_tickers = set()
    cache_updated = False

    for d_str in tqdm(dates_str, desc="Universe Building"):
        if universe_source == "shadow_finviz":
            setups_path = PROJECT_ROOT / "outputs" / "shadow_sandbox" / "finviz_runs" / d_str / "setups.csv"
            if setups_path.exists():
                try:
                    df_setups = pd.read_csv(setups_path)
                    snap_tickers = df_setups["ticker"].dropna().unique().tolist()
                except Exception as e:
                    logger.warning(f"Error loading setups for {d_str}: {e}")
                    snap_tickers = []
            else:
                snap_tickers = []
        else:
            if d_str in universe_cache:
                snap_tickers = universe_cache[d_str]
            else:
                u_start = (pd.to_datetime(d_str) - timedelta(days=730)).strftime("%Y-%m-%d")
                snap = build_universe_for_fold(
                    DB_PATH,
                    d_str,
                    u_start,
                    max_tickers=max_tickers,
                    index_name=index_name,
                    use_pit=use_pit,
                )
                snap_tickers = snap.tickers
                universe_cache[d_str] = snap_tickers
                cache_updated = True

        filtered_tickers = [
            t for t in snap_tickers 
            if t.upper() not in exclude_set 
            and SECTOR_MAP.get(t.upper(), "UNKNOWN") not in exclude_sectors_set
        ]
        universe_by_date[d_str] = filtered_tickers
        superset_tickers.update(filtered_tickers)

    if cache_updated:
        try:
            with open(cache_file, "w") as f:
                json.dump(universe_cache, f)
            logger.info(f"Saved {len(universe_cache)} universes to cache file: {cache_file}")
        except Exception as e:
            logger.warning(f"Error saving universe cache: {e}")

    superset_tickers.update(["SPY", "^VIX"])
    superset_tickers.update(SECTOR_ETFS)
    if use_variant_e:
        from src.data.theme_taxonomy import THEME_MAP_2020, THEME_MAP_2022, THEME_MAP_CURRENT

        all_theme_tickers = (
            set(THEME_MAP_2020.keys()) | set(THEME_MAP_2022.keys()) | set(THEME_MAP_CURRENT.keys())
        )
        for t in all_theme_tickers:
            if t.upper() not in exclude_set and SECTOR_MAP.get(t.upper(), "UNKNOWN") not in exclude_sectors_set:
                superset_tickers.add(t)

    superset_tickers.difference_update(exclude_set)
    superset_tickers = {
        t for t in superset_tickers 
        if t in ["SPY", "^VIX"] or t in SECTOR_ETFS or SECTOR_MAP.get(t.upper(), "UNKNOWN") not in exclude_sectors_set
    }

    logger.info(f"Superset size: {len(superset_tickers)} tickers")

    conn = sqlite3.connect(DB_PATH)
    rs_all = pd.read_sql(
        "SELECT date, ticker, rs_composite FROM daily_rs_rankings WHERE date >= ? AND date <= ? || ' 23:59:59'",
        conn,
        params=(start_date, end_date),
    )
    rs_all["date"] = pd.to_datetime(rs_all["date"], format="mixed").dt.normalize()
    rs_lookup = rs_all.set_index(["date", "ticker"])["rs_composite"].to_dict()

    # Pre-run RS coverage validation check (Issue #21 Prevention)
    pre_evaluated_total = 0
    pre_available_count = 0
    pre_missing_tickers = {}
    for d_str, day_universe in universe_by_date.items():
        curr_dt = pd.to_datetime(d_str).normalize()
        for ticker in day_universe:
            if ticker.upper() in exclude_set:
                continue
            pre_evaluated_total += 1
            if (curr_dt, ticker) in rs_lookup:
                pre_available_count += 1
            else:
                pre_missing_tickers[ticker] = pre_missing_tickers.get(ticker, 0) + 1
    
    pre_coverage_pct = 100.0
    if pre_evaluated_total > 0:
        pre_coverage_pct = round((pre_available_count / pre_evaluated_total) * 100, 2)
    
    logger.info(f"[METRICS] Pre-run RS Coverage Check: {pre_coverage_pct}% ({pre_available_count}/{pre_evaluated_total} lookups succeeded)")
    if pre_coverage_pct < 95.0:
        logger.warning(
            f"[WARN] PROMINENT WARNING: RS Coverage is low ({pre_coverage_pct}%). "
            f"There are {pre_evaluated_total - pre_available_count} missing RS lookups."
        )
        if pre_missing_tickers:
            top_missing = sorted(pre_missing_tickers.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.warning(f"Top tickers missing from daily_rs_rankings: {', '.join(f'{k}:{v}' for k, v in top_missing)}")
            logger.warning(
                f"Suggested fix: Run: ./.venv/bin/python3 scripts/populate_rankings_daily.py --start {start_date} --end {end_date} --workers 4 --rs-only --overwrite"
            )

    health_all = pd.read_sql(
        "SELECT date, regime_mode FROM daily_health_scores WHERE date >= ? AND date <= ? || ' 23:59:59'",
        conn,
        params=(start_date, end_date),
    )
    health_all["date"] = pd.to_datetime(health_all["date"], format="mixed").dt.normalize()
    regime_lookup = health_all.set_index("date")["regime_mode"].to_dict()

    lookback_start = (pd.to_datetime(start_date) - timedelta(days=400)).strftime("%Y-%m-%d")
    all_ohlcv = load_ohlcv_batch_memory(list(superset_tickers), lookback_start, end_date)

    logger.info("[INDICATORS] Pre-calculating indicators (MA stack, ATR, ADR%, Consolidation) for all tickers...")
    for t_sym, t_df in all_ohlcv.items():
        if len(t_df) < 5:
            continue
        c = t_df["close"]
        t_df["ema10"] = c.ewm(span=10, adjust=False).mean()
        t_df["sma20"] = c.rolling(20).mean()
        t_df["sma50"] = c.rolling(50).mean()
        t_df["sma100"] = c.rolling(100).mean()
        t_df["sma150"] = c.rolling(150).mean()
        t_df["sma200"] = c.rolling(200).mean()
        t_df["sma13"] = c.rolling(13).mean()
        t_df["sma65"] = c.rolling(65).mean()
        
        # ATR14
        h = t_df["high"]
        l = t_df["low"]
        high_low = h - l
        high_close = (h - c.shift()).abs()
        low_close = (l - c.shift()).abs()
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        t_df["atr14"] = tr.rolling(14).mean()

        # Average Volume 20
        v = t_df["volume"]
        t_df["avg_vol20"] = v.rolling(20).mean()

        # ADR pct
        t_df["adr_pct"] = (((h - l) / c.replace(0, np.nan)) * 100).rolling(20).mean()

        # Consolidation Days
        bb_std = c.rolling(20).std()
        inside_bb = (c >= t_df["sma20"] - bb_std * 2) & (c <= t_df["sma20"] + bb_std * 2)
        t_df["consol_days"] = inside_bb.rolling(20).sum()

    spy_full = all_ohlcv.get("SPY", pd.DataFrame())
    vix_full = all_ohlcv.get("^VIX", pd.DataFrame())

    etf_dists_full = {}
    for etf in SECTOR_ETFS:
        if etf in all_ohlcv:
            df = all_ohlcv[etf]
            sma20 = df["close"].rolling(20).mean()
            etf_dists_full[etf] = ((df["close"] - sma20) / sma20).to_dict()

    theme_metrics_full = {}
    if use_variant_e:
        logger.info("[THEMES] Pre-calculating Dynamic Theme Indices for Variant E...")
        from src.data.theme_taxonomy import THEME_MAP_2020, THEME_MAP_2022, THEME_MAP_CURRENT

        all_theme_tickers = (
            set(THEME_MAP_2020.keys()) | set(THEME_MAP_2022.keys()) | set(THEME_MAP_CURRENT.keys())
        )

        # 1. Calcular DataFrame de cierres y retornos
        market_data_closes = pd.DataFrame(
            {t: df["close"] for t, df in all_ohlcv.items() if t in superset_tickers}
        )
        market_returns = market_data_closes.pct_change()

        # 2. Calcular retornos diarios dinámicos por tema
        theme_daily_returns = {}
        for dt in market_data_closes.index:
            theme_map = get_theme_map_for_date(dt)
            theme_to_tickers_date = {}
            for t, themes in theme_map.items():
                for theme in themes:
                    theme_to_tickers_date.setdefault(theme, []).append(t)

            for th, members in theme_to_tickers_date.items():
                valid_members = [m for m in members if m in market_returns.columns]
                if valid_members:
                    rets_day = market_returns.loc[dt, valid_members].dropna()
                    if not rets_day.empty:
                        theme_daily_returns.setdefault(th, {})[dt] = rets_day.mean()

        # Convertir a DataFrame de retornos y calcular índices acumulados
        df_theme_returns = pd.DataFrame(theme_daily_returns).reindex(market_data_closes.index)
        df_themes = (1 + df_theme_returns.fillna(0)).cumprod() * 100

        # Restaurar NaNs donde no había miembros válidos reportando ese día
        for col in df_themes.columns:
            nan_dates = df_themes.index.difference(theme_daily_returns[col].keys())
            df_themes.loc[nan_dates, col] = np.nan

        theme_sma20 = df_themes.rolling(20).mean()
        theme_dists = (df_themes - theme_sma20) / theme_sma20

        # 3. Mapear métricas de distancia por ticker y fecha (Point-in-Time)
        for t in all_theme_tickers:
            theme_metrics_full[t] = {}
            for d in dates_str:
                dt = pd.Timestamp(d)
                t_themes = get_themes(t, dt)  # Dinámico y libre de Look-ahead
                best_dist = -999
                for th in t_themes:
                    if th in theme_dists.columns and dt in theme_dists.index:
                        d_val = theme_dists.loc[dt, th]
                        if d_val > best_dist:
                            best_dist = d_val
                if best_dist != -999:
                    theme_metrics_full[t][dt] = best_dist

    conn.close()

    # --- FASE 2: LOOP SIMULACIÓN ---
    portfolio = {"cash": initial_capital, "positions": {}, "sector_count": {}}
    all_trades, equity_curve, pending_signals = [], [], []

    for d_str in tqdm(dates_str, desc="Simulating"):
        curr_dt = pd.Timestamp(d_str)

        total_equity = portfolio["cash"]
        for t, pos in portfolio["positions"].items():
            if t in all_ohlcv and curr_dt in all_ohlcv[t].index:
                pos["last_close"] = all_ohlcv[t].loc[curr_dt, "close"]
            total_equity += pos["size"] * pos["last_close"]
        equity_curve.append({"date": d_str, "equity": total_equity})

        closed = []
        for t, pos in portfolio["positions"].items():
            if t not in all_ohlcv or curr_dt not in all_ohlcv[t].index:
                continue
            r = all_ohlcv[t].loc[curr_dt]
            pos["days_held"] += 1

            exit_px, reason = None, None
            if r["open"] < pos["stop"]:
                exit_px, reason = r["open"], "STOP_GAP"
            elif r["low"] < pos["stop"]:
                exit_px, reason = pos["stop"], "STOP"

            if exit_px:
                px = exit_px * (1 - slippage_bps / 10000)
                portfolio["cash"] += px * pos["size"] - (px * pos["size"] * fee_bps / 10000)
                pos["realized_pnl"] += (px - pos["entry_px"]) * pos["size"]
                pos["exit_reasons"].append(reason)
                closed.append(t)
                continue

            if not pos["tp1_hit"] and r["high"] >= pos["tp1"]:
                sz = int(pos["initial_size"] * 0.33)
                px = pos["tp1"] * (1 - slippage_bps / 10000)
                portfolio["cash"] += px * sz - (px * sz * fee_bps / 10000)
                pos["realized_pnl"] += (px - pos["entry_px"]) * sz
                pos["size"], pos["tp1_hit"], pos["stop"] = pos["size"] - sz, True, pos["entry_px"]
                pos["exit_reasons"].append("TP1")

            if pos["tp1_hit"] and not pos["tp2_hit"] and r["high"] >= pos["tp2"]:
                sz = min(int(pos["initial_size"] * 0.33), pos["size"])
                px = pos["tp2"] * (1 - slippage_bps / 10000)
                portfolio["cash"] += px * sz - (px * sz * fee_bps / 10000)
                pos["realized_pnl"] += (px - pos["entry_px"]) * sz
                pos["size"], pos["tp2_hit"] = pos["size"] - sz, True
                pos["exit_reasons"].append("TP2")

            if pos["days_held"] >= pos.get("target_hold_days", holding_days_limit):
                px = r["close"] * (1 - slippage_bps / 10000)
                portfolio["cash"] += px * pos["size"] - (px * pos["size"] * fee_bps / 10000)
                pos["realized_pnl"] += (px - pos["entry_px"]) * pos["size"]
                pos["exit_reasons"].append("EOD")
                closed.append(t)

        for t in closed:
            p = portfolio["positions"].pop(t)
            portfolio["sector_count"][p["sector"]] = max(
                0, portfolio["sector_count"].get(p["sector"], 0) - 1
            )
            all_trades.append(
                {
                    "symbol": t,
                    "entry_date": p["entry_date"],
                    "exit_date": d_str,
                    "entry_price": p["entry_px"],
                    "exit_price": p["last_close"],
                    "pnl": p["realized_pnl"],
                    "initial_size": p.get("initial_size", 0),  # <-- Real sizing audit
                    "return_pct": (p["realized_pnl"] / (p["entry_px"] * p["initial_size"])) * 100
                    if (p["entry_px"] * p["initial_size"]) > 0
                    else 0,
                    "exit_phase": "+".join(p["exit_reasons"]),
                    "entry_score": p["entry_score"],
                    # E25 Sizing Metadata
                    "dist_sma20": p.get("dist_sma20", 0.0),
                    "adr_pct": p.get("adr_pct", 0.0),
                    "sizing_factor": p.get("sizing_factor", 1.0),
                    "sizing_reason": p.get("sizing_reason", ""),
                    "risk_budget_usd": p.get("risk_budget_usd", 0.0),
                    "raw_risk_budget_usd": p.get("raw_risk_budget_usd", 0.0),
                    "target_hold_days": p.get("target_hold_days", holding_days_limit),
                }
            )

        for sig in pending_signals:
            t = sig.ticker
            if t not in all_ohlcv or curr_dt not in all_ohlcv[t].index:
                continue
            r = all_ohlcv[t].loc[curr_dt]
            sec = SECTOR_MAP.get(t, "UNKNOWN")
            if (
                len(portfolio["positions"]) < max_positions
                and t not in portfolio["positions"]
                and portfolio["sector_count"].get(sec, 0) < max_per_sector
            ):
                entry_px = r["open"] * (1 + slippage_bps / 10000)

                # Option A Unified Sizing: Use sig.shares calculated canonically by SignalEngine
                shares = sig.shares
                # Get the dynamic risk budget for this trade
                risk_amt = dynamic_risk_dollars * sig.sizing_factor
                raw_risk_amt = dynamic_risk_dollars

                if shares > 0:
                    # Apply ticker cap
                    if ticker_cap is not None:
                        max_cost = total_equity * ticker_cap
                        if shares * entry_px > max_cost:
                            shares = int(max_cost / entry_px)

                    # Apply sector cap
                    if sector_cap is not None:
                        current_sec_val = sum(
                            pos["size"] * pos["last_close"]
                            for pos in portfolio["positions"].values()
                            if pos["sector"] == sec
                        )
                        max_sec_val = total_equity * sector_cap
                        allowed_sec_val = max(0.0, max_sec_val - current_sec_val)
                        if shares * entry_px > allowed_sec_val:
                            shares = int(allowed_sec_val / entry_px)

                    if shares <= 0:
                        continue

                    cost = shares * entry_px
                    if portfolio["cash"] >= (cost * 1.0001):
                        portfolio["cash"] -= cost * 1.0001
                        portfolio["sector_count"][sec] = (
                            portfolio["sector_count"].get(sec, 0) + 1
                        )
                        portfolio["positions"][t] = {
                            "size": shares,
                            "initial_size": shares,
                            "entry_px": entry_px,
                            "stop": sig.stop_price,
                            "tp1": sig.tp1_price,
                            "tp2": sig.tp2_price,
                            "entry_date": d_str,
                            "sector": sec,
                            "days_held": 0,
                            "tp1_hit": False,
                            "tp2_hit": False,
                            "realized_pnl": 0,
                            "exit_reasons": [],
                            "entry_score": sig.entry_score,
                            "last_close": entry_px,
                            # E25 metrics
                            "dist_sma20": sig.tier2_metrics.dist_sma20,
                            "adr_pct": sig.tier2_metrics.adr_pct,
                            "sizing_factor": sig.sizing_factor,
                            "sizing_reason": sig.sizing_reason,
                            "risk_budget_usd": risk_amt,              # <-- RIESGO DYNAMIC REAL DEL BACKTEST
                            "raw_risk_budget_usd": raw_risk_amt,      # <-- RIESGO DYNAMIC REAL DEL BACKTEST
                            "target_hold_days": sig.target_hold_days if sig.target_hold_days is not None else holding_days_limit,
                        }

        spy_slice = spy_full.loc[:curr_dt].tail(400)
        vix_slice = vix_full.loc[:curr_dt].tail(1)
        pending_signals = []
        if (
            len(spy_slice) >= 200
            and spy_slice.iloc[-1]["close"] > spy_slice["close"].rolling(200).mean().iloc[-1]
        ):
            vix_ok = vix_slice["close"].iloc[0] < 35.0 if not vix_slice.empty else True
            if vix_ok:
                regime_mode = regime_lookup.get(curr_dt, "DEFENSE_PARTIAL")
                risk_pct = risk_pct_by_regime.get(regime_mode, 0.028)
                dynamic_risk_dollars = total_equity * risk_pct

                # Inject dynamic_risk_dollars into both combo configs tier1_strategy risk_dollars
                cfg_a.setdefault("tier1_strategy", {})["risk_dollars"] = dynamic_risk_dollars
                cfg_b.setdefault("tier1_strategy", {})["risk_dollars"] = dynamic_risk_dollars

                day_universe = universe_by_date.get(d_str, [])
                results_a, results_b = [], []
                for ticker in day_universe:
                    if ticker.upper() in exclude_set:
                        continue
                    if ticker not in all_ohlcv:
                        continue
                    ticker_df = all_ohlcv[ticker].loc[:curr_dt]
                    if len(ticker_df) < 65:
                        continue
                    
                    # Track RS percentile lookup
                    rs_val = rs_lookup.get((curr_dt, ticker))
                    evaluated_rs_total += 1
                    if rs_val is None:
                        missing_rs_count[ticker] = missing_rs_count.get(ticker, 0) + 1
                    else:
                        available_rs_count += 1

                    etf = SECTOR_MAP.get(ticker)
                    s_dist = etf_dists_full.get(etf, {}).get(curr_dt) if etf else None
                    t_dist = theme_metrics_full.get(ticker, {}).get(curr_dt)

                    # Wrap evaluate_ticker in try/except (Issue #21 General Robustness)
                    try:
                        res_a = evaluate_ticker(
                            ticker,
                            ticker_df,
                            spy_slice,
                            cfg_a,
                            rs_percentile=rs_val,
                            scan_date=d_str,
                            sector_etf_dist=s_dist,
                            theme_dist=t_dist,
                        )
                        if res_a.passed:
                            results_a.append(res_a)
                    except Exception as e:
                        logger.error(
                            f"[ERROR] Exception in evaluate_ticker {ticker} (System A) on {d_str}: {e}",
                            exc_info=True
                        )

                    try:
                        res_b = evaluate_ticker(
                            ticker,
                            ticker_df,
                            spy_slice,
                            cfg_b,
                            rs_percentile=rs_val,
                            scan_date=d_str,
                            sector_etf_dist=s_dist,
                            theme_dist=t_dist,
                        )
                        if res_b.passed:
                            results_b.append(res_b)
                    except Exception as e:
                        logger.error(
                            f"[ERROR] Exception in evaluate_ticker {ticker} (System B) on {d_str}: {e}",
                            exc_info=True
                        )

                pending_signals = merge_ab_signals(results_a, results_b)

    df_trades, df_equity = pd.DataFrame(all_trades), pd.DataFrame(equity_curve)
    df_trades.to_csv(OUTPUT_DIR / f"{tag}_trades.csv", index=False)
    df_equity.rename(columns={"equity": "0"}).to_csv(OUTPUT_DIR / f"{tag}_equity.csv", index=False)

    # Calculate RS coverage percentage
    rs_coverage_pct = 100.0
    if evaluated_rs_total > 0:
        rs_coverage_pct = round((available_rs_count / evaluated_rs_total) * 100, 2)
    
    logger.info(f"[METRICS] RS Coverage Metric: {rs_coverage_pct}% ({available_rs_count}/{evaluated_rs_total} lookups succeeded)")
    if rs_coverage_pct < 95.0:
        logger.warning(
            f"[WARN] PROMINENT WARNING: RS Coverage is low ({rs_coverage_pct}%). "
            f"There are {evaluated_rs_total - available_rs_count} missing RS lookups."
        )
        if missing_rs_count:
            # log top 10 tickers with missing RS data
            top_missing = sorted(missing_rs_count.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.warning(f"Top tickers with missing RS: {', '.join(f'{k}:{v}' for k, v in top_missing)}")

    metrics = calculate_backtest_metrics(df_trades, df_equity, rs_coverage_pct=rs_coverage_pct)
    with open(OUTPUT_DIR / f"{tag}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info(
        f"[DONE] DONE | Return: {metrics.get('total_return')}% | MDD: {metrics.get('max_drawdown')}% | Trades: {len(df_trades)}"
    )

    # Calculate comprehensive robustness report (Issue #11)
    equity_series = df_equity.set_index(pd.to_datetime(df_equity["date"]))["equity"]
    if len(equity_series) >= 30:
        try:
            from src.validation.robustness_metrics import calculate_comprehensive_robustness_report
            backtest_result = {
                "equity_curve": equity_series,
                "trades_df": df_trades,
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "max_drawdown_pct": abs(metrics.get("max_drawdown", 0.0)),
                "total_trades": len(df_trades),
                "win_rate_pct": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
            }
            robustness_report = calculate_comprehensive_robustness_report(backtest_result)
            
            # Save robustness report to outputs/backtests
            with open(OUTPUT_DIR / f"{tag}_robustness.json", "w") as f:
                json.dump(robustness_report, f, indent=2)
                
            logger.info(
                f"[SHIELD]  Robustness Metrics | Sortino: {robustness_report['risk_adjusted']['sortino']:.2f} | "
                f"Omega: {robustness_report['risk_adjusted']['omega']:.2f} | "
                f"Calmar: {robustness_report['risk_adjusted']['calmar']:.2f} | "
                f"Tail Ratio: {robustness_report['risk_adjusted']['tail_ratio']:.2f} | "
                f"Prob of Loss: {robustness_report['probability_of_loss']*100:.1f}%"
            )
        except Exception as e:
            logger.warning(f"[WARN]  Could not calculate robustness metrics: {e}")
    else:
        logger.warning(f"[WARN]  Equity curve demasiado corta para robustez ({len(equity_series)} puntos). Mínimo requerido: 30.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=100000)
    parser.add_argument("--universe-size", type=int, default=200)
    parser.add_argument("--tag", default="gold_standard_variant_e")
    parser.add_argument(
        "--variant-e", action="store_true", help="Enable Thematic Divergence Filter"
    )
    parser.add_argument(
        "--no-pit",
        action="store_false",
        dest="use_pit",
        default=True,
        help="Disable Point-In-Time universe filter even if pit_constituents table exists",
    )
    parser.add_argument(
        "--e25-sizing",
        action="store_true",
        help="Enable E25 Dynamic Extension up to 50%% with sizing penalty",
    )
    parser.add_argument(
        "--e25-version",
        default="v1_monotonic",
        choices=["v1_monotonic", "v2_atlas_informed"],
        help="Sizing curve version for E25",
    )
    parser.add_argument(
        "--index",
        default="SP500",
        choices=["SP500", "RUSSELL1000", "RUSSELL2000", "NASDAQ100"],
        help="Target index for backtesting",
    )
    parser.add_argument(
        "--exclude-tickers",
        nargs="+",
        default=[],
        metavar="TICKER",
        help="Tickers to exclude from the backtest universe. "
             "Accepts space-separated (NVDA AMD) or comma-separated (NVDA,AMD) formats.",
    )
    parser.add_argument(
        "--exclude-sectors",
        nargs="+",
        default=[],
        metavar="SECTOR",
        help="Sectors to exclude from the backtest universe. "
             "Accepts space-separated (XLF XLV) or comma-separated (XLF,XLV) formats.",
    )
    parser.add_argument(
        "--ticker-cap",
        type=float,
        default=None,
        help="Maximum position size for any single ticker as a percentage of total portfolio equity (e.g. 0.15 for 15%%)",
    )
    parser.add_argument(
        "--sector-cap",
        type=float,
        default=None,
        help="Maximum total position value for any single sector as a percentage of total portfolio equity (e.g. 0.40 for 40%%)",
    )
    parser.add_argument(
        "--universe-source",
        default="pit",
        choices=["pit", "shadow_finviz"],
        help="Source of the backtest universe (pit for index constituents, shadow_finviz for daily setups)",
    )
    args = parser.parse_args()
    run_backtest(
        args.start,
        args.end,
        args.capital,
        args.universe_size,
        args.tag,
        use_variant_e=args.variant_e,
        index_name=args.index,
        use_e25_sizing=args.e25_sizing,
        e25_version=args.e25_version,
        exclude_tickers=args.exclude_tickers,
        exclude_sectors=args.exclude_sectors,
        use_pit=args.use_pit,
        ticker_cap=args.ticker_cap,
        sector_cap=args.sector_cap,
        universe_source=args.universe_source,
    )
