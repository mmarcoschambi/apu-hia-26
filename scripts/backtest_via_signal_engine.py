
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
from src.data.theme_taxonomy import THEME_MAP, get_themes

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "backtests"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Constants
MAX_POSITIONS = 6
MAX_PER_SECTOR = 2
RISK_PCT = 0.028  # 2.8% of total equity
HOLDING_DAYS_LIMIT = 10
FEE_BPS = 1.0 # 1 bps
SLIPPAGE_BPS = 5.0 # 5 bps

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

def get_trading_dates(start_date: str, end_date: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT DISTINCT date FROM ohlcv_cache WHERE ticker='SPY' AND date >= ? AND date <= ? || ' 23:59:59' ORDER BY date"
    df = pd.read_sql(query, conn, params=(start_date, end_date))
    conn.close()
    if df.empty: return []
    dates = pd.to_datetime(df["date"], format="mixed").dt.strftime("%Y-%m-%d").unique().tolist()
    return sorted(dates)

def load_ohlcv_batch_memory(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    if not tickers: return {}
    conn = sqlite3.connect(DB_PATH)
    res = {}
    for i in range(0, len(tickers), 500):
        chunk = tickers[i:i+500]
        placeholders = ",".join(["?"] * len(chunk))
        query = f"SELECT ticker, date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ? || ' 23:59:59'"
        df_all = pd.read_sql(query, conn, params=chunk + [start, end])
        for ticker, group in df_all.groupby("ticker"):
            df = group.drop(columns=["ticker"]).copy()
            df["date_parsed"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
            df["date_len"] = df["date"].str.len()
            df = df.sort_values(["date_parsed", "date_len"]).drop_duplicates(subset=["date_parsed"], keep="last")
            res[ticker] = df.drop(columns=["date", "date_len"]).rename(columns={"date_parsed": "date"}).set_index("date").astype(float)
    conn.close()
    return res

def calculate_backtest_metrics(trades_df, equity_curve_df):
    if trades_df.empty: 
        initial = 100000.0
        final = initial
        if not equity_curve_df.empty:
             final = equity_curve_df["equity"].iloc[-1]
        return {"total_return": round(float((final/initial-1)*100), 2), "total_trades": 0, "max_drawdown": 0, "sharpe_ratio": 0}
    
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
        n_days = (pd.to_datetime(equity_curve_df["date"].iloc[-1]) - pd.to_datetime(equity_curve_df["date"].iloc[0])).days
        ann_ret = ((final / initial) ** (365.0 / max(1, n_days)) - 1) * 100 if n_days > 0 else 0
        rets = equity.pct_change().dropna()
        sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
    else:
        max_dd, initial, final, ann_ret, sharpe = 0, 1, 1, 0, 0
        
    return {
        "sharpe_ratio": round(float(sharpe), 3), "win_rate": round(float(win_rate), 2),
        "profit_factor": round(float(profit_factor), 2), "max_drawdown": round(float(max_dd), 2),
        "annualized_return": round(float(ann_ret), 2), "total_return": round(float((final/initial-1)*100), 2),
        "total_trades": len(trades_df)
    }

def run_backtest(start_date: str, end_date: str, initial_capital: float, max_tickers: int, tag: str, use_variant_e: bool = False):
    logger.info(f"🚀 BACKTEST (PARITY{' + VAR-E' if use_variant_e else ''}) | Range: {start_date} -> {end_date}")
    dates_str = get_trading_dates(start_date, end_date)
    if not dates_str: return

    # --- FASE 1: PRE-CARGA Y CONFIGURACIÓN ---
    logger.info("📦 Loading configs and pre-loading superset...")
    
    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")
    
    if use_variant_e:
        for cfg in [cfg_a, cfg_b]:
            cfg["tier2_filters"]["use_theme_group_filter"] = True
            cfg["tier2_filters"]["theme_filter_mode"] = "divergence"
            # CRITICAL: We need sector data for divergence, but we MUST NOT block if sector is weak!
            cfg["tier2_filters"]["use_sector_etf_filter"] = False 

    logger.info("🔭 Building PIT universes for each date...")
    universe_by_date = {}
    superset_tickers = set()
    for d_str in tqdm(dates_str, desc="Universe Building"):
        u_start = (pd.to_datetime(d_str) - timedelta(days=730)).strftime("%Y-%m-%d")
        snap = build_universe_for_fold(DB_PATH, d_str, u_start, max_tickers=max_tickers)
        universe_by_date[d_str] = snap.tickers
        superset_tickers.update(snap.tickers)
    
    superset_tickers.update(["SPY", "^VIX"])
    superset_tickers.update(SECTOR_ETFS)
    if use_variant_e:
        for t in THEME_MAP: superset_tickers.add(t)
    
    logger.info(f"Superset size: {len(superset_tickers)} tickers")

    conn = sqlite3.connect(DB_PATH)
    rs_all = pd.read_sql(
        "SELECT date, ticker, rs_composite FROM daily_rs_rankings WHERE date >= ? AND date <= ? || ' 23:59:59'",
        conn, params=(start_date, end_date)
    )
    rs_all["date"] = pd.to_datetime(rs_all["date"], format="mixed").dt.normalize()
    rs_lookup = rs_all.set_index(["date", "ticker"])["rs_composite"].to_dict()

    lookback_start = (pd.to_datetime(start_date) - timedelta(days=400)).strftime("%Y-%m-%d")
    all_ohlcv = load_ohlcv_batch_memory(list(superset_tickers), lookback_start, end_date)
    
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
        logger.info("🧪 Pre-calculating Theme Indices for Variant E...")
        # 1. Agrupar tickers por tema
        theme_to_tickers = {}
        for t, themes in THEME_MAP.items():
            for theme in themes: theme_to_tickers.setdefault(theme, []).append(t)
        
        # 2. Calcular índices
        market_data_closes = pd.DataFrame({t: df["close"] for t, df in all_ohlcv.items() if t in superset_tickers})
        theme_indices = {}
        for theme, members in theme_to_tickers.items():
            idx = calculate_equal_weighted_index(market_data_closes, members)
            if not idx.empty: theme_indices[theme] = idx
        
        df_themes = pd.DataFrame(theme_indices)
        theme_sma20 = df_themes.rolling(20).mean()
        theme_dists = ((df_themes - theme_sma20) / theme_sma20)
        
        for t in THEME_MAP:
            t_themes = get_themes(t)
            theme_metrics_full[t] = {}
            for d in dates_str:
                dt = pd.Timestamp(d)
                best_dist = -999
                for th in t_themes:
                    if th in theme_dists.columns and dt in theme_dists.index:
                        d_val = theme_dists.loc[dt, th]
                        if d_val > best_dist: best_dist = d_val
                if best_dist != -999: theme_metrics_full[t][dt] = best_dist

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
            if t not in all_ohlcv or curr_dt not in all_ohlcv[t].index: continue
            r = all_ohlcv[t].loc[curr_dt]
            pos["days_held"] += 1
            
            exit_px, reason = None, None
            if r["open"] < pos["stop"]: exit_px, reason = r["open"], "STOP_GAP"
            elif r["low"] < pos["stop"]: exit_px, reason = pos["stop"], "STOP"
            
            if exit_px:
                px = exit_px * (1 - SLIPPAGE_BPS/10000)
                portfolio["cash"] += (px * pos["size"] - (px * pos["size"] * FEE_BPS/10000))
                pos["realized_pnl"] += (px - pos["entry_px"]) * pos["size"]
                pos["exit_reasons"].append(reason)
                closed.append(t)
                continue

            if not pos["tp1_hit"] and r["high"] >= pos["tp1"]:
                sz = int(pos["initial_size"] * 0.33)
                px = pos["tp1"] * (1 - SLIPPAGE_BPS/10000)
                portfolio["cash"] += (px * sz - (px * sz * FEE_BPS/10000))
                pos["realized_pnl"] += (px - pos["entry_px"]) * sz
                pos["size"], pos["tp1_hit"], pos["stop"] = pos["size"] - sz, True, pos["entry_px"]
                pos["exit_reasons"].append("TP1")

            if pos["tp1_hit"] and not pos["tp2_hit"] and r["high"] >= pos["tp2"]:
                sz = min(int(pos["initial_size"] * 0.33), pos["size"])
                px = pos["tp2"] * (1 - SLIPPAGE_BPS/10000)
                portfolio["cash"] += (px * sz - (px * sz * FEE_BPS/10000))
                pos["realized_pnl"] += (px - pos["entry_px"]) * sz
                pos["size"], pos["tp2_hit"] = pos["size"] - sz, True
                pos["exit_reasons"].append("TP2")

            if pos["days_held"] >= HOLDING_DAYS_LIMIT:
                px = r["close"] * (1 - SLIPPAGE_BPS/10000)
                portfolio["cash"] += (px * pos["size"] - (px * pos["size"] * FEE_BPS/10000))
                pos["realized_pnl"] += (px - pos["entry_px"]) * pos["size"]
                pos["exit_reasons"].append("EOD")
                closed.append(t)

        for t in closed:
            p = portfolio["positions"].pop(t)
            portfolio["sector_count"][p["sector"]] = max(0, portfolio["sector_count"].get(p["sector"], 0) - 1)
            all_trades.append({
                "symbol": t, "entry_date": p["entry_date"], "exit_date": d_str, "entry_price": p["entry_px"],
                "exit_price": p["last_close"], "pnl": p["realized_pnl"], 
                "return_pct": (p["realized_pnl"] / (p["entry_px"] * p["initial_size"])) * 100 if (p["entry_px"] * p["initial_size"]) > 0 else 0,
                "exit_phase": "+".join(p["exit_reasons"]), "entry_score": p["entry_score"]
            })

        for sig in pending_signals:
            t = sig.ticker
            if t not in all_ohlcv or curr_dt not in all_ohlcv[t].index: continue
            r = all_ohlcv[t].loc[curr_dt]
            sec = SECTOR_MAP.get(t, "UNKNOWN")
            if len(portfolio["positions"]) < MAX_POSITIONS and t not in portfolio["positions"] and \
               portfolio["sector_count"].get(sec, 0) < MAX_PER_SECTOR:
                entry_px = r["open"] * (1 + SLIPPAGE_BPS/10000)
                risk_amt = total_equity * RISK_PCT
                price_risk = entry_px - sig.stop_price
                if price_risk > 0:
                    shares = int(risk_amt / price_risk)
                    if shares > 0:
                        cost = shares * entry_px
                        if portfolio["cash"] >= (cost * 1.0001):
                            portfolio["cash"] -= (cost * 1.0001)
                            portfolio["sector_count"][sec] = portfolio["sector_count"].get(sec, 0) + 1
                            portfolio["positions"][t] = {
                                "size": shares, "initial_size": shares, "entry_px": entry_px, "stop": sig.stop_price,
                                "tp1": sig.tp1_price, "tp2": sig.tp2_price, "entry_date": d_str, "sector": sec,
                                "days_held": 0, "tp1_hit": False, "tp2_hit": False, "realized_pnl": 0, "exit_reasons": [],
                                "entry_score": sig.entry_score, "last_close": entry_px
                            }
        
        spy_slice = spy_full[spy_full.index <= curr_dt].tail(400)
        vix_slice = vix_full[vix_full.index <= curr_dt].tail(1)
        pending_signals = []
        if len(spy_slice) >= 200 and spy_slice.iloc[-1]["close"] > spy_slice["close"].rolling(200).mean().iloc[-1]:
            vix_ok = vix_slice["close"].iloc[0] < 35.0 if not vix_slice.empty else True
            if vix_ok:
                day_universe = universe_by_date.get(d_str, [])
                results_a, results_b = [], []
                for ticker in day_universe:
                    if ticker not in all_ohlcv: continue
                    ticker_df = all_ohlcv[ticker][all_ohlcv[ticker].index <= curr_dt]
                    if len(ticker_df) < 65: continue
                    rs_val = rs_lookup.get((curr_dt, ticker))
                    etf = SECTOR_MAP.get(ticker)
                    s_dist = etf_dists_full.get(etf, {}).get(curr_dt) if etf else None
                    t_dist = theme_metrics_full.get(ticker, {}).get(curr_dt)
                    
                    res_a = evaluate_ticker(ticker, ticker_df, spy_slice, cfg_a, rs_percentile=rs_val, scan_date=d_str, 
                                          sector_etf_dist=s_dist, theme_dist=t_dist)
                    if res_a.passed: results_a.append(res_a)
                    res_b = evaluate_ticker(ticker, ticker_df, spy_slice, cfg_b, rs_percentile=rs_val, scan_date=d_str, 
                                          sector_etf_dist=s_dist, theme_dist=t_dist)
                    if res_b.passed: results_b.append(res_b)
                pending_signals = merge_ab_signals(results_a, results_b)

    df_trades, df_equity = pd.DataFrame(all_trades), pd.DataFrame(equity_curve)
    df_trades.to_csv(OUTPUT_DIR / f"{tag}_trades.csv", index=False)
    df_equity.rename(columns={"equity": "0"}).to_csv(OUTPUT_DIR / f"{tag}_equity.csv", index=False)
    metrics = calculate_backtest_metrics(df_trades, df_equity)
    with open(OUTPUT_DIR / f"{tag}_metrics.json", "w") as f: json.dump(metrics, f, indent=2)
    logger.info(f"✅ DONE | Return: {metrics.get('total_return')}% | MDD: {metrics.get('max_drawdown')}% | Trades: {len(df_trades)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=100000)
    parser.add_argument("--universe-size", type=int, default=200)
    parser.add_argument("--tag", default="gold_standard_variant_e")
    parser.add_argument("--variant-e", action="store_true", help="Enable Thematic Divergence Filter")
    args = parser.parse_args()
    run_backtest(args.start, args.end, args.capital, args.universe_size, args.tag, use_variant_e=args.variant_e)
