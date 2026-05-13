import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import sys
import warnings

# Suppress pandas warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.pit_universe import PointInTimeUniverse
from src.data.theme_taxonomy import THEME_MAP, get_themes

# DB and Constants
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "experiments"
SP500_CSV = PROJECT_ROOT / "sp500" / "sp500" / "sp500.csv"

# Date Ranges
IS_START, IS_END = "2024-01-01", "2025-06-30"
OOS_START, OOS_END = "2025-07-01", "2026-03-31"
HOLDOUT_START, HOLDOUT_END = "2026-04-01", "2026-05-12"

ALL_START = (pd.to_datetime(IS_START) - timedelta(days=200)).strftime("%Y-%m-%d")
ALL_END = HOLDOUT_END

ETFS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLY", "XLP", "XLB", "XLRE", "XLU", "XLC", "SPY"]

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
        logger.warning(f"SP500 CSV not found at {SP500_CSV}. ETF mapping might be incomplete.")
        return {}
    df = pd.read_csv(SP500_CSV)
    ticker_to_gics = dict(zip(df["Symbol"], df["GICS Sector"]))
    return {t: GICS_TO_ETF[s] for t, s in ticker_to_gics.items() if s in GICS_TO_ETF}

def get_theme_members():
    theme_to_tickers = {}
    for ticker, themes in THEME_MAP.items():
        for theme in themes:
            if theme not in theme_to_tickers:
                theme_to_tickers[theme] = []
            theme_to_tickers[theme].append(ticker)
    return theme_to_tickers

def run_experiment():
    logger.info("Starting Thematic Groups vs ETF Macro Sandbox Experiment")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Data
    conn = sqlite3.connect(DB_PATH)
    
    # Get all tickers in theme map + ETFs
    theme_tickers = list(THEME_MAP.keys())
    all_needed_tickers = list(set(theme_tickers + ETFS))
    
    logger.info(f"Loading price data for {len(all_needed_tickers)} tickers...")
    placeholders = ",".join(["?"] * len(all_needed_tickers))
    df_prices = pd.read_sql_query(
        f"SELECT ticker, date, close, adr_pct_20 FROM ohlcv_cache "
        f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
        conn, params=all_needed_tickers + [ALL_START, ALL_END]
    )
    df_prices["date"] = pd.to_datetime(df_prices["date"], format='mixed').dt.normalize()
    df_prices = df_prices.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    
    # Pivot for easier calculation
    close_pivot = df_prices.pivot(index="date", columns="ticker", values="close")
    adr_pivot = df_prices.pivot(index="date", columns="ticker", values="adr_pct_20")
    
    # Handle missing ETF data with yfinance if needed
    missing_etfs = [e for e in ETFS if e not in close_pivot.columns]
    if missing_etfs:
        logger.info(f"Downloading missing ETF data: {missing_etfs}")
        etf_data = yf.download(missing_etfs, start=ALL_START, end=ALL_END, progress=False)["Close"]
        if isinstance(etf_data, pd.Series): # only one ETF
            etf_data = etf_data.to_frame()
            etf_data.columns = missing_etfs
        etf_data.index = etf_data.index.normalize()
        close_pivot = pd.concat([close_pivot, etf_data], axis=1)

    # 2. Calculate Theme Indices
    theme_to_tickers = get_theme_members()
    theme_indices = {}
    
    for theme, members in theme_to_tickers.items():
        available_members = [m for m in members if m in close_pivot.columns]
        if len(available_members) < 2:
            continue
            
        # Equal-weighted index: average of daily returns, then cumulative
        member_prices = close_pivot[available_members]
        member_rets = member_prices.pct_change()
        
        # Rule: theme/day valid only if at least 5 members have price (or all if < 5 total)
        min_members = min(5, len(available_members))
        valid_days = member_prices.notna().sum(axis=1) >= min_members
        
        theme_index_rets = member_rets.mean(axis=1)
        theme_index_rets[~valid_days] = np.nan
        
        # Cumulative index (starting at 100)
        theme_index = (1 + theme_index_rets.fillna(0)).cumprod() * 100
        theme_index[theme_index_rets.isna()] = np.nan
        theme_indices[theme] = theme_index

    theme_df = pd.DataFrame(theme_indices)
    
    # 3. Calculate Theme Metrics
    theme_sma20 = theme_df.rolling(20).mean()
    
    # theme_vs_spy_20d: theme return 20d - SPY return 20d
    spy_ret_20d = close_pivot["SPY"].pct_change(20)
    theme_ret_20d = theme_df.pct_change(20)
    theme_vs_spy_20d = theme_ret_20d.sub(spy_ret_20d, axis=0)
    
    # Theme Ranks (Pct)
    theme_rank_pct = theme_ret_20d.rank(axis=1, pct=True) * 100

    # 4. Load Signals (from candidate_state as proxy for baseline signals)
    logger.info("Loading baseline signals from candidate_state for mapped tickers...")
    theme_tickers = list(THEME_MAP.keys())
    placeholders_theme = ",".join(["?"] * len(theme_tickers))
    df_signals = pd.read_sql_query(
        f"SELECT date, ticker, sector_etf, score FROM candidate_state "
        f"WHERE date BETWEEN ? AND ? AND ticker IN ({placeholders_theme})",
        conn, params=[IS_START, HOLDOUT_END] + theme_tickers
    )
    df_signals["date"] = pd.to_datetime(df_signals["date"], format='mixed').dt.normalize()
    
    ticker_to_etf = load_ticker_to_etf_map()
    
    # 5. Enrich Signals with Theme and ETF metrics
    enriched_signals = []
    
    # ETF SMA20 for Baseline 1
    etf_sma20 = close_pivot[ETFS].rolling(20).mean()
    
    logger.info(f"Enriching {len(df_signals)} signals...")
    # Progress logging every 10%
    total_sig = len(df_signals)
    log_step = max(1, total_sig // 10)

    for i, sig in enumerate(df_signals.iloc):
        if i % log_step == 0:
            logger.info(f"Progress: {i}/{total_sig} signals processed")
            
        date = sig["date"]
        ticker = sig["ticker"]
        
        # Ensure ticker is in our price data
        if ticker not in close_pivot.columns:
            continue
        
        # Sector ETF
        etf = sig["sector_etf"] or ticker_to_etf.get(ticker)
        if not etf or etf not in close_pivot.columns:
            continue
            
        sector_etf_ok = False
        if date in close_pivot.index:
            try:
                sector_etf_ok = close_pivot.at[date, etf] > etf_sma20.at[date, etf]
            except:
                pass
            
        # Themes for this ticker
        ticker_themes = get_themes(ticker)
        
        # Picking "best" theme for this trade based on theme_vs_sector_etf_20d
        best_theme = None
        best_theme_vs_sector = -999
        
        theme_metrics = {}
        for theme in ticker_themes:
            if theme not in theme_df.columns or date not in theme_df.index:
                continue
                
            try:
                t_price = theme_df.at[date, theme]
                t_sma20 = theme_sma20.at[date, theme]
                t_ret_20d = theme_ret_20d.at[date, theme]
                
                # ETF return 20d
                etf_prices = close_pivot[etf]
                etf_ret_20d = etf_prices.at[date] / etf_prices.shift(20).at[date] - 1
                vs_sector = t_ret_20d - etf_ret_20d
                
                if vs_sector > best_theme_vs_sector:
                    best_theme_vs_sector = vs_sector
                    best_theme = theme
                
                theme_metrics[theme] = {
                    "above_sma20": t_price > t_sma20,
                    "vs_sector_20d": vs_sector,
                    "rank_pct": theme_rank_pct.at[date, theme]
                }
            except:
                continue
            
        # Get Forward Returns
        fwd_rets = {}
        for w in [5, 10, 20]:
            try:
                # Find date w days ahead in close_pivot index
                idx_pos = close_pivot.index.get_loc(date)
                if idx_pos + w < len(close_pivot.index):
                    future_date = close_pivot.index[idx_pos + w]
                    fwd_rets[f"fwd_{w}d"] = close_pivot.at[future_date, ticker] / close_pivot.at[date, ticker] - 1
                else:
                    fwd_rets[f"fwd_{w}d"] = np.nan
            except:
                fwd_rets[f"fwd_{w}d"] = np.nan
        
        # Stop Distance (for Sharpe R)
        adr_val = np.nan
        if date in adr_pivot.index:
            adr_val = adr_pivot.at[date, ticker]

        res = {
            "date": date,
            "ticker": ticker,
            "etf": etf,
            "sector_etf_ok": sector_etf_ok,
            "best_theme": best_theme,
            "adr_pct_20": adr_val,
            **fwd_rets
        }
        
        if best_theme:
            res["theme_above_sma20"] = theme_metrics[best_theme]["above_sma20"]
            res["theme_vs_sector_etf_20d"] = theme_metrics[best_theme]["vs_sector_20d"]
            res["theme_rank_pct"] = theme_metrics[best_theme]["rank_pct"]
        else:
            res["theme_above_sma20"] = False
            res["theme_vs_sector_etf_20d"] = -999
            res["theme_rank_pct"] = 0
            
        enriched_signals.append(res)

    df_results = pd.DataFrame(enriched_signals)
    conn.close()

    if df_results.empty:
        logger.error("No signals could be enriched. Check data availability.")
        return

    # 6. Evaluate Variants
    variants = {
        "Baseline 0": lambda d: True,
        "Baseline 1 (Sector ETF)": lambda d: d["sector_etf_ok"],
        "Variant A (Theme SMA20)": lambda d: d["theme_above_sma20"],
        "Variant B (Theme > Sector)": lambda d: d["theme_vs_sector_etf_20d"] > 0,
        "Variant C (Theme Rank >= 70)": lambda d: d["theme_rank_pct"] >= 70,
        "Variant D (Theme & Sector OK)": lambda d: d["theme_above_sma20"] and d["sector_etf_ok"],
        "Variant E (Divergence: Theme OK, Sector NO)": lambda d: d["theme_above_sma20"] and not d["sector_etf_ok"],
    }

    periods = {
        "IS": (IS_START, IS_END),
        "OOS": (OOS_START, OOS_END),
        "HOLDOUT": (HOLDOUT_START, HOLDOUT_END)
    }

    results_report = {}
    
    for p_name, (start, end) in periods.items():
        p_df = df_results[(df_results["date"] >= start) & (df_results["date"] <= end)]
        if p_df.empty:
            logger.warning(f"No signals found for period {p_name}")
            continue
            
        p_results = {}
        for v_name, v_filter in variants.items():
            v_df = p_df[p_df.apply(v_filter, axis=1)]
            
            variant_metrics = {"trades": len(v_df)}
            for w in [5, 10, 20]:
                col = f"fwd_{w}d"
                subset = v_df[v_df[col].notna()].copy()
                if subset.empty:
                    variant_metrics[f"{w}d"] = None
                    continue
                
                rets = subset[col]
                wr = (rets > 0).mean() * 100
                pf = rets[rets > 0].sum() / abs(rets[rets < 0].sum()) if rets[rets < 0].sum() != 0 else 99
                
                # Sharpe R: R = return / (ADR_pct_20 / 100)
                # We need to filter out cases where adr_pct_20 is missing or 0
                subset = subset[subset["adr_pct_20"] > 0]
                if subset.empty:
                    variant_metrics[f"{w}d"] = None
                    continue
                    
                r_multi = subset[col] / (subset["adr_pct_20"] / 100)
                sharpe_r = (r_multi.mean() / r_multi.std() * np.sqrt(252/w)) if len(r_multi) > 1 and r_multi.std() > 0 else 0
                
                variant_metrics[f"{w}d"] = {
                    "win_rate": round(wr, 2),
                    "pf": round(pf, 2),
                    "sharpe_r": round(sharpe_r, 3),
                    "avg_ret": round(rets.mean() * 100, 2)
                }
            p_results[v_name] = variant_metrics
        results_report[p_name] = p_results

    # 7. Decision Logic (GO/NO-GO)
    oos_results = results_report.get("OOS", {})
    baseline1_oos = oos_results.get("Baseline 1 (Sector ETF)", {}).get("20d")
    
    oos_baseline1_sharpe = baseline1_oos["sharpe_r"] if baseline1_oos else 0
    
    oos_variants = {
        k: v["20d"]["sharpe_r"] 
        for k, v in oos_results.items() 
        if "Variant" in k and v.get("20d")
    }
    
    best_variant = max(oos_variants, key=oos_variants.get) if oos_variants else None
    best_sharpe = oos_variants[best_variant] if best_variant else 0
    
    # PHASE 1.1: Documenting throughput exception rationale
    throughput_exception_rationale = (
        "Variant E is a sniper setup targeting a structural market anomaly "
        "(theme diverging from sector). Low retention (33.7%) is expected and not a disqualifier. "
        "Minimum quality bar: PF > 3.0 and WR > 55% OOS at 20d horizon. Rollback triggers if "
        "live throughput drops below 15 signals/month consistently over 4 weeks."
    )
    
    go_status = "NO-GO"
    if best_variant and best_sharpe >= oos_baseline1_sharpe + 0.10:
        go_status = "GO"
        
    final_report = {
        "timestamp": datetime.now().isoformat(),
        "experiment": "Theme Groups vs ETF Macro",
        "go_no_go": go_status,
        "best_variant": best_variant,
        "delta_sharpe_oos": round(best_sharpe - oos_baseline1_sharpe, 3) if best_variant else 0,
        "throughput_exception_rationale": throughput_exception_rationale,
        "results": results_report,
        "taxonomy_size": len(THEME_MAP),
        "themes_count": len(theme_indices)
    }

    with open(OUTPUT_DIR / "theme_group_experiment_report.json", "w") as f:
        json.dump(final_report, f, indent=2)

    logger.info(f"Experiment complete. Decision: {go_status}")
    print("\n" + "="*50)
    print("THEMATIC GROUPS EXPERIMENT RESULTS (20d window)")
    print("="*50)
    for p_name, p_res in results_report.items():
        print(f"\nPERIOD: {p_name}")
        for v_name, v_metrics in p_res.items():
            m = v_metrics.get("20d")
            if m:
                print(f"  {v_name:<40} | Trades: {v_metrics['trades']:>5} | WR: {m['win_rate']:>5.1f}% | Sharpe(R): {m['sharpe_r']:>6.3f}")
            else:
                print(f"  {v_name:<40} | Trades: {v_metrics['trades']:>5} | No data")
    
    print("\n" + "="*50)
    print(f"Decision: {go_status}")
    if best_variant:
        print(f"Best Variant: {best_variant}")
        print(f"OOS Sharpe Delta: {final_report['delta_sharpe_oos']:.3f} (vs Sector ETF)")
    print("="*50 + "\n")

if __name__ == "__main__":
    run_experiment()
