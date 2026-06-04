import os, sys, pandas as pd, sqlite3
from pathlib import Path
from datetime import datetime, timedelta
PROJECT_ROOT = Path('.').resolve()
sys.path.append(str(PROJECT_ROOT))
from src.signals.thematic_logic import calculate_equal_weighted_index
from src.data.theme_taxonomy import THEME_MAP, get_themes
from src.utils.sector_rotation import SECTOR_ETFS

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
conn = sqlite3.connect(DB_PATH)
start, end = '2019-01-01', '2020-12-31'
tickers = list(THEME_MAP.keys()) + SECTOR_ETFS + ["SPY"]
placeholders = ",".join(["?"] * len(tickers))
query = f"SELECT ticker, date, close FROM ohlcv_cache WHERE ticker IN ({placeholders}) AND date >= ? AND date <= ?"
df_all = pd.read_sql(query, conn, params=tickers + [start, end])
conn.close()

df_all['date'] = pd.to_datetime(df_all['date'], format='mixed').dt.normalize()
market_data = df_all.pivot(index='date', columns='ticker', values='close')

theme_to_tickers = {}
for t, themes in THEME_MAP.items():
    for theme in themes: theme_to_tickers.setdefault(theme, []).append(t)

theme_indices = {}
for theme, members in theme_to_tickers.items():
    idx = calculate_equal_weighted_index(market_data, members)
    if not idx.empty: theme_indices[theme] = idx

df_themes = pd.DataFrame(theme_indices)
print(f"Themes calculated: {len(df_themes.columns)}")
print(df_themes.notna().sum())
