#!/usr/bin/env python3
"""
historical_signal_backtest.py
=============================
Simula el scanner diario sobre datos historicos para comparar
con el backtest de Streamlit. Mide la divergencia entre:
- Seniales generadas por el scanner (logica identica al engine)
- Trades ejecutados por el backtest (numba_core)

Uso: python3 historical_signal_backtest.py --start 2026-01-01 --end 2026-02-28
"""
import sys, json, sqlite3, argparse, warnings
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
CONFIG_PATH = PROJECT_ROOT / "config" / "production_config.json"
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "paper_trading"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(CONFIG_PATH) as f: _cfg = json.load(f)
T1=_cfg["tier1_strategy"]; T2=_cfg["tier2_filters"]; MR=_cfg["market_regime"]
MIN_RVOL=T2.get("min_rvol",0.58); MIN_ADR=T2.get("min_adr",1.49)
MAX_DIST=T2.get("max_dist_sma20",12.84); MIN_CONSOL=T2.get("min_consolidation_days",5)
MIN_DV=T2.get("min_dollar_volume",5941884); MIN_VOL=T2.get("min_volume",100000)
MIN_RS=T2.get("min_rs_percentile",70.0); RS_LB=T2.get("rs_lookback_days",60)
MAX_VIX=MR.get("max_vix",35.0); REQ_SPY=MR.get("require_spy_above_sma50",True)


def load_all_ohlcv(start_date, end_date, min_dv=MIN_DV):
    conn = sqlite3.connect(DB_PATH)
    lookback = (pd.to_datetime(start_date) - timedelta(days=150)).strftime("%Y-%m-%d")
    tickers = conn.execute(
        "SELECT ticker FROM ohlcv_cache WHERE date BETWEEN ? AND ? "
        "GROUP BY ticker HAVING COUNT(*) >= 30 AND AVG(close*volume) >= ? ORDER BY AVG(close*volume) DESC",
        (start_date, end_date, min_dv)
    ).fetchall()
    tickers = [t[0] for t in tickers]
    # Filter US-only tickers (exclude international suffixes)
    intl = ["-KS","-SZ","-HK","-T","-L","-PA","-DE","-AS","-VN","-SR"]
    tickers = [t for t in tickers if not any(t.endswith(s) for s in intl) and len(t) <= 6]
    print(f"  Universe: {len(tickers)} tickers")
    all_data = {}
    for t in tickers:
        rows = conn.execute(
            "SELECT date,open,high,low,close,volume FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",
            (t, lookback)
        ).fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
            df["date"] = pd.to_datetime(df["date"].str[:10])
            df = df.set_index("date").astype(float)
            all_data[t] = df
    conn.close()
    return all_data


def load_benchmark_df(conn, candidates, label):
    """Load benchmark data using first available ticker with rows."""
    for ticker in candidates:
        try:
            df = pd.read_sql(
                "SELECT date,close FROM ohlcv_cache WHERE ticker=? ORDER BY date",
                conn,
                params=(ticker,),
            )
        except Exception:
            continue
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"].astype(str).str[:10], errors="coerce")
        df = df.dropna(subset=["date"]).set_index("date")
        if not df.empty:
            print(f"  {label}: using ticker '{ticker}' ({len(df)} rows)")
            return ticker, df
    print(f"  WARNING: {label} not found. Tried: {', '.join(candidates)}")
    return None, pd.DataFrame(columns=["close"])


def get_spy_vix(date, spy_df, vix_df):
    try:
        spy_p = float(spy_df[spy_df.index <= date]["close"].iloc[-1])
        spy_s = float(spy_df[spy_df.index <= date]["close"].rolling(50).mean().dropna().iloc[-1])
        if vix_df.empty:
            vix_v = 0.0
            vix_ok = True
        else:
            vix_v = float(vix_df[vix_df.index <= date]["close"].iloc[-1])
            vix_ok = vix_v < MAX_VIX
        spy_ok = spy_p >= spy_s if REQ_SPY else True
        return spy_ok, vix_ok, spy_p, spy_s, vix_v
    except:
        return False, True, 0, 0, 0


def scan_on_date(date, all_data, spy_df, vix_df):
    spy_ok, vix_ok, spy_p, spy_s, vix_v = get_spy_vix(date, spy_df, vix_df)
    if not spy_ok or not vix_ok:
        return [], f"BLOCKED (SPY={spy_p:.0f}<SMA50={spy_s:.0f})" if not spy_ok else f"BLOCKED (VIX={vix_v:.1f})"

    # Build RS universe for this date
    rs_vals = {}
    for t, df in all_data.items():
        if date not in df.index:
            # Skip symbols that did not trade on this benchmark market day.
            continue
        hist = df[df.index <= date]
        if len(hist) >= 65:
            ret = hist["close"].pct_change(RS_LB).iloc[-1]
            if not np.isnan(ret):
                rs_vals[t] = ret

    signals = []
    for ticker, df in all_data.items():
        if date not in df.index:
            # Avoid stale bars from non-US calendars or symbol-specific halts/holidays.
            continue
        hist = df[df.index <= date]
        if len(hist) < 65:
            continue
        c = hist["close"]; h = hist["high"]; l = hist["low"]; v = hist["volume"]
        sma20 = c.rolling(20).mean()
        sma50 = c.rolling(50).mean()
        av20 = v.rolling(20).mean().replace(0, np.nan)
        rvol = v / av20
        adr = float(((h-l)/c*100).rolling(20).mean().iloc[-1])
        dist = float(((c-sma20)/sma20.replace(0,np.nan)*100).iloc[-1]) if not np.isnan(((c-sma20)/sma20.replace(0,np.nan)*100).iloc[-1]) else 999.0
        dv = float(c.iloc[-1] * av20.iloc[-1])
        bb = c.rolling(20).std()
        inside = (c >= sma20 - bb*2) & (c <= sma20 + bb*2)
        cd = int(inside.rolling(20).sum().iloc[-1])
        lc = float(c.iloc[-1]); ls = float(sma20.iloc[-1]) if not np.isnan(sma20.iloc[-1]) else 0.0
        lr = float(rvol.iloc[-1]) if not np.isnan(rvol.iloc[-1]) else 0.0
        if lc <= ls: continue
        if lr<MIN_RVOL or adr<MIN_ADR or dist>MAX_DIST or dv<MIN_DV or cd<MIN_CONSOL or float(v.iloc[-1])<MIN_VOL: continue
        if rs_vals:
            ticker_ret = rs_vals.get(ticker, np.nan)
            if np.isnan(ticker_ret): continue
            rs_pct = float((np.array(list(rs_vals.values())) < ticker_ret).mean() * 100)
        else:
            rs_pct = 50.0
        if rs_pct < MIN_RS: continue
        score = round(rs_pct / 100, 3)
        sd = lc * T1.get("max_stop_pct", 0.08)
        # Next open price (actual from DB if available)
        future = df[df.index > date]
        next_open = float(future["open"].iloc[0]) if len(future) > 0 else None
        signals.append({
            "signal_date": str(date.date()),
            "ticker": ticker,
            "signal_price": round(lc, 4),
            "entry_price_actual": round(next_open, 4) if next_open else None,
            "slippage_pct": round((next_open - lc) / lc * 100, 3) if next_open else None,
            "entry_score": score,
            "rs_percentile": round(rs_pct, 1),
            "rvol": round(lr, 2),
            "adr_pct": round(adr, 2),
            "dist_sma20": round(dist, 2),
            "dollar_vol_M": round(dv/1e6, 2),
            "stop_price": round(lc - sd, 4),
            "tp1": round(lc + sd * T1.get("tp1_r", 1.75), 4),
            "tp2": round(lc + sd * T1.get("tp2_r", 3.75), 4),
        })
    return signals, "OK"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-02-28")
    parser.add_argument("--min_dv", type=float, default=MIN_DV)
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  HISTORICAL SIGNAL BACKTEST  |  {args.start} to {args.end}")
    print(f"{'='*70}\n")

    conn = sqlite3.connect(DB_PATH)
    spy_symbol, spy_df = load_benchmark_df(conn, ["SPY", "SPY.US", "SPY.N"], "SPY benchmark")
    _, vix_df = load_benchmark_df(conn, ["^VIX", "VIX", "VIXY"], "VIX regime proxy")
    conn.close()

    print(f"Loading OHLCV data ({args.start} to {args.end})...")
    all_data = load_all_ohlcv(args.start, args.end, args.min_dv)

    if spy_df.empty:
        print("\nERROR: No SPY benchmark data in DB. Cannot build trading calendar.")
        print("Please populate one of: SPY, SPY.US, SPY.N")
        return

    # Use real market days from benchmark (handles US holidays automatically).
    start_ts = pd.to_datetime(args.start)
    end_ts = pd.to_datetime(args.end)
    trading_days = spy_df[(spy_df.index >= start_ts) & (spy_df.index <= end_ts)].index
    trading_days = pd.DatetimeIndex(sorted(trading_days.unique()))
    if len(trading_days) == 0:
        spy_min = spy_df.index.min().date() if not spy_df.empty else "N/A"
        spy_max = spy_df.index.max().date() if not spy_df.empty else "N/A"
        print("\nERROR: No benchmark trading days in requested range.")
        print(f"  Requested: {args.start} to {args.end}")
        print(f"  {spy_symbol} available: {spy_min} to {spy_max}")
        return

    all_signals = []
    summary = []

    for date in trading_days:
        signals, status = scan_on_date(date, all_data, spy_df, vix_df)
        n = len(signals)
        summary.append({"date": str(date.date()), "status": status, "n_signals": n})
        all_signals.extend(signals)
        if "BLOCKED" in status:
            print(f"  {date.date()}: {status}")
        else:
            print(f"  {date.date()}: {n} signals" + (f" → {[s['ticker'] for s in signals[:5]]}" if signals else ""))

    # Save
    sig_df = pd.DataFrame(all_signals)
    sum_df = pd.DataFrame(summary)
    sig_path = OUTPUT_DIR / f"historical_signals_{args.start}_{args.end}.csv"
    sum_path = OUTPUT_DIR / f"daily_summary_{args.start}_{args.end}.csv"
    sig_df.to_csv(sig_path, index=False)
    sum_df.to_csv(sum_path, index=False)

    print(f"\n{'='*70}")
    print(f"  SUMMARY")
    print(f"  Total trading days: {len(summary)}")
    if "status" in sum_df.columns and not sum_df.empty:
        blocked = sum_df["status"].fillna("").str.contains("BLOCKED").sum()
        active = len(sum_df) - blocked
    else:
        blocked = 0
        active = 0
    print(f"  Blocked days: {blocked}")
    print(f"  Active days: {active}")
    print(f"  Total signals generated: {len(all_signals)}")
    if not sig_df.empty and "slippage_pct" in sig_df.columns:
        avg_slip = sig_df["slippage_pct"].dropna().mean()
        print(f"  Avg slippage (close->next open): {avg_slip:.3f}%")
    print(f"\n  Saved signals: {sig_path}")
    print(f"  Saved summary: {sum_path}")
    print(f"\n  Next step: compare with Streamlit backtest over same period")
    print(f"  Run Streamlit with: start={args.start} end={args.end}")
    print(f"{'='*70}\n")

if __name__ == "__main__": main()
