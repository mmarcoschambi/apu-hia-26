import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import sys

# Setup Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pit_universe import PointInTimeUniverse

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"

# Research Period
START_DATE = "2025-01-01"
END_DATE = "2026-04-30"

# Train/Validation Split
TRAIN_END = "2025-09-30"
VALID_START = "2025-10-01"

# Risk Config
BASE_RISK_DOLLARS = 1000.0

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

def sector_risk_multiplier(dist: float) -> float:
    if pd.isna(dist):
        return 0.50
    if dist <= 0.00:
        return 0.50
    if dist <= 0.01:
        return 0.75
    if dist <= 0.02:
        return 1.00
    if dist <= 0.03:
        return 1.25
    return 1.10

def generate_dataset():
    logger.info("🚀 Starting Sector Strength Sizing Dataset Generation")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    etf_start = (pd.to_datetime(START_DATE) - timedelta(days=100)).strftime("%Y-%m-%d")
    logger.info(f"Downloading ETF data from {etf_start}...")
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

    logger.info(f"Loading OHLCV data for {len(superset)} tickers...")
    df_prices = pd.read_sql_query(
        f"SELECT ticker, date, close, dollar_volume, adr_pct_20 FROM ohlcv_cache "
        f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
        conn, params=superset + [buffer_start, END_DATE]
    )
    df_prices["date"] = pd.to_datetime(df_prices["date"], format="mixed").dt.normalize()
    df_prices["ticker"] = df_prices["ticker"].str.upper().str.strip()
    df_prices = df_prices.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")

    logger.info("Loading RS rankings...")
    df_rs = pd.read_sql_query(
        "SELECT ticker, date, rs_composite FROM daily_rs_rankings WHERE date BETWEEN ? AND ?",
        conn, params=[START_DATE, END_DATE]
    )
    df_rs["date"] = pd.to_datetime(df_rs["date"], format="mixed").dt.normalize()
    df_rs["ticker"] = df_rs["ticker"].str.upper().str.strip()
    df_rs = df_rs.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    conn.close()

    # 2. Build Pivots & Signals
    logger.info("Building pivots and signal masks...")
    close_pivot = df_prices.pivot(index="date", columns="ticker", values="close")
    dv_pivot = df_prices.pivot(index="date", columns="ticker", values="dollar_volume")
    adr_pivot = df_prices.pivot(index="date", columns="ticker", values="adr_pct_20")
    rs_pivot = df_rs.pivot(index="date", columns="ticker", values="rs_composite")

    is_breakout = close_pivot > close_pivot.shift(1).rolling(20).max()
    fwd_rets = {w: close_pivot.shift(-w) / close_pivot - 1 for w in [5, 10, 20]}
    stop_dist_pivot = adr_pivot * close_pivot / 100

    dates = pd.to_datetime(close_pivot.index)
    mask = pit.build_tradeable_mask(dates, list(close_pivot.columns))
    mask.index = close_pivot.index

    # 3. Generate Raw Signals
    logger.info("Generating signals...")
    raw_signals = []
    analysis_dates = close_pivot.index[close_pivot.index >= pd.to_datetime(START_DATE)]
    for d in analysis_dates:
        if d not in rs_pivot.index: continue
        rs_day = rs_pivot.loc[d]
        bo_day = is_breakout.loc[d]
        dv_day = dv_pivot.loc[d]
        mk_day = mask.loc[d]
        
        # Setup definition: rs > 58, breakout, dv > 5M, tradeable
        valid_tickers = rs_day[(rs_day > 58) & bo_day & (dv_day > 5_000_000) & mk_day].index
        for t in valid_tickers:
            etf = ticker_to_etf.get(t)
            if not etf or etf not in etf_dist.columns: continue
            try:
                dist = etf_dist.loc[d, etf]
            except KeyError: continue
            
            raw_signals.append({
                "date": d,
                "ticker": t,
                "sector_etf": etf,
                "etf_dist_sma20": dist,
                "entry_price": close_pivot.loc[d, t],
                "stop_dist": stop_dist_pivot.loc[d, t],
                "stop_pct": adr_pivot.loc[d, t] / 100,
                "rs_composite": rs_pivot.loc[d, t],
                "dollar_volume": dv_pivot.loc[d, t],
                "adr_pct_20": adr_pivot.loc[d, t],
                "fwd_5d": fwd_rets[5].loc[d, t],
                "fwd_10d": fwd_rets[10].loc[d, t],
                "fwd_20d": fwd_rets[20].loc[d, t],
            })
    
    df = pd.DataFrame(raw_signals)
    if df.empty:
        logger.error("No signals generated. Check data sources.")
        return

    # 4. Data Cleaning
    initial_count = len(df)
    df = df[df["stop_dist"] > 0].copy()
    dropped = initial_count - len(df)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} signals with invalid stop_dist (<= 0 or NaN)")

    if df.empty:
        logger.error("No valid signals left after cleaning.")
        return

    # 5. Feature Engineering: Intensity
    logger.info("Adding sector strength features...")
    df["sector_strength_raw"] = df["etf_dist_sma20"]
    df["sector_strength_clipped"] = df["etf_dist_sma20"].clip(lower=0.0, upper=0.05)
    df["sector_strength_bucket"] = pd.cut(
        df["etf_dist_sma20"],
        bins=[-999, 0.0, 0.01, 0.02, 0.03, 999],
        labels=["weak", "low", "mid", "high", "extreme"]
    )

    # 5. Sizing Simulation
    logger.info("Simulating sizing...")
    df["risk_dollars_base"] = BASE_RISK_DOLLARS
    df["shares_base"] = (df["risk_dollars_base"] / df["stop_dist"]).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    df["risk_multiplier_candidate"] = df["etf_dist_sma20"].apply(sector_risk_multiplier)
    df["risk_dollars_adj"] = df["risk_dollars_base"] * df["risk_multiplier_candidate"]
    df["shares_adj"] = (df["risk_dollars_adj"] / df["stop_dist"]).replace([np.inf, -np.inf], 0).fillna(0).astype(int)

    # 6. PnL / R-Multiples
    logger.info("Calculating PnL and R-multiples...")
    for w in [5, 10, 20]:
        # R-multiple: returns / stop_pct (risk taken)
        df[f"r_{w}d"] = df[f"fwd_{w}d"] / df["stop_pct"]
        # PnL: shares * entry * return
        df[f"pnl_base_{w}d"] = df["shares_base"] * df["entry_price"] * df[f"fwd_{w}d"]
        df[f"pnl_adj_{w}d"] = df["shares_adj"] * df["entry_price"] * df[f"fwd_{w}d"]

    # 7. Quality Checks
    logger.info("Running quality checks...")
    assert not df["sector_etf"].isna().all(), "All sector_etf are null"
    assert (df["stop_dist"] > 0).all(), "Some stop_dist <= 0"
    assert (df["shares_base"] >= 0).all(), "Negative base shares"
    assert (df["shares_adj"] >= 0).all(), "Negative adj shares"
    assert (df["risk_dollars_adj"] >= df["risk_dollars_base"] * 0.499).all(), "Risk adj too low"
    assert (df["risk_dollars_adj"] <= df["risk_dollars_base"] * 1.251).all(), "Risk adj too high"

    # Save dataset
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_path = OUTPUT_DIR / f"sector_strength_sizing_dataset_{ts}.parquet"
    df.to_parquet(dataset_path)
    logger.info(f"Dataset saved to {dataset_path}")

    # 8. Reports
    generate_reports(df, ts)

def compute_sharpe_r(r_series, window):
    if len(r_series) < 2 or r_series.std() == 0:
        return 0.0
    return (r_series.mean() / r_series.std()) * np.sqrt(252 / window)

def generate_reports(df, ts):
    logger.info("Generating summary reports...")
    
    # Bucket Analysis (Monotonicity)
    bucket_stats = []
    for bucket in ["weak", "low", "mid", "high", "extreme"]:
        b_df = df[df["sector_strength_bucket"] == bucket]
        stats = {"bucket": bucket, "count": len(b_df)}
        if len(b_df) > 0:
            for w in [5, 10, 20]:
                stats[f"mean_fwd_{w}d"] = round(float(b_df[f"fwd_{w}d"].mean()), 5)
                stats[f"sharpe_r_{w}d"] = round(compute_sharpe_r(b_df[f"r_{w}d"], w), 3)
        bucket_stats.append(stats)
    
    df_buckets = pd.DataFrame(bucket_stats)
    buckets_path = OUTPUT_DIR / f"sector_strength_sizing_buckets_{ts}.csv"
    df_buckets.to_csv(buckets_path, index=False)
    logger.info(f"Buckets report saved to {buckets_path}")

    # Sizing Comparison
    def summarize_sizing(sub_df, label):
        results = {"period": label, "trades": len(sub_df)}
        for suffix in ["base", "adj"]:
            pnl_col = f"pnl_{suffix}_20d"
            r_col = f"r_20d" # Note: R is independent of sizing multiplier if we look at R per trade, 
                           # but we want to see weighted R or total PnL impact.
                           # Actually sharpe_r is also same for base/adj if multiplier is constant per bucket,
                           # but if we aggregate across buckets it changes.
            
            # Weighted average return or just sum PnL
            results[f"gross_pnl_{suffix}"] = round(float(sub_df[pnl_col].sum()), 2)
            
            # Sharpe R of the aggregate strategy
            # We need to compute daily PnL to get true Sharpe, but here we can use trade R-multiples weighted by sizing multiplier
            weighted_r = sub_df["r_20d"] * (sub_df[f"risk_dollars_{suffix}"] / BASE_RISK_DOLLARS)
            results[f"sharpe_r_{suffix}"] = round(compute_sharpe_r(weighted_r, 20), 3)

        results["avg_risk_multiplier"] = round(float(sub_df["risk_multiplier_candidate"].mean()), 3)
        results["profit_factor_adj"] = round(
            sub_df[sub_df["pnl_adj_20d"] > 0]["pnl_adj_20d"].sum() / 
            abs(sub_df[sub_df["pnl_adj_20d"] < 0]["pnl_adj_20d"].sum()) 
            if sub_df[sub_df["pnl_adj_20d"] < 0]["pnl_adj_20d"].sum() != 0 else 0, 2
        )
        return results

    comparison = [
        summarize_sizing(df, "full_sample"),
        summarize_sizing(df[df["date"] <= pd.to_datetime(TRAIN_END)], "train"),
        summarize_sizing(df[df["date"] >= pd.to_datetime(VALID_START)], "validation")
    ]
    
    comp_path = OUTPUT_DIR / f"sector_strength_sizing_comparison_{ts}.json"
    with open(comp_path, "w") as f:
        json.dump(comparison, f, indent=2)
    logger.info(f"Comparison report saved to {comp_path}")

    # Descriptive Summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_signals": len(df),
        "buckets": bucket_stats,
        "sizing_comparison": comparison
    }
    summary_path = OUTPUT_DIR / f"sector_strength_sizing_summary_{ts}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    print("\n" + "="*60)
    print("SECTOR STRENGTH SIZING RESEARCH SUMMARY")
    print("="*60)
    print(df_buckets)
    print("-" * 60)
    print(f"VALIDATION COMPARISON:")
    valid_comp = comparison[2]
    print(f"Base PnL: ${valid_comp['gross_pnl_base']:,.2f}")
    print(f"Adj PnL:  ${valid_comp['gross_pnl_adj']:,.2f}")
    print(f"Sharpe R (Base): {valid_comp['sharpe_r_base']}")
    print(f"Sharpe R (Adj):  {valid_comp['sharpe_r_adj']}")
    print(f"Avg Multiplier:  {valid_comp['avg_risk_multiplier']}")
    print("="*60 + "\n")

if __name__ == "__main__":
    generate_dataset()
