#!/usr/bin/env python3
"""Backtest reproducible de presets (Ablation B) con flujo event-driven."""

from __future__ import annotations

import argparse
import inspect
import json
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.ticker_cache import TickerCache
from src.strategies import preset_filter_library as pfl


DEFAULT_SPEC = PROJECT_ROOT / "config" / "presets" / "screener_presets_v1.json"
DEFAULT_DB = PROJECT_ROOT / "data" / "ticker_cache.db"
DEFAULT_OUT_DIR = PROJECT_ROOT / "outputs" / "backtests" / "presets"


@dataclass
class DbResolution:
    effective_db_path: Path
    using_snapshot: bool
    snapshot_dir: Optional[Path]


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _is_db_locked_error(error: BaseException) -> bool:
    return "database is locked" in str(error).lower()


def load_spec(path: Path) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copy2(src, dst)


def _create_db_snapshot(db_path: Path) -> DbResolution:
    temp_dir = Path(tempfile.mkdtemp(prefix="preset_db_snapshot_"))
    snapshot_db = temp_dir / db_path.name
    _copy_if_exists(db_path, snapshot_db)
    _copy_if_exists(db_path.with_suffix(".db-wal"), snapshot_db.with_suffix(".db-wal"))
    _copy_if_exists(db_path.with_suffix(".db-shm"), snapshot_db.with_suffix(".db-shm"))
    return DbResolution(
        effective_db_path=snapshot_db,
        using_snapshot=True,
        snapshot_dir=temp_dir,
    )


def resolve_db_path(db_path: Path, snapshot_fallback: bool) -> DbResolution:
    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
        try:
            conn.execute("SELECT 1 FROM ohlcv_cache LIMIT 1").fetchone()
        finally:
            conn.close()
        return DbResolution(
            effective_db_path=db_path,
            using_snapshot=False,
            snapshot_dir=None,
        )
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower() and snapshot_fallback:
            return _create_db_snapshot(db_path)
        raise


def cleanup_db_resolution(resolution: DbResolution) -> None:
    if resolution.snapshot_dir and resolution.snapshot_dir.exists():
        shutil.rmtree(resolution.snapshot_dir, ignore_errors=True)


def _switch_to_snapshot_resolution(
    current: DbResolution,
    db_path: Path,
    snapshot_fallback: bool,
) -> DbResolution:
    if not snapshot_fallback:
        raise sqlite3.OperationalError("database is locked")
    if current.using_snapshot:
        raise sqlite3.OperationalError("database is locked (snapshot already in use)")
    replacement = _create_db_snapshot(db_path)
    cleanup_db_resolution(current)
    return replacement


def load_top_tickers(db_path: Path, start: str, end: str, top: int) -> list[str]:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    try:
        rows = conn.execute(
            """
            SELECT ticker, AVG(close * volume) AS avg_dv
            FROM ohlcv_cache
            WHERE date BETWEEN ? AND ?
            GROUP BY ticker
            HAVING COUNT(*) >= 60
            ORDER BY avg_dv DESC
            LIMIT ?
            """,
            (start, end, int(top)),
        ).fetchall()
    finally:
        conn.close()
    return [str(r[0]).upper() for r in rows]


def load_top_tickers_with_fallback(
    db_resolution: DbResolution,
    db_path: Path,
    start: str,
    end: str,
    top: int,
    snapshot_fallback: bool,
) -> tuple[list[str], DbResolution]:
    try:
        return (
            load_top_tickers(
                db_resolution.effective_db_path, start=start, end=end, top=top
            ),
            db_resolution,
        )
    except sqlite3.OperationalError as e:
        if not _is_db_locked_error(e):
            raise
        new_resolution = _switch_to_snapshot_resolution(
            current=db_resolution,
            db_path=db_path,
            snapshot_fallback=snapshot_fallback,
        )
        return (
            load_top_tickers(
                new_resolution.effective_db_path, start=start, end=end, top=top
            ),
            new_resolution,
        )


def load_ohlcv_batch_with_fallback(
    db_resolution: DbResolution,
    db_path: Path,
    tickers: list[str],
    start_date: str,
    end_date: str,
    snapshot_fallback: bool,
) -> tuple[dict[str, pd.DataFrame], DbResolution]:
    def _load_individual(cache: TickerCache) -> dict[str, pd.DataFrame]:
        out_individual: dict[str, pd.DataFrame] = {}
        for ticker in tickers:
            try:
                df_one = cache.get_ohlcv(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    offline=True,
                )
            except Exception:
                continue
            if df_one is not None and not df_one.empty:
                out_individual[ticker] = df_one
        return out_individual

    try:
        cache = TickerCache(db_path=db_resolution.effective_db_path)
        try:
            try:
                out = cache.get_ohlcv_batch(
                    tickers=tickers,
                    start_date=start_date,
                    end_date=end_date,
                    offline=True,
                )
            except ValueError:
                out = _load_individual(cache)
        finally:
            cache.close()
        if out or db_resolution.using_snapshot or not snapshot_fallback:
            return out, db_resolution
        new_resolution = _switch_to_snapshot_resolution(
            current=db_resolution,
            db_path=db_path,
            snapshot_fallback=snapshot_fallback,
        )
        cache = TickerCache(db_path=new_resolution.effective_db_path)
        try:
            out_retry = cache.get_ohlcv_batch(
                tickers=tickers,
                start_date=start_date,
                end_date=end_date,
                offline=True,
            )
        finally:
            cache.close()
        return out_retry, new_resolution
    except sqlite3.OperationalError as e:
        if not _is_db_locked_error(e):
            raise
        new_resolution = _switch_to_snapshot_resolution(
            current=db_resolution,
            db_path=db_path,
            snapshot_fallback=snapshot_fallback,
        )
        cache = TickerCache(db_path=new_resolution.effective_db_path)
        try:
            try:
                out = cache.get_ohlcv_batch(
                    tickers=tickers,
                    start_date=start_date,
                    end_date=end_date,
                    offline=True,
                )
            except ValueError:
                out = _load_individual(cache)
        finally:
            cache.close()
        return out, new_resolution


def normalize_ohlcv_map(raw_map: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for ticker, raw_df in raw_map.items():
        if raw_df is None or raw_df.empty:
            continue
        out[ticker] = normalize_ohlcv(raw_df).sort_index()
    return out


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    out.rename(columns=rename_map, inplace=True)
    for col in ["open", "high", "low", "close", "volume"]:
        if col not in out.columns:
            raise ValueError(f"Falta columna OHLCV requerida: {col}")
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    if out.index.has_duplicates:
        out = out[~out.index.duplicated(keep="last")]
    out = out.sort_index()
    return out


def build_rs_rank_map(
    universe_ohlcv_map: dict[str, pd.DataFrame],
) -> dict[str, pd.Series]:
    returns_21d: dict[str, pd.Series] = {}
    for ticker, df in universe_ohlcv_map.items():
        close = df["close"].astype(float)
        returns_21d[ticker] = close.pct_change(21)
    if not returns_21d:
        return {}
    cross = pd.DataFrame(returns_21d)
    ranks = cross.rank(axis=1, pct=True) * 100.0
    return {ticker: ranks[ticker] for ticker in ranks.columns}


DISPATCH: dict[str, Callable] = {
    "market_cap_min": pfl.market_cap_min,
    "avg_volume_50_min": pfl.avg_volume_50_min,
    "adr_50_min": pfl.adr_50_min,
    "trend_base": pfl.trend_base,
    "rel_volume_min": pfl.rel_volume_min,
    "power_play": pfl.power_play,
    "power_play_cluster_20d_min3": pfl.power_play_cluster_20d_min3,
    "vcs_score_min": pfl.vcs_score_min,
    "near_52w_high_band": pfl.near_52w_high_band,
    "weekly_return_min": pfl.weekly_return_min,
    "ll_hl_confirmed": pfl.ll_hl_confirmed,
    "fib_0618_break_between_hl_and_swing_high": pfl.fib_0618_break_between_hl_and_swing_high,
    "second_pivot_break_swing_high": pfl.second_pivot_break_swing_high,
    "downtrend_line_break": pfl.downtrend_line_break,
}


def _coerce_series_bool(series: pd.Series, index: pd.Index) -> pd.Series:
    aligned = series.reindex(index).fillna(False)
    return aligned.astype(bool)


def _override_params(filter_id: str, defaults: dict, preset_params: dict) -> dict:
    params = dict(defaults)
    if filter_id == "vcs_score_min" and "vcs_min" in preset_params:
        params["minimum"] = float(preset_params["vcs_min"])
    if filter_id == "near_52w_high_band":
        if "high_distance_min_pct" in preset_params:
            params["min_pct"] = float(preset_params["high_distance_min_pct"])
        if "high_distance_max_pct" in preset_params:
            params["max_pct"] = float(preset_params["high_distance_max_pct"])
    return params


def evaluate_filter_series(
    filter_id: str,
    df: pd.DataFrame,
    ticker: str,
    filter_defaults: dict,
    preset_params: dict,
    rs_rank_map: dict[str, pd.Series],
) -> pd.Series:
    if filter_id == "rs_1m_percentile_min":
        minimum = float(filter_defaults.get("minimum_pct", 70.0))
        series = rs_rank_map.get(ticker, pd.Series(np.nan, index=df.index))
        return _coerce_series_bool(series >= minimum, df.index)

    func = DISPATCH.get(filter_id)
    if func is None:
        raise ValueError(f"Filter id no implementado en dispatch: {filter_id}")

    params = _override_params(filter_id, filter_defaults, preset_params)
    sig = inspect.signature(func)
    kwargs = {}
    for name in sig.parameters:
        if name == "df":
            continue
        if name in params:
            kwargs[name] = params[name]
    out = func(df=df, **kwargs)
    return _coerce_series_bool(out, df.index)


@dataclass
class TradeResult:
    rows: list[dict]
    signal_rows: list[dict]


def simulate_preset_trades(
    preset_id: str,
    ticker: str,
    df: pd.DataFrame,
    preset_hit: pd.Series,
    requires: list[str],
    filter_states: dict[str, pd.Series],
    backtest_cfg: dict,
) -> TradeResult:
    current = preset_hit.astype(bool)
    previous = preset_hit.shift(1, fill_value=False).astype(bool)
    signals = current & (~previous)
    signal_rows: list[dict] = []
    trades: list[dict] = []

    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    stop_pct = float(backtest_cfg["stop_pct"])
    target_pct = float(backtest_cfg["target_pct"])
    timeout_bars = int(backtest_cfg["timeout_bars"])
    slippage_bps = float(backtest_cfg["slippage_bps"])
    fee_bps = float(backtest_cfg["fee_bps"])
    side_cost = (slippage_bps + fee_bps) / 10000.0

    for i in range(len(df)):
        if not bool(signals.iloc[i]):
            continue
        entry_idx = i + 1
        if entry_idx >= len(df):
            continue
        dt = pd.Timestamp(df.index[entry_idx]).strftime("%Y-%m-%d")
        signal_rows.append(
            {
                "preset_id": preset_id,
                "ticker": ticker,
                "signal_date": pd.Timestamp(df.index[i]).strftime("%Y-%m-%d"),
                "entry_date": dt,
                "entry_signal": True,
                "entry_price_rule": "open_t_plus_1",
                "preset_hit": True,
                "reason_codes": "|".join(
                    [r for r in requires if bool(filter_states[r].iloc[i])]
                ),
            }
        )

    i = 0
    in_position = False
    entry_idx = -1
    entry_price = 0.0

    while i < len(df):
        if not in_position:
            if bool(signals.iloc[i]) and i + 1 < len(df):
                entry_idx = i + 1
                entry_price = float(open_.iloc[entry_idx]) * (1.0 + side_cost)
                in_position = True
                i = entry_idx
            else:
                i += 1
            continue

        bars_held = i - entry_idx + 1
        stop = entry_price * (1.0 - stop_pct)
        target = entry_price * (1.0 + target_pct)

        exit_reason = ""
        gross_exit = float(close.iloc[i])
        if float(low.iloc[i]) <= stop:
            gross_exit = stop
            exit_reason = "stop"
        elif float(high.iloc[i]) >= target:
            gross_exit = target
            exit_reason = "target"
        elif bars_held >= timeout_bars:
            gross_exit = float(close.iloc[i])
            exit_reason = "timeout"
        elif i == len(df) - 1:
            gross_exit = float(close.iloc[i])
            exit_reason = "eod"

        if exit_reason:
            exit_price = gross_exit * (1.0 - side_cost)
            pnl = exit_price - entry_price
            initial_risk = max(entry_price * stop_pct, 1e-9)
            trades.append(
                {
                    "preset_id": preset_id,
                    "ticker": ticker,
                    "entry_date": pd.Timestamp(df.index[entry_idx]).strftime(
                        "%Y-%m-%d"
                    ),
                    "exit_date": pd.Timestamp(df.index[i]).strftime("%Y-%m-%d"),
                    "entry_price": round(entry_price, 6),
                    "exit_price": round(exit_price, 6),
                    "pnl": round(pnl, 6),
                    "r_multiple": round(pnl / initial_risk, 6),
                    "exit_reason": exit_reason,
                }
            )
            in_position = False
        i += 1

    return TradeResult(rows=trades, signal_rows=signal_rows)


def compute_metrics(trades_df: pd.DataFrame, initial_capital: float) -> dict:
    if trades_df.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "profit_factor": 0.0,
            "payoff_ratio": 0.0,
            "max_dd": 0.0,
            "sharpe": 0.0,
        }

    trades = trades_df.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"], errors="coerce")
    trades["exit_date"] = pd.to_datetime(trades["exit_date"], errors="coerce")
    trades = trades.sort_values(
        by=["exit_date", "entry_date", "ticker"], kind="mergesort"
    )

    pnl = trades["pnl"].astype(float)
    r_mult = trades["r_multiple"].astype(float)
    wins = r_mult[r_mult > 0]
    losses = r_mult[r_mult <= 0]
    win_rate = float((r_mult > 0).mean())
    loss_rate = 1.0 - win_rate
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    expectancy = (win_rate * avg_win) - (loss_rate * abs(avg_loss))

    total_profit = float(pnl[pnl > 0].sum())
    total_loss = abs(float(pnl[pnl < 0].sum()))
    if total_loss > 0:
        profit_factor = total_profit / total_loss
    else:
        profit_factor = 999.0 if total_profit > 0 else 0.0

    payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss < 0 else 0.0

    equity = initial_capital + pnl.cumsum()
    running_max = equity.cummax().replace(0.0, np.nan)
    drawdown = (equity / running_max) - 1.0
    max_dd = float(drawdown.min()) if not drawdown.empty else 0.0

    trade_returns = pnl / trades["entry_price"].replace(0.0, np.nan)
    trade_returns = trade_returns.replace([np.inf, -np.inf], np.nan).dropna()
    tr_std = float(trade_returns.std(ddof=0)) if len(trade_returns) > 1 else 0.0
    if len(trade_returns) >= 3 and tr_std > 1e-9:
        sharpe = float(trade_returns.mean() / tr_std * np.sqrt(len(trade_returns)))
    else:
        sharpe = 0.0

    return {
        "trades": int(len(trades_df)),
        "win_rate": round(win_rate, 6),
        "avg_win": round(avg_win, 6),
        "avg_loss": round(avg_loss, 6),
        "expectancy": round(expectancy, 6),
        "profit_factor": round(float(profit_factor), 6),
        "payoff_ratio": round(float(payoff_ratio), 6),
        "max_dd": round(max_dd, 6),
        "sharpe": round(sharpe, 6),
    }


def gate_promotion(metrics: dict, gate_cfg: dict) -> tuple[bool, list[str]]:
    checks = {
        "min_trades": metrics["trades"] >= int(gate_cfg.get("min_trades", 0)),
        "min_expectancy": metrics["expectancy"]
        >= float(gate_cfg.get("min_expectancy", 0.0)),
        "min_profit_factor": metrics["profit_factor"]
        >= float(gate_cfg.get("min_profit_factor", 0.0)),
        "min_sharpe": metrics["sharpe"] >= float(gate_cfg.get("min_sharpe", -999.0)),
        "max_dd": metrics["max_dd"] >= -abs(float(gate_cfg.get("max_dd", 1.0))),
    }
    failed = [k for k, passed in checks.items() if not passed]
    return len(failed) == 0, failed


def run(args: argparse.Namespace) -> dict:
    spec = load_spec(Path(args.spec))
    filter_defaults = spec.get("filter_defaults", {})
    backtest_cfg = spec.get("backtest_defaults", {})
    gate_cfg = spec.get("promotion_gate", {})

    db_path = Path(args.db_path)
    snapshot_fallback = parse_bool(args.db_snapshot_fallback)
    db_resolution = resolve_db_path(db_path, snapshot_fallback=snapshot_fallback)

    try:
        if args.tickers:
            tickers = [t.upper() for t in args.tickers]
        else:
            tickers, db_resolution = load_top_tickers_with_fallback(
                db_resolution=db_resolution,
                db_path=db_path,
                start=args.start,
                end=args.end,
                top=args.top,
                snapshot_fallback=snapshot_fallback,
            )
        if not tickers:
            raise RuntimeError(
                "No se encontraron tickers para ejecutar el pack de presets"
            )

        if args.rs_tickers:
            rs_universe = [t.upper() for t in args.rs_tickers]
        else:
            rs_universe, db_resolution = load_top_tickers_with_fallback(
                db_resolution=db_resolution,
                db_path=db_path,
                start=args.start,
                end=args.end,
                top=args.rs_top,
                snapshot_fallback=snapshot_fallback,
            )
        rs_universe = sorted(set(rs_universe).union(set(tickers)))

        run_raw, db_resolution = load_ohlcv_batch_with_fallback(
            db_resolution=db_resolution,
            db_path=db_path,
            tickers=tickers,
            start_date=args.start,
            end_date=args.end,
            snapshot_fallback=snapshot_fallback,
        )
        ohlcv_map = normalize_ohlcv_map(run_raw)

        rs_raw, db_resolution = load_ohlcv_batch_with_fallback(
            db_resolution=db_resolution,
            db_path=db_path,
            tickers=rs_universe,
            start_date=args.start,
            end_date=args.end,
            snapshot_fallback=snapshot_fallback,
        )
        rs_ohlcv_map = normalize_ohlcv_map(rs_raw)
        rs_rank_map = build_rs_rank_map(rs_ohlcv_map)
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        summary_rows = []
        promotion_rows = []

        for preset in spec.get("presets", []):
            preset_id = preset["id"]
            requires = list(preset.get("requires", []))
            preset_params = dict(preset.get("params", {}))

            all_trades = []
            all_signals = []
            for ticker, df in ohlcv_map.items():
                if len(df) < 70:
                    continue
                filter_states: dict[str, pd.Series] = {}
                for filter_id in requires:
                    defaults = dict(filter_defaults.get(filter_id, {}))
                    filter_states[filter_id] = evaluate_filter_series(
                        filter_id=filter_id,
                        df=df,
                        ticker=ticker,
                        filter_defaults=defaults,
                        preset_params=preset_params,
                        rs_rank_map=rs_rank_map,
                    )

                if not filter_states:
                    continue
                preset_hit = pd.Series(True, index=df.index)
                for state in filter_states.values():
                    preset_hit &= state

                trade_result = simulate_preset_trades(
                    preset_id=preset_id,
                    ticker=ticker,
                    df=df,
                    preset_hit=preset_hit,
                    requires=requires,
                    filter_states=filter_states,
                    backtest_cfg=backtest_cfg,
                )
                all_trades.extend(trade_result.rows)
                all_signals.extend(trade_result.signal_rows)

            trades_df = pd.DataFrame(all_trades)
            signals_df = pd.DataFrame(all_signals)
            preset_suffix = (
                preset_id[len("preset_") :]
                if str(preset_id).startswith("preset_")
                else str(preset_id)
            )
            trades_path = out_dir / f"preset_{preset_suffix}_trades.csv"
            signals_path = out_dir / f"preset_{preset_suffix}_signals.csv"
            if trades_df.empty:
                trades_df = pd.DataFrame(
                    columns=[
                        "preset_id",
                        "ticker",
                        "entry_date",
                        "exit_date",
                        "entry_price",
                        "exit_price",
                        "pnl",
                        "r_multiple",
                        "exit_reason",
                    ]
                )
            if signals_df.empty:
                signals_df = pd.DataFrame(
                    columns=[
                        "preset_id",
                        "ticker",
                        "signal_date",
                        "entry_date",
                        "entry_signal",
                        "entry_price_rule",
                        "preset_hit",
                        "reason_codes",
                    ]
                )

            trades_df.to_csv(trades_path, index=False)
            signals_df.to_csv(signals_path, index=False)

            metrics = compute_metrics(
                trades_df,
                initial_capital=float(backtest_cfg.get("initial_capital", 100000)),
            )
            promote, failed_checks = gate_promotion(metrics, gate_cfg)

            summary = {
                "preset_id": preset_id,
                "preset_name": preset.get("name", ""),
                "stage": preset.get("stage", ""),
                "status": preset.get("status", ""),
                "requires": "|".join(requires),
                "signals": int(len(signals_df)),
                "candidate_promotion": bool(promote),
                "failed_gate_checks": "|".join(failed_checks),
            }
            summary.update(metrics)
            summary_rows.append(summary)
            promotion_rows.append(
                {
                    "preset_id": preset_id,
                    "candidate": bool(promote),
                    "failed_checks": failed_checks,
                    "metrics": metrics,
                }
            )

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_df = pd.DataFrame(summary_rows).sort_values(
            by=["candidate_promotion", "expectancy"], ascending=[False, False]
        )
        summary_csv = out_dir / f"preset_summary_{ts}.csv"
        summary_json = out_dir / f"preset_summary_{ts}.json"
        summary_df.to_csv(summary_csv, index=False)

        payload = {
            "generated_at": ts,
            "start": args.start,
            "end": args.end,
            "tickers": tickers,
            "rs_universe_count": len(rs_ohlcv_map),
            "db_path": str(db_resolution.effective_db_path),
            "db_snapshot_fallback_used": db_resolution.using_snapshot,
            "summary": summary_rows,
            "gate": gate_cfg,
            "promotion_candidates": promotion_rows,
        }
        with open(summary_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        gate_artifact = out_dir / f"preset_gate_input_{ts}.json"
        with open(gate_artifact, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "type": "system_b_presets_gate_input",
                    "summary_json": str(summary_json),
                    "promotion_candidates": promotion_rows,
                },
                f,
                indent=2,
            )

        return {
            "summary_csv": str(summary_csv),
            "summary_json": str(summary_json),
            "gate_artifact": str(gate_artifact),
            "used_snapshot": db_resolution.using_snapshot,
            "tickers_count": len(tickers),
            "presets_count": len(summary_rows),
        }
    finally:
        cleanup_db_resolution(db_resolution)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest pack de 12 presets (Ablation B)"
    )
    parser.add_argument("--start", type=str, required=True)
    parser.add_argument("--end", type=str, required=True)
    parser.add_argument("--top", type=int, default=200)
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--rs-top", type=int, default=500)
    parser.add_argument("--rs-tickers", nargs="+", default=None)
    parser.add_argument("--db-path", type=str, default=str(DEFAULT_DB))
    parser.add_argument("--db-snapshot-fallback", type=str, default="true")
    parser.add_argument("--spec", type=str, default=str(DEFAULT_SPEC))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUT_DIR))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = run(args)
    print("=" * 80)
    print("BACKTEST PRESETS PACK (SYSTEM B)")
    print("=" * 80)
    print(f"Tickers: {result['tickers_count']}")
    print(f"Presets: {result['presets_count']}")
    print(f"Snapshot fallback usado: {result['used_snapshot']}")
    print(f"Summary CSV: {result['summary_csv']}")
    print(f"Summary JSON: {result['summary_json']}")
    print(f"Gate artifact: {result['gate_artifact']}")


if __name__ == "__main__":
    main()
