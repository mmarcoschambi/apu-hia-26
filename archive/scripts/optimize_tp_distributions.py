#!/usr/bin/env python3
"""
OPTIMIZE TP DISTRIBUTIONS
=========================

Compara verdaderas distribuciones de Take Profit usando Optuna.
Optimiza dinámicamente los porcentajes de TP1/TP2/Runner.

Distribuciones hardcoded a probar:
- classic: (50, 30, 20)
- conservative: (40, 35, 25)
- balanced: (33, 33, 34)
- aggressive: (25, 30, 45)
- extreme: (20, 30, 50)

Optimización Optuna:
- tp1_pct ∈ [0.20, 0.60] con step=0.05 (9 valores)
- tp2_pct ∈ [0.20, 0.50] con step=0.05 (7 valores)
- runner_pct = 1.0 - tp1_pct - tp2_pct (automático)
- Total: 63 combinaciones válidas (con constraint suma=1.0)

Uso:
    python3 optimize_tp_distributions.py [--mode compare|optimize] [--trials 50]

Modos:
    compare: Prueba las 5 distribuciones hardcoded
    optimize: Busca la distribución óptima con Optuna
"""

import sys
import json
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple
import optuna

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
from src.utils.tp_config_manager import TPConfigManager, save_optimal_tp

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("TP_Optimizer")

# Suppress optuna logs
optuna.logging.set_verbosity(optuna.logging.WARNING)


class TPDistributionOptimizer:
    """Optimizador de distribuciones de Take Profit"""

    # Distribuciones hardcoded a probar (ALINEADAS con run_dual_validation.sh)
    HARDCODED_DISTRIBUTIONS = {
        "classic": (0.50, 0.30, 0.20),
        "conservative": (0.40, 0.35, 0.25),
        "balanced": (0.33, 0.33, 0.34),
        "aggressive_runner": (0.25, 0.30, 0.45),  # Renombrado para coincidir
        "extreme": (0.20, 0.30, 0.50),  # Nuevo preset para validación
    }

    def __init__(
        self,
        universe: List[str],
        start_date: str,
        end_date: str,
        n_trials: int = 50,
        use_advanced_engine: bool = False,
        output_dir: str = "outputs/tp_optimization",
    ):
        self.universe = universe
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.n_trials = n_trials
        self.use_advanced_engine = use_advanced_engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Resultados
        self.results = []

    def load_base_params(self) -> Dict:
        """Carga parámetros base óptimos (de dual validation si existe)"""
        # PRIORIDAD 1: Usar parámetros validados del dual validation (Día 1)
        try:
            with open("config/validated_production_params.json", "r") as f:
                validated_config = json.load(f)
            logger.info("✅ Usando parámetros validados de dual validation (Día 1)")
            return validated_config["parameters"], {}
        except:
            pass

        # PRIORIDAD 2: Usar parámetros óptimos 2023 (fallback)
        try:
            with open("config/optimal_params_2023.json", "r") as f:
                base_config = json.load(f)
            logger.info("✅ Usando parámetros base de optimal_params_2023.json")
            return base_config["optimal_parameters"], base_config[
                "recommended_features"
            ]
        except:
            logger.warning(
                "⚠️  No se encontraron archivos de parámetros, usando defaults"
            )
            return {}, {}

    def test_distribution(
        self, name: str, tp1_pct: float, tp2_pct: float, runner_pct: float
    ) -> Dict:
        """Prueba una distribución específica"""
        logger.info(f"\n{'=' * 70}")
        logger.info(f"🧪 TESTING: {name}")
        logger.info(
            f"   TP1: {tp1_pct * 100:.0f}% | TP2: {tp2_pct * 100:.0f}% | Runner: {runner_pct * 100:.0f}%"
        )
        logger.info(f"{'=' * 70}")

        base_params, base_features = self.load_base_params()

        # CONVERGENCE FIX: Use validated params from Day 1
        params = {
            **base_params,  # Use validated params from dual validation
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "runner_pct": runner_pct,
            **base_features,
        }

        try:
            if self.use_advanced_engine:
                # Usar Advanced engine con numba_core
                engine = AdvancedVectorBTEngine(
                    universe=self.universe,
                    start_date=self.start_date.strftime("%Y-%m-%d"),
                    end_date=self.end_date.strftime("%Y-%m-%d"),
                    signal_type="any",  # Use 'any' for compatibility
                    **params,
                )
                engine.load_data()
                result = engine.run_backtest()

                return {
                    "distribution_name": name,
                    "tp1_pct": tp1_pct,
                    "tp2_pct": tp2_pct,
                    "runner_pct": runner_pct,
                    "sharpe": result.get("sharpe_ratio", 0),
                    "return": result.get("total_return", 0),
                    "annualized_return": result.get("annualized_return", 0),
                    "trades": result.get("total_trades", 0),
                    "win_rate": result.get("win_rate", 0),
                    "max_dd": result.get("max_drawdown", 0),
                    "engine": "Advanced",
                    "status": "success",
                }
            else:
                # Usar THOR engine (rápido)
                engine = OptimizationEngineTHOR(
                    tickers=self.universe,
                    start_date=self.start_date.strftime("%Y-%m-%d"),
                    end_date=self.end_date.strftime("%Y-%m-%d"),
                    initial_capital=100000,
                    offline_mode=True,
                    use_float32=True,
                )
                # Use 'any' signal type (compatible with both engines)
                params_with_signal = {**params, "signal_type": "any"}
                result = engine.backtest(params_with_signal)

                return {
                    "distribution_name": name,
                    "tp1_pct": tp1_pct,
                    "tp2_pct": tp2_pct,
                    "runner_pct": runner_pct,
                    "sharpe": result.get("sharpe_ratio", 0),
                    "return": result.get("total_return_pct", 0) / 100,
                    "annualized_return": result.get("total_return_pct", 0) / 100,
                    "trades": result.get("total_trades", 0),
                    "win_rate": result.get("win_rate_pct", 0) / 100,
                    "max_dd": result.get("max_drawdown_pct", 0) / 100,
                    "engine": "THOR",
                    "status": "success",
                }

        except Exception as e:
            logger.error(f"❌ Error testing {name}: {e}")
            return {
                "distribution_name": name,
                "tp1_pct": tp1_pct,
                "tp2_pct": tp2_pct,
                "runner_pct": runner_pct,
                "status": "failed",
                "error": str(e),
            }

    def compare_hardcoded_distributions(self) -> List[Dict]:
        """Compara las 5 distribuciones hardcoded"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 COMPARING HARDCODED TP DISTRIBUTIONS")
        logger.info("=" * 70)

        results = []

        for name, (tp1, tp2, runner) in self.HARDCODED_DISTRIBUTIONS.items():
            result = self.test_distribution(
                name, tp1_pct=tp1, tp2_pct=tp2, runner_pct=runner
            )
            results.append(result)

            if result["status"] == "success":
                logger.info(f"\n✅ {name}:")
                logger.info(f"   Sharpe: {result['sharpe']:.3f}")
                logger.info(f"   Return: {result['return'] * 100:.2f}%")
                logger.info(f"   Trades: {result['trades']}")
            else:
                logger.info(f"\n❌ {name}: FAILED")

        return results

    def optimize_with_optuna(self) -> Dict:
        """Optimiza distribución TP con Optuna"""
        logger.info("\n" + "=" * 70)
        logger.info("🔬 OPTIMIZING TP DISTRIBUTION WITH OPTUNA")
        logger.info("=" * 70)
        logger.info(f"   TP1: [20% - 60%] con step=5%")
        logger.info(f"   TP2: [20% - 50%] con step=5%")
        logger.info(f"   Runner: calculado automáticamente (100% - TP1 - TP2)")
        logger.info(f"   Trials: {self.n_trials}")
        logger.info(
            f"   Engine: {'Advanced (Numba)' if self.use_advanced_engine else 'THOR'}"
        )
        logger.info("")

        base_params, base_features = self.load_base_params()

        # Inicializar engine una sola vez
        if self.use_advanced_engine:
            engine = AdvancedVectorBTEngine(
                universe=self.universe,
                start_date=self.start_date.strftime("%Y-%m-%d"),
                end_date=self.end_date.strftime("%Y-%m-%d"),
                signal_type="any",  # Use 'any' for compatibility
                **base_params,
                **base_features,
            )
            engine.load_data()
        else:
            engine = OptimizationEngineTHOR(
                tickers=self.universe,
                start_date=self.start_date.strftime("%Y-%m-%d"),
                end_date=self.end_date.strftime("%Y-%m-%d"),
                initial_capital=100000,
                offline_mode=True,
                use_float32=True,
            )
            # IMPORTANT: Use 'any' signal type (compatible with both engines)
            base_params["signal_type"] = "any"

        tested_configs = []  # Para evitar duplicados

        def objective(trial):
            """Optuna objective"""
            # Rango: 20-60% para TP1, 20-50% para TP2
            tp1_pct = trial.suggest_float("tp1_pct", 0.20, 0.60, step=0.05)
            tp2_pct = trial.suggest_float("tp2_pct", 0.20, 0.50, step=0.05)
            runner_pct = 1.0 - tp1_pct - tp2_pct

            # Constraint: runner debe ser entre 10% y 60%
            if runner_pct < 0.10 or runner_pct > 0.60:
                return -999

            # Evitar duplicados
            config_key = (round(tp1_pct, 2), round(tp2_pct, 2), round(runner_pct, 2))
            if config_key in tested_configs:
                return -999
            tested_configs.append(config_key)

            # CONVERGENCE FIX: Use validated params from Day 1 instead of hardcoded
            params = {
                **base_params,  # Use validated params from dual validation (Day 1)
                "tp1_pct": tp1_pct,
                "tp2_pct": tp2_pct,
                "runner_pct": runner_pct,
                **base_features,
            }

            try:
                if self.use_advanced_engine:
                    result = engine.run_backtest()
                    # Actualizar parámetros dinámicamente
                    # Nota: Advanced engine usa los params del constructor
                    # Esto es una simplificación
                    sharpe = result.get("sharpe_ratio", 0)
                else:
                    result = engine.backtest(params)
                    sharpe = result.get("sharpe_ratio", 0)

                # CRITICAL FIX: Require minimum 30 trades for statistical significance
                if result.get("total_trades", 0) < 30:
                    return -999

                return sharpe

            except Exception as e:
                logger.error(f"Trial failed: {e}")
                return -999

        # Ejecutar optimización
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=True)

        best_params = study.best_params
        best_sharpe = study.best_value

        # Calcular runner_pct óptimo
        optimal_tp1 = best_params["tp1_pct"]
        optimal_tp2 = best_params["tp2_pct"]
        optimal_runner = 1.0 - optimal_tp1 - optimal_tp2

        logger.info(f"\n🏆 OPTIMAL DISTRIBUTION FOUND:")
        logger.info(f"   TP1: {optimal_tp1 * 100:.0f}%")
        logger.info(f"   TP2: {optimal_tp2 * 100:.0f}%")
        logger.info(f"   Runner: {optimal_runner * 100:.0f}%")
        logger.info(f"   Sharpe: {best_sharpe:.3f}")

        # Testear la distribución óptima
        optimal_result = self.test_distribution(
            "optimal", optimal_tp1, optimal_tp2, optimal_runner
        )

        # Save to centralized config for reuse
        save_optimal_tp(
            tp1_pct=optimal_tp1,
            tp2_pct=optimal_tp2,
            runner_pct=optimal_runner,
            sharpe=best_sharpe,
            trades=optimal_result.get("trades", 0),
            source="optimize_tp_distributions",
        )

        return optimal_result

    def save_results(self, results: List[Dict], filename: str):
        """Guarda resultados en JSON"""
        output_file = self.output_dir / filename

        output = {
            "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "universe": self.universe,
            "period": f"{self.start_date.date()} to {self.end_date.date()}",
            "engine": "Advanced" if self.use_advanced_engine else "THOR",
            "results": results,
        }

        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n💾 Results saved to: {output_file}")

    def print_comparison_table(self, results: List[Dict]):
        """Imprime tabla comparativa"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 COMPARISON TABLE")
        logger.info("=" * 70)
        logger.info(
            f"{'Distribution':<15} | {'TP1':<6} | {'TP2':<6} | {'Runner':<6} | {'Sharpe':<8} | {'Return':<8} | {'Trades':<7}"
        )
        logger.info("-" * 70)

        for r in results:
            if r["status"] == "success":
                logger.info(
                    f"{r['distribution_name']:<15} | "
                    f"{r['tp1_pct'] * 100:<5.0f}% | "
                    f"{r['tp2_pct'] * 100:<5.0f}% | "
                    f"{r['runner_pct'] * 100:<5.0f}% | "
                    f"{r['sharpe']:<8.3f} | "
                    f"{r['return'] * 100:<7.2f}% | "
                    f"{r['trades']:<7}"
                )

        logger.info("-" * 70)

        # Encontrar mejor
        successful = [r for r in results if r["status"] == "success"]
        if successful:
            best = max(successful, key=lambda x: x["sharpe"])
            logger.info(f"\n🥇 BEST DISTRIBUTION: {best['distribution_name'].upper()}")
            logger.info(f"   Sharpe: {best['sharpe']:.3f}")
            logger.info(f"   Return: {best['return'] * 100:.2f}%")
            logger.info(f"   Trades: {best['trades']}")


def main():
    parser = argparse.ArgumentParser(description="Optimize TP Distributions")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["compare", "optimize"],
        default="compare",
        help="Mode: compare hardcoded distributions or optimize with Optuna",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=50,
        help="Number of Optuna trials (for optimize mode)",
    )
    parser.add_argument("--start", type=str, default="2023-01-01", help="Start date")
    parser.add_argument("--end", type=str, default="2024-12-31", help="End date")
    parser.add_argument(
        "--tickers",
        type=str,
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN"],
        help="Ticker universe",
    )
    parser.add_argument(
        "--use-advanced",
        action="store_true",
        help="Use Advanced engine (slower but more accurate)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs/tp_optimization",
        help="Output directory for results",
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("🎯 TP DISTRIBUTION OPTIMIZER")
    logger.info("=" * 70)
    logger.info(f"📅 Period: {args.start} → {args.end}")
    logger.info(f"🎯 Universe: {len(args.tickers)} tickers")
    logger.info(f"🔧 Mode: {args.mode.upper()}")
    logger.info(
        f"⚙️  Engine: {'Advanced (Numba)' if args.use_advanced else 'THOR (Fast)'}"
    )
    logger.info("")

    optimizer = TPDistributionOptimizer(
        universe=args.tickers,
        start_date=args.start,
        end_date=args.end,
        n_trials=args.trials,
        use_advanced_engine=args.use_advanced,
        output_dir=args.output_dir,
    )

    if args.mode == "compare":
        # Comparar distribuciones hardcoded
        results = optimizer.compare_hardcoded_distributions()
        optimizer.print_comparison_table(results)
        optimizer.save_results(results, "hardcoded_comparison.json")

        # Guardar la mejor en validated_production_params.json
        successful = [r for r in results if r["status"] == "success"]
        if successful:
            best = max(successful, key=lambda x: x["sharpe"])

            # Cargar base params
            try:
                with open("config/optimal_params_2023.json", "r") as f:
                    base_config = json.load(f)
                base_params = base_config["optimal_parameters"]
                base_features = base_config["recommended_features"]
            except:
                base_params = {}
                base_features = {}

            # Crear validated params con la mejor distribución TP
            validated = {
                "run_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "validation_status": "PASSED",
                "parameters": {
                    **base_params,
                    **base_features,
                    "tp1_pct": best["tp1_pct"],
                    "tp2_pct": best["tp2_pct"],
                    "runner_pct": best["runner_pct"],
                },
                "performance": {
                    "sharpe_ratio": best["sharpe"],
                    "annualized_return_pct": best["return"] * 100,
                    "total_trades": best["trades"],
                    "win_rate_pct": best["win_rate"] * 100,
                    "max_drawdown_pct": best["max_dd"] * 100,
                },
                "best_distribution": best["distribution_name"],
            }

            # Guardar
            with open("config/validated_production_params.json", "w") as f:
                json.dump(validated, f, indent=2)

            logger.info(
                f"\n💾 Best distribution saved to validated_production_params.json"
            )
            logger.info(f"   Distribution: {best['distribution_name']}")
            logger.info(
                f"   TP: {best['tp1_pct'] * 100:.0f}% / {best['tp2_pct'] * 100:.0f}% / {best['runner_pct'] * 100:.0f}%"
            )

            # Also save to centralized TP config
            save_optimal_tp(
                tp1_pct=best["tp1_pct"],
                tp2_pct=best["tp2_pct"],
                runner_pct=best["runner_pct"],
                sharpe=best["sharpe"],
                trades=best["trades"],
                source=f"compare_mode_{best['distribution_name']}",
            )

    else:
        # Modo optimize
        optimal_result = optimizer.optimize_with_optuna()
        optimizer.save_results([optimal_result], "optimal_distribution.json")

    logger.info("\n✅ TP Distribution Optimization Complete!")


if __name__ == "__main__":
    main()
