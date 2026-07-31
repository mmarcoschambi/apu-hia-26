"""Check RS gap: DB percentile vs SPY fallback for every ticker."""
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/ticker_cache.db")
conn = sqlite3.connect(str(DB_PATH))

# Load universe from DB source
universe = [r[0] for r in conn.execute(
    "SELECT DISTINCT ticker FROM universe WHERE ticker NOT LIKE '%-%' AND ticker NOT LIKE '%.%' ORDER BY ticker"
).fetchall()]
print(f"Universe: {len(universe)} tickers")

# Latest RS data
rs_date = conn.execute("SELECT MAX(date) FROM daily_rs_rankings").fetchone()[0]
print(f"Latest RS date: {rs_date}")

# For every ticker with RS data, compare DB percentile vs actual vs SPY
cutoff = "2025-07-30"  # ~1 year back
spy_ret_60d = None

# Get SPY 60d return
spy_rows = conn.execute(
    "SELECT date,close FROM ohlcv_cache WHERE ticker='SPY' AND date>=? ORDER BY date",
    (cutoff,)
).fetchall()
if len(spy_rows) >= 61:
    spy_close = pd.Series([r[1] for r in spy_rows])
    spy_ret_60d = spy_close.iloc[-1] / spy_close.iloc[-61] - 1
    print(f"SPY 60d return: {spy_ret_60d*100:.1f}%")

# Check AAPL as sample
ticker = "AAPL"
ticker_rows = conn.execute(
    "SELECT date,close FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
    (ticker, cutoff)
).fetchall()
if len(ticker_rows) >= 61:
    t_close = pd.Series([r[1] for r in ticker_rows])
    t_ret = t_close.iloc[-1] / t_close.iloc[-61] - 1
    rel = t_ret - spy_ret_60d
    rs_fallback = max(0.0, min(100.0, 50.0 + rel * 500.0))
    
    # DB value
    db_rs = conn.execute(
        "SELECT rs_composite FROM daily_rs_rankings WHERE ticker=? ORDER BY date DESC LIMIT 1",
        (ticker,)
    ).fetchone()
    db_val = db_rs[0] if db_rs else None
    
    print(f"\n{ticker}:")
    print(f"  DB RS: {db_val}")
    print(f"  Return: {t_ret*100:.1f}%, SPY: {spy_ret_60d*100:.1f}%")
    print(f"  Fallback: {rs_fallback:.1f}")

# How many tickers pass RS >= 75 with DB value vs fallback
pass_db = 0
pass_fallback = 0
total_with_rs = 0
tickers_check = universe[:100] if len(universe) > 100 else universe

for t in tickers_check:
    db_rs = conn.execute(
        "SELECT rs_composite FROM daily_rs_rankings WHERE ticker=? ORDER BY date DESC LIMIT 1",
        (t,)
    ).fetchone()
    if db_rs is None:
        continue
    total_with_rs += 1
    rs_val = db_rs[0]
    if rs_val is not None and rs_val >= 75:
        pass_db += 1
    
    # Fallback check - need ~60 days of data
    rows = conn.execute(
        "SELECT date,close FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
        (t, cutoff)
    ).fetchall()
    if len(rows) >= 61:
        close = pd.Series([r[1] for r in rows])
        ret = close.iloc[-1] / close.iloc[-61] - 1
        rel = ret - spy_ret_60d
        rs_fb = max(0.0, min(100.0, 50.0 + rel * 500.0))
        if rs_fb >= 75:
            pass_fallback += 1

print(f"\n=== First {total_with_rs} tickers with RS data ===")
print(f"Pass DB RS >= 75: {pass_db}/{total_with_rs}")
print(f"Pass fallback >= 75: {pass_fallback}/{total_with_rs}")

# Check how many tickers have RS >= 75 but still fail the screener
conn.close()
