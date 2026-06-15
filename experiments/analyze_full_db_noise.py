#!/usr/bin/env python3
"""Analyze noise vs useful expansion for the full DB Gold Standard experiment.

Calculates key trading metrics (Win Rate, Profit Factor, Expectancy) and desgloses
(Yearly, Sector, Liquidity buckets, Ticker Concentration, and Incremental Degradation U1->U4).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def _spearman(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 3 or len(b) < 3:
        return 0.0
    return float(a.corr(b, method="spearman"))


def calculate_subset_metrics(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_rmult": 0.0,
            "expectancy_pnl": 0.0,
            "expectancy_pct": 0.0,
        }

    total_trades = len(df)
    pnl_col = None
    for col in ["pnl", "r_multiple", "return_pct", "return"]:
        if col in df.columns:
            pnl_col = col
            break

    if pnl_col is None:
        return {
            "trades": total_trades,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy_rmult": 0.0,
            "expectancy_pnl": 0.0,
            "expectancy_pct": 0.0,
        }

    wins = df[df[pnl_col] > 0]
    losses = df[df[pnl_col] < 0]

    win_count = len(wins)
    win_rate = float(win_count / total_trades * 100) if total_trades > 0 else 0.0

    # Profit Factor: Gross Profits / Gross Losses
    gross_profits = float(wins[pnl_col].sum())
    gross_losses = float(losses[pnl_col].sum())
    profit_factor = (
        float(gross_profits / abs(gross_losses))
        if gross_losses != 0
        else (gross_profits if gross_profits > 0 else 1.0)
    )
    if np.isinf(profit_factor) or np.isnan(profit_factor):
        profit_factor = 99.0

    expectancy_rmult = float(df["r_multiple"].mean()) if "r_multiple" in df.columns else 0.0
    expectancy_pnl = float(df["pnl"].mean()) if "pnl" in df.columns else 0.0
    expectancy_pct = float(df["return_pct"].mean()) if "return_pct" in df.columns else 0.0

    return {
        "trades": int(total_trades),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_rmult": round(expectancy_rmult, 4),
        "expectancy_pnl": round(expectancy_pnl, 2),
        "expectancy_pct": round(expectancy_pct, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze experiment noise and degradation")
    parser.add_argument("--trades", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not Path(args.trades).exists() or Path(args.trades).stat().st_size == 0:
        Path(args.output).write_text(json.dumps({"status": "empty", "message": "No trades found (empty file)"}, indent=2))
        return 0

    try:
        trades = pd.read_csv(args.trades)
    except pd.errors.EmptyDataError:
        Path(args.output).write_text(json.dumps({"status": "empty", "message": "No trades found (empty columns)"}, indent=2))
        return 0

    metrics = json.loads(Path(args.metrics).read_text())

    if trades.empty:
        Path(args.output).write_text(json.dumps({"status": "empty", "message": "No trades found (empty dataframe)"}, indent=2))
        return 0

    # Clean date column
    date_col = "entry_date" if "entry_date" in trades.columns else trades.columns[0]
    trades[date_col] = pd.to_datetime(trades[date_col], errors="coerce")
    trades = trades.dropna(subset=[date_col])

    # Extract ticker column
    symbol_col = None
    for c in ["symbol", "ticker"]:
        if c in trades.columns:
            symbol_col = c
            break
    if symbol_col is None:
        raise ValueError("Could not find ticker/symbol column in trades")

    # Connect to local cache SQLite database to fetch sectors and average dollar volumes
    db_path = PROJECT_ROOT / "data" / "ticker_cache.db"
    sector_map = {}
    dvol_map = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            # Load sectors
            sec_df = pd.read_sql_query("SELECT ticker, sector FROM universe", conn)
            sector_map = dict(zip(sec_df["ticker"], sec_df["sector"]))
            # Load average dollar volume
            dvol_df = pd.read_sql_query(
                "SELECT ticker, AVG(rolling_dollar_vol_20) AS avg_dvol FROM ohlcv_cache GROUP BY ticker",
                conn,
            )
            dvol_map = dict(zip(dvol_df["ticker"], dvol_df["avg_dvol"]))
            conn.close()
        except Exception as e:
            print(f"Warning: Could not fetch metadata from SQLite cache DB ({e})", file=sys.stderr)

    # Map sector and liquidity values
    trades["sector"] = trades[symbol_col].map(sector_map).fillna("Unknown")
    trades["avg_dvol"] = trades[symbol_col].map(dvol_map).fillna(0.0)

    # Assign liquidity buckets
    def get_liq_bucket(dvol: float) -> str:
        if dvol <= 0:
            return "0_Unknown"
        elif dvol < 5_000_000:
            return "1_Low (<$5M)"
        elif dvol < 15_000_000:
            return "2_Medium ($5M-$15M)"
        elif dvol < 50_000_000:
            return "3_High ($15M-$50M)"
        else:
            return "4_Mega (>= $50M)"

    trades["liquidity_bucket"] = trades["avg_dvol"].apply(get_liq_bucket)

    analysis: dict[str, Any] = {
        "rows": int(len(trades)),
        "unique_symbols": int(trades[symbol_col].nunique()),
        "years": sorted(trades[date_col].dt.year.dropna().unique().tolist()),
        "overall": calculate_subset_metrics(trades),
    }

    # Spearman rank correlation
    if "entry_score" in trades.columns and "r_multiple" in trades.columns:
        analysis["spearman_score_rmultiple"] = _spearman(
            trades["entry_score"], trades["r_multiple"]
        )
    if "entry_score" in trades.columns and "return_pct" in trades.columns:
        analysis["spearman_score_returnpct"] = _spearman(
            trades["entry_score"], trades["return_pct"]
        )

    # 1. GROUP BY COMBO + LAYER Metrics
    if "combo_name" in trades.columns and "universe_layer" in trades.columns:
        by_combo_layer = []
        for (combo, layer), grp in trades.groupby(["combo_name", "universe_layer"]):
            m = calculate_subset_metrics(grp)
            m.update({"combo_name": combo, "universe_layer": layer})
            by_combo_layer.append(m)
        analysis["by_combo_layer"] = by_combo_layer

    # 2. YEARLY BREAKDOWN PER LAYER
    yearly = []
    for (year, layer), grp in trades.groupby([trades[date_col].dt.year, "universe_layer"]):
        m = calculate_subset_metrics(grp)
        m.update({"year": int(year), "universe_layer": layer})
        yearly.append(m)
    analysis["yearly_breakdown"] = yearly

    # 3. SECTOR BREAKDOWN PER LAYER
    sector_breakdown = []
    for (sec, layer), grp in trades.groupby(["sector", "universe_layer"]):
        m = calculate_subset_metrics(grp)
        m.update({"sector": sec, "universe_layer": layer})
        sector_breakdown.append(m)
    analysis["sector_breakdown"] = sector_breakdown

    # 4. LIQUIDITY BUCKET BREAKDOWN PER LAYER
    liquidity_breakdown = []
    for (liq, layer), grp in trades.groupby(["liquidity_bucket", "universe_layer"]):
        m = calculate_subset_metrics(grp)
        m.update({"liquidity_bucket": liq, "universe_layer": layer})
        liquidity_breakdown.append(m)
    analysis["liquidity_breakdown"] = liquidity_breakdown

    # 5. TICKER CONCENTRATION PER LAYER
    concentration = {}
    for layer, grp in trades.groupby("universe_layer"):
        ticker_counts = grp[symbol_col].value_counts()
        top_5 = ticker_counts.head(5)
        total_layer_trades = len(grp)
        top_5_trades = int(top_5.sum())
        top_5_pct = float(top_5_trades / total_layer_trades * 100) if total_layer_trades > 0 else 0.0
        concentration[str(layer)] = {
            "top_5_tickers": top_5.to_dict(),
            "top_5_trades": top_5_trades,
            "top_5_pct": round(top_5_pct, 2),
        }
    analysis["ticker_concentration"] = concentration

    # 6. INCREMENTAL DEGRADATION (U1 -> U2 -> U3 -> U4)
    degradation = {}
    for layer in [
        "U1_pit_validated",
        "U2_db_liquidity_strong",
        "U3_db_liquidity_medium",
        "U4_db_broad",
    ]:
        grp = trades[trades["universe_layer"] == layer]
        metrics_dict = calculate_subset_metrics(grp)
        degradation[layer] = metrics_dict

    # Calculate absolute and relative degradation from U1 baseline
    u1_base = degradation.get("U1_pit_validated", {})
    if u1_base and u1_base.get("trades", 0) > 0:
        for layer in ["U2_db_liquidity_strong", "U3_db_liquidity_medium", "U4_db_broad"]:
            curr = degradation[layer]
            if curr.get("trades", 0) > 0:
                curr["degradation_vs_u1"] = {
                    "win_rate_diff": round(curr["win_rate"] - u1_base["win_rate"], 2),
                    "profit_factor_diff": round(curr["profit_factor"] - u1_base["profit_factor"], 2),
                    "expectancy_rmult_diff": round(curr["expectancy_rmult"] - u1_base["expectancy_rmult"], 4),
                    "win_rate_pct_change": round((curr["win_rate"] - u1_base["win_rate"]) / (u1_base["win_rate"] or 1.0) * 100, 2),
                    "profit_factor_pct_change": round((curr["profit_factor"] - u1_base["profit_factor"]) / (u1_base["profit_factor"] or 1.0) * 100, 2),
                }

    analysis["incremental_degradation"] = degradation
    analysis["metrics_keys"] = list(metrics.keys())
    analysis["status"] = "ok"

    Path(args.output).write_text(json.dumps(analysis, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
