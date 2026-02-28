#!/usr/bin/env python3
"""
WALK FORWARD VALIDATION
========================

Implementa Walk Forward Analysis para validar robustez de parámetros.

Metodología:
1. Divide datos en ventanas train/test consecutivas
2. Optimiza en train, valida en test
3. Agrega resultados OOS de todas las ventanas
4. Compara vs estrategia estática

Ventanas sugeridas:
- Train: 12 meses
- Test: 3 meses
- Walk: 3 meses (rolling window)

Usage:
    python walk_forward_validation.py --train-months 12 --test-months 3 --walk-months 3
"""

import sys
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple
import optuna

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO
from src.utils.tp_config_manager import TPConfigManager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("WalkForward")

# Suppress optuna logs
optuna.logging.set_verbosity(optuna.logging.WARNING)


class WalkForwardValidator:
    """Walk Forward Analysis Engine"""

    def __init__(
        self,
        universe: List[str],
        start_date: str,
        end_date: str,
        train_months: int = 12,
        test_months: int = 3,
        walk_months: int = 3,
        n_trials: int = 50,
        tp_preset: str = "optimize",
    ):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.train_months = train_months
        self.test_months = test_months
        self.walk_months = walk_months
        self.n_trials = n_trials
        self.tp_preset = tp_preset

        self.windows = []
        self.results = []

        # TP Distribution: Use centralized manager
        self.tp_config_manager = TPConfigManager()

        # Try to load saved optimal if preset is "optimize"
        if tp_preset == "optimize":
            saved_optimal = self.tp_config_manager.get_optimal_tp("optimize")
            if saved_optimal:
                logger.info(
                    f"💡 Using saved optimal TP: {saved_optimal['tp1_pct']:.0%}/{saved_optimal['tp2_pct']:.0%}/{saved_optimal['runner_pct']:.0%}"
                )
                logger.info(f"   Source: {saved_optimal.get('source', 'unknown')}")
                logger.info(f"   Sharpe: {saved_optimal.get('sharpe', 'N/A')}")
                # Use saved optimal as fixed preset
                self.tp_presets = {"optimize": saved_optimal}
            else:
                logger.info("💡 No saved optimal TP found, will optimize dynamically")
                self.tp_presets = {"optimize": None}
        else:
            # Use specified preset
            self.tp_presets = {tp_preset: self.tp_config_manager.PRESETS.get(tp_preset)}

        # Backwards compatibility: keep old presets dict for direct access
        self.tp_presets_legacy = {
            "optimize": None,  # Will optimize
            "classic": {"tp1_pct": 0.50, "tp2_pct": 0.30, "runner_pct": 0.20},
            "balanced": {"tp1_pct": 0.33, "tp2_pct": 0.33, "runner_pct": 0.34},
            "aggressive_runner": {"tp1_pct": 0.25, "tp2_pct": 0.30, "runner_pct": 0.45},
            "conservative": {"tp1_pct": 0.40, "tp2_pct": 0.35, "runner_pct": 0.25},
            "extreme": {
                "tp1_pct": 0.20,
                "tp2_pct": 0.30,
                "runner_pct": 0.50,
            },  # Nuevo preset alineado
        }

    def generate_windows(self):
        """Genera ventanas train/test solapadas."""
        logger.info(f"\n🗓️  Generando ventanas Walk Forward...")
        logger.info(f"   Train: {self.train_months} meses")
        logger.info(f"   Test: {self.test_months} meses")
        logger.info(f"   Walk: {self.walk_months} meses\n")

        current_start = self.start_date
        window_id = 1

        while current_start < self.end_date:
            # Train period
            train_start = current_start
            train_end = train_start + pd.DateOffset(months=self.train_months)

            # Test period
            test_start = train_end
            test_end = test_start + pd.DateOffset(months=self.test_months)

            if test_end > self.end_date:
                break

            window = {
                "id": window_id,
                "train_start": train_start.strftime("%Y-%m-%d"),
                "train_end": train_end.strftime("%Y-%m-%d"),
                "test_start": test_start.strftime("%Y-%m-%d"),
                "test_end": test_end.strftime("%Y-%m-%d"),
            }

            self.windows.append(window)
            logger.info(f"Window {window_id}:")
            logger.info(f"  📚 Train: {window['train_start']} → {window['train_end']}")
            logger.info(f"  🧪 Test:  {window['test_start']} → {window['test_end']}\n")

            # Move forward
            current_start += pd.DateOffset(months=self.walk_months)
            window_id += 1

        logger.info(f"✅ Generated {len(self.windows)} windows\n")

    def optimize_window(self, window: Dict) -> Dict:
        """Optimiza parámetros en período train."""
        logger.info(f"\n{'=' * 70}")
        logger.info(f"🔧 OPTIMIZING WINDOW {window['id']}")
        logger.info(f"{'=' * 70}")

        # Load optimal params as starting point
        with open("config/optimal_params_2023.json", "r") as f:
            base_config = json.load(f)

        base_params = base_config["optimal_parameters"]
        base_features = base_config["recommended_features"]

        # 🔥 PERFORMANCE OPTIMIZATION: Load data ONCE using V6_PRO engine
        logger.info("   🚀 Initializing High-Performance Engine (V6 PRO)...")
        engine = OptimizationEngineV6_PRO(
            tickers=self.universe,
            start_date=window["train_start"],
            end_date=window["train_end"],
            initial_capital=100000,
            offline_mode=True,
        )

        def objective(trial):
            """Optuna objective function."""
            params = {
                "min_rvol": trial.suggest_float("min_rvol", 1.0, 2.5, step=0.5),
                "min_adr": trial.suggest_float("min_adr", 1.5, 3.5, step=0.5),
                "risk_dollars": trial.suggest_categorical(
                    "risk_dollars", [150, 300, 500, 750, 1000, 1200, 1500, 2000]
                ),
                "max_dist_sma20": trial.suggest_float(
                    "max_dist_sma20", 7.0, 15.0, step=1.0
                ),
                "max_stop_pct": trial.suggest_float("max_stop_pct", 3.0, 7.0, step=0.5),
                "tp1_r": trial.suggest_float("tp1_r", 1.0, 2.0, step=0.25),
                "tp2_r": trial.suggest_float("tp2_r", 2.5, 4.0, step=0.5),
                # Fixed params
                "min_volume": 300000,
                "min_dollar_volume": 5000000,
                "min_consolidation_days": 10,
                "rvol_warning": 2.0,
                "rvol_danger": 3.0,
                "rvol_warning_size": 0.65,
                "rvol_danger_size": 0.30,
                # Enable phases for optimization
                "use_phases": True,
                # Features
                **base_features,
            }

            # TP Distribution: Use preset or optimize
            tp_config = self.tp_presets.get(self.tp_preset)
            if tp_config is None:  # 'optimize' mode
                params["tp1_pct"] = trial.suggest_float(
                    "tp1_pct", 0.25, 0.50, step=0.05
                )
                params["tp2_pct"] = trial.suggest_float(
                    "tp2_pct", 0.25, 0.40, step=0.05
                )
                params["runner_pct"] = trial.suggest_float(
                    "runner_pct", 0.15, 0.40, step=0.05
                )

                # Constraint: TP percentages must sum to ~1.0 (allow 5% tolerance)
                total_pct = params["tp1_pct"] + params["tp2_pct"] + params["runner_pct"]
                if not (0.95 <= total_pct <= 1.05):
                    return -999  # Invalid configuration
            else:  # Fixed preset
                params.update(tp_config)

            try:
                # Reuse the pre-loaded engine
                result = engine.backtest(params)

                # CRITICAL FIX: Require minimum 30 trades for statistical significance
                # Sharpe with < 30 trades has no statistical validity
                if result["total_trades"] < 30:
                    return -999

                return result["sharpe_ratio"]

            except Exception as e:
                logger.error(f"Trial failed: {e}")
                return -999

        # Run optimization
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=True)

        best_params = study.best_params
        best_sharpe = study.best_value

        logger.info(f"\n🏆 BEST PARAMS (Window {window['id']}):")
        for key, val in best_params.items():
            logger.info(f"   🔹 {key}: {val}")
        logger.info(f"   Best Sharpe: {best_sharpe:.3f}\n")

        # Combine with fixed params and features
        full_params = {**best_params, **base_features}
        full_params.update(
            {
                "min_volume": 300000,
                "min_dollar_volume": 5000000,
                "min_consolidation_days": 10,
                "rvol_warning": 2.0,
                "rvol_danger": 3.0,
                "rvol_warning_size": 0.65,
                "rvol_danger_size": 0.30,
                "use_phases": True,
            }
        )

        # Add TP percentages if using preset (not in best_params from Optuna)
        tp_config = self.tp_presets.get(self.tp_preset)
        logger.info(f"🔍 DEBUG TP CONFIG:")
        logger.info(f"   tp_preset: {self.tp_preset}")
        logger.info(f"   tp_config: {tp_config}")
        logger.info(
            f"   Before update: tp1={full_params.get('tp1_pct')}, tp2={full_params.get('tp2_pct')}, runner={full_params.get('runner_pct')}"
        )
        if tp_config is not None:
            full_params.update(tp_config)
            logger.info(
                f"   After update: tp1={full_params.get('tp1_pct')}, tp2={full_params.get('tp2_pct')}, runner={full_params.get('runner_pct')}"
            )
        else:
            logger.info(f"   ⚠️  tp_config is None, using Optuna values")

        # Clean up
        del engine
        import gc

        gc.collect()

        return full_params

    def validate_window(self, window: Dict, params: Dict) -> Dict:
        """Valida parámetros en período test (OOS)."""
        logger.info(f"\n{'=' * 70}")
        logger.info(f"🧪 VALIDATING WINDOW {window['id']} (OOS)")
        logger.info(f"{'=' * 70}")

        # Use V6 PRO for validation too, for consistency and speed
        engine = OptimizationEngineV6_PRO(
            tickers=self.universe,
            start_date=window["test_start"],
            end_date=window["test_end"],
            initial_capital=100000,
            offline_mode=True,
        )

        result = engine.backtest(params)

        logger.info(f"\n📊 OOS Results:")
        logger.info(f"   Sharpe: {result['sharpe_ratio']:.3f}")
        logger.info(f"   Return: {result['total_return'] * 100:.2f}%")
        logger.info(f"   Trades: {result['total_trades']}")
        logger.info(f"   Win Rate: {result['win_rate'] * 100:.1f}%")
        logger.info(f"   Max DD: {result['max_drawdown'] * 100:.2f}%\n")

        del engine
        import gc

        gc.collect()

        return result

    def run_walk_forward(self):
        """Ejecuta Walk Forward completo."""
        logger.info("\n" + "=" * 70)
        logger.info("🚀 WALK FORWARD ANALYSIS")
        logger.info("=" * 70)

        self.generate_windows()

        all_oos_results = []

        for window in self.windows:
            # Optimize on train
            optimal_params = self.optimize_window(window)

            # Validate on test
            oos_result = self.validate_window(window, optimal_params)

            window_result = {
                "window_id": window["id"],
                "train_period": f"{window['train_start']} to {window['train_end']}",
                "test_period": f"{window['test_start']} to {window['test_end']}",
                "params": optimal_params,
                "oos_sharpe": oos_result["sharpe_ratio"],
                "oos_return": oos_result["total_return"],
                "oos_trades": oos_result["total_trades"],
                "oos_win_rate": oos_result["win_rate"],
                "oos_max_dd": oos_result["max_drawdown"],
            }

            all_oos_results.append(window_result)

        # Aggregate results
        self._report_aggregate_results(all_oos_results)

        # Save results
        self._save_results(all_oos_results)

        return all_oos_results

    def _report_aggregate_results(self, results: List[Dict]):
        """Reporta resultados agregados."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 WALK FORWARD AGGREGATE RESULTS")
        logger.info("=" * 70)

        sharpes = [r["oos_sharpe"] for r in results]
        returns = [r["oos_return"] for r in results]
        trades = [r["oos_trades"] for r in results]
        win_rates = [r["oos_win_rate"] for r in results]
        max_dds = [r["oos_max_dd"] for r in results]

        logger.info(
            f"\n{'Metric':<20} | {'Mean':<10} | {'Median':<10} | {'Std':<10} | {'Min':<10} | {'Max':<10}"
        )
        logger.info("-" * 80)

        metrics = [
            ("Sharpe Ratio", sharpes),
            ("Return %", [r * 100 for r in returns]),
            ("Trades", trades),
            ("Win Rate %", [w * 100 for w in win_rates]),
            ("Max DD %", [d * 100 for d in max_dds]),
        ]

        for name, values in metrics:
            logger.info(
                f"{name:<20} | "
                f"{np.mean(values):<10.2f} | "
                f"{np.median(values):<10.2f} | "
                f"{np.std(values):<10.2f} | "
                f"{np.min(values):<10.2f} | "
                f"{np.max(values):<10.2f}"
            )

        logger.info("-" * 80)

        # Robustness check
        avg_sharpe = np.mean(sharpes)
        std_sharpe = np.std(sharpes)
        consistency = (avg_sharpe / std_sharpe) if std_sharpe > 0 else 0

        logger.info(f"\n🎯 ROBUSTNESS SCORE: {consistency:.2f}")
        if consistency > 2.0:
            logger.info("✅ EXCELLENT: Very consistent across windows")
        elif consistency > 1.0:
            logger.info("✅ GOOD: Reasonably consistent")
        elif consistency > 0.5:
            logger.info("⚠️ FAIR: Some variability")
        else:
            logger.info("❌ POOR: High variability, parameters may be overfit")

    def _save_results(self, results: List[Dict]):
        """Guarda resultados en JSON."""
        output_file = Path("outputs/walk_forward_results.json")
        output_file.parent.mkdir(exist_ok=True)

        output = {
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "universe": self.universe,
            "config": {
                "train_months": self.train_months,
                "test_months": self.test_months,
                "walk_months": self.walk_months,
                "n_trials_per_window": self.n_trials,
            },
            "windows": results,
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Walk Forward Validation")
    parser.add_argument(
        "--train-months", type=int, default=12, help="Training window (months)"
    )
    parser.add_argument(
        "--test-months", type=int, default=3, help="Test window (months)"
    )
    parser.add_argument("--walk-months", type=int, default=3, help="Walk step (months)")
    parser.add_argument(
        "--trials", type=int, default=30, help="Optuna trials per window"
    )
    parser.add_argument("--start", type=str, default="2020-01-01", help="Start date")
    parser.add_argument("--end", type=str, default="2024-12-31", help="End date")
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        default=None,  # Will load from universe.json for diverse 200+ ticker coverage
        help="Ticker universe (list). If not provided, uses full universe.json (200+ tickers)",
    )
    parser.add_argument(
        "--universe-file", type=str, help="Path to file with ticker list (one per line)"
    )
    parser.add_argument(
        "--tp-preset",
        type=str,
        choices=[
            "optimize",
            "classic",
            "balanced",
            "aggressive_runner",
            "conservative",
            "extreme",  # Nuevo preset alineado con optimize_tp_distributions.py
        ],
        default="optimize",
        help="TP distribution preset: optimize (search optimal), classic (50/30/20), balanced (33/33/33), aggressive_runner (25/30/45), conservative (40/35/25), extreme (20/30/50)",
    )

    args = parser.parse_args()

    # Load universe from file if provided
    if args.universe_file:
        try:
            with open(args.universe_file, "r") as f:
                # Read lines, strip whitespace, ignore comments and empty lines
                file_tickers = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]

            if file_tickers:
                args.tickers = file_tickers
                logger.info(
                    f"📂 Loaded {len(args.tickers)} tickers from {args.universe_file}"
                )
            else:
                logger.warning(
                    f"⚠️  Universe file {args.universe_file} is empty, loading from universe.json."
                )
        except Exception as e:
            logger.error(f"❌ Failed to load universe file: {e}")
            sys.exit(1)

    # CRITICAL FIX: Load diverse universe if no tickers provided
    # Avoid survivorship bias by using 200+ tickers instead of just mega-caps
    if args.tickers is None:
        try:
            universe_path = (
                Path(__file__).parent / "data" / "universe" / "universe.json"
            )
            with open(universe_path, "r") as f:
                universe_data = json.load(f)
                args.tickers = universe_data.get("tickers", [])
            if len(args.tickers) < 100:
                logger.warning(
                    f"⚠️  Universe only has {len(args.tickers)} tickers. "
                    f"Consider expanding for better statistical significance."
                )
            else:
                logger.info(f"📊 Loaded {len(args.tickers)} tickers from universe.json")
        except Exception as e:
            logger.error(f"❌ Failed to load universe.json: {e}")
            logger.error(
                "Please provide tickers manually with --tickers or --universe-file"
            )
            sys.exit(1)

    logger.info("=" * 70)
    logger.info("🚀 WALK FORWARD VALIDATION")
    logger.info("=" * 70)
    logger.info(f"📅 Period: {args.start} → {args.end}")
    logger.info(f"🎯 Universe: {len(args.tickers)} tickers")
    logger.info(
        f"⚙️  Config: Train={args.train_months}m, Test={args.test_months}m, Walk={args.walk_months}m"
    )
    logger.info(f"🔬 Trials per window: {args.trials}")

    # Show TP preset info
    if args.tp_preset == "optimize":
        logger.info(f"🎲 TP Distribution: OPTIMIZING (25-50% / 25-40% / 15-40%)")
    else:
        preset_info = {
            "classic": "50% / 30% / 20%",
            "balanced": "33% / 33% / 34%",
            "aggressive_runner": "25% / 30% / 45%",
            "conservative": "40% / 35% / 25%",
            "extreme": "20% / 30% / 50%",
        }
        logger.info(
            f"🎯 TP Distribution: {args.tp_preset.upper()} ({preset_info[args.tp_preset]})"
        )
    logger.info("")

    validator = WalkForwardValidator(
        universe=args.tickers,
        start_date=args.start,
        end_date=args.end,
        train_months=args.train_months,
        test_months=args.test_months,
        walk_months=args.walk_months,
        n_trials=args.trials,
        tp_preset=args.tp_preset,
    )

    results = validator.run_walk_forward()

    logger.info("\n✅ Walk Forward Analysis Complete!")

    return results


if __name__ == "__main__":
    main()
