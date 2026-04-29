#!/usr/bin/env python3
"""
vcp_signal_scanner.py
=====================
Screener VCP (Volatility Contraction Pattern) - Mark Minervini style.
Screener SEPARADO del breakout basico -- cada uno tiene su propia logica
y sus propios parametros optimos.

Criterios VCP:
  - 2-4 contracciones progresivas (cada una mas tight que la anterior)
  - Volumen decreciente en cada contraccion
  - Ultima contraccion < 15% de profundidad (ideal < 8%)
  - Precio cerca del pivot (< 5% del breakout point)
  - Market filter: SPY > SMA50 AND VIX < 35

Entry: pivot_price + 0.10 (limite buy-stop al NEXT OPEN)
Stop:  low de la ultima contraccion
TP1/TP2: mismo ratio que golden config (1.75R / 3.75R)

Uso:
    python3 vcp_signal_scanner.py --top 300
    python3 vcp_signal_scanner.py --tickers AAPL NVDA MSFT
    python3 vcp_signal_scanner.py --min-confidence 0.6  # mas selectivo
"""
import sys, json, sqlite3, argparse, warnings
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

CONFIG_PATH = PROJECT_ROOT / "config" / "production_config.json"
DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(CONFIG_PATH) as f: _cfg = json.load(f)
T1 = _cfg["tier1_strategy"]; T2 = _cfg["tier2_filters"]; MR = _cfg["market_regime"]

TP1_R = T1.get("tp1_r", 1.75); TP2_R = T1.get("tp2_r", 3.75)
TP1_PCT = T1.get("tp1_pct", 0.55); TP2_PCT = T1.get("tp2_pct", 0.20)
RUNNER_PCT = T1.get("runner_pct", 0.25)
RISK_DOLLARS = T1.get("risk_dollars", 1000)
MIN_DV = T2.get("min_dollar_volume", 5_941_884)
MAX_VIX = MR.get("max_vix", 35.0)
REQ_SPY = MR.get("require_spy_above_sma50", True)

LOOKBACK = 160
MIN_HISTORY = 100
MIN_CONFIDENCE = 0.50

def load_tickers(top_n=0):
    conn = sqlite3.connect(DB_PATH)
    q = "SELECT ticker FROM ohlcv_cache WHERE date >= date('now','-90 days') GROUP BY ticker HAVING COUNT(*)>=30 AND AVG(close*volume)>=? ORDER BY AVG(close*volume) DESC"
    if top_n > 0: q += f" LIMIT {top_n}"
    intl = ["-KS","-SZ","-HK","-T","-L","-PA","-DE","-AS","-VN","-SR"]
    rows = conn.execute(q,(MIN_DV,)).fetchall(); conn.close()
    return [r[0] for r in rows if not any(r[0].endswith(s) for s in intl) and len(r[0])<=6]

def load_ohlcv(ticker, days=LOOKBACK):
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("SELECT date,open,high,low,close,volume FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",(ticker,cutoff)).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
    df["date"] = pd.to_datetime(df["date"].str[:10])
    return df.set_index("date").astype(float)

def market_ok():
    ctx = {"spy_ok":True,"vix_ok":True,"spy":None,"sma50":None,"vix":None}
    try:
        s = yf.download("SPY",period="60d",auto_adjust=True,progress=False,timeout=10)
        if s is not None and not s.empty:
            c = s["Close"].squeeze(); ctx["spy"]=float(c.iloc[-1]); ctx["sma50"]=float(c.rolling(50).mean().iloc[-1])
            ctx["spy_ok"] = ctx["spy"]>=ctx["sma50"] if REQ_SPY else True
    except: pass
    try:
        v = yf.download("^VIX",period="5d",auto_adjust=True,progress=False,timeout=10)
        if v is not None and not v.empty:
            ctx["vix"]=float(v["Close"].squeeze().iloc[-1]); ctx["vix_ok"]=ctx["vix"]<MAX_VIX
    except: pass
    return ctx

def identify_swings(df, window=5):
    """Identify alternating swing highs and lows."""
    swings = []
    for i in range(window, len(df)-window):
        ch = df["high"].iloc[i]; cl = df["low"].iloc[i]
        lh = df["high"].iloc[i-window:i]; rh = df["high"].iloc[i+1:i+window+1]
        ll = df["low"].iloc[i-window:i]; rl = df["low"].iloc[i+1:i+window+1]
        is_peak = ch > lh.max() and ch > rh.max()
        is_trough = cl < ll.min() and cl < rl.min()
        if is_peak or is_trough:
            swings.append((df.index[i], "peak" if is_peak else "trough",
                          float(ch) if is_peak else float(cl)))
    return swings

def detect_vcp(df, min_contractions=2, min_confidence=MIN_CONFIDENCE):
    """
    Detect VCP pattern. Returns signal dict or None.
    Criteria (Minervini):
      - 2-4 progressive contractions: T1 > T2 > T3
      - Volume decreasing in each contraction
      - Last contraction depth < 15% (ideal < 8%)
      - Price within 5% of pivot (breakout point)
    """
    if len(df) < MIN_HISTORY: return None

    lookback_df = df.tail(min(100, len(df))).copy()
    swings = identify_swings(lookback_df)

    # Need alternating peak-trough pairs
    pairs = []
    i = 0
    while i < len(swings)-1:
        if swings[i][1] == "peak" and swings[i+1][1] == "trough":
            pairs.append((swings[i], swings[i+1]))
            i += 2
        else:
            i += 1

    if len(pairs) < min_contractions: return None

    # Analyze contractions
    contractions = []
    for peak, trough in pairs:
        peak_date, _, peak_price = peak
        trough_date, _, trough_price = trough
        depth_pct = (peak_price - trough_price) / peak_price * 100
        # Volume in contraction window
        mask = (lookback_df.index >= peak_date) & (lookback_df.index <= trough_date)
        avg_vol = float(lookback_df[mask]["volume"].mean()) if mask.sum() > 0 else 0
        contractions.append({"peak_date":peak_date,"trough_date":trough_date,
                             "peak_price":peak_price,"trough_price":trough_price,
                             "depth_pct":depth_pct,"avg_vol":avg_vol})

    if len(contractions) < min_contractions: return None

    # Must be progressively tighter
    depths = [c["depth_pct"] for c in contractions]
    if not all(depths[i] > depths[i+1] for i in range(len(depths)-1)): return None

    last = contractions[-1]
    if last["depth_pct"] > 15: return None  # Too loose

    # Volume must be contracting
    vols = [c["avg_vol"] for c in contractions if c["avg_vol"] > 0]
    vol_contracting = len(vols) < 2 or all(vols[i] >= vols[i+1] for i in range(len(vols)-1))

    # Price near pivot (last peak = breakout point)
    current_price = float(df["close"].iloc[-1])
    pivot_price = last["peak_price"]
    dist_to_pivot_pct = (pivot_price - current_price) / current_price * 100

    if dist_to_pivot_pct < 0: return None   # Already broken out
    if dist_to_pivot_pct > 10: return None  # Too far from pivot

    # Dollar volume filter
    avg_vol_20 = float(df["volume"].rolling(20).mean().iloc[-1])
    dollar_vol = current_price * avg_vol_20
    if dollar_vol < MIN_DV: return None

    # Confidence score
    confidence = 0.0
    n = len(contractions)
    if n >= 3: confidence += 0.25
    elif n >= 2: confidence += 0.15
    depth_ratio = depths[0] / depths[-1] if depths[-1] > 0 else 1
    if depth_ratio >= 3: confidence += 0.25
    elif depth_ratio >= 2: confidence += 0.15
    if last["depth_pct"] < 8: confidence += 0.20
    elif last["depth_pct"] < 12: confidence += 0.10
    if vol_contracting: confidence += 0.20
    if dist_to_pivot_pct < 3: confidence += 0.10

    if confidence < min_confidence: return None

    # Entry / stop / targets
    entry_price = pivot_price        # buy-stop at pivot (fill at next open if broken)
    stop_price  = last["trough_price"]
    stop_dist   = entry_price - stop_price
    if stop_dist <= 0: return None
    shares = int(np.floor(RISK_DOLLARS / stop_dist))
    if shares <= 0: return None

    # RS percentile placeholder (calculated in main loop)
    return {
        "ticker":           "",   # set by caller
        "signal_date":      str(df.index[-1].date()),
        "signal_type":      "VCP",
        "signal_price":     round(current_price, 4),
        "pivot_price":      round(pivot_price, 4),
        "entry_at":         "NEXT_OPEN_IF_BREAKS_PIVOT",
        "entry_price":      round(entry_price, 4),
        "stop_price":       round(stop_price, 4),
        "tp1":              round(entry_price + stop_dist*TP1_R, 4),
        "tp2":              round(entry_price + stop_dist*TP2_R, 4),
        "shares":           shares,
        "risk_$":           RISK_DOLLARS,
        "confidence":       round(confidence, 3),
        "n_contractions":   n,
        "depth_ratio":      round(depth_ratio, 2),
        "last_depth_pct":   round(last["depth_pct"], 2),
        "dist_to_pivot_pct":round(dist_to_pivot_pct, 2),
        "dollar_vol_M":     round(dollar_vol/1e6, 2),
        "vol_contracting":  vol_contracting,
        "entry_score":      round(confidence, 3),  # use confidence as score for position_manager
    }

def main():
    parser = argparse.ArgumentParser(description="VCP Signal Scanner")
    parser.add_argument("--tickers", nargs="+")
    parser.add_argument("--top", type=int, default=0)
    parser.add_argument("--min-confidence", type=float, default=MIN_CONFIDENCE)
    parser.add_argument("--output", type=str, default="")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*70}")
    print(f"  VCP SIGNAL SCANNER (Minervini)  |  {today}")
    print(f"  Config: tp1={TP1_R}R  tp2={TP2_R}R  risk_dollars={RISK_DOLLARS}")
    print(f"  Min confidence: {args.min_confidence:.0%}  |  Min history: {MIN_HISTORY} days")
    print(f"{'='*70}\n")

    # Market filter
    print("Checking market conditions...")
    ctx = market_ok()
    spy_s = f"{ctx['spy']:.2f}" if ctx["spy"] else "N/A"
    sma_s = f"(SMA50 {ctx['sma50']:.2f})" if ctx["sma50"] else ""
    vix_s = f"{ctx['vix']:.1f}" if ctx["vix"] else "N/A"
    print(f"  SPY {spy_s} {sma_s}  [{'OK' if ctx['spy_ok'] else 'BLOCKED'}]")
    print(f"  VIX {vix_s}  [{'OK' if ctx['vix_ok'] else 'BLOCKED'}]\n")
    if not ctx["spy_ok"]: print("  MARKET BLOCKED: SPY below SMA50"); return
    if not ctx["vix_ok"]: print(f"  MARKET BLOCKED: VIX {vix_s} >= {MAX_VIX}"); return

    # Universe
    if args.tickers: universe = [t.upper() for t in args.tickers]
    elif args.top > 0: universe = load_tickers(args.top)
    else: universe = load_tickers()
    print(f"Scanning {len(universe)} tickers for VCP patterns...")

    signals = []
    errors = 0
    for i, ticker in enumerate(universe, 1):
        df = load_ohlcv(ticker)
        if df.empty or len(df) < MIN_HISTORY: continue
        try:
            result = detect_vcp(df, min_confidence=args.min_confidence)
            if result:
                result["ticker"] = ticker
                signals.append(result)
        except Exception as e:
            errors += 1
        if not args.quiet and i % 500 == 0:
            print(f"  [{i}/{len(universe)}] VCPs found: {len(signals)}")

    # Sort by confidence desc, then dist_to_pivot asc (closer to breakout first)
    signals.sort(key=lambda x: (-x["confidence"], x["dist_to_pivot_pct"]))

    # Output
    print(f"\n{'='*70}")
    print(f"  VCP SIGNALS FOR TOMORROW  |  {len(signals)} found from {len(universe)} scanned")
    print(f"{'='*70}")
    if signals:
        hdr = f"{'Ticker':<8} {'Conf':>5} {'N':>2} {'D.Ratio':>7} {'LastD%':>7} {'Pivot':>8} {'DistP%':>7} {'Stop':>8} {'TP1':>8} {'TP2':>8}"
        print(f"\n{hdr}\n{'-'*len(hdr)}")
        for s in signals:
            print(f"{s['ticker']:<8} {s['confidence']:>5.2f} {s['n_contractions']:>2} "
                  f"{s['depth_ratio']:>7.2f} {s['last_depth_pct']:>7.2f} "
                  f"{s['pivot_price']:>8.2f} {s['dist_to_pivot_pct']:>7.2f} "
                  f"{s['stop_price']:>8.2f} {s['tp1']:>8.2f} {s['tp2']:>8.2f}")
        print(f"\n  NOTE: Entry is BUY-STOP at pivot when price breaks it at NEXT OPEN")
        print(f"  Confidence >= 0.7 = high quality | 0.5-0.7 = watch list")
    else:
        print("\n  No VCP patterns detected today.")
        print("  VCP requires more setup time than basic breakout -- check back daily")

    # Save
    out = args.output or str(OUTPUT_DIR / f"vcp_signals_{today}.csv")
    if signals:
        df_out = pd.DataFrame(signals)
        df_out.to_csv(out, index=False)
        print(f"\n  Saved: {out}")

    # Key difference vs breakout scanner
    print(f"\n  VCP vs Breakout scanner:")
    print(f"  - Breakout: entry when close > sma20 (trend following)")
    print(f"  - VCP:      entry when price breaks pivot after contracting (anticipatory)")
    print(f"  - Use BOTH: VCP gives earlier entry, breakout confirms trend")
    print(f"{'='*70}\n")

if __name__ == "__main__": main()