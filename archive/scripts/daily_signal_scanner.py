#!/usr/bin/env python3
import sys,json,sqlite3,argparse,warnings
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
warnings.filterwarnings("ignore")
PROJECT_ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(PROJECT_ROOT))
CONFIG_PATH=PROJECT_ROOT/"config"/"production_config.json"
DB_PATH=PROJECT_ROOT/"data"/"ticker_cache.db"
OUTPUT_DIR=PROJECT_ROOT/"outputs"/"live_signals"
OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
with open(CONFIG_PATH) as f: _cfg=json.load(f)
T1=_cfg["tier1_strategy"]; T2=_cfg["tier2_filters"]; MR=_cfg["market_regime"]
MIN_RVOL=T2.get("min_rvol",0.58); MIN_ADR=T2.get("min_adr",1.49)
MAX_DIST=T2.get("max_dist_sma20",12.84); MIN_CONSOL=T2.get("min_consolidation_days",5)
MIN_DV=T2.get("min_dollar_volume",5941884); MIN_VOL=T2.get("min_volume",100000)
MIN_RS=T2.get("min_rs_percentile",70.0); RS_LB=T2.get("rs_lookback_days",60)
MAX_VIX=MR.get("max_vix",35.0); REQ_SPY=MR.get("require_spy_above_sma50",True)
LOOK=130; MINH=65

def load_tickers(top_n=0):
    conn=sqlite3.connect(DB_PATH)
    q="SELECT ticker,AVG(close*volume) as dv FROM ohlcv_cache WHERE date>=date('now','-90 days') GROUP BY ticker HAVING COUNT(*)>=30 AND AVG(close*volume)>=? ORDER BY dv DESC"
    if top_n>0: q+=f" LIMIT {top_n}"
    rows=conn.execute(q,(MIN_DV,)).fetchall(); conn.close()
    return [r[0] for r in rows]

def load_ohlcv(ticker,days=LOOK):
    conn=sqlite3.connect(DB_PATH)
    cutoff=(datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
    rows=conn.execute("SELECT date,open,high,low,close,volume FROM ohlcv_cache WHERE ticker=? AND date>=? ORDER BY date",(ticker,cutoff)).fetchall()
    conn.close()
    if not rows: return pd.DataFrame()
    df=pd.DataFrame(rows,columns=["date","open","high","low","close","volume"])
    df["date"]=pd.to_datetime(df["date"])
    return df.set_index("date").astype(float)

def market_ok():
    ctx={"spy_ok":True,"vix_ok":True,"spy":None,"sma50":None,"vix":None}
    try:
        s=yf.download("SPY",period="60d",auto_adjust=True,progress=False,timeout=10)
        if s is not None and not s.empty:
            c=s["Close"].squeeze(); ctx["spy"]=float(c.iloc[-1]); ctx["sma50"]=float(c.rolling(50).mean().iloc[-1])
            ctx["spy_ok"]=ctx["spy"]>=ctx["sma50"] if REQ_SPY else True
    except: pass
    try:
        v=yf.download("^VIX",period="5d",auto_adjust=True,progress=False,timeout=10)
        if v is not None and not v.empty:
            ctx["vix"]=float(v["Close"].squeeze().iloc[-1]); ctx["vix_ok"]=ctx["vix"]<MAX_VIX
    except: pass
    return ctx

def scan(ticker,df,rs_df):
    if len(df)<MINH: return None
    c=df["close"]; h=df["high"]; l=df["low"]; v=df["volume"]
    sma20=c.rolling(20).mean(); sma50=c.rolling(50).mean()
    av20=v.rolling(20).mean().replace(0,np.nan); rvol=v/av20
    adr=float(((h-l)/c*100).rolling(20).mean().iloc[-1])
    dist=float(((c-sma20)/sma20.replace(0,np.nan)*100).iloc[-1]) if not np.isnan(((c-sma20)/sma20.replace(0,np.nan)*100).iloc[-1]) else 999.0
    dv=float(c.iloc[-1]*av20.iloc[-1])
    bb=c.rolling(20).std(); inside=(c>=sma20-bb*2)&(c<=sma20+bb*2)
    cd=int(inside.rolling(20).sum().iloc[-1])
    lc=float(c.iloc[-1]); ls=float(sma20.iloc[-1]) if not np.isnan(sma20.iloc[-1]) else 0.0
    lr=float(rvol.iloc[-1]) if not np.isnan(rvol.iloc[-1]) else 0.0
    ls50=float(sma50.iloc[-1]) if not np.isnan(sma50.iloc[-1]) else 0.0
    if lc<=ls: return None
    if lr<MIN_RVOL or adr<MIN_ADR or dist>MAX_DIST or dv<MIN_DV or cd<MIN_CONSOL or float(v.iloc[-1])<MIN_VOL: return None
    rs=50.0
    if not rs_df.empty and ticker in rs_df.columns:
        row=rs_df.iloc[-1].dropna(); val=row.get(ticker,np.nan)
        if not np.isnan(val): rs=float((row<val).mean()*100)
    if rs<MIN_RS: return None
    sc=round(rs/100,3)
    h52=float(h.rolling(min(252,len(h))).max().iloc[-1])
    sd=lc*T1.get("max_stop_pct",0.08)
    return {"ticker":ticker,"signal_date":str(df.index[-1].date()),"signal_price":round(lc,4),
            "entry_at":"NEXT_OPEN","entry_score":sc,"rs_percentile":round(rs,1),
            "rvol":round(lr,2),"adr_pct":round(adr,2),"dist_sma20":round(dist,2),
            "dollar_vol_M":round(dv/1e6,2),"consol_days":cd,"above_sma50":lc>ls50,
            "stop_price":round(lc-sd,4),"tp1":round(lc+sd*T1.get("tp1_r",1.75),4),
            "tp2":round(lc+sd*T1.get("tp2_r",3.75),4),"risk_$":T1.get("risk_dollars",1000)}

def main():
    parser=argparse.ArgumentParser(description="Daily signal scanner - production logic")
    parser.add_argument("--tickers",nargs="+"); parser.add_argument("--top",type=int,default=0)
    parser.add_argument("--output",type=str,default=""); parser.add_argument("--quiet",action="store_true")
    args=parser.parse_args()
    today=datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*70}\n  MOMENTUM-V2 DAILY SIGNAL SCANNER  |  {today}")
    print(f"  Config: tp1={T1['tp1_r']}R  tp2={T1['tp2_r']}R  stop={T1['max_stop_pct']*100:.0f}%  risk=${T1['risk_dollars']}\n{'='*70}\n")
    print("Checking market conditions...")
    ctx=market_ok()
    spy_s=f"${ctx['spy']:.2f} (SMA50 ${ctx['sma50']:.2f})" if ctx["spy"] else "N/A"
    vix_s=f"{ctx['vix']:.1f}" if ctx["vix"] else "N/A"
    print(f"  SPY {spy_s}  [{'OK' if ctx['spy_ok'] else 'BLOCKED'}]")
    print(f"  VIX {vix_s} (max {MAX_VIX})  [{'OK' if ctx['vix_ok'] else 'BLOCKED'}]\n")
    if not ctx["spy_ok"]: print("  MARKET BLOCKED: SPY below SMA50"); return
    if not ctx["vix_ok"]: print(f"  MARKET BLOCKED: VIX {vix_s} >= {MAX_VIX}"); return
    if args.tickers: universe=[t.upper() for t in args.tickers]
    elif args.top>0: universe=load_tickers(args.top)
    else: universe=load_tickers()
    print(f"Scanning {len(universe)} tickers...")
    all_c={}
    for t in universe:
        df=load_ohlcv(t)
        if len(df)>=MINH: all_c[t]=df["close"].pct_change(RS_LB)
    rs_df=pd.DataFrame(all_c)
    signals=[]
    for i,t in enumerate(universe,1):
        df=load_ohlcv(t)
        if df.empty or len(df)<MINH: continue
        r=scan(t,df,rs_df)
        if r: signals.append(r)
        if not args.quiet and i%500==0: print(f"  [{i}/{len(universe)}] signals: {len(signals)}")
    signals.sort(key=lambda x:x["entry_score"],reverse=True)
    print(f"\n{'='*70}\n  SIGNALS FOR TOMORROW  |  {len(signals)} found from {len(universe)} scanned\n{'='*70}")
    if signals:
        hdr=f"{'Ticker':<8} {'Score':>6} {'RS%':>5} {'RVOL':>5} {'ADR%':>5} {'Dist%':>6} {'$M':>6} {'Price':>8} {'Stop':>8} {'TP1':>8} {'TP2':>8}"
        print(f"\n{hdr}\n{'-'*len(hdr)}")
        for s in signals:
            print(f"{s['ticker']:<8} {s['entry_score']:>6.3f} {s['rs_percentile']:>5.1f} {s['rvol']:>5.2f} {s['adr_pct']:>5.2f} {s['dist_sma20']:>6.2f} {s['dollar_vol_M']:>6.1f} {s['signal_price']:>8.2f} {s['stop_price']:>8.2f} {s['tp1']:>8.2f} {s['tp2']:>8.2f}")
    else: print("\n  No signals today.")
    out=args.output or str(OUTPUT_DIR/f"signals_{today}.csv")
    if signals: pd.DataFrame(signals).to_csv(out,index=False); print(f"\n  Saved: {out}")
    print(f"\n  NOTE: Entry at NEXT DAY OPEN - do NOT enter at signal_price")
    print(f"  Risk: ${T1['risk_dollars']} | TP1={T1['tp1_r']}R/{int(T1['tp1_pct']*100)}%  TP2={T1['tp2_r']}R/{int(T1['tp2_pct']*100)}%  Runner={int(T1['runner_pct']*100)}%")
    print(f"{'='*70}\n")

if __name__=="__main__": main()