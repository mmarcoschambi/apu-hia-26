#!/usr/bin/env python3
"""
scripts/validate_theme_on_historical_signals.py
Validates the Thematic Divergence filter on historical candidate signals.
This confirms the OOS results by applying the new filter logic to stored candidate_state.
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import logging

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.theme_taxonomy import THEME_MAP, get_themes
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

def main():
    # Range: Last 30 days of available candidates
    end_date = "2026-04-30"
    start_date = (pd.to_datetime(end_date) - timedelta(days=60)).strftime("%Y-%m-%d")
    
    logger.info(f"Loading historical signals from {start_date} to {end_date}...")
    
    conn = sqlite3.connect(DB_PATH)
    # Get signals only for tickers in our taxonomy
    theme_tickers = list(THEME_MAP.keys())
    placeholders = ",".join(["?"] * len(theme_tickers))
    
    query = f"""
    SELECT date, ticker, sector_etf, close 
    FROM candidate_state 
    WHERE date BETWEEN ? AND ? 
    AND ticker IN ({placeholders})
    """
    df_signals = pd.read_sql_query(query, conn, params=[start_date, end_date] + theme_tickers)
    conn.close()
    
    if df_signals.empty:
        logger.error("No signals found in the given range for mapped tickers.")
        return

    df_signals["date"] = pd.to_datetime(df_signals["date"], format="mixed").dt.normalize()
    unique_dates = sorted(df_signals["date"].unique())
    
    logger.info(f"Found {len(df_signals)} signals across {len(unique_dates)} dates.")
    
    # Pre-fetch price data for all needed tickers and ETFs
    all_tickers = list(set(theme_tickers + SECTOR_ETFS))
    fetch_start = (min(unique_dates) - timedelta(days=100)).strftime("%Y-%m-%d")
    fetch_end = max(unique_dates).strftime("%Y-%m-%d")
    
    logger.info(f"Fetching market data for {len(all_tickers)} tickers...")
    market_data = yf.download(all_tickers, start=fetch_start, end=fetch_end, progress=False)["Close"]
    market_data.index = market_data.index.normalize()
    market_data = market_data.ffill()

    # Calculate Theme Indices
    theme_to_tickers = {}
    for t, themes in THEME_MAP.items():
        for theme in themes:
            theme_to_tickers.setdefault(theme, []).append(t)
            
    theme_indices = {}
    for theme, members in theme_to_tickers.items():
        avail = [m for m in members if m in market_data.columns]
        if len(avail) < 2: continue
        m_rets = market_data[avail].pct_change()
        min_m = min(5, len(avail))
        valid = market_data[avail].notna().sum(axis=1) >= min_m
        t_rets = m_rets.mean(axis=1)
        t_rets[~valid] = np.nan
        t_idx = (1 + t_rets.fillna(0)).cumprod()
        t_idx[t_rets.isna()] = np.nan
        theme_indices[theme] = t_idx
        
    df_themes = pd.DataFrame(theme_indices)
    theme_sma20 = df_themes.rolling(20).mean()
    
    # Calculate ETF SMA20
    etf_sma20 = market_data[SECTOR_ETFS].rolling(20).mean()
    
    # Validate each signal
    results = []
    for _, sig in df_signals.iterrows():
        date = sig["date"]
        ticker = sig["ticker"]
        etf = sig["sector_etf"] or SECTOR_MAP.get(ticker)
        
        if date not in market_data.index: continue
        
        # Sector status
        sector_ok = False
        if etf and etf in market_data.columns:
            try:
                sector_ok = market_data.at[date, etf] > etf_sma20.at[date, etf]
            except: pass
            
        # Theme status
        ticker_themes = get_themes(ticker)
        theme_ok = False
        best_theme = None
        
        # For validation, we just need to see if ANY theme passes above SMA20
        # and if the best theme is in divergence
        for theme in ticker_themes:
            if theme in df_themes.columns and date in df_themes.index:
                try:
                    if df_themes.at[date, theme] > theme_sma20.at[date, theme]:
                        theme_ok = True
                        best_theme = theme
                        break
                except: pass
        
        # Variant E logic: Theme OK and Sector NOT OK
        passed_divergence = theme_ok and not sector_ok
        
        results.append({
            "date": date,
            "ticker": ticker,
            "theme_ok": theme_ok,
            "sector_ok": sector_ok,
            "passed_divergence": passed_divergence
        })
        
    df_res = pd.DataFrame(results)
    
    print("\n" + "="*60)
    print("HISTORICAL SIGNAL VALIDATION (Variant E: Divergence)")
    print("="*60)
    summary = df_res.groupby("date")["passed_divergence"].agg(["sum", "count"])
    summary.columns = ["Divergence Signals", "Total Mapped Signals"]
    print(summary)
    
    total_div = df_res["passed_divergence"].sum()
    total_sig = len(df_res)
    print(f"\nTotal Divergence Signals: {total_div}")
    print(f"Total Mapped Signals: {total_sig}")
    print(f"Thematic Sniper Throughput: {total_div / total_sig * 100:.1f}%")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
