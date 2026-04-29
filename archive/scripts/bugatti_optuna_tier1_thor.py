#!/usr/bin/env python3
"""
TIER 1 OPTIMIZER - VERSION THOR
================================

Optimización de Tier 1 usando el motor THOR en lugar de V6_PRO.
THOR es más robusto y tiene mejor cálculo de métricas.

Uso:
    python3 bugatti_optuna_tier1_thor.py --trials 100 --tickers 50
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

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.data.ticker_cache import TickerCache

# Importar configuraciones fijas
sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
from tier3_risk_management import get_tier3_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def load_tier2_config(config_file: str = "config/tier2_filters_balanced.json") -> dict:
    """Cargar configuración de Tier 2 (Filtros)."""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        logger.info(f"✅ Tier 2 filters cargados desde {config_file}")
        return config
    except FileNotFoundError:
        logger.warning(f"⚠️  No se encontró {config_file}, usando defaults")
        return {
            "min_rvol": 1.5,
            "max_dist_sma20": 10.0,
            "min_consolidation_days": 10,
            "min_adr": 2.0,
            "min_dollar_volume": 2_000_000,
            "require_sector_strength": False,
            "sector_top_percentile": 0.50,
        }


def get_liquid_universe(
    start_date: str, end_date: str, limit: int = 200, ticker_file: str = None
):
    """Get top liquid tickers for the period - Ahora usa bugatti_ready_tickers.txt"""

    # If a custom ticker file is specified, use it
    if ticker_file:
        custom_file = Path(ticker_file)
        if custom_file.exists():
            with open(custom_file, "r") as f:
                lines = f.readlines()
                tickers = [
                    line.strip()
                    for line in lines
                    if line.strip() and not line.startswith("#")
                ]
            tickers = tickers[:limit]
            logger.info(f"Loaded {len(tickers)} tickers from {ticker_file}")
            return tickers
        else:
            logger.warning(f"{ticker_file} not found, falling back to defaults")

    # Cargar tickers desde archivo bugatti_ready_tickers.txt
    tickers_file = Path("bugatti_ready_tickers.txt")
    if tickers_file.exists():
        with open(tickers_file, "r") as f:
            lines = f.readlines()
            # Skip header lines starting with #
            tickers = [
                line.strip()
                for line in lines
                if line.strip() and not line.startswith("#")
            ]

        # Limit to requested amount
        tickers = tickers[:limit]
        logger.info(f"Loaded {len(tickers)} tickers from bugatti_ready_tickers.txt")
        return tickers
    else:
        # Fallback to DB query
        logger.warning("bugatti_ready_tickers.txt not found, using DB fallback")
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
        logger.info(f"Found {len(tickers)} liquid tickers from DB")
        return tickers


def create_objective(engine, tier2_config: dict, tier3_config: dict, metric="sharpe"):
    """
    Create Optuna objective function for TIER 1 ONLY.
    OPTIMIZADO: Mejores rangos para arreglar desbalance R:R
    """

    def objective(trial):
        # ====================================
        # TIER 1: PARÁMETROS DE ESTRATEGIA (Optimizar)
        # ====================================

        # 1. Take-Profit Levels (R-multiples) - Extended range for better R:R
        tp1_r = trial.suggest_categorical("tp1_r", [1.5, 1.75, 2.0, 2.25, 2.5])
        tp2_r = trial.suggest_categorical("tp2_r", [3.0, 3.5, 4.0, 4.5, 5.0])

        # 2. Position Distribution - Optimizado para mejor edge
        # FIX: Mayor % en TP1 (más rápido profit taking)
        tp1_pct = trial.suggest_categorical("tp1_pct", [0.40, 0.50, 0.60])
        tp2_pct = trial.suggest_categorical("tp2_pct", [0.25, 0.30, 0.40])
        runner_pct = 1.0 - tp1_pct - tp2_pct

        if runner_pct < 0.10 or runner_pct > 0.40:
            return -999

        # 3. Stop Loss Distance - Tighter stops for better R:R
        max_stop_pct = trial.suggest_categorical(
            "max_stop_pct", [0.03, 0.04, 0.05, 0.06]
        )

        # 4. Risk per Trade - Lower risk to survive drawdowns
        risk_dollars = trial.suggest_categorical("risk_dollars", [100, 150, 200])

        # ====================================
        # BUILD PARAMS DICT
        # ====================================
        params = {
            # TIER 1: Estrategia
            "tp1_r": tp1_r,
            "tp2_r": tp2_r,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "runner_pct": runner_pct,
            "max_stop_pct": max_stop_pct,
            "risk_dollars": risk_dollars,
            "use_phases": True,
            # TIER 2: Filtros (Fijos)
            "min_rvol": tier2_config["min_rvol"],
            "min_adr": tier2_config["min_adr"],
            "max_dist_sma20": tier2_config["max_dist_sma20"],
            "min_consolidation_days": tier2_config["min_consolidation_days"],
            "min_dollar_volume": tier2_config.get("min_dollar_volume", 2_000_000),
            "min_volume": 200000,
            "require_sector_strength": tier2_config.get(
                "require_sector_strength", False
            ),
            "sector_top_percentile": tier2_config.get("sector_top_percentile", 0.50),
            # TIER 3: Risk Management (Fijos)
            "rvol_danger": tier3_config["rvol_danger"],
            "rvol_warning": tier3_config["rvol_warning"],
            "rvol_danger_size": tier3_config["rvol_danger_size"],
            "rvol_warning_size": tier3_config["rvol_warning_size"],
            "adr_high": tier3_config["adr_high"],
            "adr_med": tier3_config["adr_med"],
            "max_exposure_pct": tier3_config["max_exposure_pct"],
            # Otros
            "signal_type": "any",
            "max_consolidation_range": 15.0,
        }

        # Run backtest with THOR
        try:
            stats = engine.backtest(params)

            # Require minimum 30 trades
            if not stats or stats.get("total_trades", 0) < 30:
                return -999

            # Return metric to optimize
            if metric == "sharpe":
                return stats.get("sharpe_ratio", -999)
            elif metric == "profit_factor":
                return stats.get("profit_factor", 0)
            else:
                return stats.get("sharpe_ratio", -999)

        except Exception as e:
            logger.error(f"Trial failed: {e}")
            return -999

    return objective


def main():
    parser = argparse.ArgumentParser(
        description="Bugatti TIER 1 Optimization (THOR Engine)"
    )

    # Data split dates
    parser.add_argument("--in-start", type=str, default="2020-01-01")
    parser.add_argument("--in-end", type=str, default="2022-12-31")
    parser.add_argument("--val-start", type=str, default="2023-01-01")
    parser.add_argument("--val-end", type=str, default="2024-12-31")

    # Optuna settings
    parser.add_argument(
        "--trials", type=int, default=100, help="Number of Optuna trials"
    )
    parser.add_argument(
        "--tickers",
        type=int,
        default=300,
        help="Number of tickers (200-500 recommended)",
    )
    parser.add_argument("--metric", type=str, default="sharpe")
    parser.add_argument("--equity", type=float, default=100000)
    parser.add_argument(
        "--tier2-config", type=str, default="config/tier2_filters_balanced.json"
    )
    parser.add_argument(
        "--ticker-file",
        type=str,
        default=None,
        help="Path to custom ticker list file (one ticker per line)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🏎️  BUGATTI TIER 1 OPTIMIZER - THOR ENGINE")
    print("=" * 80)

    # Cargar configuraciones
    tier2_config = load_tier2_config(args.tier2_config)
    tier3_config = get_tier3_config()

    # ==========================================
    # PHASE 1: IN-SAMPLE OPTIMIZATION
    # ==========================================
    logger.info("\n" + "=" * 80)
    logger.info("📈 PHASE 1: IN-SAMPLE OPTIMIZATION (THOR)")
    logger.info("=" * 80)

    # Get universe
    universe_in = get_liquid_universe(
        args.in_start, args.in_end, args.tickers, args.ticker_file
    )
    logger.info(f"✅ Universe: {len(universe_in)} tickers")

    # Initialize THOR engine
    logger.info("🔨 Initializing THOR engine...")
    engine_in = OptimizationEngineTHOR(
        tickers=universe_in,
        start_date=args.in_start,
        end_date=args.in_end,
        initial_capital=args.equity,
    )
    logger.info("✅ THOR Engine ready!")

    # Create Optuna study
    logger.info(f"🔬 Starting Optuna optimization ({args.trials} trials)...")
    study = optuna.create_study(
        direction="maximize",
        study_name=f"bugatti_tier1_thor_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    # Run optimization
    objective = create_objective(engine_in, tier2_config, tier3_config, args.metric)
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    # Best parameters
    best_params = study.best_params
    best_value = study.best_value
    best_params["runner_pct"] = 1.0 - best_params["tp1_pct"] - best_params["tp2_pct"]

    print("\n" + "=" * 80)
    print("🏆 IN-SAMPLE BEST CONFIGURATION (TIER 1)")
    print("=" * 80)
    print(f"{args.metric.upper()}: {best_value:.2f}")
    print(f"\n🎯 Best Parameters:")
    print(f"   tp1_r:      {best_params['tp1_r']} R")
    print(f"   tp2_r:      {best_params['tp2_r']} R")
    print(f"   tp1_pct:    {best_params['tp1_pct'] * 100:.0f}%")
    print(f"   tp2_pct:    {best_params['tp2_pct'] * 100:.0f}%")
    print(f"   runner_pct: {best_params['runner_pct'] * 100:.0f}%")
    print(f"   max_stop:   {best_params['max_stop_pct'] * 100:.1f}%")
    print(f"   risk_:      ${best_params['risk_dollars']}")

    # ==========================================
    # PHASE 2: VALIDATION TEST
    # ==========================================
    logger.info("\n" + "=" * 80)
    logger.info("🔍 PHASE 2: VALIDATION TEST")
    logger.info("=" * 80)

    universe_val = get_liquid_universe(
        args.val_start, args.val_end, args.tickers, args.ticker_file
    )
    engine_val = OptimizationEngineTHOR(
        tickers=universe_val,
        start_date=args.val_start,
        end_date=args.val_end,
        initial_capital=args.equity,
    )

    # Build full params
    full_params = {**best_params, **tier2_config}
    full_params.update(
        {
            "rvol_danger": tier3_config["rvol_danger"],
            "rvol_warning": tier3_config["rvol_warning"],
            "adr_high": tier3_config["adr_high"],
            "adr_med": tier3_config["adr_med"],
        }
    )

    logger.info("⚡ Testing best parameters on VALIDATION period...")
    stats_val = engine_val.backtest(full_params)

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

        degradation = (
            ((val_sharpe - best_value) / best_value) * 100 if best_value != 0 else 0
        )
        print(f"\n📉 Degradation: {degradation:.1f}%")

        if abs(degradation) < 20:
            print("✅ GOOD! Parameters are robust")
        elif abs(degradation) < 40:
            print("⚠️  WARNING! Moderate overfitting")
        else:
            print("❌ CRITICAL! Severe overfitting")

    # Save report
    output_dir = Path("outputs/tier1_optimization_thor")
    output_dir.mkdir(parents=True, exist_ok=True)

    final_report = {
        "timestamp": datetime.now().isoformat(),
        "method": "Tier1_THOR_Optimization",
        "trials": args.trials,
        "tier1_optimized": best_params,
        "tier2_fixed": tier2_config,
        "tier3_fixed": tier3_config,
        "in_sample": {"metric": args.metric, "value": best_value},
        "validation": {
            "sharpe": val_sharpe if stats_val else 0,
            "total_return_pct": stats_val.get("total_return_pct", 0)
            if stats_val
            else 0,
            "max_drawdown_pct": stats_val.get("max_drawdown_pct", 0)
            if stats_val
            else 0,
            "win_rate_pct": stats_val.get("win_rate_pct", 0) if stats_val else 0,
            "total_trades": stats_val.get("total_trades", 0) if stats_val else 0,
            "degradation_pct": round(degradation, 2) if stats_val else 0,
        },
    }

    with open(output_dir / "tier1_thor_report.json", "w") as f:
        json.dump(final_report, f, indent=2)

    print("\n" + "=" * 80)
    print("✅ TIER 1 OPTIMIZATION (THOR) COMPLETE!")
    print(f"📁 Results: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
