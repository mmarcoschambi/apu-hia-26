#!/usr/bin/env python3
"""
CLI backtest runner - Uses production_config.json to run backtest and save enriched trades.
Output: outputs/backtests/complete_trades_clean.csv (with context columns for derive_tier2_filters.py)
"""

import json
import sqlite3
import pandas as pd
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.config.dynamic_config import load_production_config, flatten_config


def get_universe_tickers(start_date="2021-01-01", end_date="2025-12-31", min_days=100):
    """Get ticker list from DB, same as app.py."""
    conn = sqlite3.connect("./data/ticker_cache.db")
    query = """SELECT ticker FROM ohlcv_cache 
               WHERE date BETWEEN ? AND ? 
               GROUP BY ticker HAVING COUNT(*) >= ? 
               ORDER BY ticker"""
    cursor = conn.execute(query, (start_date, end_date, min_days))
    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tickers


def main():
    # Load config
    config = load_production_config()
    flat = flatten_config(config)

    t1 = config.get("tier1_strategy", {})
    t2 = config.get("tier2_filters", {})
    t3 = config.get("tier3_risk", {})
    mr = config.get("market_regime", {})

    # Get universe from DB (same as UI)
    universe = get_universe_tickers()
    print(f"Universe: {len(universe)} tickers from DB")

    # Unit conversions (same as app.py)
    rvol_danger_size = flat.get("rvol_danger_size", 30)
    rvol_warning_size = flat.get("rvol_warning_size", 65)
    max_stop_pct = flat.get("max_stop_pct", 3)

    print("=" * 70)
    print("CLI BACKTEST - Production Config")
    print("=" * 70)
    print(f"Tier 1: TP1={t1['tp1_r']}R, TP2={t1['tp2_r']}R, Risk=${t1['risk_dollars']}")
    print(f"        Distribution: {t1['tp1_pct']}/{t1['tp2_pct']}/{t1['runner_pct']}")
    print(f"        Max Stop: {t1['max_stop_pct'] * 100:.1f}%")
    print(
        f"Tier 2: RVOL>={t2['min_rvol']}, ADR>={t2['min_adr']}%, Dist<={t2['max_dist_sma20']}%"
    )
    print(
        f"Tier 3: RVOL Danger={t3['rvol_danger']}x@{t3['rvol_danger_size'] * 100:.0f}%"
    )
    print(f"Market: SPY>SMA50={mr.get('require_spy_above_sma50', False)}")
    print(f"Adaptive Filtering: OFF (matching THOR)")
    print("=" * 70)

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date="2013-01-01",
        end_date="2026-02-08",
        initial_capital=100000,
        risk_pct=0.5,
        risk_dollars=int(t1.get("risk_dollars", 200)),
        max_exposure_pct=float(flat.get("max_exposure_pct", 0.35)),
        max_dist_sma20=float(t2.get("max_dist_sma20", 15.0)),
        min_rvol=float(t2.get("min_rvol", 1.5)),
        min_adr=float(t2.get("min_adr", 1.5)),
        min_volume=int(t2.get("min_volume", 200000)),
        min_dollar_volume=int(t2.get("min_dollar_volume", 3000000)),
        rvol_danger=float(t3.get("rvol_danger", 3.0)),
        rvol_warning=float(t3.get("rvol_warning", 2.0)),
        rvol_danger_size=rvol_danger_size,
        rvol_warning_size=rvol_warning_size,
        adr_high=float(t3.get("adr_high", 6.0)),
        adr_med=float(t3.get("adr_med", 5.0)),
        max_stop_pct=max_stop_pct,
        min_consolidation_days=int(t2.get("min_consolidation_days", 10)),
        earnings_days=int(t3.get("earnings_days", 5)),
        earnings_cushion=int(t3.get("earnings_cushion", 2)),
        offline_mode=True,
        use_adaptive_filtering=False,  # Match THOR - no adaptive
        tp1_r=float(t1.get("tp1_r", 2.5)),
        tp2_r=float(t1.get("tp2_r", 4.5)),
        require_spy_above_sma50=bool(mr.get("require_spy_above_sma50", False)),
        tp1_pct=float(t1.get("tp1_pct", 0.4)),
        tp2_pct=float(t1.get("tp2_pct", 0.25)),
        runner_pct=float(t1.get("runner_pct", 0.35)),
    )

    print("\nRunning backtest...")
    results = engine.run_backtest()
    engine.cleanup()

    trades = results.get("trades", pd.DataFrame())
    equity = results.get("equity_curve", None)

    if trades.empty:
        print("ERROR: No trades generated!")
        return

    # Save enriched trades (with context columns)
    trades.to_csv("outputs/backtests/complete_trades_clean.csv", index=False)
    print(
        f"\nSaved {len(trades)} partial exits to outputs/backtests/complete_trades_clean.csv"
    )
    print(f"Columns: {list(trades.columns)}")

    # Also save stripped version for backward compat
    symbol_col = "symbol" if "symbol" in trades.columns else "ticker"
    entry_date_col = (
        "entry_date" if "entry_date" in trades.columns else "Entry Timestamp"
    )
    exit_date_col = "exit_date" if "exit_date" in trades.columns else "Exit Timestamp"
    entry_price_col = (
        "entry_price" if "entry_price" in trades.columns else "Avg Entry Price"
    )
    exit_price_col = (
        "exit_price" if "exit_price" in trades.columns else "Avg Exit Price"
    )

    output_df = pd.DataFrame(
        {
            "symbol": trades[symbol_col],
            "entry_date": pd.to_datetime(trades[entry_date_col]),
            "exit_date": pd.to_datetime(trades[exit_date_col]),
            "entry_price": trades[entry_price_col],
            "exit_price": trades[exit_price_col],
            "shares": trades["shares"],
            "pnl": trades["pnl"],
            "exit_phase": trades.get("exit_phase", "FULL"),
            "signal_type": trades.get("entry_signal", "MOMENTUM"),
        }
    )
    output_df.to_csv("outputs/backtests/backtest_results.csv", index=False)

    if equity is not None:
        equity.to_csv("outputs/backtests/equity_curve.csv")

    # Summary stats
    total_pnl = trades["pnl"].sum()
    # Group partial exits into complete trades
    grouped = (
        trades.groupby(
            [
                symbol_col,
                "entry_date" if "entry_date" in trades.columns else "Entry Timestamp",
            ]
        )
        .agg(total_pnl=("pnl", "sum"), exits=("exit_phase", "count"))
        .reset_index()
    )

    n_trades = len(grouped)
    n_winners = (grouped["total_pnl"] > 0).sum()
    win_rate = n_winners / n_trades * 100 if n_trades > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 70}")
    print(f"Partial exits: {len(trades)}")
    print(f"Complete trades: {n_trades}")
    print(f"Net PnL: ${total_pnl:,.0f}")
    print(f"Win Rate: {win_rate:.1f}% ({n_winners}W / {n_trades - n_winners}L)")
    print(f"Return: {total_pnl / 100000 * 100:.1f}%")

    # Context column check
    for col in ["context_rvol", "context_adr", "dist_sma20_pct"]:
        if col in trades.columns:
            valid = trades[col].notna() & (trades[col] != 0)
            print(
                f"  {col}: {valid.sum()}/{len(trades)} rows have data (mean={trades.loc[valid, col].mean():.2f})"
            )
        else:
            print(f"  {col}: MISSING!")


if __name__ == "__main__":
    main()
