#!/usr/bin/env python3
"""
BUGATTI ADVANCED + OPTUNA ROBUST
================================
Optimización de nivel institucional usando:
1. AdvancedVectorBTEngine (Motor de producción con costos y deslizamiento)
2. Robust Objective Function (Prioriza p5/p10 bootstrap y penaliza Drawdown)
3. Research Gate Validation (Validación final de 3 fases)

Uso:
    python3 bugatti_optuna_robust.py --trials 50 --tickers 30
"""

import argparse
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import optuna
import sqlite3

# Configuración de rutas
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    from src.validation import ResearchGate
    from src.validation.robustness_metrics import (
        robust_objective_function,
        RobustObjectiveConfig
    )
    from src.data.cache_manager import CacheManager
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    sys.exit(1)

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("optuna_robust.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_universe_from_db(limit=50):
    """Obtiene los tickers con más datos en el cache."""
    cm = CacheManager()
    
    try:
        # Intentar primero con metadatos
        df_stats = cm.get_cache_info()
        if not df_stats.empty:
            tickers = df_stats.sort_values("record_count", ascending=False).head(limit)["ticker"].tolist()
            if len(tickers) >= 10:  # Si encontramos una cantidad razonable
                return tickers
    except Exception:
        pass

    # Si falla o hay pocos, consultar price_data directamente
    try:
        conn = sqlite3.connect(cm.db_path)
        query = "SELECT ticker, COUNT(*) as count FROM price_data GROUP BY ticker ORDER BY count DESC LIMIT ?"
        df_direct = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        
        if not df_direct.empty:
            return df_direct["ticker"].tolist()
    except Exception as e:
        logger.warning(f"Error consultando price_data: {e}")

    # Backup final si todo falla
    return ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX"]

def objective(trial, engine_params, robust_config):
    """Función objetivo para Optuna."""
    
    # 1. Definir hiperparámetros a optimizar (RANGOS ROBUSTOS)
    params = {
        # Momentum & Entry
        "min_rvol": trial.suggest_float("min_rvol", 1.2, 3.0, step=0.1),
        "min_adr": trial.suggest_float("min_adr", 1.5, 4.0, step=0.1),
        "max_dist_sma20": trial.suggest_float("max_dist_sma20", 3.0, 10.0, step=0.5),
        "signal_type": trial.suggest_categorical("signal_type", ["breakout", "any"]),
        
        # Risk & Sizing
        "max_stop_pct": trial.suggest_float("max_stop_pct", 2.0, 5.0, step=0.5),
        "tp1_r": trial.suggest_float("tp1_r", 1.0, 2.0, step=0.1),
        "tp2_r": trial.suggest_float("tp2_r", 2.5, 5.0, step=0.5),
        
        # Market Filters
        "use_market_regime_filter": trial.suggest_categorical("use_market_regime_filter", [True, False]),
        "require_spy_above_sma50": trial.suggest_categorical("require_spy_above_sma50", [True, False]),
        
        # Advanced sizing
        "rvol_warning": 2.0,
        "rvol_danger": 3.0,
        
        # Defaults fijos
        "mode": "production",
        "fees": 0.001,      # 0.1%
        "slippage": 0.001,  # 0.1%
        "risk_dollars": engine_params.get("risk_dollars", 150),
        "initial_capital": engine_params.get("initial_capital", 100000)
    }
    
    try:
        # 2. Configurar y ejecutar motor
        engine = AdvancedVectorBTEngine(
            universe=engine_params["universe"],
            start_date=engine_params["start_date"],
            end_date=engine_params["end_date"],
            **params
        )
        engine.load_data()
        results = engine.run_backtest()
        
        # 3. Calcular Score Robusto
        # Prioriza p5/p10 oos y penaliza MaxDD
        score = robust_objective_function(results, robust_config)
        
        # Guardar métricas adicionales en el trial para análisis posterior
        trial.set_user_attr("return_pct", results.get("total_return_pct", 0))
        trial.set_user_attr("sharpe", results.get("sharpe_ratio", 0))
        trial.set_user_attr("max_dd", results.get("max_drawdown_pct", 0))
        trial.set_user_attr("win_rate", results.get("win_rate_pct", 0))
        trial.set_user_attr("trades", results.get("total_trades", 0))
        
        return score

    except Exception as e:
        logger.error(f"Error en trial {trial.number}: {e}")
        return -100.0  # Penalización por error

def main():
    parser = argparse.ArgumentParser(description="Bugatti Robust Optimization")
    parser.add_argument("--trials", type=int, default=50, help="Número de trials")
    parser.add_argument("--tickers", type=int, default=30, help="Número de tickers")
    parser.add_argument("--start", type=str, default="2023-01-01", help="Fecha inicio")
    parser.add_argument("--end", type=str, default="2024-12-31", help="Fecha fin")
    args = parser.parse_args()

    logger.info("🚀 INICIANDO OPTIMIZACIÓN ROBUSTA")
    logger.info(f"   Config: {args.trials} trials, {args.tickers} tickers")

    # 1. Preparar Universo
    universe = get_universe_from_db(limit=args.tickers)
    logger.info(f"   Universo: {', '.join(universe[:5])}...")

    # 2. Configurar Parámetros del Motor y Robustez
    engine_params = {
        "universe": universe,
        "start_date": args.start,
        "end_date": args.end,
        "risk_dollars": 150,
        "initial_capital": 100000
    }
    
    robust_config = RobustObjectiveConfig(
        p5_weight=1.0,
        p10_weight=0.5,
        sharpe_weight=0.3,
        max_dd_penalty=2.0
    )

    # 3. Crear Estudio Optuna
    study = optuna.create_study(
        direction="maximize",
        study_name=f"Bugatti_Robust_{datetime.now().strftime('%Y%m%d_%H%M')}"
    )
    
    # Ejecutar optimización
    study.optimize(
        lambda t: objective(t, engine_params, robust_config),
        n_trials=args.trials,
        show_progress_bar=True
    )

    # 4. Resultados Iniciales
    logger.info("\n" + "="*50)
    logger.info("🏆 MEJORES PARÁMETROS ENCONTRADOS")
    logger.info("="*50)
    for k, v in study.best_params.items():
        logger.info(f"   {k}: {v}")
    logger.info(f"   Score Robusto: {study.best_value:.2f}")

    # 5. VALIDACIÓN FINAL (Research Gate)
    logger.info("\n🔬 EJECUTANDO RESEARCH GATE EN MEJORES PARÁMETROS...")
    gate = ResearchGate()
    
    # IMPORTANTE: Combinar best_params con los parámetros obligatorios que no fueron optimizados
    full_params = {
        **study.best_params,
        "risk_dollars": engine_params.get("risk_dollars", 150),
        "initial_capital": engine_params.get("initial_capital", 100000),
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "rvol_warning": 2.0,
        "rvol_danger": 3.0
    }

    # Ejecutar validación con el set completo de parámetros
    validation_result = gate.validate_strategy(
        engine_class=AdvancedVectorBTEngine,
        params=full_params,
        universe=universe,
        train_dates=("2022-01-01", "2023-12-31"),
        test_dates=("2024-01-01", "2024-12-31"),
        verbose=True
    )

    # 6. Informe Final y Guardado
    output_data = {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "validation": {
            "approved": validation_result.promotion_approved,
            "pbo": validation_result.pbo_score,
            "p5_oos": validation_result.bootstrap_p5,
            "reasons": validation_result.rejection_reasons
        },
        "optimized_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    output_path = Path("outputs/robust_params.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=4)

    logger.info("\n" + "="*50)
    if validation_result.promotion_approved:
        logger.info("🎉 ESTRATEGIA APROBADA PARA PRODUCCIÓN")
    else:
        logger.info("⚠️  ESTRATEGIA RECHAZADA POR RESEARCH GATE")
        for reason in validation_result.rejection_reasons:
            logger.info(f"   • {reason}")
    
    logger.info(f"📁 Resultados guardados en: {output_path}")
    logger.info("="*50)

if __name__ == "__main__":
    main()
