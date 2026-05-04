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

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"
START_DATE = "2025-01-01"
END_DATE = "2026-04-30"

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

# Sweep thresholds: Distance from ETF Close to SMA20 (e.g. 0.01 = 1% above SMA20)
THRESHOLDS = [0.0, 0.005, 0.01, 0.015, 0.02, 0.03]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_ticker_to_etf_map():
    if not SP500_CSV.exists():
        logger.warning(f"SP500 CSV not found at {SP500_CSV}.")
        return {}
    df = pd.read_csv(SP500_CSV)
    ticker_to_gics = dict(zip(df["Symbol"], df["GICS Sector"]))
    return {t: GICS_TO_ETF[s] for t, s in ticker_to_gics.items() if s in GICS_TO_ETF}


def get_forward_returns(price_df, windows=[5, 10, 20]):
    return {w: price_df.shift(-w) / price_df - 1 for w in windows}


def compute_metrics(group_df, close_pivot, w):
    col = f"fwd_{w}d"
    data = group_df[group_df[col].notna()].copy()
    if data.empty:
        return None
    rets = data[col]
    gains = rets[rets > 0].sum()
    losses = abs(rets[rets < 0].sum())
    pf = gains / losses if losses > 0 else (99.9 if gains > 0 else 0.0)
    wr = (rets > 0).mean() * 100
    entry_prices = np.array([close_pivot.at[d, t] for d, t in zip(data["date"], data["ticker"])])
    stop_pcts = data["stop_dist"].values / entry_prices
    valid = stop_pcts > 0
    r_multi = rets.values[valid] / stop_pcts[valid]
    if len(r_multi) < 2 or r_multi.std() == 0:
        sharpe = 0.0
    else:
        sharpe = (r_multi.mean() / r_multi.std()) * np.sqrt(252 / w)
    return {
        "trades": len(data),
        "win_rate": round(float(wr), 2),
        "pf": round(float(pf), 3),
        "sharpe_r": round(float(sharpe), 3),
        "median_ret_pct": round(float(rets.median() * 100), 2),
        "mean_ret_pct": round(float(rets.mean() * 100), 2),
    }


def run_sweep():
    logger.info(f"Starting Sector Threshold Sweep — Thresh: {THRESHOLDS}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    etf_start = (pd.to_datetime(START_DATE) - timedelta(days=100)).strftime("%Y-%m-%d")
    logger.info("Downloading ETF data...")
    etf_prices = yf.download(ETFS, start=etf_start, end="2026-05-02", progress=False)["Close"]
    if isinstance(etf_prices.columns, pd.MultiIndex):
        etf_prices.columns = etf_prices.columns.get_level_values(0)
    etf_sma20 = etf_prices.rolling(20).mean()
    etf_dist = (etf_prices / etf_sma20) - 1

    pit = PointInTimeUniverse()
    ticker_to_etf = load_ticker_to_etf_map()
    conn = sqlite3.connect(DB_PATH)
    superset = pit.get_superset(START_DATE, END_DATE)

    buffer_start = (pd.to_datetime(START_DATE) - timedelta(days=60)).strftime("%Y-%m-%d")
    placeholders = ",".join(["?"] * len(superset))

    df_prices = pd.read_sql_query(
        f"SELECT ticker, date, close, dollar_volume, adr_pct_20 FROM ohlcv_cache"
        f" WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
        conn, params=superset + [buffer_start, END_DATE],
    )
    df_prices["date"] = pd.to_datetime(df_prices["date"], format="mixed").dt.normalize()
    df_prices["ticker"] = df_prices["ticker"].str.upper().str.strip()
    df_prices = df_prices.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")

    df_rs = pd.read_sql_query(
        "SELECT ticker, date, rs_composite FROM daily_rs_rankings WHERE date BETWEEN ? AND ?",
        conn, params=[START_DATE, END_DATE],
    )
    df_rs["date"] = pd.to_datetime(df_rs["date"], format="mixed").dt.normalize()
    df_rs["ticker"] = df_rs["ticker"].str.upper().str.strip()
    conn.close()

    close_pivot = df_prices.pivot(index="date", columns="ticker", values="close")
    dv_pivot = df_prices.pivot(index="date", columns="ticker", values="dollar_volume")
    adr_pivot = df_prices.pivot(index="date", columns="ticker", values="adr_pct_20")
    rs_pivot = df_rs.pivot(index="date", columns="ticker", values="rs_composite")

    rolling_max_20 = close_pivot.shift(1).rolling(20).max()
    is_breakout = close_pivot > rolling_max_20
    fwd_rets = get_forward_returns(close_pivot)
    stop_dist = adr_pivot * close_pivot / 100

    dates = pd.to_datetime(close_pivot.index, format="mixed")
    mask = pit.build_tradeable_mask(dates, list(close_pivot.columns))
    mask.index = close_pivot.index

    start_dt = pd.to_datetime(START_DATE)
    analysis_dates = close_pivot.index[close_pivot.index >= start_dt]
    
    # 1. First, build all potential signals without filter
    all_raw_signals = []
    for date in analysis_dates:
        if date not in rs_pivot.index: continue
        rs_day = rs_pivot.loc[date]
        breakout_day = is_breakout.loc[date]
        dv_day = dv_pivot.loc[date]
        mask_day = mask.loc[date]
        valid = rs_day[(rs_day > 58) & breakout_day & (dv_day > 5_000_000) & mask_day].index
        for ticker in valid:
            etf = ticker_to_etf.get(ticker)
            if not etf or etf not in etf_dist.columns: continue
            try:
                dist = etf_dist.loc[date, etf]
            except KeyError: continue
            
            all_raw_signals.append({
                "date": date,
                "ticker": ticker,
                "sector_etf": etf,
                "etf_dist_sma20": dist,
                "fwd_5d": fwd_rets[5].loc[date, ticker],
                "fwd_10d": fwd_rets[10].loc[date, ticker],
                "fwd_20d": fwd_rets[20].loc[date, ticker],
                "stop_dist": stop_dist.loc[date, ticker],
            })
    
    df_raw = pd.DataFrame(all_raw_signals)
    
    # 2. Compute Baseline (All signals)
    baseline_metrics = {}
    for w in [5, 10, 20]:
        baseline_metrics[f"metrics_{w}d"] = compute_metrics(df_raw, close_pivot, w)
    
    sweep_results = []
    
    # 3. Sweep Thresholds
    for thresh in THRESHOLDS:
        filtered_df = df_raw[df_raw["etf_dist_sma20"] > thresh].copy()
        
        row = {"threshold_pct": thresh * 100, "count": len(filtered_df)}
        for w in [5, 10, 20]:
            m = compute_metrics(filtered_df, close_pivot, w)
            if m:
                row[f"sharpe_{w}d"] = m["sharpe_r"]
                row[f"wr_{w}d"] = m["win_rate"]
                # Delta vs baseline
                row[f"delta_{w}d"] = round(m["sharpe_r"] - baseline_metrics[f"metrics_{w}d"]["sharpe_r"], 3)
        sweep_results.append(row)

    df_sweep = pd.DataFrame(sweep_results)
    
    report = {
        "experiment": "Sector Filter Threshold Sweep — ETF Dist SMA20",
        "baseline_sharpe": {w: baseline_metrics[f"metrics_{w}d"]["sharpe_r"] for w in [5, 10, 20]},
        "sweep": sweep_results,
        "timestamp": datetime.now().isoformat(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"sector_filter_sweep_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    print("\n" + "="*80)
    print("SECTOR FILTER THRESHOLD SWEEP (Delta Sharpe vs Baseline)")
    print("="*80)
    print(f"Baseline Sharpes: 5d={report['baseline_sharpe'][5]:.3f} | 10d={report['baseline_sharpe'][10]:.3f} | 20d={report['baseline_sharpe'][20]:.3f}")
    print("-"*80)
    print(f"{'Thresh (%)':>10} | {'Trades':>6} | {'Delta 5d':>10} | {'Delta 10d':>10} | {'Delta 20d':>10}")
    print("-"*80)
    for res in sweep_results:
        print(f"{res['threshold_pct']:>9.1f}% | {res['count']:>6} | {res.get('delta_5d', 0.0):>+10.3f} | {res.get('delta_10d', 0.0):>+10.3f} | {res.get('delta_20d', 0.0):>+10.3f}")
    print("="*80)
    print("PROTOCOLO:")
    print("  GO if Delta 10d >= +0.10 AND Delta 20d >= +0.10 for ANY threshold.")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_sweep()
