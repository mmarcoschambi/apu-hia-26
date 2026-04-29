#!/usr/bin/env python3
"""
BUGATTI V6 PRO + OPTUNA - Optimization Anti-Overfitting
========================================================
Walk-forward optimization usando Optuna para encontrar RANGOS robustos,
no números mágicos.

Filosofía:
- MAL: min_rvol = 2.5 (número mágico que solo funciona en un período)
- BIEN: min_rvol = trial.suggest_categorical([1.0, 1.5, 2.0, 2.5]) (rangos robustos)

Performance:
- 100 trials × 50 tickers = ~10 minutos usando V6_PRO engine
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging
import optuna

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO
from src.data.ticker_cache import TickerCache

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def get_liquid_universe(start_date: str, end_date: str, limit: int = 50):
    """Get top liquid tickers for the period"""
    cache = TickerCache()
    query = """
    SELECT ticker, AVG(volume * close) as avg_dv
    FROM ohlcv_cache
    WHERE date BETWEEN ? AND ?
    GROUP BY ticker
    HAVING COUNT(*) >= 40
    ORDER BY avg_dv DESC
    LIMIT ?
    """
    result = cache.conn.execute(query, (start_date, end_date, limit)).fetchall()
    tickers = [row[0] for row in result]
    logger.info(f"Found {len(tickers)} liquid tickers")
    return tickers


def create_objective(engine, metric="sharpe"):
    """
    Create Optuna objective function.

    Args:
        engine: OptimizationEngineV6_PRO instance (data already loaded)
        metric: Metric to optimize ('sharpe', 'profit_factor', 'sortino')
    """

    def objective(trial):
        # ====================================
        # RANGOS ROBUSTOS (No números mágicos)
        # ====================================

        # SIGNAL TYPE - VCP vs BREAKOUT vs ATH vs ANY (ATH incluido)
        signal_type = trial.suggest_categorical(
            "signal_type", ["vcp", "breakout", "ath", "any"]
        )

        # Momentum filters - RANGOS conservadores (1.5 mínimo, no 1.0)
        min_adr = trial.suggest_categorical("min_adr", [1.5, 2.0, 2.5, 3.0])
        min_rvol = trial.suggest_categorical("min_rvol", [1.5, 1.75, 2.0, 2.25, 2.5])

        # Risk management - RANGOS profesionales (15-25% exposure max)
        max_exposure_pct = trial.suggest_categorical(
            "max_exposure_pct", [0.15, 0.20, 0.25]
        )
        risk_dollars = trial.suggest_categorical(
            "risk_dollars", [150, 175, 200, 225, 250]
        )
        max_stop_pct = trial.suggest_categorical("max_stop_pct", [0.06, 0.07, 0.08])

        # SECTOR ROTATION - Top X% methodology (opcional)
        require_sector_strength = trial.suggest_categorical(
            "require_sector_strength", [False, True]
        )
        sector_top_percentile = trial.suggest_categorical(
            "sector_top_percentile", [0.30, 0.35, 0.40, 0.45, 0.50]
        )

        # VCP/CONSOLIDATION QUALITY (max 20% range, no 25%)
        min_consolidation_days = trial.suggest_categorical(
            "min_consolidation_days", [5, 10, 15]
        )
        max_consolidation_range = trial.suggest_categorical(
            "max_consolidation_range", [10.0, 12.5, 15.0, 17.5, 20.0]
        )

        # Distance from SMA - RANGOS discretos
        max_dist_sma20 = trial.suggest_categorical(
            "max_dist_sma20", [7.5, 10.0, 12.5, 15.0]
        )

        # Liquidity - RANGOS simplificados
        min_volume = trial.suggest_categorical("min_volume", [200000, 300000, 500000])
        min_dollar_volume = trial.suggest_categorical("min_dollar_volume", [10e6, 15e6])

        # RVOL-based position sizing (reduce size on danger/warning)
        rvol_danger = trial.suggest_categorical("rvol_danger", [2.5, 3.0, 3.5])
        rvol_warning = trial.suggest_categorical("rvol_warning", [1.5, 2.0])
        rvol_danger_size = trial.suggest_categorical(
            "rvol_danger_size", [0.25, 0.30, 0.35]
        )
        rvol_warning_size = trial.suggest_categorical(
            "rvol_warning_size", [0.55, 0.60, 0.65, 0.70]
        )

        # ADR-based position sizing (reduce size on high volatility stocks)
        adr_high = trial.suggest_categorical("adr_high", [6.0, 6.5, 7.0])
        adr_med = trial.suggest_categorical("adr_med", [4.5, 5.0, 5.5])
        adr_high_size = trial.suggest_categorical("adr_high_size", [0.20, 0.25, 0.30])
        adr_med_size = trial.suggest_categorical("adr_med_size", [0.30, 0.35, 0.40])

        # Earnings calendar filter (opcional - momentum puede aprovechar earnings)
        use_earnings_filter = trial.suggest_categorical(
            "use_earnings_filter", [False, True]
        )
        earnings_days = trial.suggest_categorical("earnings_days", [5, 7])

        # Relative Strength filter (opcional, rangos más amplios)
        require_positive_rs = trial.suggest_categorical(
            "require_positive_rs", [False, True]
        )
        min_rs = trial.suggest_categorical("min_rs", [30.0, 40.0, 50.0, 60.0])
        rs_lookback = trial.suggest_categorical("rs_lookback", ["21d", "63d"])

        # Market regime filters (NO market timing)
        require_bullish_spy = False
        max_vix = 40.0

        # Multi-phase exits (SIEMPRE activo, TP1 más conservador)
        use_phases = True
        tp1_r = trial.suggest_categorical("tp1_r", [1.25, 1.5, 1.75, 2.0])
        tp2_r = trial.suggest_categorical("tp2_r", [3.0, 3.5, 4.0])

        # Build params dict with ALL features
        params = {
            # Signal types
            "signal_type": signal_type,
            # Momentum
            "min_adr": min_adr,
            "min_rvol": min_rvol,
            "max_dist_sma20": max_dist_sma20,
            # Risk management
            "max_exposure_pct": max_exposure_pct,
            "risk_dollars": risk_dollars,
            "max_stop_pct": max_stop_pct,
            # Sector rotation (Top 40% methodology)
            "require_sector_strength": require_sector_strength,
            "sector_top_percentile": sector_top_percentile,
            # VCP/Consolidation quality
            "min_consolidation_days": min_consolidation_days,
            "max_consolidation_range": max_consolidation_range,
            # Liquidity
            "min_volume": min_volume,
            "min_dollar_volume": min_dollar_volume,
            # RVOL-based position sizing (reduce on hot stocks)
            "rvol_danger": rvol_danger,
            "rvol_warning": rvol_warning,
            "rvol_danger_size": rvol_danger_size,
            "rvol_warning_size": rvol_warning_size,
            # ADR-based position sizing (reduce on volatile stocks)
            "adr_high": adr_high,
            "adr_med": adr_med,
            "adr_high_size": adr_high_size,
            "adr_med_size": adr_med_size,
            # Earnings filter
            "use_earnings_filter": use_earnings_filter,
            "earnings_days": earnings_days,
            # Relative Strength filter
            "require_positive_rs": require_positive_rs,
            "min_rs": min_rs,
            "rs_lookback": rs_lookback,
            "require_bullish_spy": require_bullish_spy,
            "max_vix": max_vix,
            # Multi-phase exits
            "use_phases": use_phases,
            "tp1_r": tp1_r,
            "tp2_r": tp2_r,
        }

        # Run backtest
        try:
            stats = engine.backtest(params)

            # CRITICAL FIX: Require minimum 30 trades for statistical significance
            # Sharpe with < 30 trades has no statistical validity
            if not stats or stats.get("total_trades", 0) < 30:
                return -999

            # Return metric to optimize
            if metric == "sharpe":
                return stats.get("sharpe_ratio", -999)
            elif metric == "profit_factor":
                return stats.get("profit_factor", 0)
            elif metric == "sortino":
                # Calculate Sortino if available, else use Sharpe
                return stats.get("sortino_ratio", stats.get("sharpe_ratio", -999))
            else:
                return stats.get("sharpe_ratio", -999)

        except Exception as e:
            logger.error(f"Trial failed: {e}")
            return -999

    return objective


def main():
    parser = argparse.ArgumentParser(description="Bugatti V6 PRO + Optuna Optimization")

    # Data split dates
    parser.add_argument("--in-start", type=str, default="2018-01-01")
    parser.add_argument("--in-end", type=str, default="2021-12-31")
    parser.add_argument("--val-start", type=str, default="2022-01-01")
    parser.add_argument("--val-end", type=str, default="2023-12-31")
    parser.add_argument("--oos-start", type=str, default="2024-01-01")
    parser.add_argument("--oos-end", type=str, default="2024-12-31")

    # Optuna settings
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of Optuna trials"
    )
    parser.add_argument("--tickers", type=int, default=50, help="Number of tickers")
    parser.add_argument(
        "--metric",
        type=str,
        default="sharpe",
        choices=["sharpe", "profit_factor", "sortino"],
    )
    parser.add_argument("--equity", type=float, default=100000)
    parser.add_argument("--lookback", type=int, default=365)

    args = parser.parse_args()

    print("=" * 80)
    print("🏎️  BUGATTI V6 PRO + OPTUNA - ANTI-OVERFITTING")
    print("=" * 80)
    print(f"\n📊 DATA SPLIT:")
    print(f"  IN-SAMPLE:     {args.in_start} to {args.in_end}  (Optimize)")
    print(f"  VALIDATION:    {args.val_start} to {args.val_end}  (Test)")
    print(
        f"  OUT-OF-SAMPLE: {args.oos_start} to {args.oos_end}  (Final - NEVER TOUCHED)"
    )
    print(f"\n⚙️  Settings:")
    print(f"  Optuna Trials: {args.trials}")
    print(f"  Tickers: {args.tickers}")
    print(f"  Optimize: {args.metric.upper()}")
    print(f"  Capital: ${args.equity:,.0f}")
    print("=" * 80)

    # ==========================================
    # PHASE 1: IN-SAMPLE OPTIMIZATION (OPTUNA)
    # ==========================================
    logger.info("\n" + "=" * 80)
    logger.info("📈 PHASE 1: IN-SAMPLE OPTIMIZATION (OPTUNA)")
    logger.info("=" * 80)

    # Get universe
    universe_in = get_liquid_universe(args.in_start, args.in_end, args.tickers)
    logger.info(f"✅ Universe: {len(universe_in)} tickers")

    # Initialize engine (loads ALL data ONCE)
    logger.info("🏎️  Initializing V6_PRO engine...")
    engine_in = OptimizationEngineV6_PRO(
        tickers=universe_in,
        start_date=args.in_start,
        end_date=args.in_end,
        initial_capital=args.equity,
        lookback_days=args.lookback,
        offline_mode=True,
    )
    logger.info("✅ Engine ready!")

    # Create Optuna study
    logger.info(f"🔬 Starting Optuna optimization ({args.trials} trials)...")
    study = optuna.create_study(
        direction="maximize",
        study_name=f"bugatti_v6_pro_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    # Run optimization
    objective = create_objective(engine_in, args.metric)
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    # Best parameters
    best_params = study.best_params
    best_value = study.best_value

    print("\n" + "=" * 80)
    print("🏆 IN-SAMPLE BEST CONFIGURATION")
    print("=" * 80)
    print(f"{args.metric.upper()}: {best_value:.2f}")
    print(f"\n🎯 Best Parameters (ROBUST RANGES):")
    for key, value in best_params.items():
        print(f"   {key}: {value}")

    # Save optimization history
    output_dir = Path("outputs/walk_forward_v6_pro_optuna")
    output_dir.mkdir(parents=True, exist_ok=True)

    df_trials = study.trials_dataframe()
    df_trials.to_csv(output_dir / "in_sample_trials.csv", index=False)
    logger.info(f"💾 Trials saved to: {output_dir / 'in_sample_trials.csv'}")

    # Show top 5 configurations
    print("\n📊 TOP 5 CONFIGURATIONS:")
    cols_to_show = [
        "value",
        "params_signal_type",
        "params_min_adr",
        "params_max_exposure_pct",
        "params_min_rvol",
        "params_require_sector_strength",
        "params_sector_top_percentile",
        "params_min_consolidation_days",
    ]
    available_cols = [c for c in cols_to_show if c in df_trials.columns]
    top5 = df_trials.nlargest(5, "value")[available_cols]
    print(top5.to_string(index=False))

    # ==========================================
    # PHASE 2: VALIDATION TEST
    # ==========================================
    logger.info("\n" + "=" * 80)
    logger.info("🔍 PHASE 2: VALIDATION TEST")
    logger.info("=" * 80)

    universe_val = get_liquid_universe(args.val_start, args.val_end, args.tickers)
    logger.info(f"✅ Validation universe: {len(universe_val)} tickers")

    engine_val = OptimizationEngineV6_PRO(
        tickers=universe_val,
        start_date=args.val_start,
        end_date=args.val_end,
        initial_capital=args.equity,
        lookback_days=args.lookback,
        offline_mode=True,
    )

    logger.info("⚡ Testing best parameters on VALIDATION period...")
    stats_val = engine_val.backtest(best_params)

    print("\n" + "=" * 80)
    print("📊 VALIDATION RESULTS")
    print("=" * 80)
    if stats_val:
        val_sharpe = stats_val.get("sharpe_ratio", 0)
        print(f"Sharpe Ratio: {val_sharpe:.2f}")
        print(f"Total Return: {stats_val.get('total_return_pct', 0):.2f}%")
        print(f"Max Drawdown: {stats_val.get('max_drawdown_pct', 0):.2f}%")
        print(f"Win Rate: {stats_val.get('win_rate_pct', 0):.2f}%")
        print(f"Total Trades: {stats_val.get('total_trades', 0)}")
        print(f"Profit Factor: {stats_val.get('profit_factor', 0):.2f}")

        # Degradation analysis
        degradation = (
            ((val_sharpe - best_value) / best_value) * 100 if best_value != 0 else 0
        )
        print(f"\n📉 Degradation: {degradation:.1f}%")

        if abs(degradation) < 20:
            print("✅ GOOD! Parameters are robust (< 20% degradation)")
        elif abs(degradation) < 40:
            print("⚠️  WARNING! Moderate overfitting (20-40% degradation)")
        else:
            print("❌ CRITICAL! Severe overfitting (> 40% degradation)")

    # ==========================================
    # PHASE 3: OUT-OF-SAMPLE (OPTIONAL)
    # ==========================================
    print("\n" + "=" * 80)
    print("🎯 PHASE 3: OUT-OF-SAMPLE TEST")
    print("=" * 80)
    print("⚠️  Final test - only run when ready to deploy!")
    print("=" * 80)

    run_oos = input("\nRun OUT-OF-SAMPLE test? (yes/no): ").strip().lower()

    if run_oos == "yes":
        logger.info("🚀 Running OUT-OF-SAMPLE test...")

        universe_oos = get_liquid_universe(args.oos_start, args.oos_end, args.tickers)
        engine_oos = OptimizationEngineV6_PRO(
            tickers=universe_oos,
            start_date=args.oos_start,
            end_date=args.oos_end,
            initial_capital=args.equity,
            lookback_days=args.lookback,
            offline_mode=True,
        )

        stats_oos = engine_oos.backtest(best_params)

        print("\n" + "=" * 80)
        print("🏁 OUT-OF-SAMPLE RESULTS")
        print("=" * 80)
        if stats_oos:
            print(f"Sharpe Ratio: {stats_oos.get('sharpe_ratio', 0):.2f}")
            print(f"Total Return: {stats_oos.get('total_return_pct', 0):.2f}%")
            print(f"Max Drawdown: {stats_oos.get('max_drawdown_pct', 0):.2f}%")
            print(f"Win Rate: {stats_oos.get('win_rate_pct', 0):.2f}%")
            print(f"Total Trades: {stats_oos.get('total_trades', 0)}")
            print(f"Profit Factor: {stats_oos.get('profit_factor', 0):.2f}")

        # Save final report
        final_report = {
            "timestamp": datetime.now().isoformat(),
            "method": "Optuna_TPESampler",
            "trials": args.trials,
            "best_parameters": best_params,
            "in_sample": {
                "period": f"{args.in_start} to {args.in_end}",
                "metric": args.metric,
                "value": best_value,
            },
            "validation": {
                "period": f"{args.val_start} to {args.val_end}",
                "sharpe": val_sharpe if stats_val else 0,
                "degradation_pct": degradation if stats_val else 0,
            },
            "out_of_sample": {
                "period": f"{args.oos_start} to {args.oos_end}",
                "stats": stats_oos if stats_oos else {},
            },
        }

        with open(output_dir / "final_report.json", "w") as f:
            json.dump(final_report, f, indent=2)

        logger.info(f"\n💾 Final report: {output_dir / 'final_report.json'}")

    print("\n" + "=" * 80)
    print("✅ OPTIMIZATION COMPLETE!")
    print("=" * 80)
    print(f"📁 Results: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
