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
        raise FileNotFoundError(f"Signals not found: {path}")
    df = pd.read_csv(path)
    if agents:
        df = df[df["agent_name"].isin(agents)]
    return df.sort_values("entry_score", ascending=False).reset_index(drop=True)


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
        return {
            "ok": True,
            "orders": [],
            "fills": [],
            "positions": [],
            "equity": [],
            "error": None,
        }

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

        entry_price = float(signal.get("entry_price", 0))
        if entry_price <= 0:
            logger.debug(f"Skipping {ticker}: invalid entry_price {entry_price}")
            continue

        fill_price = entry_price * slippage_mult
        stop_pct = 0.08
        stop_price = entry_price * (1 - stop_pct)
        tp1_r = 1.25
        tp2_r = 3.0
        tp1_price = entry_price * (1 + stop_pct * tp1_r)
        tp2_price = entry_price * (1 + stop_pct * tp2_r)

        pos = compute_position_risk(entry_price, stop_price, risk_pct, capital)
        size = pos["size"]
        if size <= 0:
            logger.debug(f"Skipping {ticker}: zero size")
            continue

        order = {
            "order_id": f"ord_{ticker}_{date}",
            "ticker": ticker,
            "agent": signal["agent_name"],
            "combo": signal["combo_name"],
            "signal_date": signal["signal_date"],
            "entry_score": signal["entry_score"],
            "entry_price_signal": entry_price,
            "stop_price": round(stop_price, 4),
            "tp1_price": round(tp1_price, 4),
            "tp2_price": round(tp2_price, 4),
            "size_requested": size,
            "size_filled": size,
            "fill_price": round(fill_price, 4),
            "entry_fee": round(fill_price * size * fee_bps / 10000, 2),
            "status": "filled",
            "filled_at": f"{date} 09:30:00",
        }
        orders.append(order)
        capital -= fill_price * size + order["entry_fee"]
        equity_curve.append(capital)

        pos_rec = {
            "ticker": ticker,
            "agent": signal["agent_name"],
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
            "fee": order["entry_fee"],
            "timestamp": f"{date} 09:30:00",
        }
        fills.append(fill_rec)

        logger.info(
            f"  OPEN {ticker}  size={size}  entry=${fill_price:.2f}  "
            f"stop=${stop_price:.2f}  tp1=${tp1_price:.2f}  tp2=${tp2_price:.2f}"
        )

    # Find actual close date for this simulation (Lookahead fix)
    # El trade entra al día siguiente de la señal y dura HOLDING_DAYS
    for pos in positions:
        ticker = pos["ticker"]
        # Usar un lookback mayor para asegurar que capturamos el futuro del trade
        df_full = load_ohlcv(ticker, date, lookback=HOLDING_DAYS + 5)
        if df_full.empty:
            continue

        try:
            # La señal ocurrió en 'date'. Entrada es el siguiente día hábil.
            ts_signal = pd.Timestamp(date)
            all_dates = df_full.index
            
            # Buscar el índice de la fecha de la señal
            if ts_signal not in all_dates:
                # Si no está, buscar la fecha más cercana anterior
                idx_sig_list = all_dates[all_dates <= ts_signal]
                if len(idx_sig_list) == 0: continue
                ts_signal = idx_sig_list[-1]
            
            idx_sig = all_dates.get_loc(ts_signal)
            if isinstance(idx_sig, slice): idx_sig = idx_sig.start
            
            # Entrada: Día siguiente (idx + 1)
            if idx_sig + 1 >= len(all_dates):
                pos["exit_reason"] = "no_future_data"
                continue
            
            idx_ent = idx_sig + 1
            idx_ext = min(idx_ent + HOLDING_DAYS, len(all_dates) - 1)
            
            # FILTRAR VENTANA DE HOLDING (Fix crítico: evita lookahead)
            holding_df = df_full.iloc[idx_ent : idx_ext + 1]
            if holding_df.empty: continue

            entry_date = all_dates[idx_ent]
            entry_price_actual = float(holding_df.iloc[0]["open"])
            
            # Evaluar Highs y Lows SOLO en la ventana de holding
            high_in_hold = float(holding_df["high"].max())
            low_in_hold = float(holding_df["low"].min())
            
            exit_reason = "EOD" # Default: fin de holding
            exit_idx_actual = len(holding_df) - 1
            
            # Check de STOP primero (prioridad a la protección)
            # Buscamos el primer día que toca el stop
            stops = holding_df[holding_df["low"] <= pos["stop_price"]]
            if not stops.empty:
                exit_reason = "STOP"
                exit_date_actual = stops.index[0]
                exit_price = pos["stop_price"]
            else:
                # Check de TPs
                tp2s = holding_df[holding_df["high"] >= pos["tp2_price"]]
                if not tp2s.empty:
                    exit_reason = "TP2"
                    exit_date_actual = tp2s.index[0]
                    exit_price = pos["tp2_price"]
                else:
                    tp1s = holding_df[holding_df["high"] >= pos["tp1_price"]]
                    if not tp1s.empty:
                        exit_reason = "TP1"
                        exit_date_actual = tp1s.index[0]
                        exit_price = pos["tp1_price"]
                    else:
                        # Salida por tiempo
                        exit_date_actual = holding_df.index[-1]
                        exit_price = float(holding_df.iloc[-1]["close"])

            # Recalcular PnL con precios reales de entrada/salida
            exit_fill = exit_price * (1 - slippage_bps / 10000)
            exit_fee = round(exit_fill * pos["size"] * fee_bps / 10000, 2)
            
            # Usamos el entry_price que ya tenía la pos (que incluye slippage)
            realized_pnl = (exit_fill - pos["entry_price"]) * pos["size"] - exit_fee

            fill_exit = {
                "fill_id": f"fill_{ticker}_exit_{date}",
                "order_id": f"ord_{ticker}_{date}",
                "ticker": ticker,
                "side": "SELL",
                "price": round(exit_fill, 4),
                "size": pos["size"],
                "fee": exit_fee,
                "timestamp": f"{str(exit_date_actual.date())} 16:00:00",
                "reason": exit_reason,
            }
            fills.append(fill_exit)

            pos["exit_reason"] = exit_reason
            pos["exit_price"] = round(exit_fill, 4)
            pos["exit_fee"] = exit_fee
            pos["realized_pnl"] = round(realized_pnl, 2)
            pos["exited"] = True
            pos["exit_date"] = str(exit_date_actual.date())

            capital += exit_fill * pos["size"] - exit_fee

            logger.info(
                f"  CLOSE {ticker}  reason={exit_reason}  date={pos['exit_date']}  "
                f"price=${exit_fill:.2f}  pnl=${realized_pnl:.2f}"
            )
        except Exception as e:
            logger.error(f"Error simulating exit for {ticker}: {e}")
            continue


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
