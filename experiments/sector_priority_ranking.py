import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pit_universe import PointInTimeUniverse

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"

# Walk-Forward Periods
VALID_START = "2025-01-01"
VALID_END = "2026-04-30"

# Experiment Params - Hypothesis A v2.1
MAX_TRADES_PER_DAY = [3, 5, 10]

ETFS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC"]
GICS_TO_ETF = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def load_ticker_to_etf_map():
    if not SP500_CSV.exists():
        logger.warning(f"SP500 CSV not found at {SP500_CSV}.")
        return {}
    df = pd.read_csv(SP500_CSV)
    ticker_to_gics = dict(zip(df["Symbol"], df["GICS Sector"]))
    return {t: GICS_TO_ETF[s] for t, s in ticker_to_gics.items() if s in GICS_TO_ETF}

def compute_metrics(data, close_pivot, w):
    col = f"fwd_{w}d"
    valid_data = data[data[col].notna()].copy()
    if valid_data.empty:
        return {"trades": 0, "win_rate": 0.0, "pf": 0.0, "sharpe_r": 0.0}
    
    rets = valid_data[col]
    gains = rets[rets > 0].sum()
    losses = abs(rets[rets < 0].sum())
    pf = gains / losses if losses > 0 else (99.9 if gains > 0 else 0.0)
    wr = (rets > 0).mean() * 100
    
    # R-Multiples calculation
    entry_prices = np.array([close_pivot.at[d, t] for d, t in zip(valid_data["date"], valid_data["ticker"])])
    stop_dist = valid_data["stop_dist"].values
    stop_pcts = stop_dist / entry_prices
    
    valid_mask = (stop_pcts > 0)
    if not valid_mask.any():
        sharpe = 0.0
    else:
        r_multi = rets.values[valid_mask] / stop_pcts[valid_mask]
        if len(r_multi) < 2 or r_multi.std() == 0:
            sharpe = 0.0
        else:
            sharpe = (r_multi.mean() / r_multi.std()) * np.sqrt(252 / w)
            
    return {
        "trades": len(valid_data),
        "win_rate": round(float(wr), 2),
        "pf": round(float(pf), 3),
        "sharpe_r": round(float(sharpe), 3)
    }

def run_ranking_experiment():
    logger.info("🚀 Starting Sector Priority Ranking Experiment (Hypothesis A v2.1)")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    etf_start = (pd.to_datetime(VALID_START) - timedelta(days=60)).strftime("%Y-%m-%d")
    etf_prices = yf.download(ETFS, start=etf_start, end="2026-05-02", progress=False)["Close"]
    if isinstance(etf_prices.columns, pd.MultiIndex):
        etf_prices.columns = etf_prices.columns.get_level_values(0)
    etf_sma20 = etf_prices.rolling(20).mean()
    etf_dist = (etf_prices / etf_sma20) - 1

    pit = PointInTimeUniverse()
    ticker_to_etf = load_ticker_to_etf_map()
    
    conn = sqlite3.connect(DB_PATH)
    superset = pit.get_superset(VALID_START, VALID_END)
    buffer_start = (pd.to_datetime(VALID_START) - timedelta(days=60)).strftime("%Y-%m-%d")
    placeholders = ",".join(["?"] * len(superset))

    df_prices = pd.read_sql_query(
        f"SELECT ticker, date, close, dollar_volume, adr_pct_20 FROM ohlcv_cache "
        f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
        conn, params=superset + [buffer_start, VALID_END]
    )
    df_prices["date"] = pd.to_datetime(df_prices["date"], format="mixed").dt.normalize()
    df_prices["ticker"] = df_prices["ticker"].str.upper().str.strip()
    df_prices = df_prices.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")

    df_rs = pd.read_sql_query(
        "SELECT ticker, date, rs_composite FROM daily_rs_rankings WHERE date BETWEEN ? AND ?",
        conn, params=[VALID_START, VALID_END]
    )
    df_rs["date"] = pd.to_datetime(df_rs["date"], format="mixed").dt.normalize()
    df_rs["ticker"] = df_rs["ticker"].str.upper().str.strip()
    df_rs = df_rs.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    conn.close()

    # 2. Build Pivots & Signals
    close_pivot = df_prices.pivot(index="date", columns="ticker", values="close")
    dv_pivot = df_prices.pivot(index="date", columns="ticker", values="dollar_volume")
    adr_pivot = df_prices.pivot(index="date", columns="ticker", values="adr_pct_20")
    rs_pivot = df_rs.pivot(index="date", columns="ticker", values="rs_composite")

    is_breakout = close_pivot > close_pivot.shift(1).rolling(20).max()
    fwd_rets = {w: close_pivot.shift(-w) / close_pivot - 1 for w in [5, 10, 20]}
    stop_dist = adr_pivot * close_pivot / 100

    dates = pd.to_datetime(close_pivot.index)
    mask = pit.build_tradeable_mask(dates, list(close_pivot.columns))
    mask.index = close_pivot.index

    # 3. Generate Raw Signals
    raw_signals = []
    analysis_dates = close_pivot.index[(close_pivot.index >= pd.to_datetime(VALID_START)) & (close_pivot.index <= pd.to_datetime(VALID_END))]
    for d in analysis_dates:
        if d not in rs_pivot.index: continue
        rs_day = rs_pivot.loc[d]
        bo_day = is_breakout.loc[d]
        dv_day = dv_pivot.loc[d]
        mk_day = mask.loc[d]
        
        valid_tickers = rs_day[(rs_day > 58) & bo_day & (dv_day > 5_000_000) & mk_day].index
        for t in valid_tickers:
            etf = ticker_to_etf.get(t)
            if not etf or etf not in etf_dist.columns: continue
            try:
                dist = etf_dist.loc[d, etf]
            except KeyError: continue
            
            raw_signals.append({
                "date": d, "ticker": t,
                "rs_composite": rs_day[t],
                "etf_dist_sma20": dist,
                "fwd_5d": fwd_rets[5].loc[d, t],
                "fwd_10d": fwd_rets[10].loc[d, t],
                "fwd_20d": fwd_rets[20].loc[d, t],
                "stop_dist": stop_dist.loc[d, t]
            })
            
    df_raw = pd.DataFrame(raw_signals)
    
    # Base filter (Binary S1 Filter: ETF > SMA20)
    df_base = df_raw[df_raw["etf_dist_sma20"] > 0.0].copy()
    
    logger.info(f"Total Valid Signals (Post-S1 filter): {len(df_base)}")

    # 4. Evaluate Ranking Methods
    results = {}
    
    for max_n in MAX_TRADES_PER_DAY:
        logger.info(f"Evaluating limits: Max {max_n} trades per day")
        
        # Method 1: Baseline Tie-Breaker (RS Composite)
        df_baseline = df_base.sort_values(["date", "rs_composite"], ascending=[True, False]).groupby("date").head(max_n)
        metrics_baseline = {w: compute_metrics(df_baseline, close_pivot, w) for w in [5, 10, 20]}
        
        # Method 2: Sector Strength Tie-Breaker (A v2.1)
        df_sector_rank = df_base.sort_values(["date", "etf_dist_sma20"], ascending=[True, False]).groupby("date").head(max_n)
        metrics_sector = {w: compute_metrics(df_sector_rank, close_pivot, w) for w in [5, 10, 20]}
        
        results[max_n] = {
            "baseline": metrics_baseline,
            "sector_rank": metrics_sector,
            "delta_10d": round(metrics_sector[10]["sharpe_r"] - metrics_baseline[10]["sharpe_r"], 3),
            "delta_20d": round(metrics_sector[20]["sharpe_r"] - metrics_baseline[20]["sharpe_r"], 3)
        }
        
    # 5. Output
    print("\n" + "="*70)
    print("SECTOR PRIORITY RANKING RESULTS (Hypothesis A v2.1)")
    print("="*70)
    for max_n in MAX_TRADES_PER_DAY:
        res = results[max_n]
        print(f"--- MAX {max_n} TRADES PER DAY ---")
        print(f"{'Metric':<10} | {'RS Baseline':>12} | {'Sector Rank':>12} | {'Delta':>8}")
        for w in [5, 10, 20]:
            b_sh = res['baseline'][w]['sharpe_r']
            s_sh = res['sector_rank'][w]['sharpe_r']
            d_sh = s_sh - b_sh
            print(f"Sharpe {w:>2}d | {b_sh:>12.3f} | {s_sh:>12.3f} | {d_sh:>+8.3f}")
            
        print(f"PF 10d     | {res['baseline'][10]['pf']:>12.3f} | {res['sector_rank'][10]['pf']:>12.3f} |")
        print(f"Trades     | {res['baseline'][10]['trades']:>12} | {res['sector_rank'][10]['trades']:>12} |")
        print()

    # Decision Gate
    # A v2.1 passes if it materially improves Sharpe (>= +0.05) and PF in multiple buckets
    avg_delta_10d = np.mean([r["delta_10d"] for r in results.values()])
    avg_delta_20d = np.mean([r["delta_20d"] for r in results.values()])
    
    is_go = avg_delta_10d >= 0.05 and avg_delta_20d >= 0.05
    decision = "GO to A v2.2 (Defensive Cap Sandbox)" if is_go else "NO-GO (Keep Baseline RS Tie-breaker)"
    
    print("-" * 70)
    print(f"Avg Delta Sharpe 10d: {avg_delta_10d:+.3f}")
    print(f"Avg Delta Sharpe 20d: {avg_delta_20d:+.3f}")
    print(f"DECISION: {decision}")
    print("="*70 + "\n")
    
    report = {
        "experiment": "Sector Priority Ranking (A v2.1)",
        "period": [VALID_START, VALID_END],
        "results": results,
        "decision": decision,
        "timestamp": datetime.now().isoformat()
    }
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(OUTPUT_DIR / f"sector_priority_ranking_{ts}.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_ranking_experiment()
