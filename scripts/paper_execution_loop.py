#!/usr/bin/env python3
"""
paper_execution_loop.py - Simulación paper de ejecución desde señales.

Uso:
    python3 scripts/paper_execution_loop.py --date 2026-04-24

    # Con parámetros custom
    python3 scripts/paper_execution_loop.py --date 2026-04-24 \
        --capital 50000 --risk-per-trade 0.01 --max-positions 6

    # Simular con skip de tickers ya en posiciones (cerrar y reopen)
    python3 scripts/paper_execution_loop.py --date 2026-04-24 --allow-reopen

    # Dry run (solo verboso sin escribir archivos)
    python3 scripts/paper_execution_loop.py --date 2026-04-24 --dry-run

    # Limitar a ciertos agentes
    python3 scripts/paper_execution_loop.py --date 2026-04-24 \
        --agents combo_pure_momentum combo_pullback_entry
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "live_signals"
RUNS_DIR = PROJECT_ROOT / "outputs" / "paper_trading" / "runs"
INTENTS_DIR = PROJECT_ROOT / "outputs" / "execution_intents"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_CAPITAL = 100_000.0
DEFAULT_RISK_PCT = 0.02
DEFAULT_MAX_POSITIONS = 6
DEFAULT_SLIPPAGE_BPS = 10
DEFAULT_FEE_BPS = 1
HOLDING_DAYS = 10


def load_ohlcv(ticker: str, date: str, lookback: int = 20) -> pd.DataFrame:
    cutoff = (
        datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback + 10)
    ).strftime("%Y-%m-%d")
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    # Normalizar fechas a solo día para poder deduplicar
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.normalize()
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)


def load_signals(date: str, agents: list[str] | None = None) -> pd.DataFrame:
    path = OUTPUT_DIR / date / "combined.csv"
    if not path.exists():
        logger.info(f"No signals file for {date}: {path}")
        return pd.DataFrame()
    df = pd.read_csv(path)
    if agents:
        df = df[df["agent_name"].isin(agents)]
    return df.sort_values("entry_score", ascending=False).reset_index(drop=True)


def load_intents(date: str) -> pd.DataFrame:
    path = INTENTS_DIR / date / "execution_intents.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def compute_position_risk(
    entry_price: float, stop_price: float, risk_pct: float, capital: float
) -> dict:
    risk_amount = capital * risk_pct
    price_risk = abs(entry_price - stop_price)
    if price_risk == 0:
        return {
            "size": 0,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "risk_amount": 0,
        }
    shares = int(risk_amount / price_risk)
    actual_risk = shares * price_risk
    return {
        "size": shares,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "risk_amount": actual_risk,
    }


def simulate_run(
    signals: pd.DataFrame,
    date: str,
    capital: float = DEFAULT_CAPITAL,
    risk_pct: float = DEFAULT_RISK_PCT,
    max_positions: int = DEFAULT_MAX_POSITIONS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    fee_bps: float = DEFAULT_FEE_BPS,
    dry_run: bool = False,
) -> dict:
    logging.info(
        f"Paper run | date={date} | capital=${capital:,.0f} | risk={risk_pct:.0%} | max_pos={max_positions}"
    )

    if signals.empty:
        logger.warning("No signals to simulate")
        result = {
            "ok": True,
            "date": date,
            "starting_capital": capital,
            "ending_capital": round(capital, 2),
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "orders_count": 0,
            "fills_count": 0,
            "trades_count": 0,
            "positions_open": 0,
            "slippage_bps": slippage_bps,
            "fee_bps": fee_bps,
            "dry_run": dry_run,
            "orders": [],
            "fills": [],
            "positions": [],
            "equity": [],
            "error": None,
        }
        if not dry_run:
            run_dir = RUNS_DIR / date
            run_dir.mkdir(parents=True, exist_ok=True)
            _save_ledger(run_dir, [], [], [], [], result)
        return result

    run_dir = None
    if not dry_run:
        run_dir = RUNS_DIR / date
        run_dir.mkdir(parents=True, exist_ok=True)

    orders = []
    fills = []
    positions = []
    equity_curve = []
    active_tickers = {}

    slippage_mult = 1 + slippage_bps / 10000

    initial_capital = capital

    for _, signal in signals.iterrows():
        ticker = signal["ticker"]
        if len(active_tickers) >= max_positions and ticker not in active_tickers:
            logger.debug(f"Skipping {ticker}: max positions reached")
            continue

        # Canonical execution fields from signal
        stop_price = signal.get("stop_loss", signal.get("stop_price", None))
        tp1_price = signal.get("tp1_price", None)
        tp2_price = signal.get("tp2_price", None)
        size = signal.get("position_size", signal.get("shares", None))
        
        tp1_pct = signal.get("tp1_pct", 0.33)
        tp2_pct = signal.get("tp2_pct", 0.33)
        runner_pct = signal.get("runner_pct", 0.34)

        if stop_price is None or tp1_price is None or tp2_price is None or size is None or pd.isna(size):
            logger.warning(f"Skipping {ticker}: Missing canonical risk/target fields in signal. (Requires stop, TPs, size).")
            continue
            
        stop_price = float(stop_price)
        tp1_price = float(tp1_price)
        tp2_price = float(tp2_price)
        size = int(size)

        if size <= 0:
            logger.debug(f"Skipping {ticker}: zero size")
            continue

        # Load data to find the ACTUAL next-day open for entry
        df_full = load_ohlcv(ticker, date, lookback=HOLDING_DAYS + 5)
        if df_full.empty:
            logger.debug(f"Skipping {ticker}: no ohlcv data")
            continue

        ts_signal = pd.Timestamp(date)
        all_dates = df_full.index

        if ts_signal not in all_dates:
            idx_sig_list = all_dates[all_dates <= ts_signal]
            if len(idx_sig_list) == 0:
                continue
            ts_signal = idx_sig_list[-1]

        idx_sig = all_dates.get_loc(ts_signal)
        if isinstance(idx_sig, slice):
            idx_sig = idx_sig.start

        # Entrada: Día siguiente (idx + 1)
        if idx_sig + 1 >= len(all_dates):
            logger.debug(f"Skipping {ticker}: no future data for entry")
            continue

        idx_ent = idx_sig + 1
        idx_ext = min(idx_ent + HOLDING_DAYS, len(all_dates) - 1)

        holding_df = df_full.iloc[idx_ent : idx_ext + 1]
        if holding_df.empty:
            continue

        entry_date = all_dates[idx_ent]
        entry_price_actual = float(holding_df.iloc[0]["open"])

        # Usar el precio real de apertura + slippage
        fill_price = entry_price_actual * slippage_mult
        entry_fee = round(fill_price * size * fee_bps / 10000, 2)

        entry_score = float(
            signal.get(
                "entry_score",
                signal.get("normalized_score", signal.get("raw_score", 0)) or 0,
            )
        )

        order = {
            "order_id": f"ord_{ticker}_{date}",
            "ticker": ticker,
            "agent": signal.get("agent_name", signal.get("strategy_id", "unknown")),
            "combo": signal.get("combo_name", signal.get("strategy_id", "unknown")),
            "signal_date": signal.get("signal_date", date),
            "entry_score": entry_score,
            "entry_price_signal": entry_price_actual,
            "stop_price": round(stop_price, 4),
            "tp1_price": round(tp1_price, 4),
            "tp2_price": round(tp2_price, 4),
            "size_requested": size,
            "size_filled": size,
            "fill_price": round(fill_price, 4),
            "entry_fee": entry_fee,
            "status": "filled",
            "filled_at": f"{str(entry_date.date())} 09:30:00",
            "signal_id": signal.get("signal_id"),
            "intent_id": signal.get("intent_id"),
            "source_universe": signal.get("source_universe", "local_db"),
            "decision_source": signal.get("decision_source", "system"),
            "confirmed_by": signal.get("confirmed_by"),
            "confirmed_at": signal.get("confirmed_at"),
        }
        orders.append(order)
        capital -= (fill_price * size + entry_fee)

        pos_rec = {
            "ticker": ticker,
            "agent": signal.get("agent_name", signal.get("strategy_id", "unknown")),
            "size": size,
            "entry_price": round(fill_price, 4),
            "stop_price": round(stop_price, 4),
            "tp1_price": round(tp1_price, 4),
            "tp2_price": round(tp2_price, 4),
            "position_value": round(fill_price * size, 2),
            "unrealized_pnl": 0.0,
            "exited": False,
            "exit_reason": None,
            "exit_price": None,
            "exit_fee": None,
            "realized_pnl": None,
            "rvol": signal.get("rvol", 0),
            "adr_pct": signal.get("adr_pct", 0),
            "signal_id": signal.get("signal_id"),
            "intent_id": signal.get("intent_id"),
            "source_universe": signal.get("source_universe", "local_db"),
            "decision_source": signal.get("decision_source", "system"),
            "confirmed_by": signal.get("confirmed_by"),
            "confirmed_at": signal.get("confirmed_at"),
        }
        positions.append(pos_rec)
        active_tickers[ticker] = pos_rec

        fill_rec = {
            "fill_id": f"fill_{ticker}_{date}",
            "order_id": order["order_id"],
            "ticker": ticker,
            "side": "BUY",
            "price": round(fill_price, 4),
            "size": size,
            "fee": entry_fee,
            "timestamp": f"{str(entry_date.date())} 09:30:00",
        }
        fills.append(fill_rec)

        logger.info(
            f"  OPEN {ticker}  size={size}  entry=${fill_price:.2f} (open=${entry_price_actual:.2f})  "
            f"stop=${stop_price:.2f}  tp1=${tp1_price:.2f}  tp2=${tp2_price:.2f}"
        )

        # -------------------------------------------------------------
        # Simulación de Salidas (dentro del mismo loop)
        # -------------------------------------------------------------
        remaining_size = size
        current_stop = stop_price
        
        tp1_filled = False
        tp2_filled = False
        
        size_tp1 = int(size * tp1_pct)
        size_tp2 = int(size * tp2_pct)
        
        total_realized_pnl = 0.0
        final_exit_reason = "EOD"
        final_exit_date = holding_df.index[-1]

        for current_date, row in holding_df.iterrows():
            high = float(row["high"])
            low = float(row["low"])
            
            # Stop Check
            if low <= current_stop:
                exit_fill = current_stop * (1 - slippage_bps / 10000)
                exit_fee = round(exit_fill * remaining_size * fee_bps / 10000, 2)
                pnl = (exit_fill - fill_price) * remaining_size - exit_fee
                total_realized_pnl += pnl
                capital += exit_fill * remaining_size - exit_fee
                
                fills.append({
                    "fill_id": f"fill_{ticker}_stop_{date}_{current_date.date()}",
                    "order_id": f"ord_{ticker}_{date}",
                    "ticker": ticker,
                    "side": "SELL",
                    "price": round(exit_fill, 4),
                    "size": remaining_size,
                    "fee": exit_fee,
                    "timestamp": f"{current_date.date()} 16:00:00",
                    "reason": "STOP" if current_stop < fill_price else "BREAKEVEN",
                })
                remaining_size = 0
                final_exit_reason = "STOP" if current_stop < fill_price else "BREAKEVEN"
                final_exit_date = current_date
                break
            
            # TP1 Check
            if not tp1_filled and high >= tp1_price and remaining_size > 0:
                tp1_filled = True
                fill_sz = min(size_tp1, remaining_size)
                exit_fill = tp1_price * (1 - slippage_bps / 10000)
                exit_fee = round(exit_fill * fill_sz * fee_bps / 10000, 2)
                pnl = (exit_fill - fill_price) * fill_sz - exit_fee
                total_realized_pnl += pnl
                capital += exit_fill * fill_sz - exit_fee
                
                fills.append({
                    "fill_id": f"fill_{ticker}_tp1_{date}_{current_date.date()}",
                    "order_id": f"ord_{ticker}_{date}",
                    "ticker": ticker,
                    "side": "SELL",
                    "price": round(exit_fill, 4),
                    "size": fill_sz,
                    "fee": exit_fee,
                    "timestamp": f"{current_date.date()} 16:00:00",
                    "reason": "TP1",
                })
                remaining_size -= fill_sz
                current_stop = fill_price # Breakeven tras TP1
            
            # TP2 Check
            if tp1_filled and not tp2_filled and high >= tp2_price and remaining_size > 0:
                tp2_filled = True
                fill_sz = min(size_tp2, remaining_size)
                exit_fill = tp2_price * (1 - slippage_bps / 10000)
                exit_fee = round(exit_fill * fill_sz * fee_bps / 10000, 2)
                pnl = (exit_fill - fill_price) * fill_sz - exit_fee
                total_realized_pnl += pnl
                capital += exit_fill * fill_sz - exit_fee
                
                fills.append({
                    "fill_id": f"fill_{ticker}_tp2_{date}_{current_date.date()}",
                    "order_id": f"ord_{ticker}_{date}",
                    "ticker": ticker,
                    "side": "SELL",
                    "price": round(exit_fill, 4),
                    "size": fill_sz,
                    "fee": exit_fee,
                    "timestamp": f"{current_date.date()} 16:00:00",
                    "reason": "TP2",
                })
                remaining_size -= fill_sz

        # Salida EOD si queda remanente
        if remaining_size > 0:
            eod_price = float(holding_df.iloc[-1]["close"])
            exit_fill = eod_price * (1 - slippage_bps / 10000)
            exit_fee = round(exit_fill * remaining_size * fee_bps / 10000, 2)
            pnl = (exit_fill - fill_price) * remaining_size - exit_fee
            total_realized_pnl += pnl
            capital += exit_fill * remaining_size - exit_fee
            
            fills.append({
                "fill_id": f"fill_{ticker}_eod_{date}_{final_exit_date.date()}",
                "order_id": f"ord_{ticker}_{date}",
                "ticker": ticker,
                "side": "SELL",
                "price": round(exit_fill, 4),
                "size": remaining_size,
                "fee": exit_fee,
                "timestamp": f"{final_exit_date.date()} 16:00:00",
                "reason": "EOD",
            })
            remaining_size = 0
            final_exit_reason = "EOD"
            
        pos_rec["exit_reason"] = final_exit_reason
        pos_rec["exit_price"] = None # Múltiples precios de salida
        pos_rec["exit_fee"] = None
        pos_rec["realized_pnl"] = round(total_realized_pnl, 2)
        pos_rec["exited"] = True
        pos_rec["exit_date"] = str(final_exit_date.date())
        pos_rec["remaining_size"] = remaining_size

        logger.info(
            f"  CLOSE {ticker}  reason={final_exit_reason}  date={pos_rec['exit_date']}  "
            f"pnl=${total_realized_pnl:.2f}"
        )

    equity_curve.append(capital)

    result = {
        "ok": True,
        "date": date,
        "starting_capital": initial_capital,
        "ending_capital": round(capital, 2),
        "pnl": round(capital - initial_capital, 2),
        "pnl_pct": round((capital - initial_capital) / initial_capital * 100, 2),
        "orders_count": len(orders),
        "fills_count": len(fills),
        "trades_count": len([p for p in positions if p["exited"]]),
        "positions_open": len([p for p in positions if not p["exited"]]),
        "max_positions": max_positions,
        "slippage_bps": slippage_bps,
        "fee_bps": fee_bps,
        "dry_run": dry_run,
    }

    if not dry_run and run_dir:
        _save_ledger(run_dir, orders, fills, positions, equity_curve, result)

    return {
        **result,
        "orders": orders,
        "fills": fills,
        "positions": positions,
        "equity": equity_curve,
    }


def _save_ledger(
    run_dir: Path,
    orders: list,
    fills: list,
    positions: list,
    equity: list,
    summary: dict,
) -> None:
    pd.DataFrame(orders).to_csv(run_dir / "orders.csv", index=False)
    pd.DataFrame(fills).to_csv(run_dir / "fills.csv", index=False)
    pd.DataFrame(positions).to_csv(run_dir / "positions.csv", index=False)

    eq_df = pd.DataFrame(
        {
            "step": list(range(len(equity))),
            "equity": equity,
            "run_date": [summary["date"]] * len(equity),
        }
    )
    eq_df.to_csv(run_dir / "equity_curve.csv", index=False)

    with open(run_dir / "run_report.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"  Ledger saved: {run_dir}")


def main():
    parser = argparse.ArgumentParser(description="Paper execution loop")
    parser.add_argument(
        "--date", type=str, default=None, help="Simulation date (YYYY-MM-DD)"
    )
    parser.add_argument("--agents", nargs="+", help="Filter by agent names")
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--risk-per-trade", type=float, default=DEFAULT_RISK_PCT)
    parser.add_argument("--max-positions", type=int, default=DEFAULT_MAX_POSITIONS)
    parser.add_argument("--slippage-bps", type=float, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--fee-bps", type=float, default=DEFAULT_FEE_BPS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    try:
        intents = load_intents(date)
        if not intents.empty:
            signals = intents
            logger.info(f"Loaded {len(signals)} execution intents for {date}")
        else:
            signals = load_signals(date, agents=args.agents)
            logger.info(f"Loaded {len(signals)} signals for {date}")
    except FileNotFoundError as e:
        logger.error(f"{e}")
        sys.exit(1)

    result = simulate_run(
        signals,
        date,
        capital=args.capital,
        risk_pct=args.risk_per_trade,
        max_positions=args.max_positions,
        slippage_bps=args.slippage_bps,
        fee_bps=args.fee_bps,
        dry_run=args.dry_run,
    )

    _print_summary(result)


def _print_summary(r: dict) -> None:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  PAPER RUN  |  {r['date']}")
    print(f"{sep}")
    print(f"  Starting capital:  ${r['starting_capital']:,.2f}")
    print(f"  Ending capital:     ${r['ending_capital']:,.2f}")
    print(f"  P&L:                ${r['pnl']:,.2f}  ({r['pnl_pct']:+.2f}%)")
    print(f"  Orders:             {r['orders_count']}")
    print(f"  Fills:              {r['fills_count']}")
    print(f"  Trades (exited):    {r['trades_count']}")
    print(f"  Positions open:     {r['positions_open']}")
    print(f"  Slippage:           {r['slippage_bps']} bps")
    print(f"  Fee:                {r['fee_bps']} bps")
    print(f"{sep}\n")

    if not r["dry_run"]:
        print(f"  Ledger: outputs/paper_trading/runs/{r['date']}/")


if __name__ == "__main__":
    main()
