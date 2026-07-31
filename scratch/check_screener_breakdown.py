"""Run Qullamaggie screener on a subset to see which criteria fail."""
import sys, sqlite3
sys.path.insert(0, "scripts")
sys.path.insert(0, "src")
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from src.screeners.qullamaggie_momentum import QullamaggieMomentumScreener
from src.screeners.base import ScreenerConfig
from src.screeners.registry import ScreenerRegistry

DB_PATH = Path("data/ticker_cache.db")
LOOKBACK_DAYS = 365
cutoff = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

conn = sqlite3.connect(str(DB_PATH))
universe = [r[0] for r in conn.execute(
    "SELECT DISTINCT ticker FROM universe WHERE ticker NOT LIKE '%-%' AND ticker NOT LIKE '%.%' ORDER BY ticker"
).fetchall()[:200]]

# Load config from disk (same as evaluate_ticker does)
config = ScreenerRegistry.load_config("qullamaggie_momentum")
# Apply the validated overrides
config.min_adr_pct = 1.2
config.params.update({
    "min_rs_percentile": 75,
    "min_trend_intensity": 104,
    "require_ma_stack": True,
})
screener = ScreenerRegistry.get("qullamaggie_momentum", config)

# Load SPY
spy_rows = conn.execute(
    "SELECT date,close FROM ohlcv_cache WHERE ticker='SPY' AND date>=? ORDER BY date",
    (cutoff,)
).fetchall()
spy_df = pd.DataFrame(spy_rows, columns=["date","close"])
spy_df["date"] = pd.to_datetime(spy_df["date"], format="mixed")
spy_df = spy_df.set_index("date").astype(float)

# Track failures
stats = {"total": 0, "pass": 0, "rs_fail": 0, "ma_fail": 0, "ti_fail": 0, "hist_fail": 0, "base_fail": 0}
fail_rs_vs = {"db_below_75": 0, "db_none": 0}

for ticker in universe[:100]:
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff)
    ).fetchall()
    if not rows:
        continue
    df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.set_index("date").astype(float)
    
    stats["total"] += 1
    
    # Base filters
    passed, reason = screener.apply_base_filters(df)
    if not passed:
        stats["base_fail"] += 1
        continue
    
    if len(df) < 200:
        stats["hist_fail"] += 1
        continue
    
    c = df["close"]
    price = float(c.iloc[-1])
    p = screener.config.params
    
    # RS
    from src.data.rs_rankings import get_rs_percentile
    rs_pct = get_rs_percentile(ticker, date=None, metric=p["rs_metric"])
    
    used_fallback = False
    if rs_pct is None:
        fail_rs_vs["db_none"] += 1
        if p.get("rs_fallback_spy") and spy_df is not None:
            rs_pct = screener._calc_rs_vs_spy(df, spy_df)
            used_fallback = True
    
    if rs_pct is not None and rs_pct < p["min_rs_percentile"]:
        if rs_pct is not None and not used_fallback:
            fail_rs_vs["db_below_75"] += 1
    
    rs_ok = rs_pct is not None and rs_pct >= p["min_rs_percentile"]
    
    # MA Stack
    ema10 = screener.ensure_ma(df, 10, kind="ema")
    sma20 = screener.ensure_ma(df, 20)
    sma50 = screener.ensure_ma(df, 50)
    sma100 = screener.ensure_ma(df, 100)
    sma200 = screener.ensure_ma(df, 200)
    tol = p["ma_stack_tolerance"]
    stack_ok = (
        price >= float(ema10.iloc[-1]) * (1 - tol)
        and float(ema10.iloc[-1]) >= float(sma20.iloc[-1]) * (1 - tol)
        and float(sma20.iloc[-1]) >= float(sma50.iloc[-1]) * (1 - tol)
        and float(sma50.iloc[-1]) >= float(sma100.iloc[-1]) * (1 - tol)
        and float(sma100.iloc[-1]) >= float(sma200.iloc[-1]) * (1 - tol)
    ) if p["require_ma_stack"] else True
    
    # Trend Intensity
    ma13 = float(screener.ensure_ma(df, 13).iloc[-1])
    ma65 = float(screener.ensure_ma(df, 65).iloc[-1])
    ti = (ma13 / ma65 * 100) if ma65 > 0 else 0.0
    ti_ok = ti >= p["min_trend_intensity"]
    
    if not rs_ok:
        stats["rs_fail"] += 1
    if not stack_ok:
        stats["ma_fail"] += 1
    if not ti_ok:
        stats["ti_fail"] += 1
    if rs_ok and stack_ok and ti_ok:
        stats["pass"] += 1

conn.close()
print(f"Total evaluated: {stats['total']}")
print(f"Pass:           {stats['pass']}")
print(f"Base filter:    {stats['base_fail']}")
print(f"History fail:   {stats['hist_fail']}")
print(f"RS fail:        {stats['rs_fail']}")
print(f"  - DB RS < 75: {fail_rs_vs['db_below_75']}")
print(f"  - DB RS None: {fail_rs_vs['db_none']}")
print(f"MA stack fail:  {stats['ma_fail']}")
print(f"Trend Int fail: {stats['ti_fail']}")
