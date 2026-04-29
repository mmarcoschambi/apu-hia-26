#!/usr/bin/env python3
"""
position_manager.py
===================
Gestiona posiciones de paper trading con logica de regime de mercado.

Nuevas features:
  - review_positions_by_regime(): ajusta stops segun estado del mercado
  - merge multi-señal: lee breakout + vcp + futuros CSVs
  - breadth check: % acciones sobre SMA50 como filtro adicional
  - comando 'review' en CLI para ejecutar revision diaria de posiciones
"""
import json, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH  = PROJECT_ROOT / "config" / "production_config.json"
PAPER_DIR    = PROJECT_ROOT / "outputs" / "paper_trading"
PAPER_DIR.mkdir(parents=True, exist_ok=True)
POS_FILE     = PAPER_DIR / "positions.json"
TRADES_FILE  = PAPER_DIR / "paper_trades.csv"
CAPITAL_FILE = PAPER_DIR / "capital.json"
REVIEW_FILE  = PAPER_DIR / "stop_review.csv"

with open(CONFIG_PATH) as f: _cfg = json.load(f)
T1 = _cfg["tier1_strategy"]; T3 = _cfg.get("tier3_risk", {})
RISK_DOLLARS    = T1.get("risk_dollars", 1000)
MAX_STOP_PCT    = T1.get("max_stop_pct", 0.08)
TP1_R           = T1.get("tp1_r", 1.75); TP2_R = T1.get("tp2_r", 3.75)
TP1_PCT         = T1.get("tp1_pct", 0.55); TP2_PCT = T1.get("tp2_pct", 0.20)
RUNNER_PCT      = T1.get("runner_pct", 0.25)
MAX_EXPOSURE_PCT = T3.get("max_exposure_pct", 0.65)

# ── Breadth thresholds ────────────────────────────────────────────────────────
BREADTH_GREEN  = 40.0   # >40% acciones sobre SMA50 = mercado sano
BREADTH_YELLOW = 25.0   # 25-40% = cautela, reducir riesgo
# <25% = rojo, no nuevas entradas aunque SPY este sobre SMA50

# ── Stop tightening por regime ────────────────────────────────────────────────
# Cuando el mercado esta rojo y la posicion no llego a TP1:
# el nuevo stop es entry_price - (stop_dist_original * TIGHT_FACTOR)
TIGHT_FACTOR_RED    = 0.50   # stop a 50% del riesgo original
TIGHT_FACTOR_YELLOW = 0.75   # stop a 75% del riesgo original


def get_market_breadth() -> dict:
    """
    Descarga % de acciones del S&P500 sobre su SMA50 via yfinance.
    Ticker: ^SP500-50 no siempre disponible; usamos proxy RSP/SPY.
    Alternativa mas confiable: calcular desde la DB local si hay suficientes tickers.
    Retorna dict con keys: pct_above_sma50, status (GREEN/YELLOW/RED), spy_ok, vix
    """
    result = {"pct_above_sma50": None, "status": "UNKNOWN",
              "spy_ok": True, "vix": None, "spy": None, "sma50": None}
    try:
        import yfinance as yf
        # SPY vs SMA50
        spy = yf.download("SPY", period="60d", auto_adjust=True, progress=False, timeout=10)
        if spy is not None and not spy.empty:
            c = spy["Close"].squeeze()
            result["spy"]   = float(c.iloc[-1])
            result["sma50"] = float(c.rolling(50).mean().iloc[-1])
            result["spy_ok"] = result["spy"] >= result["sma50"]
        # VIX
        vix = yf.download("^VIX", period="5d", auto_adjust=True, progress=False, timeout=10)
        if vix is not None and not vix.empty:
            result["vix"] = float(vix["Close"].squeeze().iloc[-1])
    except Exception:
        pass

    # Intentar breadth desde DB local (rapido, no requiere yfinance extra)
    try:
        import sqlite3 as _sq
        db = PROJECT_ROOT / "data" / "ticker_cache.db"
        conn = _sq.connect(db)
        cutoff = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT ticker, date, close FROM ohlcv_cache "
            "WHERE date >= ? ORDER BY ticker, date", (cutoff,)
        ).fetchall()
        conn.close()
        if rows:
            df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values(["ticker", "date"])
            df["sma50"] = df.groupby("ticker")["close"].transform(lambda x: x.rolling(50, min_periods=30).mean())
            last = df.sort_values("date").groupby("ticker").last().dropna(subset=["sma50"])
            pct = (last["close"] > last["sma50"]).mean() * 100
            result["pct_above_sma50"] = round(pct, 1)
    except Exception:
        pass

    # Determinar status
    pct = result["pct_above_sma50"]
    spy_ok = result["spy_ok"]
    vix    = result["vix"] or 0
    if not spy_ok or (pct is not None and pct < BREADTH_YELLOW) or vix > 35:
        result["status"] = "RED"
    elif pct is not None and pct < BREADTH_GREEN:
        result["status"] = "YELLOW"
    elif spy_ok and (pct is None or pct >= BREADTH_GREEN):
        result["status"] = "GREEN"
    return result


def load_all_signals(today: str) -> list:
    """
    Merge de señales de todos los scanners disponibles.
    Lee: signals_DATE.csv (breakout) + vcp_signals_DATE.csv + futuros.
    """
    sig_dir = PROJECT_ROOT / "outputs" / "live_signals"
    patterns = [
        f"signals_{today}.csv",
        f"vcp_signals_{today}.csv",
        f"pocket_pivot_signals_{today}.csv",
        f"flat_base_signals_{today}.csv",
    ]
    all_signals = []
    for fname in patterns:
        path = sig_dir / fname
        if path.exists():
            try:
                df = pd.read_csv(path)
                if "signal_type" not in df.columns:
                    # inferir desde nombre de archivo
                    if "vcp" in fname:        df["signal_type"] = "VCP"
                    elif "pocket" in fname:   df["signal_type"] = "POCKET_PIVOT"
                    elif "flat" in fname:     df["signal_type"] = "FLAT_BASE"
                    else:                     df["signal_type"] = "BREAKOUT"
                all_signals.extend(df.to_dict("records"))
                print(f"  Loaded {len(df)} signals from {fname}")
            except Exception as e:
                print(f"  WARN: could not load {fname}: {e}")
    return all_signals


class Position:
    def __init__(self, ticker, entry_date, entry_price, shares, stop_price,
                 tp1_price, tp2_price, entry_score=0.0, signal_type="BREAKOUT"):
        self.ticker       = ticker
        self.entry_date   = entry_date
        self.entry_price  = entry_price
        self.shares       = shares
        self.shares_orig  = shares
        self.stop_price   = stop_price
        self.tp1_price    = tp1_price
        self.tp2_price    = tp2_price
        self.entry_score  = entry_score
        self.signal_type  = signal_type
        self.tp1_done     = False
        self.tp2_done     = False
        self.be_done      = False
        self.status       = "OPEN"
        self.pnl          = 0.0
        self.stop_original = stop_price   # guardamos el stop original para calcular tightening

    def cost(self):            return self.entry_price * self.shares
    def current_value(self, p): return p * self.shares
    def unrealized_pnl(self, p): return (p - self.entry_price) * self.shares
    def r_multiple(self, price):
        rps = abs(self.entry_price - self.stop_original)
        return (price - self.entry_price) / rps if rps > 0 else 0.0
    def stop_distance_original(self):
        return abs(self.entry_price - self.stop_original)
    def to_dict(self):   return self.__dict__
    @classmethod
    def from_dict(cls, d):
        p = cls.__new__(cls); p.__dict__.update(d)
        if not hasattr(p, "stop_original"):  p.stop_original  = p.stop_price
        if not hasattr(p, "signal_type"):    p.signal_type    = "BREAKOUT"
        return p


class PositionManager:
    def __init__(self, initial_capital=100_000.0):
        self.initial_capital = initial_capital
        self.cash            = initial_capital
        self.positions       = {}
        self.trades_log      = []

    def save(self):
        json.dump({"cash": self.cash, "initial_capital": self.initial_capital,
                   "last_updated": datetime.now().isoformat()},
                  open(CAPITAL_FILE, "w"), indent=2)
        json.dump({k: v.to_dict() for k, v in self.positions.items()},
                  open(POS_FILE, "w"), indent=2, default=str)
        if self.trades_log:
            df = pd.DataFrame(self.trades_log)
            if TRADES_FILE.exists():
                df = pd.concat([pd.read_csv(TRADES_FILE), df]).drop_duplicates()
            df.to_csv(TRADES_FILE, index=False)
        print(f"  Saved: {len(self.positions)} positions")

    def load(self):
        if CAPITAL_FILE.exists():
            s = json.load(open(CAPITAL_FILE))
            self.cash = s["cash"]; self.initial_capital = s.get("initial_capital", self.initial_capital)
        if POS_FILE.exists():
            self.positions = {k: Position.from_dict(v) for k, v in json.load(open(POS_FILE)).items()}
        print(f"  Loaded: {len(self.positions)} positions")

    def equity(self, prices=None):
        return self.cash + sum(
            p.current_value(prices.get(p.ticker, p.entry_price) if prices else p.entry_price)
            for p in self.positions.values()
        )
    def invested(self, prices=None): return self.equity(prices) - self.cash
    def exposure_pct(self, prices=None):
        eq = self.equity(prices); return self.invested(prices) / eq if eq > 0 else 0.0

    # ── NUEVO: revision de posiciones por regime ──────────────────────────────
    def review_positions_by_regime(self, prices: dict, breadth: dict = None) -> list:
        """
        Evalua cada posicion abierta segun el estado del mercado y genera
        recomendaciones de ajuste de stop. NO ejecuta cambios automaticamente --
        devuelve una lista de acciones sugeridas para revision manual.

        Logica por estado:
          GREEN:  mantener stops como estan. Si TP1 hecho -> stop a breakeven.
          YELLOW: posiciones sin TP1 -> apretar stop a 75% del riesgo original.
          RED:    posiciones sin TP1 y cerca del stop -> apretar a 50%.
                  posiciones con TP1 hecho -> mover a breakeven si no esta ya.
                  posiciones fuertes (+1.5R) -> dejar correr, stop a breakeven.

        Args:
            prices: dict {ticker: precio_actual}
            breadth: dict de get_market_breadth() -- si None se calcula

        Returns:
            lista de dicts con accion sugerida por posicion
        """
        if breadth is None:
            print("  Checking market breadth...")
            breadth = get_market_breadth()

        status = breadth.get("status", "UNKNOWN")
        pct    = breadth.get("pct_above_sma50")
        vix    = breadth.get("vix")
        spy    = breadth.get("spy")
        sma50  = breadth.get("sma50")

        print(f"\n  Market breadth: {status}")
        if pct  is not None: print(f"    Stocks > SMA50 : {pct:.1f}%  (green>={BREADTH_GREEN}%  yellow>={BREADTH_YELLOW}%)")
        if spy  is not None: print(f"    SPY            : {spy:.2f}  (SMA50={sma50:.2f})")
        if vix  is not None: print(f"    VIX            : {vix:.1f}")

        actions = []
        for ticker, pos in self.positions.items():
            price = prices.get(ticker)
            if price is None:
                actions.append({"ticker": ticker, "action": "FETCH_PRICE",
                                 "note": "precio no disponible -- obtener manualmente"})
                continue

            r_now     = pos.r_multiple(price)
            stop_dist = pos.stop_distance_original()
            pct_from_stop = (price - pos.stop_price) / price * 100 if price > 0 else 0
            action = {"ticker": ticker, "signal_type": pos.signal_type,
                      "entry": pos.entry_price, "current": price,
                      "stop_current": pos.stop_price, "stop_original": pos.stop_original,
                      "tp1_done": pos.tp1_done, "r_current": round(r_now, 2),
                      "pct_from_stop": round(pct_from_stop, 1)}

            if status == "GREEN":
                # Mercado sano -- solo revisar breakeven despues de TP1
                if pos.tp1_done and not pos.be_done:
                    action.update({"action": "MOVE_TO_BREAKEVEN",
                                   "new_stop": round(pos.entry_price, 4),
                                   "reason": "TP1 hecho + mercado verde -> breakeven"})
                else:
                    action.update({"action": "HOLD",
                                   "reason": f"mercado verde, {r_now:+.2f}R -- mantener"})

            elif status == "YELLOW":
                if pos.tp1_done:
                    # Con ganancia parcial, mover a breakeven
                    new_stop = pos.entry_price
                    action.update({"action": "MOVE_TO_BREAKEVEN",
                                   "new_stop": round(new_stop, 4),
                                   "reason": "TP1 hecho + mercado amarillo -> proteger"})
                elif r_now < 0 and pct_from_stop < 3.0:
                    # En negativo y cerca del stop: apretar
                    new_stop = round(pos.entry_price - stop_dist * TIGHT_FACTOR_YELLOW, 4)
                    new_stop = max(new_stop, pos.stop_price)   # no bajar el stop
                    action.update({"action": "TIGHTEN_STOP",
                                   "new_stop": new_stop,
                                   "reason": f"mercado amarillo + {r_now:.2f}R + {pct_from_stop:.1f}% del stop"})
                else:
                    action.update({"action": "HOLD",
                                   "reason": f"mercado amarillo pero {r_now:+.2f}R -- un dia de gracia"})

            elif status == "RED":
                if r_now >= 1.5 or pos.tp1_done:
                    # Posicion fuerte: mover a breakeven y dejar correr el runner
                    new_stop = pos.entry_price
                    action.update({"action": "MOVE_TO_BREAKEVEN",
                                   "new_stop": round(new_stop, 4),
                                   "reason": f"mercado rojo pero {r_now:+.2f}R -- proteger con BE"})
                elif r_now < 0:
                    # En negativo: apretar agresivamente
                    new_stop = round(pos.entry_price - stop_dist * TIGHT_FACTOR_RED, 4)
                    new_stop = max(new_stop, pos.stop_price)
                    action.update({"action": "TIGHTEN_STOP",
                                   "new_stop": new_stop,
                                   "reason": f"mercado rojo + {r_now:.2f}R -- apretar stop al 50%"})
                else:
                    # Entre 0 y 1.5R sin TP1: un dia de gracia si ayer era YELLOW
                    new_stop = round(pos.entry_price - stop_dist * TIGHT_FACTOR_YELLOW, 4)
                    new_stop = max(new_stop, pos.stop_price)
                    action.update({"action": "TIGHTEN_STOP",
                                   "new_stop": new_stop,
                                   "reason": f"mercado rojo + {r_now:.2f}R -- apretar al 75%"})
            else:
                action.update({"action": "HOLD", "reason": "regime desconocido -- mantener"})

            actions.append(action)
        return actions

    def print_review(self, actions: list):
        """Imprime el resultado de review_positions_by_regime de forma legible."""
        print(f"\n{'='*70}")
        print(f"  STOP REVIEW  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        if not actions:
            print("  No open positions to review."); return

        hold   = [a for a in actions if a.get("action") == "HOLD"]
        tight  = [a for a in actions if a.get("action") == "TIGHTEN_STOP"]
        be     = [a for a in actions if a.get("action") == "MOVE_TO_BREAKEVEN"]
        manual = [a for a in actions if a.get("action") == "FETCH_PRICE"]

        if be:
            print(f"\n  MOVE TO BREAKEVEN ({len(be)}):")
            for a in be:
                print(f"    {a['ticker']:<8} {a['r_current']:+.2f}R  stop {a['stop_current']:.2f} -> {a['new_stop']:.2f}  | {a['reason']}")
        if tight:
            print(f"\n  TIGHTEN STOP ({len(tight)}):")
            for a in tight:
                print(f"    {a['ticker']:<8} {a['r_current']:+.2f}R  stop {a['stop_current']:.2f} -> {a['new_stop']:.2f}  | {a['reason']}")
        if hold:
            print(f"\n  HOLD AS-IS ({len(hold)}):")
            for a in hold:
                print(f"    {a['ticker']:<8} {a['r_current']:+.2f}R  | {a['reason']}")
        if manual:
            print(f"\n  NEEDS PRICE ({len(manual)}):")
            for a in manual:
                print(f"    {a['ticker']:<8} {a['note']}")
        print(f"\n  NOTE: estas son RECOMENDACIONES. Ejecutalas manualmente en tu broker.")
        print(f"        Los stops NO se actualizan automaticamente en positions.json.")
        print(f"        Usa: python3 position_manager.py update-stop --ticker AAPL --stop 195.50")
        print(f"{'='*70}\n")

        # Guardar para auditoria
        pd.DataFrame(actions).to_csv(REVIEW_FILE, index=False)
        print(f"  Review saved: {REVIEW_FILE}")

    # ── Metodo para aplicar un stop manualmente despues de revision ───────────
    def update_stop(self, ticker: str, new_stop: float):
        """Actualiza el stop de una posicion abierta."""
        if ticker not in self.positions:
            print(f"  ERROR: {ticker} not in positions"); return
        pos = self.positions[ticker]
        old_stop = pos.stop_price
        pos.stop_price = new_stop
        if new_stop >= pos.entry_price:
            pos.be_done = True
        print(f"  {ticker}: stop updated {old_stop:.4f} -> {new_stop:.4f}"
              f"  ({'breakeven' if pos.be_done else 'tightened'})")


    def process_signals(self, signals, prices=None, breadth=None):
        """
        Procesa señales nuevas respetando exposure maximo y breadth del mercado.
        Si breadth=RED, no entra nada nuevo independientemente de las señales.
        """
        if breadth is None:
            breadth = get_market_breadth()

        market_status = breadth.get("status", "UNKNOWN")
        pct = breadth.get("pct_above_sma50")
        pct_str = f"  breadth={pct:.1f}%" if pct is not None else ""

        if market_status == "RED":
            print(f"  MARKET RED{pct_str} -- no new entries (regime blocked)")
            return []

        eq  = self.equity(prices); inv = self.invested(prices); max_inv = eq * MAX_EXPOSURE_PCT
        # En YELLOW reducir exposicion maxima al 50%
        if market_status == "YELLOW":
            max_inv = eq * MAX_EXPOSURE_PCT * 0.50
            print(f"  MARKET YELLOW{pct_str} -- max exposure halved to {max_inv/eq*100:.0f}%")

        orders = []
        print(f"\n  Portfolio: equity={eq:,.0f} | invested={inv:,.0f} | "
              f"exposure={inv/eq*100 if eq>0 else 0:.1f}%")
        if inv >= max_inv:
            print(f"  MAX EXPOSURE -- no new entries"); return []

        available = [s for s in signals if s.get("ticker") not in self.positions]
        if not available:
            print("  All signals already in positions"); return []
        available.sort(key=lambda x: x.get("entry_score", 0), reverse=True)

        for sig in available:
            if inv >= max_inv: break
            ticker = sig["ticker"]; price = sig["signal_price"]
            stop   = sig.get("stop_price", price * (1 - MAX_STOP_PCT))
            sd     = price - stop
            if sd <= 0: continue
            shares = int(np.floor(RISK_DOLLARS / sd))
            if shares <= 0: continue
            cost = shares * price
            if self.cash < cost:
                print(f"  SKIP {ticker}: need {cost:,.0f} have {self.cash:,.0f}"); continue
            tp1 = sig.get("tp1", price + sd * TP1_R)
            tp2 = sig.get("tp2", price + sd * TP2_R)
            stype = sig.get("signal_type", "BREAKOUT")
            orders.append({
                "action": "BUY", "ticker": ticker, "signal_type": stype,
                "signal_date": sig.get("signal_date", ""), "entry_at": "NEXT_OPEN",
                "signal_price": round(price, 4), "shares": shares,
                "risk_$": RISK_DOLLARS, "stop_price": round(stop, 4),
                "tp1": round(tp1, 4), "tp1_shares": int(np.floor(shares * TP1_PCT)),
                "tp2": round(tp2, 4), "tp2_shares": int(np.floor(shares * TP2_PCT)),
                "runner_shares": int(np.floor(shares * RUNNER_PCT)),
                "entry_score": sig.get("entry_score", 0),
                "rs_percentile": sig.get("rs_percentile", 0),
                "cost_approx": round(cost, 2),
            })
            self.cash -= cost; inv += cost
        return orders

    def record_entry(self, ticker, entry_date, entry_price, shares,
                     stop_price, tp1_price, tp2_price,
                     entry_score=0.0, signal_type="BREAKOUT"):
        pos = Position(ticker, entry_date, entry_price, shares,
                       stop_price, tp1_price, tp2_price, entry_score, signal_type)
        self.positions[ticker] = pos
        print(f"  ENTERED {ticker} [{signal_type}]: {shares}sh @ {entry_price:.2f}"
              f" | stop={stop_price:.2f} | tp1={tp1_price:.2f} | tp2={tp2_price:.2f}")

    def record_exit(self, ticker, exit_date, exit_price, shares_exited, exit_type):
        if ticker not in self.positions:
            print(f"  WARNING: {ticker} not in positions"); return
        pos = self.positions[ticker]
        pnl = (exit_price - pos.entry_price) * shares_exited
        self.cash += exit_price * shares_exited
        pos.shares -= shares_exited; pos.pnl += pnl
        if exit_type == "TP1": pos.tp1_done = True
        if exit_type == "TP2": pos.tp2_done = True
        rps = abs(pos.entry_price - pos.stop_original)
        self.trades_log.append({
            "ticker": ticker, "signal_type": getattr(pos, "signal_type", "BREAKOUT"),
            "exit_date": exit_date, "exit_type": exit_type,
            "entry_price": pos.entry_price, "exit_price": exit_price,
            "shares": shares_exited, "pnl": round(pnl, 2),
            "r_multiple": round((exit_price - pos.entry_price) / rps, 3) if rps > 0 else 0,
        })
        print(f"  EXIT {ticker} [{exit_type}]: {shares_exited}sh @ {exit_price:.2f}"
              f" | PnL={pnl:+,.2f}")
        if pos.shares <= 0:
            del self.positions[ticker]
            print(f"    Closed. Total PnL={pos.pnl:+,.2f}")

    def report(self, prices=None):
        eq  = self.equity(prices); pnl = eq - self.initial_capital
        print(f"\n{'='*60}\n  PORTFOLIO  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  Capital:  {self.initial_capital:>12,.2f}")
        print(f"  Equity:   {eq:>12,.2f}  ({pnl:+,.2f} / {pnl/self.initial_capital*100:+.2f}%)")
        print(f"  Cash:     {self.cash:>12,.2f}")
        print(f"  Exposure: {self.exposure_pct(prices)*100:.1f}%  (max {MAX_EXPOSURE_PCT*100:.0f}%)")
        print(f"  Open:     {len(self.positions)} positions")
        if self.positions:
            print(f"\n  {'Ticker':<8} {'Type':<12} {'Sh':>5} {'Entry':>8} {'Stop':>8} {'TP1':>8} {'R':>6}")
            print(f"  {'-'*58}")
            for t, pos in self.positions.items():
                cur = prices.get(t, pos.entry_price) if prices else pos.entry_price
                print(f"  {t:<8} {getattr(pos,'signal_type','?'):<12} {pos.shares:>5} "
                      f"{pos.entry_price:>8.2f} {pos.stop_price:>8.2f} "
                      f"{pos.tp1_price:>8.2f} {pos.r_multiple(cur):>+6.2f}R")
        if TRADES_FILE.exists():
            hist = pd.read_csv(TRADES_FILE)
            if len(hist) > 0:
                wr = (hist["pnl"] > 0).mean()
                w  = hist[hist["pnl"] > 0]["pnl"].sum()
                l  = abs(hist[hist["pnl"] < 0]["pnl"].sum())
                pf = w / l if l > 0 else float("inf")
                print(f"\n  History ({len(hist)} trades): WR={wr:.1%}  PF={pf:.2f}  PnL={hist['pnl'].sum():+,.2f}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse, sys
    pa = argparse.ArgumentParser(description="Position Manager CLI")
    pa.add_argument("command", choices=["report","scan","enter","exit","review","update-stop","reset","breadth"])
    pa.add_argument("--ticker",  type=str)
    pa.add_argument("--price",   type=float)
    pa.add_argument("--stop",    type=float)
    pa.add_argument("--shares",  type=int)
    pa.add_argument("--type",    type=str, default="STOP")
    pa.add_argument("--capital", type=float, default=100_000)
    args = pa.parse_args()

    pm = PositionManager(initial_capital=args.capital)

    if args.command == "reset":
        pm.save()
        print(f"  Reset: capital={args.capital:,.0f}")

    elif args.command == "breadth":
        b = get_market_breadth()
        print(f"\n  Market breadth status: {b['status']}")
        if b['pct_above_sma50'] is not None:
            print(f"  Stocks > SMA50 : {b['pct_above_sma50']:.1f}%")
        if b['spy'] is not None:
            print(f"  SPY            : {b['spy']:.2f}  (SMA50={b['sma50']:.2f})  {'OK' if b['spy_ok'] else 'BELOW'}")
        if b['vix'] is not None:
            print(f"  VIX            : {b['vix']:.1f}")

    elif args.command == "report":
        pm.load(); pm.report()

    elif args.command == "review":
        pm.load()
        # Obtener precios actuales de las posiciones abiertas
        prices = {}
        if pm.positions:
            try:
                import yfinance as yf
                tickers = list(pm.positions.keys())
                data = yf.download(tickers, period="2d", auto_adjust=True, progress=False)
                if data is not None and not data.empty:
                    last = data["Close"].iloc[-1] if isinstance(data["Close"], pd.DataFrame) else data["Close"]
                    for t in tickers:
                        if t in last.index:
                            prices[t] = float(last[t])
                        elif hasattr(last, 'name'):
                            prices[t] = float(last.iloc[-1])
            except Exception as e:
                print(f"  WARN: could not fetch prices: {e}")
        breadth = get_market_breadth()
        actions = pm.review_positions_by_regime(prices, breadth)
        pm.print_review(actions)

    elif args.command == "update-stop":
        if not args.ticker or not args.stop:
            print("  Usage: update-stop --ticker AAPL --stop 195.50"); sys.exit(1)
        pm.load()
        pm.update_stop(args.ticker, args.stop)
        pm.save()

    elif args.command == "scan":
        pm.load()
        today = datetime.now().strftime("%Y-%m-%d")
        signals = load_all_signals(today)
        if not signals:
            print(f"  No signals for today. Run scanners first."); sys.exit(1)
        print(f"  Total signals loaded: {len(signals)}")
        breadth = get_market_breadth()
        orders = pm.process_signals(signals, breadth=breadth)
        if orders:
            print(f"\n  ORDERS FOR TOMORROW ({len(orders)}):")
            print(f"  {'Ticker':<8} {'Type':<12} {'Sh':>5} {'~Price':>8} {'Stop':>8} {'TP1':>8} {'TP2':>8} {'Score':>6}")
            print(f"  {'-'*66}")
            for o in orders:
                print(f"  {o['ticker']:<8} {o['signal_type']:<12} {o['shares']:>5} "
                      f"{o['signal_price']:>8.2f} {o['stop_price']:>8.2f} "
                      f"{o['tp1']:>8.2f} {o['tp2']:>8.2f} {o['entry_score']:>6.3f}")
            pd.DataFrame(orders).to_csv(PAPER_DIR / f"orders_{today}.csv", index=False)
            print(f"  Saved: outputs/paper_trading/orders_{today}.csv")
        else:
            print("  No orders.")
        pm.save()

    elif args.command == "enter":
        if not all([args.ticker, args.price, args.shares]):
            print("  Usage: enter --ticker AAPL --price 195.50 --shares 12"); sys.exit(1)
        pm.load()
        sd = args.price * MAX_STOP_PCT
        pm.record_entry(args.ticker, datetime.now().strftime("%Y-%m-%d"),
                        args.price, args.shares,
                        args.price - sd,
                        args.price + sd * TP1_R,
                        args.price + sd * TP2_R)
        pm.save(); pm.report()

    elif args.command == "exit":
        if not all([args.ticker, args.price, args.shares]):
            print("  Usage: exit --ticker AAPL --price 210 --shares 7 --type TP1"); sys.exit(1)
        pm.load()
        pm.record_exit(args.ticker, datetime.now().strftime("%Y-%m-%d"),
                       args.price, args.shares, args.type)
        pm.save(); pm.report()
