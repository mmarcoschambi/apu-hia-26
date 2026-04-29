#!/usr/bin/env python3
"""
BUGATTI TIER 1 OPTIMIZER - Optimización SOLO de Parámetros de Estrategia
=======================================================================

Este script optimiza UNICAMENTE los parámetros de Tier 1 (Estrategia) usando Optuna.
Los parámetros de Tier 2 (Filtros) y Tier 3 (Risk Management) están fijos.

TIER 1 - Parámetros de ESTRATEGIA (Optimizar):
- tp1_r: R-multiple para primer take-profit
- tp2_r: R-multiple para segundo take-profit
- tp1_pct/tp2_pct/runner_pct: Distribución de salidas
- max_stop_pct: Distancia máxima del stop

TIER 2 - Parámetros de FILTRO (Fijos desde derive_tier2_filters.py):
- min_rvol, min_adr, max_dist_sma20, min_consolidation_days

TIER 3 - Parámetros de RISK MANAGEMENT (Fijos desde tier3_risk_management.py):
- rvol_danger/warning, adr_high/med, max_exposure_pct

Beneficio:
- Reduce espacio de búsqueda de 15+ a solo 4-5 parámetros
- Con 100 trials, Optuna explora adecuadamente el espacio
- Elimina overfitting en parámetros de filtro

Uso:
    python bugatti_optuna_tier1.py --trials 100 --tickers 50
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

# Importar configuraciones fijas
sys.path.insert(0, str(Path(__file__).resolve().parent / "config"))
from tier3_risk_management import get_tier3_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def load_tier2_config(config_file: str = "config/tier2_filters_derived.json") -> dict:
    """Cargar configuración de Tier 2 (Filtros) derivada estadísticamente."""
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        logger.info(f"✅ Tier 2 filters cargados desde {config_file}")
        return config
    except FileNotFoundError:
        logger.warning(f"⚠️  No se encontró {config_file}, usando defaults")
        return {
            "min_rvol": 1.75,
            "max_dist_sma20": 10.0,
            "min_consolidation_days": 10,
            "min_adr": 2.5,
            "min_dollar_volume": 3_000_000,
            "require_sector_strength": True,
            "sector_top_percentile": 0.40,
        }


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


def create_objective(engine, tier2_config: dict, tier3_config: dict, metric="sharpe"):
    """
    Create Optuna objective function for TIER 1 ONLY.

    Args:
        engine: OptimizationEngineV6_PRO instance
        tier2_config: Configuración fija de Tier 2 (Filtros)
        tier3_config: Configuración fija de Tier 3 (Risk Management)
        metric: Metric to optimize
    """

    def objective(trial):
        # ====================================
        # TIER 1: PARÁMETROS DE ESTRATEGIA (Optimizar)
        # ====================================

        # 1. Take-Profit Levels (R-multiples)
        tp1_r = trial.suggest_categorical("tp1_r", [1.0, 1.25, 1.5, 1.75, 2.0])
        tp2_r = trial.suggest_categorical("tp2_r", [2.5, 3.0, 3.5, 4.0])

        # 2. Position Distribution (debe sumar 100%)
        # Usar variable intermedia y calcular el resto
        tp1_pct = trial.suggest_categorical("tp1_pct", [0.30, 0.40, 0.50])
        tp2_pct = trial.suggest_categorical("tp2_pct", [0.30, 0.40, 0.50])

        # Constraint: runner_pct = 1 - tp1_pct - tp2_pct
        # Asegurar que quede al menos 10% para runner
        runner_pct = 1.0 - tp1_pct - tp2_pct

        # Si no cumple constraint, penalizar fuertemente
        if runner_pct < 0.10 or runner_pct > 0.50:
            return -999

        # 3. Stop Loss Distance
        max_stop_pct = trial.suggest_categorical(
            "max_stop_pct", [0.04, 0.05, 0.06, 0.07]
        )

        # 4. Risk per Trade (sizing)
        risk_dollars = trial.suggest_categorical("risk_dollars", [150, 200, 250])

        # ====================================
        # TIER 2: FILTROS (Fijos - NO OPTIMIZAR)
        # ====================================
        min_rvol = tier2_config["min_rvol"]
        min_adr = tier2_config["min_adr"]
        max_dist_sma20 = tier2_config["max_dist_sma20"]
        min_consolidation_days = tier2_config["min_consolidation_days"]
        min_dollar_volume = tier2_config.get("min_dollar_volume", 3_000_000)
        require_sector_strength = tier2_config.get("require_sector_strength", True)
        sector_top_percentile = tier2_config.get("sector_top_percentile", 0.40)

        # ====================================
        # TIER 3: RISK MANAGEMENT (Fijos - NO OPTIMIZAR)
        # ====================================
        rvol_danger = tier3_config["rvol_danger"]
        rvol_warning = tier3_config["rvol_warning"]
        rvol_danger_size = tier3_config["rvol_danger_size"]
        rvol_warning_size = tier3_config["rvol_warning_size"]
        adr_high = tier3_config["adr_high"]
        adr_med = tier3_config["adr_med"]
        adr_high_size = tier3_config["adr_high_size"]
        adr_med_size = tier3_config["adr_med_size"]
        max_exposure_pct = tier3_config["max_exposure_pct"]
        earnings_days = tier3_config["earnings_days"]

        # ====================================
        # BUILD PARAMS DICT
        # ====================================
        params = {
            # TIER 1: Estrategia (Optimizados)
            "tp1_r": tp1_r,
            "tp2_r": tp2_r,
            "tp1_pct": tp1_pct,
            "tp2_pct": tp2_pct,
            "runner_pct": runner_pct,
            "max_stop_pct": max_stop_pct,
            "risk_dollars": risk_dollars,
            "use_phases": True,  # Siempre usar multi-phase exits
            # TIER 2: Filtros (Fijos)
            "min_rvol": min_rvol,
            "min_adr": min_adr,
            "max_dist_sma20": max_dist_sma20,
            "min_consolidation_days": min_consolidation_days,
            "min_dollar_volume": min_dollar_volume,
            "min_volume": 200000,
            "require_sector_strength": require_sector_strength,
            "sector_top_percentile": sector_top_percentile,
            # TIER 3: Risk Management (Fijos)
            "rvol_danger": rvol_danger,
            "rvol_warning": rvol_warning,
            "rvol_danger_size": rvol_danger_size,
            "rvol_warning_size": rvol_warning_size,
            "adr_high": adr_high,
            "adr_med": adr_med,
            "adr_high_size": adr_high_size,
            "adr_med_size": adr_med_size,
            "max_exposure_pct": max_exposure_pct,
            "earnings_days": earnings_days,
            "use_earnings_filter": True,
            # Otros (defaults)
            "signal_type": "vcp",
            "max_consolidation_range": 15.0,
            "require_positive_rs": False,
            "min_rs": 50.0,
            "rs_lookback": "21d",
            "require_bullish_spy": False,
            "max_vix": 40.0,
        }

        # Run backtest
        try:
            stats = engine.backtest(params)

            # CRITICAL FIX: Require minimum 30 trades for statistical significance
            if not stats or stats.get("total_trades", 0) < 30:
                return -999

            # Return metric to optimize
            if metric == "sharpe":
                return stats.get("sharpe_ratio", -999)
            elif metric == "profit_factor":
                return stats.get("profit_factor", 0)
            elif metric == "sortino":
                return stats.get("sortino_ratio", stats.get("sharpe_ratio", -999))
            else:
                return stats.get("sharpe_ratio", -999)

        except Exception as e:
            logger.error(f"Trial failed: {e}")
            return -999

    return objective


def main():
    parser = argparse.ArgumentParser(
        description="Bugatti TIER 1 Optimization (Estrategia solamente)"
    )

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
    parser.add_argument(
        "--tier2-config",
        type=str,
        default="config/tier2_filters_derived.json",
        help="Archivo de configuración Tier 2",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("🏎️  BUGATTI TIER 1 OPTIMIZER")
    print("   Optimizando SOLO parámetros de Estrategia")
    print("=" * 80)
    print(f"\n📊 DATA SPLIT:")
    print(f"  IN-SAMPLE:     {args.in_start} to {args.in_end}  (Optimize)")
    print(f"  VALIDATION:    {args.val_start} to {args.val_end}  (Test)")
    print(f"  OUT-OF-SAMPLE: {args.oos_start} to {args.oos_end}  (Final)")
    print(f"\n⚙️  Settings:")
    print(f"  Optuna Trials: {args.trials}")
    print(f"  Tickers: {args.tickers}")
    print(f"  Optimize: {args.metric.upper()}")
    print(f"  Capital: ${args.equity:,.0f}")

    # Cargar configuraciones fijas
    tier2_config = load_tier2_config(args.tier2_config)
    tier3_config = get_tier3_config()

    print(f"\n🔒 TIER 2 (Filtros) - FIJOS:")
    print(f"   min_rvol: {tier2_config['min_rvol']}x")
    print(f"   max_dist_sma20: {tier2_config['max_dist_sma20']}%")
    print(f"   min_consolidation_days: {tier2_config['min_consolidation_days']}d")

    print(f"\n🔒 TIER 3 (Risk Management) - FIJOS:")
    print(
        f"   rvol_danger/warning: {tier3_config['rvol_danger']}/{tier3_config['rvol_warning']}"
    )
    print(f"   adr_high/med: {tier3_config['adr_high']}%/{tier3_config['adr_med']}%")
    print(f"   max_exposure: {tier3_config['max_exposure_pct'] * 100:.0f}%")

    print(f"\n🎯 TIER 1 (Estrategia) - OPTIMIZANDO:")
    print(f"   tp1_r, tp2_r, tp1_pct/tp2_pct/runner_pct, max_stop_pct, risk_dollars")
    print("=" * 80)

    # ==========================================
    # PHASE 1: IN-SAMPLE OPTIMIZATION (OPTUNA)
    # ==========================================
    logger.info("\n" + "=" * 80)
    logger.info("📈 PHASE 1: IN-SAMPLE OPTIMIZATION (TIER 1 ONLY)")
    logger.info("=" * 80)

    # Get universe
    universe_in = get_liquid_universe(args.in_start, args.in_end, args.tickers)
    logger.info(f"✅ Universe: {len(universe_in)} tickers")

    # Initialize engine
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
        study_name=f"bugatti_tier1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    # Run optimization
    objective = create_objective(engine_in, tier2_config, tier3_config, args.metric)
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    # Best parameters
    best_params = study.best_params
    best_value = study.best_value

    # Agregar derived params al best_params
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

    # Save optimization history
    output_dir = Path("outputs/tier1_optimization")
    output_dir.mkdir(parents=True, exist_ok=True)

    df_trials = study.trials_dataframe()
    df_trials.to_csv(output_dir / "in_sample_trials.csv", index=False)
    logger.info(f"💾 Trials saved to: {output_dir / 'in_sample_trials.csv'}")

    # Show top 5 configurations
    print("\n📊 TOP 5 CONFIGURATIONS:")
    top5 = df_trials.nlargest(5, "value")[
        [
            "value",
            "params_tp1_r",
            "params_tp2_r",
            "params_tp1_pct",
            "params_tp2_pct",
            "params_max_stop_pct",
            "params_risk_dollars",
        ]
    ]
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

    # Build full params con Tier 1 + Tier 2 + Tier 3
    full_params = {
        **best_params,
        # Tier 2
        "min_rvol": tier2_config["min_rvol"],
        "min_adr": tier2_config["min_adr"],
        "max_dist_sma20": tier2_config["max_dist_sma20"],
        "min_consolidation_days": tier2_config["min_consolidation_days"],
        "min_dollar_volume": tier2_config.get("min_dollar_volume", 3_000_000),
        "min_volume": 200000,
        "require_sector_strength": tier2_config.get("require_sector_strength", True),
        "sector_top_percentile": tier2_config.get("sector_top_percentile", 0.40),
        # Tier 3
        "rvol_danger": tier3_config["rvol_danger"],
        "rvol_warning": tier3_config["rvol_warning"],
        "rvol_danger_size": tier3_config["rvol_danger_size"],
        "rvol_warning_size": tier3_config["rvol_warning_size"],
        "adr_high": tier3_config["adr_high"],
        "adr_med": tier3_config["adr_med"],
        "adr_high_size": tier3_config["adr_high_size"],
        "adr_med_size": tier3_config["adr_med_size"],
        "max_exposure_pct": tier3_config["max_exposure_pct"],
        "earnings_days": tier3_config["earnings_days"],
        "use_earnings_filter": True,
        "use_phases": True,
    }

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

    # Save final report
    final_report = {
        "timestamp": datetime.now().isoformat(),
        "method": "Tier1_Only_Optimization",
        "trials": args.trials,
        "tier1_optimized": best_params,
        "tier2_fixed": tier2_config,
        "tier3_fixed": tier3_config,
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
    }

    with open(output_dir / "tier1_optimization_report.json", "w") as f:
        json.dump(final_report, f, indent=2)

    logger.info(f"\n💾 Final report: {output_dir / 'tier1_optimization_report.json'}")

    print("\n" + "=" * 80)
    print("✅ TIER 1 OPTIMIZATION COMPLETE!")
    print("=" * 80)
    print(f"📁 Results: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
