#!/usr/bin/env python3
"""
scripts/run_walkforward_hybrid.py
Walk-forward validation PRO para sistema A/B/A+B.

MODELO TOP:
- Escaneo diario (sin lookahead).
- Entrada next_open ($10k notional).
- Salida fija (holding_days).
- Gate dinámico intra-fold.
- Overrides globales (A y B).
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional, List

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.signals.signal_engine import (
    SignalDecision,
    evaluate_ticker,
    merge_ab_signals,
)
from src.integration.combo_loader import load_combo_merged, load_combo_base_only
from src.integration.hybrid_gate import DEFAULT_MIN_OOS_TRADES
from src.integration.universe_builder import build_universe_for_fold, UniverseSnapshot

SignalMode = Literal["A", "B", "A_BOTH"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "ticker_cache.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "walkforward"
COMBO_ALIASES = {
    "A": "combo_pure_momentum",
    "B": "combo_stage2_breakout",
}
RS_LOOKBACK = 60
HOLDING_DAYS = 10
FEE_RATE = 0.001
SLIPPAGE = 0.0005
NOTIONAL_PER_TRADE = 10000.0  # $10k por posición
STARTING_CAPITAL = 100000.0  # $100k para cálculo de % DD


def load_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM ohlcv_cache "
        "WHERE ticker=? AND date>=? AND date<=? ORDER BY date",
        (ticker, start, end),
    ).fetchall()
    conn.close()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="mixed")
    df = df.drop_duplicates(subset=["date"]).set_index("date")
    return df.astype(float)


def _fmt_metric(value: float | None, ndigits: int = 2) -> str:
    if value is None:
        return "INF"
    return f"{value:.{ndigits}f}"


def _safe_round(value: float | None, ndigits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, ndigits)


def compute_metrics(trades: list[dict]) -> dict:
    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "profit_factor": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "expectancy": 0.0,
            "profit_factor_defined": False,
            "sharpe_defined": False,
            "low_sample": True,
        }

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins) if wins else 0.0
    gross_loss = abs(sum(losses)) if losses else 0.0

    if gross_loss > 0:
        pf = gross_profit / gross_loss
        pf_defined = True
    elif gross_profit > 0:
        pf = None
        pf_defined = False
    else:
        pf = 0.0
        pf_defined = False

    # Drawdown sobre capital de $100k
    equity = [STARTING_CAPITAL]
    peak = STARTING_CAPITAL
    max_dd = 0.0
    for pnl in pnls:
        equity.append(equity[-1] + pnl)
        peak = max(peak, equity[-1])
        dd = (peak - equity[-1]) / peak
        max_dd = max(max_dd, dd)

    wr = len(wins) / len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses)) / len(losses) if losses else 0.0
    expectancy = (wr * avg_win) - ((1 - wr) * avg_loss)

    if len(trades) < 2:
        sharpe = 0.0
        sharpe_defined = False
    else:
        mean_ret = np.mean(pnls)
        std_ret = np.std(pnls)
        sharpe_defined = std_ret > 1e-9
        sharpe = (mean_ret / std_ret) * np.sqrt(252) if sharpe_defined else 0.0

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(wr, 3),
        "total_pnl": round(sum(pnls), 2),
        "profit_factor": pf,
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "expectancy": round(expectancy, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor_defined": pf_defined,
        "sharpe_defined": sharpe_defined,
        "low_sample": len(trades) < 15,
    }


def _load_combos_for_mode(
    mode: SignalMode, combo_source: str, experiment_overrides: dict | None = None
) -> tuple[dict, dict] | dict:
    def _load(name: str) -> dict:
        loaded = (
            load_combo_merged(name)
            if combo_source == "merged"
            else (load_combo_base_only(name), None)
        )
        cfg = loaded[0]
        # Overrides Globales: Se aplican a cualquier modo (A o B) si se pasan
        if experiment_overrides:
            if "screener" not in cfg:
                cfg["screener"] = {}
            if "params" not in cfg["screener"]:
                cfg["screener"]["params"] = {}
            if "tier2_filters" not in cfg:
                cfg["tier2_filters"] = {}

            for k, v in experiment_overrides.items():
                # 1. Filtros de Régimen y Tier2
                if (
                    k
                    in [
                        "require_spy_above_sma50",
                        "require_spy_above_sma200",
                        "min_rs_percentile",
                        "min_rvol",
                        "min_adr",
                    ]
                    or k in cfg["tier2_filters"]
                ):
                    cfg["tier2_filters"][k] = v
                # 2. Screener params
                cfg["screener"]["params"][k] = v
                # 3. Screener top-level
                if k in ["min_adr_pct", "max_adr_pct", "min_price"]:
                    cfg["screener"][k] = v
        return cfg

    if mode == "A_BOTH":
        return _load(COMBO_ALIASES["A"]), _load(COMBO_ALIASES["B"])
    return _load(COMBO_ALIASES.get(mode, mode))


def generate_signals_over_window(
    universe: list[str],
    df_cache: dict,
    spy_df: pd.DataFrame,
    mode: SignalMode,
    start_date: str,
    end_date: str,
    skip_tier2: bool,
    combo_source: str,
    overrides: dict | None,
    phase: Literal["is", "oos"],
) -> tuple[list[SignalDecision], dict]:
    all_decisions = []
    funnel = {
        "n_evaluations": 0,
        "n_min_data_fail": 0,
        "n_screener_fail": 0,
        "n_tier2_fail": 0,
        "n_passed": 0,
    }

    window_days = spy_df.index[
        (spy_df.index >= start_date) & (spy_df.index <= end_date)
    ]
    if mode == "A_BOTH":
        cfg_a, cfg_b = _load_combos_for_mode(mode, combo_source, overrides)
    else:
        cfg = _load_combos_for_mode(mode, combo_source, overrides)

    for current_dt in window_days:
        curr_str = str(current_dt.date())
        spy_pit = spy_df[:current_dt]

        for ticker in universe:
            cache = df_cache.get(ticker)
            if not cache:
                continue
            df_source = cache.get(f"full_{phase}")
            if df_source is None or current_dt not in df_source.index:
                continue

            df_pit = df_source[:current_dt]
            if len(df_pit) < 65:
                funnel["n_min_data_fail"] += 1
                continue

            funnel["n_evaluations"] += 1
            if mode == "A":
                d = evaluate_ticker(
                    ticker=ticker,
                    df=df_pit,
                    spy_df=spy_pit,
                    combo_cfg=cfg,
                    mode="A",
                    skip_tier2=skip_tier2,
                    scan_date=curr_str,
                )
            elif mode == "B":
                d = evaluate_ticker(
                    ticker=ticker,
                    df=df_pit,
                    spy_df=spy_pit,
                    combo_cfg=cfg,
                    mode="B",
                    skip_tier2=skip_tier2,
                    scan_date=curr_str,
                )
            else:
                da = evaluate_ticker(
                    ticker=ticker,
                    df=df_pit,
                    spy_df=spy_pit,
                    combo_cfg=cfg_a,
                    mode="A",
                    skip_tier2=skip_tier2,
                    scan_date=curr_str,
                )
                db = evaluate_ticker(
                    ticker=ticker,
                    df=df_pit,
                    spy_df=spy_pit,
                    combo_cfg=cfg_b,
                    mode="B",
                    skip_tier2=skip_tier2,
                    scan_date=curr_str,
                )
                merged = merge_ab_signals(
                    [da] if da.passed else [], [db] if db.passed else []
                )
                d = merged[0] if merged else da

            if d.passed:
                d.signal_date = curr_str
                all_decisions.append(d)
                funnel["n_passed"] += 1
            else:
                reason = (d.reject_reason or "").lower()
                if "screener_fail" in reason:
                    funnel["n_screener_fail"] += 1
                elif "tier2_fail" in reason:
                    funnel["n_tier2_fail"] += 1
    return all_decisions, funnel


def simulate_trades_from_signals(
    signals: list[SignalDecision], df_cache: dict
) -> list[dict]:
    trades = []
    active_positions = {}
    signals.sort(key=lambda x: x.signal_date)

    for s in signals:
        ticker, signal_date = s.ticker, s.signal_date
        ts_signal = pd.Timestamp(signal_date)
        if ticker in active_positions and ts_signal <= active_positions[ticker]:
            continue

        df_source = None
        for k in ["full_is", "full_oos"]:
            df = df_cache.get(ticker, {}).get(k)
            if df is not None and ts_signal in df.index:
                df_source = df
                break
        if df_source is None:
            continue

        try:
            idx_sig = df_source.index.get_loc(ts_signal)
            if isinstance(idx_sig, slice):
                idx_sig = idx_sig.start
            if idx_sig + 1 >= len(df_source):
                continue

            idx_ent = idx_sig + 1
            idx_ext = min(idx_ent + HOLDING_DAYS, len(df_source) - 1)

            ent_p = float(df_source.iloc[idx_ent]["open"])
            ext_p = float(df_source.iloc[idx_ext]["close"])

            # Sizing: Fixed Notional ($10k por posición)
            shares = NOTIONAL_PER_TRADE / ent_p
            gross_pnl = (ext_p - ent_p) * shares
            costs = (NOTIONAL_PER_TRADE + (shares * ext_p)) * (FEE_RATE + SLIPPAGE)
            pnl = gross_pnl - costs

            trades.append(
                {
                    "ticker": ticker,
                    "mode": s.mode,
                    "signal_date": signal_date,
                    "entry_date": str(df_source.index[idx_ent].date()),
                    "exit_date": str(df_source.index[idx_ext].date()),
                    "entry_price": ent_p,
                    "exit_price": ext_p,
                    "pnl": round(pnl, 2),
                    "return_pct": round((ext_p - ent_p) / ent_p * 100, 2),
                }
            )
            active_positions[ticker] = df_source.index[idx_ext]
        except Exception:
            continue
    return trades


def run_fold(
    fold_idx,
    is_start,
    is_end,
    oos_start,
    oos_end,
    universe,
    mode,
    dry_run,
    skip_tier2,
    combo_source,
    snapshot,
    overrides,
    debug_trades=False,
) -> dict:
    logger.info(f"  FOLD {fold_idx}: OOS {oos_start} -> {oos_end}")
    if dry_run:
        return {
            "fold": fold_idx,
            "mode": mode,
            "gate": {"verdict": "HOLD", "reasons": ["dry_run"]},
        }

    fsi_spy = (pd.to_datetime(is_start) - timedelta(days=400)).strftime("%Y-%m-%d")
    fso_spy = (pd.to_datetime(oos_start) - timedelta(days=400)).strftime("%Y-%m-%d")

    is_spy = load_ohlcv("SPY", fsi_spy, is_end)
    oos_spy = load_ohlcv("SPY", fso_spy, oos_end)

    df_cache = {}
    for t in universe:
        try:
            fsi = (pd.to_datetime(is_start) - timedelta(days=300)).strftime("%Y-%m-%d")
            fso = (pd.to_datetime(oos_start) - timedelta(days=300)).strftime("%Y-%m-%d")
            df_cache[t] = {
                "full_is": load_ohlcv(t, fsi, is_end),
                "full_oos": load_ohlcv(t, fso, oos_end),
            }
        except Exception:
            continue

    is_sigs, is_fun = generate_signals_over_window(
        universe,
        df_cache,
        is_spy,
        mode,
        is_start,
        is_end,
        skip_tier2,
        combo_source,
        overrides,
        phase="is",
    )
    oos_sigs, oos_fun = generate_signals_over_window(
        universe,
        df_cache,
        oos_spy,
        mode,
        oos_start,
        oos_end,
        skip_tier2,
        combo_source,
        overrides,
        phase="oos",
    )

    is_trades = simulate_trades_from_signals(is_sigs, df_cache)
    oos_trades = simulate_trades_from_signals(oos_sigs, df_cache)

    is_m, oos_m = compute_metrics(is_trades), compute_metrics(oos_trades)

    if debug_trades and oos_trades:
        logger.info(f"    [DEBUG] OOS Trades details (Mode {mode}):")
        for t in oos_trades[:15]:
            logger.info(
                f"      {t['ticker']} | Sig: {t['signal_date']} | Ent: {t['entry_date']} @ {t['entry_price']:.2f} | Ext: {t['exit_date']} @ {t['exit_price']:.2f} | PnL: ${t['pnl']}"
            )
        if len(oos_trades) > 15:
            logger.info(f"      ... and {len(oos_trades) - 15} more.")

    gate_v = "HOLD"
    if oos_m["trades"] >= DEFAULT_MIN_OOS_TRADES:
        if (oos_m["profit_factor"] is None or oos_m["profit_factor"] >= 1.2) and oos_m[
            "win_rate"
        ] >= 0.35:
            gate_v = "PROMOTE"
        else:
            gate_v = "REJECT"

    res = {
        "fold": fold_idx,
        "mode": mode,
        "is_start": is_start,
        "is_end": is_end,
        "oos_start": oos_start,
        "oos_end": oos_end,
        "is_metrics": is_m,
        "oos_metrics": oos_m,
        "gate": {"verdict": gate_v},
        "funnel": {"is": is_fun, "oos": oos_fun},
        "oos_tickers": sorted({s.ticker for s in oos_sigs}),
        "oos_signal_count": len(oos_sigs),
        "is_tickers": sorted({s.ticker for s in is_sigs}),
        "is_signal_count": len(is_sigs),
    }
    if snapshot:
        res["universe"] = {
            "n_tickers": snapshot.n_selected,
            "tickers": snapshot.tickers,
        }

    logger.info(
        f"    IS: {is_m['trades']} trades (PF={_fmt_metric(is_m['profit_factor'])}) | OOS: {oos_m['trades']} trades (PF={_fmt_metric(oos_m['profit_factor'])}) | GATE: {gate_v}"
    )
    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--modes", nargs="+", default=["A", "B", "A_BOTH"])
    parser.add_argument("--max-tickers", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-tier2", action="store_true")
    parser.add_argument("--debug-trades", action="store_true")
    parser.add_argument("--combo-source", choices=["merged", "base"], default="merged")
    parser.add_argument("--override-a-min-rs-percentile", type=float)
    parser.add_argument("--override-a-min-trend-intensity", type=float)
    parser.add_argument("--override-a-min-adr-pct", type=float)
    parser.add_argument("--override-a-require-ma-stack", choices=["true", "false"])
    parser.add_argument(
        "--override-a-require-spy-above-sma50", choices=["true", "false"]
    )
    parser.add_argument(
        "--override-a-require-spy-above-sma200", choices=["true", "false"]
    )
    args = parser.parse_args()

    overrides = {}
    if args.override_a_min_rs_percentile:
        overrides["min_rs_percentile"] = args.override_a_min_rs_percentile
    if args.override_a_min_trend_intensity:
        overrides["min_trend_intensity"] = args.override_a_min_trend_intensity
    if args.override_a_min_adr_pct:
        overrides["min_adr_pct"] = args.override_a_min_adr_pct
    if args.override_a_require_ma_stack:
        overrides["require_ma_stack"] = args.override_a_require_ma_stack == "true"
    if args.override_a_require_spy_above_sma50:
        overrides["require_spy_above_sma50"] = (
            args.override_a_require_spy_above_sma50 == "true"
        )
    if args.override_a_require_spy_above_sma200:
        overrides["require_spy_above_sma200"] = (
            args.override_a_require_spy_above_sma200 == "true"
        )

    s_dt, e_dt = pd.to_datetime(args.start), pd.to_datetime(args.end)
    oos_days = (e_dt - s_dt).days // args.folds
    folds = []
    for i in range(1, args.folds):
        is_e = s_dt + timedelta(days=oos_days * i - 1)
        oos_s = s_dt + timedelta(days=oos_days * i)
        oos_e = s_dt + timedelta(days=oos_days * (i + 1))
        if oos_e > e_dt:
            oos_e = e_dt
        folds.append(
            (
                args.start,
                is_e.strftime("%Y-%m-%d"),
                oos_s.strftime("%Y-%m-%d"),
                oos_e.strftime("%Y-%m-%d"),
            )
        )

    u_lb_s = (pd.to_datetime(args.start) - timedelta(days=730)).strftime("%Y-%m-%d")
    all_results = []
    for mode in args.modes:
        logger.info(f"Evaluating Mode: {mode}")
        f_results = []
        for i, (is_s, is_e, oos_s, oos_e) in enumerate(folds):
            snap = build_universe_for_fold(DB_PATH, is_e, u_lb_s, args.max_tickers)
            f_results.append(
                run_fold(
                    i,
                    is_s,
                    is_e,
                    oos_s,
                    oos_e,
                    snap.tickers,
                    mode,
                    args.dry_run,
                    args.skip_tier2,
                    args.combo_source,
                    snap,
                    overrides,
                    args.debug_trades,
                )
            )
        all_results.append({"mode": mode, "folds": f_results})

    out_dir = OUTPUT_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "walkforward_report.json", "w") as f:
        json.dump(
            {"generated_at": datetime.now().isoformat(), "results": all_results},
            f,
            indent=2,
            default=str,
        )

    print(f"\nReport: {out_dir / 'walkforward_report.json'}")


if __name__ == "__main__":
    main()
