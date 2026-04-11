#!/usr/bin/env python3
"""
daily_signal_scanner.py
=======================
Genera seniales de entrada para el dia siguiente usando exactamente
la misma logica que AdvancedVectorBTEngine en produccion (ADVANCED MODE).

Uso:
    python3 daily_signal_scanner.py                 # universo completo del DB
    python3 daily_signal_scanner.py --top 200       # top 200 por dollar volume
    python3 daily_signal_scanner.py --tickers AAPL NVDA MSFT
    python3 daily_signal_scanner.py --quiet         # sin detalle por ticker

Logica identica al engine:
    Entry:  close > sma20
    TIER1:  SPY > SMA50 AND VIX < max_vix
    TIER2:  rvol, adr, dist_sma20, dollar_volume, consolidation
    RS:     percentile >= 70 en 60d lookback
    Price:  NEXT BAR OPEN (sin look-ahead bias)
"""

import sys, json, sqlite3, argparse, warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.utils.market_context_live import get_market_context_live

CONFIG_PATH = PROJECT_ROOT / "config" / "production_config.json"
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load golden config
with open(CONFIG_PATH) as f:
    _cfg = json.load(f)

T1 = _cfg["tier1_strategy"]
T2 = _cfg["tier2_filters"]
MR = _cfg["market_regime"]


MIN_RVOL = T2.get("min_rvol", 0.58)
MIN_ADR = T2.get("min_adr", 1.49)
MAX_DIST_SMA20 = T2.get("max_dist_sma20", 12.84)
MIN_CONSOL = T2.get("min_consolidation_days", 5)
MIN_DOLLAR_VOL = T2.get("min_dollar_volume", 5_941_884)
MIN_VOLUME = T2.get("min_volume", 100_000)
MIN_RS_PCT = T2.get("min_rs_percentile", 70.0)
RS_LOOKBACK = T2.get("rs_lookback_days", 60)
MAX_VIX = MR.get("max_vix", 35.0)
REQ_SPY_SMA50 = MR.get("require_spy_above_sma50", True)

LOOKBACK_DAYS = 130
MIN_HISTORY = 65


def load_tickers_from_db(top_n=0):
    conn = sqlite3.connect(DB_PATH)
    q = """

        SELECT ticker, AVG(close * volume) as avg_dv
        FROM ohlcv_cache
        WHERE date >= date('now', '-90 days')
        GROUP BY ticker
        HAVING COUNT(*) >= 30 AND AVG(close * volume) >= ?
        ORDER BY avg_dv DESC
    """
    if top_n > 0:
        q += f" LIMIT {top_n}"
    rows = conn.execute(q, (MIN_DOLLAR_VOL,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def load_ohlcv(ticker, days=LOOKBACK_DAYS):
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").astype(float)
    return df


def get_market_context():
    ctx_live = get_market_context_live(
        require_spy_above_sma50=REQ_SPY_SMA50,
        max_vix=MAX_VIX,
        db_path=DB_PATH,
    )
    ctx = {
        "spy_ok": ctx_live.get("spy_ok", True),
        "vix_ok": ctx_live.get("vix_ok", True),
        "spy_price": ctx_live.get("spy_price"),
        "spy_sma50": ctx_live.get("spy_sma50"),
        "vix": ctx_live.get("vix"),
    }
    return ctx


def scan_ticker(ticker, df, rs_universe_df):
    if len(df) < MIN_HISTORY:
        return None

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    avg_vol_20 = volume.rolling(20).mean().replace(0, np.nan)
    rvol = volume / avg_vol_20

    daily_range = (high - low) / close * 100
    adr_val = float(daily_range.rolling(20).mean().iloc[-1])

    dist_sma20 = (close - sma20) / sma20.replace(0, np.nan) * 100
    dollar_vol = float(close.iloc[-1] * avg_vol_20.iloc[-1])

    bb_std = close.rolling(20).std()
    inside_bb = (close >= sma20 - bb_std * 2) & (close <= sma20 + bb_std * 2)
    consol_days = int(inside_bb.rolling(20).sum().iloc[-1])

    last_close = float(close.iloc[-1])
    last_sma20 = float(sma20.iloc[-1]) if not np.isnan(sma20.iloc[-1]) else 0.0

    last_rvol = float(rvol.iloc[-1]) if not np.isnan(rvol.iloc[-1]) else 0.0
    last_dist = (
        float(dist_sma20.iloc[-1]) if not np.isnan(dist_sma20.iloc[-1]) else 999.0
    )
    last_sma50 = float(sma50.iloc[-1]) if not np.isnan(sma50.iloc[-1]) else 0.0

    # Entry signal: close > sma20 (ADVANCED MODE base)
    if last_close <= last_sma20:
        return None

    # TIER2 filters
    if last_rvol < MIN_RVOL:
        return None
    if adr_val < MIN_ADR:
        return None
    if last_dist > MAX_DIST_SMA20:
        return None
    if dollar_vol < MIN_DOLLAR_VOL:
        return None
    if consol_days < MIN_CONSOL:
        return None
    if float(volume.iloc[-1]) < MIN_VOLUME:
        return None

    # RS percentile (cross-sectional)
    rs_pct = 50.0
    if not rs_universe_df.empty and ticker in rs_universe_df.columns:
        last_row = rs_universe_df.iloc[-1].dropna()
        ticker_val = last_row.get(ticker, np.nan)
        if not np.isnan(ticker_val):
            rs_pct = float((last_row < ticker_val).mean() * 100)

    if rs_pct < MIN_RS_PCT:
        return None

    # Entry score (golden config: rs_weight=1.0)
    rs_score = rs_pct / 100.0
    high_52w = float(high.rolling(min(252, len(high))).max().iloc[-1])
    prox_52w = last_close / high_52w if high_52w > 0 else 0.5

    entry_score = round(1.0 * rs_score + 0.0 * prox_52w, 3)

    # Stop / TP levels (reference for paper trading)
    stop_dist = last_close * T1.get("max_stop_pct", 0.08)
    stop_price = round(last_close - stop_dist, 4)
    tp1_price = round(last_close + stop_dist * T1.get("tp1_r", 1.75), 4)
    tp2_price = round(last_close + stop_dist * T1.get("tp2_r", 3.75), 4)

    return {
        "ticker": ticker,
        "signal_date": str(df.index[-1].date()),
        "signal_price": round(last_close, 4),
        "entry_at": "NEXT_OPEN",
        "entry_score": entry_score,
        "rs_percentile": round(rs_pct, 1),
        "rvol": round(last_rvol, 2),
        "adr_pct": round(adr_val, 2),
        "dist_sma20": round(last_dist, 2),
        "dollar_vol_M": round(dollar_vol / 1e6, 2),
        "consol_days": consol_days,
        "above_sma50": last_close > last_sma50,
        "stop_price": stop_price,
        "tp1": tp1_price,
        "tp2": tp2_price,
        "risk_$": T1.get("risk_dollars", 1000),
    }


def main():
    parser = argparse.ArgumentParser(description="Daily signal scanner")
    parser.add_argument("--tickers", nargs="+")
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'=' * 70}")
    print(f"  MOMENTUM-V2 DAILY SIGNAL SCANNER  |  {today}")
    print(
        f"  Config: tp1={T1['tp1_r']}R  tp2={T1['tp2_r']}R  "
        f"stop={T1['max_stop_pct'] * 100:.0f}%  risk=${T1['risk_dollars']}"
    )
    print(f"{'=' * 70}\n")

    # Market context
    print("Checking market conditions...")
    ctx = get_market_context()
    spy_ok = "OK" if ctx["spy_ok"] else "BLOCKED"
    vix_ok = "OK" if ctx["vix_ok"] else "BLOCKED"
    spy_p = f"${ctx['spy_price']:.2f}" if ctx["spy_price"] else "N/A"

    sma_p = f"(SMA50 ${ctx['spy_sma50']:.2f})" if ctx["spy_sma50"] else ""
    vix_v = f"{ctx['vix']:.1f}" if ctx["vix"] else "N/A"
    print(f"  SPY {spy_p} {sma_p}  [{spy_ok}]")
    print(f"  VIX {vix_v} (max {MAX_VIX})  [{vix_ok}]")

    if not ctx["spy_ok"]:
        print("\n  MARKET BLOCKED: SPY below SMA50 — no new entries today")
        return
    if not ctx["vix_ok"]:
        print(f"\n  MARKET BLOCKED: VIX {vix_v} >= {MAX_VIX} — no new entries today")
        return
    print()

    # Universe
    if args.tickers:
        universe = [t.upper() for t in args.tickers]
    elif args.top > 0:
        universe = load_tickers_from_db(top_n=args.top)
    else:
        universe = load_tickers_from_db(top_n=0)
    print(f"Scanning {len(universe)} tickers...")

    # Load RS universe
    all_closes = {}
    for t in universe:
        df = load_ohlcv(t)

        if len(df) >= MIN_HISTORY:
            all_closes[t] = df["close"].pct_change(RS_LOOKBACK)
    rs_universe_df = pd.DataFrame(all_closes)

    # Scan
    signals = []
    for i, ticker in enumerate(universe, 1):
        df = load_ohlcv(ticker)
        if df.empty or len(df) < MIN_HISTORY:
            continue
        r = scan_ticker(ticker, df, rs_universe_df)
        if r:
            signals.append(r)
        if not args.quiet and i % 500 == 0:
            print(f"  [{i}/{len(universe)}] signals: {len(signals)}")

    signals.sort(key=lambda x: x["entry_score"], reverse=True)

    # Display
    print(f"\n{'=' * 70}")
    print(
        f"  SIGNALS FOR TOMORROW  |  {len(signals)} found from {len(universe)} scanned"
    )
    print(f"{'=' * 70}")
    if signals:
        hdr = f"{'Ticker':<8} {'Score':>6} {'RS%':>5} {'RVOL':>5} {'ADR%':>5} {'Dist%':>6} {'$M':>6} {'Price':>8} {'Stop':>8} {'TP1':>8} {'TP2':>8}"
        print(f"\n{hdr}")
        print("-" * len(hdr))
        for s in signals:
            print(
                f"{s['ticker']:<8} {s['entry_score']:>6.3f} {s['rs_percentile']:>5.1f} "
                f"{s['rvol']:>5.2f} {s['adr_pct']:>5.2f} {s['dist_sma20']:>6.2f} "
                f"{s['dollar_vol_M']:>6.1f} {s['signal_price']:>8.2f} "
                f"{s['stop_price']:>8.2f} {s['tp1']:>8.2f} {s['tp2']:>8.2f}"
            )
    else:
        print("\n  No signals today.")

    # Save
    out = args.output or str(OUTPUT_DIR / f"signals_{today}.csv")
    if signals:
        pd.DataFrame(signals).to_csv(out, index=False)
        print(f"\n  Saved to: {out}")

    print(f"\n  NOTE: Entry at NEXT DAY OPEN — do NOT enter at signal_price")
    print(
        f"  Risk: ${T1['risk_dollars']} | Exits: TP1={T1['tp1_r']}R/{int(T1['tp1_pct'] * 100)}%  "
        f"TP2={T1['tp2_r']}R/{int(T1['tp2_pct'] * 100)}%  Runner={int(T1['runner_pct'] * 100)}%"
    )
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
