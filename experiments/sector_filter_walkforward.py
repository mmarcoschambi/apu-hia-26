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
TRAIN_START = "2025-01-01"
TRAIN_END = "2025-09-30"
VALID_START = "2025-10-01"
VALID_END = "2026-04-30"

# Experiment Params
THRESHOLDS = [0.0, 0.005, 0.01, 0.015, 0.02, 0.03]
GATE_DELTA = 0.10
GATE_WINDOWS = [10, 20]

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

def slice_period(df, start, end):
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    return df[(df["date"] >= s) & (df["date"] <= e)].copy()

def run_walk_forward():
    logger.info("🚀 Starting Sector Filter Walk-Forward Validation")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    etf_start = (pd.to_datetime(TRAIN_START) - timedelta(days=100)).strftime("%Y-%m-%d")
    etf_prices = yf.download(ETFS, start=etf_start, end="2026-05-02", progress=False)["Close"]
    if isinstance(etf_prices.columns, pd.MultiIndex):
        etf_prices.columns = etf_prices.columns.get_level_values(0)
    etf_sma20 = etf_prices.rolling(20).mean()
    etf_dist = (etf_prices / etf_sma20) - 1

    pit = PointInTimeUniverse()
    ticker_to_etf = load_ticker_to_etf_map()
    
    conn = sqlite3.connect(DB_PATH)
    superset = pit.get_superset(TRAIN_START, VALID_END)
    buffer_start = (pd.to_datetime(TRAIN_START) - timedelta(days=60)).strftime("%Y-%m-%d")
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
        conn, params=[TRAIN_START, VALID_END]
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

    # 3. Generate Raw Signals (Unified)
    raw_signals = []
    analysis_dates = close_pivot.index[close_pivot.index >= pd.to_datetime(TRAIN_START)]
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
                "date": d, "ticker": t, "etf_dist_sma20": dist,
                "fwd_5d": fwd_rets[5].loc[d, t],
                "fwd_10d": fwd_rets[10].loc[d, t],
                "fwd_20d": fwd_rets[20].loc[d, t],
                "stop_dist": stop_dist.loc[d, t]
            })
    df_raw = pd.DataFrame(raw_signals)

    # 4. TRAIN PHASE
    logger.info(f"--- TRAIN PHASE ({TRAIN_START} to {TRAIN_END}) ---")
    df_train_base = slice_period(df_raw, TRAIN_START, TRAIN_END)
    baseline_train = {w: compute_metrics(df_train_base, close_pivot, w) for w in [5, 10, 20]}
    
    train_results = []
    for th in THRESHOLDS:
        df_th = df_train_base[df_train_base["etf_dist_sma20"] > th]
        metrics = {w: compute_metrics(df_th, close_pivot, w) for w in [5, 10, 20]}
        train_results.append({
            "threshold": th,
            "threshold_pct": th * 100,
            "count": len(df_th),
            "sharpe_10d": metrics[10]["sharpe_r"],
            "sharpe_20d": metrics[20]["sharpe_r"],
            "delta_10d": round(metrics[10]["sharpe_r"] - baseline_train[10]["sharpe_r"], 3),
            "delta_20d": round(metrics[20]["sharpe_r"] - baseline_train[20]["sharpe_r"], 3)
        })
    
    df_train_res = pd.DataFrame(train_results)
    # Selection rule: max delta_10d, then delta_20d, then count, then lower threshold
    train_ranked = df_train_res.sort_values(
        by=["delta_10d", "delta_20d", "count", "threshold_pct"],
        ascending=[False, False, False, True]
    ).reset_index(drop=True)
    
    winner = train_ranked.iloc[0]
    best_th = winner["threshold"]
    logger.info(f"Selected Threshold: {best_th:.1%}")

    # 5. VALIDATION PHASE (OOS)
    logger.info(f"--- VALIDATION PHASE ({VALID_START} to {VALID_END}) ---")
    df_valid_base = slice_period(df_raw, VALID_START, VALID_END)
    baseline_valid = {w: compute_metrics(df_valid_base, close_pivot, w) for w in [5, 10, 20]}
    
    df_valid_filtered = df_valid_base[df_valid_base["etf_dist_sma20"] > best_th]
    filtered_valid = {w: compute_metrics(df_valid_filtered, close_pivot, w) for w in [5, 10, 20]}
    
    deltas = {w: round(filtered_valid[w]["sharpe_r"] - baseline_valid[w]["sharpe_r"], 3) for w in [5, 10, 20]}
    
    # Decision Gate
    is_go = deltas[10] >= GATE_DELTA and deltas[20] >= GATE_DELTA
    decision = "GO" if is_go else "NO-GO"

    # 6. Report & Output
    report = {
        "experiment": "Sector Filter Walk-Forward Validation",
        "train_period": [TRAIN_START, TRAIN_END],
        "validation_period": [VALID_START, VALID_END],
        "threshold_grid": THRESHOLDS,
        "selected_threshold": best_th,
        "train_results": train_results,
        "validation": {
            "baseline": baseline_valid,
            "filtered": filtered_valid,
            "delta": deltas
        },
        "gate": f"GO if delta_10d >= {GATE_DELTA} and delta_20d >= {GATE_DELTA} in validation",
        "decision": decision,
        "timestamp": datetime.now().isoformat()
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(OUTPUT_DIR / f"sector_filter_walkforward_{ts}.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "="*60)
    print("WALK-FORWARD VALIDATION RESULTS")
    print("="*60)
    print("TRAIN RANKING (Top 3):")
    print(train_ranked[["threshold_pct", "count", "delta_10d", "delta_20d"]].head(3))
    print(f"\nSELECTED THRESHOLD: {best_th:.1%}")
    print("-" * 60)
    print(f"VALIDATION ({VALID_START} to {VALID_END})")
    print(f"{'Metric':<10} | {'Baseline':>10} | {'Filtered':>10} | {'Delta':>10}")
    for w in [5, 10, 20]:
        b_sh = baseline_valid[w]['sharpe_r']
        f_sh = filtered_valid[w]['sharpe_r']
        d_sh = deltas[w]
        print(f"Sharpe {w:>2}d | {b_sh:>10.3f} | {f_sh:>10.3f} | {d_sh:>+10.3f}")
    print("-" * 60)
    print(f"DECISION: {decision}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_walk_forward()
