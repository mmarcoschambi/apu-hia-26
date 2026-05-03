import os
import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pit_universe import PointInTimeUniverse

# Configuration
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"
START_DATE = "2025-01-01"
END_DATE = "2026-04-30"

ETFS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC"]

GICS_TO_ETF = {
    'Information Technology': 'XLK',
    'Financials': 'XLF',
    'Health Care': 'XLV',
    'Energy': 'XLE',
    'Consumer Discretionary': 'XLY',
    'Consumer Staples': 'XLP',
    'Industrials': 'XLI',
    'Materials': 'XLB',
    'Real Estate': 'XLRE',
    'Utilities': 'XLU',
    'Communication Services': 'XLC'
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def load_ticker_to_etf_map():
    """Maps tickers to their corresponding sector ETF using GICS sectors."""
    if not SP500_CSV.exists():
        logger.warning(f"S&P 500 CSV not found at {SP500_CSV}. Using fallback map.")
        return {}
    
    df = pd.read_csv(SP500_CSV)
    # Map Symbol to GICS Sector
    ticker_to_gics = dict(zip(df['Symbol'], df['GICS Sector']))
    
    ticker_to_etf = {}
    for ticker, sector in ticker_to_gics.items():
        etf = GICS_TO_ETF.get(sector)
        if etf:
            ticker_to_etf[ticker] = etf
            
    return ticker_to_etf

def get_forward_returns(price_df, windows=[5, 10, 20]):
    """Calculates forward returns for specified windows."""
    returns = {}
    for w in windows:
        # shifted_price = price_df.shift(-w)
        # returns[w] = (shifted_price / price_df) - 1
        # More precise: for each date T, get price at T+w
        # Since we use business days, shift(-w) works if the index is continuous business days
        returns[w] = price_df.shift(-w) / price_df - 1
    return returns

def run_experiment():
    logger.info("🚀 Starting Rotation Leaders Experiment")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Load ETF Data
    logger.info("📊 Downloading ETF data...")
    # Buffer to calculate SMA20 at the start
    etf_start = (pd.to_datetime(START_DATE) - timedelta(days=100)).strftime("%Y-%m-%d")
    etf_prices = yf.download(ETFS, start=etf_start, end="2026-05-02", progress=False)["Close"]
    
    # Fix yfinance MultiIndex columns if necessary
    if isinstance(etf_prices.columns, pd.MultiIndex):
        etf_prices.columns = etf_prices.columns.get_level_values(0)
        
    etf_sma20 = etf_prices.rolling(20).mean()
    etf_sma50 = etf_prices.rolling(50).mean()
    
    # 2. Prepare Universe and Ticker Data
    pit = PointInTimeUniverse()
    ticker_to_etf = load_ticker_to_etf_map()
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get superset of tickers to load data efficiently
    superset = pit.get_superset(START_DATE, END_DATE)
    logger.info(f"Superset of tickers: {len(superset)}")
    
    # Load Price, Vol, and RS data in bulk
    logger.info("📥 Loading price and RS data from DB...")
    placeholders = ",".join(["?"] * len(superset))
    
    # Use a slightly earlier start for breakout/SMA calculations
    buffer_start = (pd.to_datetime(START_DATE) - timedelta(days=60)).strftime("%Y-%m-%d")
    
    price_query = f"""
        SELECT ticker, date, close, dollar_volume, adr_pct_20
        FROM ohlcv_cache
        WHERE ticker IN ({placeholders})
          AND date BETWEEN ? AND ?
        ORDER BY ticker, date
    """
    df_prices = pd.read_sql_query(price_query, conn, params=superset + [buffer_start, END_DATE])
    # Convert to datetime and normalize to midnight to avoid format-based duplicates
    df_prices['date'] = pd.to_datetime(df_prices['date'], format='mixed').dt.normalize()
    # Normalize tickers
    df_prices['ticker'] = df_prices['ticker'].str.upper().str.strip()
    
    # Deduplicate: database might have same date in different formats
    before_count = len(df_prices)
    df_prices = df_prices.sort_values(['ticker', 'date']).drop_duplicates(subset=['ticker', 'date'], keep='last')
    after_count = len(df_prices)
    if before_count != after_count:
        logger.info(f"Deduplicated df_prices: {before_count} -> {after_count} rows")
    
    # Check for remaining duplicates if any (safety check)
    dupes = df_prices.duplicated(subset=['ticker', 'date']).sum()
    if dupes > 0:
        logger.error(f"FATAL: Still found {dupes} duplicates in df_prices after cleaning.")
        # Print a few to debug
        print(df_prices[df_prices.duplicated(subset=['ticker', 'date'], keep=False)].head(10))

    rs_query = f"""
        SELECT ticker, date, rs_composite
        FROM daily_rs_rankings
        WHERE date BETWEEN ? AND ?
    """
    df_rs = pd.read_sql_query(rs_query, conn, params=[START_DATE, END_DATE])
    df_rs['date'] = pd.to_datetime(df_rs['date'], format='mixed').dt.normalize()
    df_rs['ticker'] = df_rs['ticker'].str.upper().str.strip()
    df_rs = df_rs.sort_values(['ticker', 'date']).drop_duplicates(subset=['ticker', 'date'], keep='last')
    
    conn.close()
    
    if df_prices.empty or df_rs.empty:
        logger.error("No data found in DB.")
        return
    
    # Pivot for vectorization
    logger.info("🔄 Pivoting data for vectorization...")
    close_pivot = df_prices.pivot(index='date', columns='ticker', values='close')
    dv_pivot = df_prices.pivot(index='date', columns='ticker', values='dollar_volume')
    rs_pivot = df_rs.pivot(index='date', columns='ticker', values='rs_composite')
    
    # Breakout proxy: close > max(close, previous 20 days)
    # We use shift(1) to avoid including today in the max
    rolling_max_20 = close_pivot.shift(1).rolling(window=20).max()
    is_breakout = (close_pivot > rolling_max_20)
    
    # Forward returns
    logger.info("📈 Calculating forward returns...")
    fwd_rets = get_forward_returns(close_pivot, windows=[5, 10, 20])
    
    # Tradeable Mask (PIT Universe)
    logger.info("🛡️ Building PIT tradeable mask...")
    dates = pd.to_datetime(close_pivot.index, format='mixed')
    mask = pit.build_tradeable_mask(dates, list(close_pivot.columns))
    mask.index = close_pivot.index # Ensure same index type
    
    # ATR for R-multiple (proxy using adr_pct_20 * close / 100)
    # We use adr_pct_20 from DB
    adr_pivot = df_prices.pivot(index='date', columns='ticker', values='adr_pct_20')
    stop_dist = (adr_pivot * close_pivot / 100)
    
    # 3. Identify Signals
    logger.info("🔍 Identifying signals across all dates...")
    
    # Base Conditions: 
    # - In PIT Universe
    # - RS > 58
    # - Breakout Proxy
    # - Min Dollar Volume > 5M
    # - Date >= START_DATE (buffer was used for calculations)
    
    start_dt = pd.to_datetime(START_DATE)
    analysis_dates = close_pivot.index[close_pivot.index >= start_dt]
    
    signals = []
    
    for date in analysis_dates:
        # RS condition
        if date not in rs_pivot.index:
            continue
            
        rs_day = rs_pivot.loc[date]
        breakout_day = is_breakout.loc[date]
        dv_day = dv_pivot.loc[date]
        mask_day = mask.loc[date]
        
        # Valid tickers for today: RS > 58 & Breakout & Liq > 5M & In PIT
        valid_tickers = rs_day[ (rs_day > 58) & breakout_day & (dv_day > 5000000) & mask_day ].index
        
        for ticker in valid_tickers:
            etf = ticker_to_etf.get(ticker)
            if not etf or etf not in etf_prices.columns:
                continue
            
            # ETF metrics on signal date
            try:
                etf_c = etf_prices.loc[date, etf]
                etf_s20 = etf_sma20.loc[date, etf]
                etf_s50 = etf_sma50.loc[date, etf]
            except KeyError:
                continue
                
            # Classify group
            group = "baseline"
            if etf_c < etf_s20:
                group = "early_leader"
            elif etf_c > etf_s50 * 1.05:
                group = "late_entry"
            
            # Record signal
            sig_data = {
                "date": date,
                "ticker": ticker,
                "sector_etf": etf,
                "group": group,
                "fwd_5d": fwd_rets[5].loc[date, ticker],
                "fwd_10d": fwd_rets[10].loc[date, ticker],
                "fwd_20d": fwd_rets[20].loc[date, ticker],
                "stop_dist": stop_dist.loc[date, ticker]
            }
            signals.append(sig_data)
            
    df_signals = pd.DataFrame(signals)
    logger.info(f"Total signals generated: {len(df_signals)}")
    
    if df_signals.empty:
        logger.warning("No signals found.")
        return

    # 4. Analysis and Metrics
    logger.info("📊 Calculating metrics per group...")
    
    results = {}
    
    for group in ["early_leader", "baseline", "late_entry"]:
        group_df = df_signals[df_signals['group'] == group]
        group_results = {"count": len(group_df)}
        
        for w in [5, 10, 20]:
            col = f"fwd_{w}d"
            data = group_df[group_df[col].notna()]
            
            if data.empty:
                group_results[f"metrics_{w}d"] = None
                continue
                
            rets = data[col]
            # PF = sum gains / sum losses
            gains = rets[rets > 0].sum()
            losses = abs(rets[rets < 0].sum())
            pf = gains / losses if losses > 0 else (99.9 if gains > 0 else 0)
            
            # Win Rate
            wr = (rets > 0).mean() * 100
            
            # Sharpe on R-multiple: (ret / stop)
            # Proxy: r_multiple = rets / (stop_dist / entry_price) -> wait, rets is already decimal
            # stop_pct = data['stop_dist'] / close_at_entry
            # BUT we already have rets. Let's assume stop distance in % is roughly ADR
            # stop_pct = adr_at_entry / 100
            # To be simple and consistent with user's Sharpe(R-multiple):
            r_multiples = data[col] / (data['stop_dist'] / close_pivot.loc[data['date'], data['ticker']].values.diagonal())
            # Wait, close_pivot.loc[data['date'], data['ticker']] is slow in a loop.
            # Let's just use the stop distance relative to entry price.
            # Re-calculating entry price for R-multiple:
            entry_prices = np.array([close_pivot.at[d, t] for d, t in zip(data['date'], data['ticker'])])
            stop_pcts = data['stop_dist'] / entry_prices
            r_multi = data[col] / stop_pcts
            
            sharpe = (r_multi.mean() / r_multi.std()) * np.sqrt(252/w) if r_multi.std() > 0 else 0
            
            group_results[f"metrics_{w}d"] = {
                "trades": len(data),
                "win_rate": round(float(wr), 2),
                "pf": round(float(pf), 3),
                "sharpe_r": round(float(sharpe), 3),
                "median_ret": round(float(rets.median() * 100), 2)
            }
            
        results[group] = group_results

    # 5. Temporal Bias Check
    df_signals['month'] = pd.to_datetime(df_signals['date']).dt.to_period('M').astype(str)
    temporal_dist = df_signals.groupby(['month', 'group']).size().unstack(fill_value=0).to_dict()

    # 6. Final Report
    report = {
        "experiment": "Rotation Leaders - Early Leader Hypothesis",
        "period": f"{START_DATE} to {END_DATE}",
        "summary": results,
        "temporal_distribution": temporal_dist,
        "config": {
            "rs_threshold": 58,
            "min_dollar_volume": 5000000,
            "breakout_window": 20
        },
        "timestamp": datetime.now().isoformat()
    }
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"rotation_leaders_eval_{ts}.json"
    
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
        
    logger.info(f"✅ Experiment complete. Report saved to {out_path}")
    
    # Print summary to console
    print("\n" + "="*50)
    print("ROTATION LEADERS EXPERIMENT SUMMARY")
    print("="*50)
    for group, res in results.items():
        print(f"\nGroup: {group.upper()} (Total Trades: {res['count']})")
        for w in [5, 10, 20]:
            m = res.get(f"metrics_{w}d")
            if m:
                print(f"  {w}d: WR={m['win_rate']}% | PF={m['pf']} | Sharpe(R)={m['sharpe_r']} | Median={m['median_ret']}%")
    print("="*50)

if __name__ == "__main__":
    run_experiment()
