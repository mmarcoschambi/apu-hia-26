
import os
import sys
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.signals.signal_engine import evaluate_ticker, merge_ab_signals
from src.integration.combo_loader import load_combo_merged
from src.integration.universe_builder import build_universe_for_fold
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS
from src.signals.thematic_logic import calculate_equal_weighted_index
from src.data.theme_taxonomy import THEME_MAP, get_themes

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"

def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker=? AND date >= ? AND date <= ? || ' 23:59:59' ORDER BY date"
    df = pd.read_sql(query, conn, params=(ticker, start, end))
    conn.close()
    if df.empty: return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df = df.drop_duplicates(subset=["date"], keep="last").set_index("date").astype(float)
    return df

def compare_signals(date_str: str):
    print(f"\n--- Comparing Signals for {date_str} ---")
    today = pd.Timestamp(date_str)
    u_start = (today - timedelta(days=730)).strftime("%Y-%m-%d")
    snap = build_universe_for_fold(DB_PATH, date_str, u_start, max_tickers=200)
    universe = snap.tickers
    
    cfg_a, _ = load_combo_merged("combo_pure_momentum")
    cfg_b, _ = load_combo_merged("combo_stage2_breakout")
    
    # Base Line configs (from production_config.json basically, but let's assume default for this test)
    # The user mentioned Base Line has use_sector_etf_filter: True
    cfg_a_base = cfg_a.copy()
    cfg_b_base = cfg_b.copy()
    cfg_a_base["tier2_filters"]["use_sector_etf_filter"] = True
    cfg_b_base["tier2_filters"]["use_sector_etf_filter"] = True
    
    # Variant E configs
    cfg_a_ve = cfg_a.copy()
    cfg_b_ve = cfg_b.copy()
    cfg_a_ve["tier2_filters"]["use_theme_group_filter"] = True
    cfg_a_ve["tier2_filters"]["theme_filter_mode"] = "divergence"
    cfg_a_ve["tier2_filters"]["use_sector_etf_filter"] = False
    cfg_b_ve["tier2_filters"]["use_theme_group_filter"] = True
    cfg_b_ve["tier2_filters"]["theme_filter_mode"] = "divergence"
    cfg_b_ve["tier2_filters"]["use_sector_etf_filter"] = False

    # Load SPY
    spy_df = load_ohlcv("SPY", (today - timedelta(days=400)).strftime("%Y-%m-%d"), date_str)
    
    # Pre-calculate Sector and Theme dists
    etf_dists = {}
    for etf in SECTOR_ETFS:
        df = load_ohlcv(etf, (today - timedelta(days=90)).strftime("%Y-%m-%d"), date_str)
        if not df.empty:
            sma20 = df["close"].rolling(20).mean().iloc[-1]
            etf_dists[etf] = (df["close"].iloc[-1] / sma20) - 1

    # Theme dists
    theme_to_tickers = {}
    for t, themes in THEME_MAP.items():
        for theme in themes: theme_to_tickers.setdefault(theme, []).append(t)
    
    all_needed_tickers = set(THEME_MAP.keys()) | set(SECTOR_ETFS) | {"SPY"}
    market_data = {}
    for t in all_needed_tickers:
        df = load_ohlcv(t, (today - timedelta(days=90)).strftime("%Y-%m-%d"), date_str)
        if not df.empty: market_data[t] = df["close"]
    
    df_market = pd.DataFrame(market_data)
    theme_indices = {}
    for theme, members in theme_to_tickers.items():
        idx = calculate_equal_weighted_index(df_market, members)
        if not idx.empty: theme_indices[theme] = idx
    
    df_themes = pd.DataFrame(theme_indices)
    theme_sma20 = df_themes.rolling(20).mean()
    theme_dists_df = ((df_themes - theme_sma20) / theme_sma20)
    
    theme_metrics = {}
    for t in THEME_MAP:
        t_themes = get_themes(t)
        best_dist = -999
        for th in t_themes:
            if th in theme_dists_df.columns:
                d_val = theme_dists_df[th].iloc[-1]
                if d_val > best_dist: best_dist = d_val
        if best_dist != -999: theme_metrics[t] = best_dist

    # Evaluate
    results_base = []
    results_ve = []
    
    conn = sqlite3.connect(DB_PATH)
    for ticker in universe:
        df = load_ohlcv(ticker, (today - timedelta(days=400)).strftime("%Y-%m-%d"), date_str)
        if len(df) < 65: continue
        
        rs_row = conn.execute("SELECT rs_composite FROM daily_rs_rankings WHERE ticker=? AND date=?", (ticker, date_str)).fetchone()
        rs_val = rs_row[0] if rs_row else None
        
        etf = SECTOR_MAP.get(ticker)
        s_dist = etf_dists.get(etf)
        t_dist = theme_metrics.get(ticker)
        
        # Base
        res_a_base = evaluate_ticker(ticker, df, spy_df, cfg_a_base, rs_percentile=rs_val, scan_date=date_str, sector_etf_dist=s_dist)
        res_b_base = evaluate_ticker(ticker, df, spy_df, cfg_b_base, rs_percentile=rs_val, scan_date=date_str, sector_etf_dist=s_dist)
        if res_a_base.passed: results_base.append(res_a_base)
        if res_b_base.passed: results_base.append(res_b_base)
        
        # VE
        res_a_ve = evaluate_ticker(ticker, df, spy_df, cfg_a_ve, rs_percentile=rs_val, scan_date=date_str, sector_etf_dist=s_dist, theme_dist=t_dist)
        res_b_ve = evaluate_ticker(ticker, df, spy_df, cfg_b_ve, rs_percentile=rs_val, scan_date=date_str, sector_etf_dist=s_dist, theme_dist=t_dist)
        if res_a_ve.passed: results_ve.append(res_a_ve)
        if res_b_ve.passed: results_ve.append(res_b_ve)
        
    conn.close()
    
    merged_base = merge_ab_signals([r for r in results_base if r.mode=="A"], [r for r in results_base if r.mode=="B"])
    merged_ve = merge_ab_signals([r for r in results_ve if r.mode=="A"], [r for r in results_ve if r.mode=="B"])
    
    tickers_base = set([r.ticker for r in merged_base])
    tickers_ve = set([r.ticker for r in merged_ve])
    
    print(f"Base Tickers ({len(tickers_base)}): {tickers_base}")
    print(f"VE Tickers ({len(tickers_ve)}): {tickers_ve}")
    print(f"Only in Base: {tickers_base - tickers_ve}")
    print(f"Only in VE: {tickers_ve - tickers_base}")
    
    if tickers_base - tickers_ve:
        for t in (tickers_base - tickers_ve):
            # Why did it fail VE?
            etf = SECTOR_MAP.get(t)
            s_dist = etf_dists.get(etf)
            t_dist = theme_metrics.get(t)
            print(f"  {t} rejected in VE: Sector Dist {s_dist}, Theme Dist {t_dist}")

dates = ["2024-03-15", "2024-05-10", "2023-11-20"]
for d in dates:
    compare_signals(d)
