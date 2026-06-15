import os, sys, pandas as pd, sqlite3
from pathlib import Path
from datetime import datetime, timedelta
PROJECT_ROOT = Path('.').resolve()
sys.path.append(str(PROJECT_ROOT))
from src.signals.signal_engine import evaluate_ticker
from src.integration.combo_loader import load_combo_merged
from src.data.theme_taxonomy import THEME_MAP, get_themes
from src.utils.sector_rotation import SECTOR_MAP, SECTOR_ETFS

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
conn = sqlite3.connect(DB_PATH)
# Check NVDA on a date it passed in Base Line
ticker = 'NVDA'
date_str = '2019-06-03' # Just an example date
today = pd.Timestamp(date_str)
df_start = (today - timedelta(days=400)).strftime("%Y-%m-%d")

df = pd.read_sql("SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker=? AND date >= ? AND date <= ?", conn, params=(ticker, df_start, date_str))
spy = pd.read_sql("SELECT date, open, high, low, close, volume FROM ohlcv_cache WHERE ticker='SPY' AND date >= ? AND date <= ?", conn, params=(df_start, date_str))
xlk = pd.read_sql("SELECT date, close FROM ohlcv_cache WHERE ticker='XLK' AND date >= ? AND date <= ?", conn, params=(df_start, date_str))

df['date'] = pd.to_datetime(df['date'], format='mixed').dt.normalize()
spy['date'] = pd.to_datetime(spy['date'], format='mixed').dt.normalize()
xlk['date'] = pd.to_datetime(xlk['date'], format='mixed').dt.normalize()
df.set_index('date', inplace=True)
spy.set_index('date', inplace=True)
xlk.set_index('date', inplace=True)

# Calc distances
xlk_sma20 = xlk['close'].rolling(20).mean().iloc[-1]
s_dist = (xlk['close'].iloc[-1] / xlk_sma20) - 1

cfg_a, _ = load_combo_merged("combo_pure_momentum")
# Variant E setup
cfg_a["tier2_filters"]["use_theme_group_filter"] = True
cfg_a["tier2_filters"]["theme_filter_mode"] = "divergence"
cfg_a["tier2_filters"]["use_sector_etf_filter"] = False

# Mock theme dist (assuming fuerte)
t_dist = 0.05 

res = evaluate_ticker(ticker, df, spy, cfg_a, sector_etf_dist=s_dist, theme_dist=t_dist)
print(f"Passed: {res.passed}")
print(f"Reject Reason: {res.reject_reason}")
print(f"Sector Dist: {s_dist}")
print(f"Theme Dist: {t_dist}")
