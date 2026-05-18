
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

from src.signals.signal_engine import evaluate_ticker
from src.config.dynamic_config import load_production_config
from src.scanner.universe_loader import load_scan_universe
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

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

def run_backtest(start_date: str, end_date: str, initial_capital: float, universe_size: int, tag: str):
    logger.info(f"🚀 GOLD STANDARD BACKTEST (PIT) | Range: {start_date} -> {end_date}")
    dates_str = get_trading_dates(start_date, end_date)
    if not dates_str: return

    # --- FASE 1: PRE-CARGA FIDELITY ---
    logger.info("📦 Pre-loading Daily PIT Universes...")
    conn = sqlite3.connect(DB_PATH)
    
    rs_all = pd.read_sql(
        "SELECT date, ticker, rs_60d_pct, rs_composite FROM daily_rs_rankings WHERE date >= ? AND date <= ? || ' 23:59:59'",
        conn, params=(start_date, end_date)
    )
    rs_all["date"] = pd.to_datetime(rs_all["date"], format="mixed").dt.normalize()
    
    universe_daily = {}
    for d, group in rs_all.groupby("date"):
        universe_daily[d] = group.sort_values("rs_60d_pct", ascending=False).head(max(500, universe_size * 2))["ticker"].tolist()
    
    superset = sorted(list(set([t for univ in universe_daily.values() for t in univ])))
    logger.info(f"Fidelity Superset size: {len(superset)} tickers")
    
    rs_lookup = rs_all.set_index(["date", "ticker"])["rs_composite"].to_dict()

    spy_full = pd.read_sql("SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker='SPY' ORDER BY date", conn)
    spy_full["date"] = pd.to_datetime(spy_full["date"], format="mixed").dt.normalize()
    spy_full = spy_full.drop_duplicates(subset=["date"], keep="last").set_index("date")
    
    vix_full = pd.read_sql("SELECT date, close FROM ohlcv_cache WHERE ticker='^VIX' ORDER BY date", conn)
    vix_full["date"] = pd.to_datetime(vix_full["date"], format="mixed").dt.normalize()
    vix_full = vix_full.drop_duplicates(subset=["date"], keep="last").set_index("date")
    
    etf_ohlcv = load_ohlcv_batch_memory(SECTOR_ETFS, (pd.to_datetime(start_date) - timedelta(days=100)).strftime("%Y-%m-%d"), end_date)
    etf_dists = {} 
    for etf, df in etf_ohlcv.items():
        sma20 = df["close"].rolling(20).mean()
        etf_dists[etf] = ((df["close"] - sma20) / sma20 * 100).to_dict()

    lookback_start = (pd.to_datetime(start_date) - timedelta(days=350)).strftime("%Y-%m-%d")
    all_ohlcv = load_ohlcv_batch_memory(superset, lookback_start, end_date)
    conn.close()

    # --- FASE 2: LOOP ---
    portfolio = {"cash": initial_capital, "positions": {}, "sector_count": {}}
    all_trades, equity_curve, pending_signals = [], [], []
    combo_cfg = load_production_config()

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
            if r["open"] < pos["stop"]: 
                exit_px, reason = r["open"], "STOP_GAP"
            elif r["low"] < pos["stop"]: 
                exit_px, reason = pos["stop"], "STOP"
            
            if exit_px:
                px = exit_px * (1 - SLIPPAGE_BPS/10000)
                fee = px * pos["size"] * (FEE_BPS/10000)
                portfolio["cash"] += (px * pos["size"] - fee)
                pos["realized_pnl"] += (px - pos["entry_px"]) * pos["size"] - fee
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
            t = sig["ticker"]
            if t not in all_ohlcv or curr_dt not in all_ohlcv[t].index: continue
            r = all_ohlcv[t].loc[curr_dt]
            sec = SECTOR_MAP.get(t, "UNKNOWN")
            
            if len(portfolio["positions"]) < MAX_POSITIONS and t not in portfolio["positions"] and \
               portfolio["sector_count"].get(sec, 0) < MAX_PER_SECTOR:
                entry_px = r["open"] * (1 + SLIPPAGE_BPS/10000)
                risk_amt = total_equity * RISK_PCT
                price_risk = entry_px - sig["stop_price"]
                if price_risk > 0:
                    shares = int(risk_amt / price_risk)
                    if shares > 0:
                        cost = shares * entry_px
                        fee = cost * (FEE_BPS/10000)
                        if portfolio["cash"] >= (cost + fee):
                            portfolio["cash"] -= (cost + fee)
                            portfolio["sector_count"][sec] = portfolio["sector_count"].get(sec, 0) + 1
                            portfolio["positions"][t] = {
                                "size": shares, "initial_size": shares, "entry_px": entry_px, "stop": sig["stop_price"],
                                "tp1": sig["tp1_price"], "tp2": sig["tp2_price"], "entry_date": d_str, "sector": sec,
                                "days_held": 0, "tp1_hit": False, "tp2_hit": False, "realized_pnl": 0, "exit_reasons": [],
                                "entry_score": sig["entry_score"], "last_close": entry_px
                            }
        
        spy_slice = spy_full[spy_full.index <= curr_dt].tail(400)
        vix_slice = vix_full[vix_full.index <= curr_dt].tail(1)
        
        pending_signals = []
        if len(spy_slice) >= 200 and spy_slice.iloc[-1]["close"] > spy_slice["close"].rolling(200).mean().iloc[-1]:
            vix_ok = vix_slice["close"].iloc[0] < 35.0 if not vix_slice.empty else True
            if vix_ok:
                day_universe = universe_daily.get(curr_dt, [])
                for ticker in day_universe:
                    if ticker not in all_ohlcv: continue
                    ticker_df = all_ohlcv[ticker][all_ohlcv[ticker].index <= curr_dt]
                    if len(ticker_df) < 65: continue
                    rs_val = rs_lookup.get((curr_dt, ticker))
                    etf = SECTOR_MAP.get(ticker)
                    s_dist = etf_dists.get(etf, {}).get(curr_dt) if etf else None
                    res = evaluate_ticker(ticker, ticker_df, spy_slice, combo_cfg, 
                                          rs_percentile=rs_val, scan_date=d_str, 
                                          sector_etf_dist=s_dist)
                    if res.passed:
                        pending_signals.append({
                            "ticker": res.ticker, "stop_price": res.stop_price, "tp1_price": res.tp1_price, 
                            "tp2_price": res.tp2_price, "entry_score": res.entry_score
                        })
                pending_signals = sorted(pending_signals, key=lambda x: x["entry_score"], reverse=True)[:universe_size]

    df_trades, df_equity = pd.DataFrame(all_trades), pd.DataFrame(equity_curve)
    # Save first to ensure data recovery
    df_trades.to_csv(OUTPUT_DIR / "complete_trades_clean.csv", index=False)
    df_equity.rename(columns={"equity": "0"}).to_csv(OUTPUT_DIR / "equity_curve.csv", index=False)
    
    metrics = calculate_backtest_metrics(df_trades, df_equity)
    with open(OUTPUT_DIR / "backtest_metrics.json", "w") as f: json.dump(metrics, f, indent=2)
    logger.info(f"✅ DONE | Return: {metrics.get('total_return')}% | MDD: {metrics.get('max_drawdown')}% | Trades: {len(df_trades)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=100000)
    parser.add_argument("--universe-size", type=int, default=100)
    parser.add_argument("--tag", default="gold_standard_v2")
    args = parser.parse_args()
    run_backtest(args.start, args.end, args.capital, args.universe_size, args.tag)
