#!/usr/bin/env python3
import json,sqlite3
from datetime import datetime,timedelta
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT=Path(__file__).resolve().parent
CONFIG_PATH=PROJECT_ROOT/"config"/"production_config.json"
PAPER_DIR=PROJECT_ROOT/"outputs"/"paper_trading"
PAPER_DIR.mkdir(parents=True,exist_ok=True)
POS_FILE=PAPER_DIR/"positions.json"
TRADES_FILE=PAPER_DIR/"paper_trades.csv"
CAPITAL_FILE=PAPER_DIR/"capital.json"
with open(CONFIG_PATH) as f: _cfg=json.load(f)
T1=_cfg["tier1_strategy"]; T3=_cfg.get("tier3_risk",{})
RISK_DOLLARS=T1.get("risk_dollars",1000)
MAX_STOP_PCT=T1.get("max_stop_pct",0.08)
TP1_R=T1.get("tp1_r",1.75); TP2_R=T1.get("tp2_r",3.75)
TP1_PCT=T1.get("tp1_pct",0.55); TP2_PCT=T1.get("tp2_pct",0.20); RUNNER_PCT=T1.get("runner_pct",0.25)
MAX_EXPOSURE_PCT=T3.get("max_exposure_pct",0.65)

class Position:
    def __init__(self,ticker,entry_date,entry_price,shares,stop_price,tp1_price,tp2_price,entry_score=0.0):
        self.ticker=ticker; self.entry_date=entry_date; self.entry_price=entry_price
        self.shares=shares; self.shares_orig=shares; self.stop_price=stop_price
        self.tp1_price=tp1_price; self.tp2_price=tp2_price; self.entry_score=entry_score
        self.tp1_done=False; self.tp2_done=False; self.be_done=False
        self.status="OPEN"; self.pnl=0.0
    def cost(self): return self.entry_price*self.shares
    def current_value(self,price): return price*self.shares
    def unrealized_pnl(self,price): return (price-self.entry_price)*self.shares
    def r_multiple(self,price):
        rps=abs(self.entry_price-self.stop_price)
        return (price-self.entry_price)/rps if rps>0 else 0.0
    def to_dict(self): return self.__dict__
    @classmethod
    def from_dict(cls,d):
        p=cls.__new__(cls); p.__dict__.update(d); return p

class PositionManager:
    def __init__(self,initial_capital=100_000.0):
        self.initial_capital=initial_capital; self.cash=initial_capital
        self.positions={}; self.trades_log=[]

    def save(self):
        json.dump({"cash":self.cash,"initial_capital":self.initial_capital,"last_updated":datetime.now().isoformat()},open(CAPITAL_FILE,"w"),indent=2)
        json.dump({k:v.to_dict() for k,v in self.positions.items()},open(POS_FILE,"w"),indent=2,default=str)
        if self.trades_log:
            df=pd.DataFrame(self.trades_log)
            if TRADES_FILE.exists(): df=pd.concat([pd.read_csv(TRADES_FILE),df]).drop_duplicates()
            df.to_csv(TRADES_FILE,index=False)
        print(f"  Saved: {len(self.positions)} positions | cash=")

    def load(self):
        if CAPITAL_FILE.exists():
            s=json.load(open(CAPITAL_FILE)); self.cash=s["cash"]; self.initial_capital=s.get("initial_capital",self.initial_capital)
        if POS_FILE.exists():
            self.positions={k:Position.from_dict(v) for k,v in json.load(open(POS_FILE)).items()}
        print(f"  Loaded: {len(self.positions)} positions | cash=")

    def equity(self,prices=None):
        return self.cash+sum(p.current_value(prices.get(p.ticker,p.entry_price) if prices else p.entry_price) for p in self.positions.values())

    def invested(self,prices=None): return self.equity(prices)-self.cash
    def exposure_pct(self,prices=None):
        eq=self.equity(prices); return self.invested(prices)/eq if eq>0 else 0.0

    def process_signals(self,signals,prices=None):
        """Mirrors numba_core entry logic: max exposure -> sort by score -> size -> cash check."""
        eq=self.equity(prices); inv=self.invested(prices); max_inv=eq*MAX_EXPOSURE_PCT
        orders=[]
        print(f"\n  Portfolio: equity= | invested= | exposure={inv/eq*100 if eq>0 else 0:.1f}% (max {MAX_EXPOSURE_PCT*100:.0f}%)")
        if inv>=max_inv: print(f"  MAX EXPOSURE — no new entries"); return []
        available=[s for s in signals if s.get("ticker") not in self.positions]
        if not available: print("  All signals already in positions"); return []
        available.sort(key=lambda x:x.get("entry_score",0),reverse=True)
        for sig in available:
            if inv>=max_inv: break
            ticker=sig["ticker"]; price=sig["signal_price"]
            stop=sig.get("stop_price",price*(1-MAX_STOP_PCT)); sd=price-stop
            if sd<=0: continue
            shares=int(np.floor(RISK_DOLLARS/sd))
            if shares<=0: continue
            cost=shares*price
            if self.cash<cost: print(f"  SKIP {ticker}: need  have "); continue
            tp1=sig.get("tp1",price+sd*TP1_R); tp2=sig.get("tp2",price+sd*TP2_R)
            orders.append({"action":"BUY","ticker":ticker,"signal_date":sig.get("signal_date",""),"entry_at":"NEXT_OPEN",
                "signal_price":round(price,4),"shares":shares,"risk_$":RISK_DOLLARS,
                "stop_price":round(stop,4),"tp1":round(tp1,4),"tp1_shares":int(np.floor(shares*TP1_PCT)),
                "tp2":round(tp2,4),"tp2_shares":int(np.floor(shares*TP2_PCT)),"runner_shares":int(np.floor(shares*RUNNER_PCT)),
                "entry_score":sig.get("entry_score",0),"rs_percentile":sig.get("rs_percentile",0),"cost_approx":round(cost,2)})
            self.cash-=cost; inv+=cost
        return orders

    def record_entry(self,ticker,entry_date,entry_price,shares,stop_price,tp1_price,tp2_price,entry_score=0.0):
        pos=Position(ticker,entry_date,entry_price,shares,stop_price,tp1_price,tp2_price,entry_score)
        self.positions[ticker]=pos
        print(f"  ENTERED {ticker}: {shares}sh @  | stop= | tp1= | tp2=")

    def record_exit(self,ticker,exit_date,exit_price,shares_exited,exit_type):
        if ticker not in self.positions: print(f"  WARNING: {ticker} not in positions"); return
        pos=self.positions[ticker]; pnl=(exit_price-pos.entry_price)*shares_exited
        self.cash+=exit_price*shares_exited; pos.shares-=shares_exited; pos.pnl+=pnl
        if exit_type=="TP1": pos.tp1_done=True
        if exit_type=="TP2": pos.tp2_done=True
        print(f"  EXIT {ticker} [{exit_type}]: {shares_exited}sh @  | PnL=")
        rps=abs(pos.entry_price-pos.stop_price)
        self.trades_log.append({"ticker":ticker,"exit_date":exit_date,"exit_type":exit_type,
            "entry_price":pos.entry_price,"exit_price":exit_price,"shares":shares_exited,"pnl":round(pnl,2),
            "r_multiple":round((exit_price-pos.entry_price)/rps,3) if rps>0 else 0})
        if pos.shares<=0: del self.positions[ticker]; print(f"    Closed. Total PnL=")

    def report(self,prices=None):
        eq=self.equity(prices); pnl=eq-self.initial_capital
        print(f"\n{'='*60}\n  PORTFOLIO  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  Capital:  ")
        print(f"  Equity:     ({pnl:+,.2f} / {pnl/self.initial_capital*100:+.2f}%)")
        print(f"  Cash:     ")
        print(f"  Exposure: {self.exposure_pct(prices)*100:.1f}% (max {MAX_EXPOSURE_PCT*100:.0f}%)")
        print(f"  Open:     {len(self.positions)} positions")
        if self.positions:
            print(f"\n  {'Ticker':<8} {'Shares':>6} {'Entry':>8} {'Stop':>8} {'TP1':>8} {'Score':>6}")
            print(f"  {'-'*50}")
            for t,pos in self.positions.items():
                cur=prices.get(t,pos.entry_price) if prices else pos.entry_price
                print(f"  {t:<8} {pos.shares:>6} {pos.entry_price:>8.2f} {pos.stop_price:>8.2f} {pos.tp1_price:>8.2f} {pos.entry_score:>6.3f}  UPnL=  {pos.r_multiple(cur):+.2f}R")
        if TRADES_FILE.exists():
            hist=pd.read_csv(TRADES_FILE)
            if len(hist)>0:
                wr=(hist["pnl"]>0).mean(); w=hist[hist["pnl"]>0]["pnl"].sum(); l=abs(hist[hist["pnl"]<0]["pnl"].sum())
                print(f"\n  History ({len(hist)} trades): WR={wr:.1%}  PF={w/l:.2f if l>0 else 'INF'}  PnL=")
        print(f"{'='*60}\n")


if __name__=="__main__":
    import argparse,sys
    pa=argparse.ArgumentParser(description="Position Manager CLI")
    pa.add_argument("command",choices=["report","scan","enter","exit","reset"])
    pa.add_argument("--ticker",type=str); pa.add_argument("--price",type=float)
    pa.add_argument("--shares",type=int); pa.add_argument("--type",type=str,default="STOP")
    pa.add_argument("--capital",type=float,default=100_000)
    args=pa.parse_args()
    pm=PositionManager(initial_capital=args.capital)
    if args.command=="reset":
        pm.save(); print(f"  Reset: capital=")
    elif args.command=="report":
        pm.load(); pm.report()
    elif args.command=="scan":
        pm.load()
        today=datetime.now().strftime("%Y-%m-%d")
        sig_path=PROJECT_ROOT/"outputs"/"live_signals"/f"signals_{today}.csv"
        if not sig_path.exists(): print(f"  No signals for today. Run: python3 daily_signal_scanner.py"); sys.exit(1)
        signals=pd.read_csv(sig_path).to_dict("records")
        print(f"  Loaded {len(signals)} signals")
        orders=pm.process_signals(signals)
        if orders:
            print(f"\n  ORDERS FOR TOMORROW ({len(orders)}):")
            print(f"  {'Ticker':<8} {'Shares':>6} {'~Price':>8} {'Stop':>8} {'TP1':>8} {'TP2':>8} {'Score':>6}")
            print(f"  {'-'*60}")
            for o in orders:
                print(f"  {o['ticker']:<8} {o['shares']:>6} {o['signal_price']:>8.2f} {o['stop_price']:>8.2f} {o['tp1']:>8.2f} {o['tp2']:>8.2f} {o['entry_score']:>6.3f}")
            pd.DataFrame(orders).to_csv(PAPER_DIR/f"orders_{today}.csv",index=False)
            print(f"  Saved: outputs/paper_trading/orders_{today}.csv")
        else: print("  No orders.")
        pm.save()
    elif args.command=="enter":
        if not all([args.ticker,args.price,args.shares]): print("  Usage: enter --ticker AAPL --price 195.50 --shares 12"); sys.exit(1)
        pm.load(); sd=args.price*MAX_STOP_PCT
        pm.record_entry(args.ticker,datetime.now().strftime("%Y-%m-%d"),args.price,args.shares,
            args.price-sd,args.price+sd*TP1_R,args.price+sd*TP2_R); pm.save(); pm.report()
    elif args.command=="exit":
        if not all([args.ticker,args.price,args.shares]): print("  Usage: exit --ticker AAPL --price 210 --shares 7 --type TP1"); sys.exit(1)
        pm.load(); pm.record_exit(args.ticker,datetime.now().strftime("%Y-%m-%d"),args.price,args.shares,args.type); pm.save(); pm.report()