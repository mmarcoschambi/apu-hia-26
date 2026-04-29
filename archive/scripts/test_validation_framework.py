#!/usr/bin/env python3
"""
Test Script - Three-Phase Research Gate Validation
==================================================

Este script prueba el workflow completo de validación con el motor Advanced.

Uso:
    python3 test_validation_framework.py

Requisitos:
    - Datos descargados en data/cache/ (ejecutar primero: python3 manage_universe.py --download)
    - Universe definido en data/universe/universe.json

El script ejecutará:
    1. Validación de estrategia con ResearchGate
    2. Stress testing completo
    3. Métricas de robustez
"""

import json
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Añadir src al path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine
    from src.validation import ResearchGate, StressTestSuite
    from src.validation.robustness_metrics import (
        robust_objective_function,
        calculate_comprehensive_robustness_report,
        RobustObjectiveConfig,
    )

    logger.info("✅ Módulos importados correctamente")
except ImportError as e:
    logger.error(f"❌ Error importando módulos: {e}")
    logger.error("Asegúrate de estar en el directorio raíz del proyecto")
    sys.exit(1)


def load_test_universe(max_tickers: int = 20) -> list:
    """Carga universo de prueba desde JSON."""
    universe_path = Path("data/universe/universe.json")

    if not universe_path.exists():
        logger.error(f"❌ No se encuentra {universe_path}")
        logger.info("Creando universo de prueba básico...")
        return ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX"]

    with open(universe_path, "r") as f:
        data = json.load(f)
        tickers = data.get("tickers", [])

    # Limitar para prueba rápida
    test_universe = tickers[:max_tickers]
    logger.info(f"✅ Universo cargado: {len(test_universe)} tickers")
    logger.info(f"   Tickers: {', '.join(test_universe[:5])}...")

    return test_universe


def test_basic_backtest():
    """Prueba 1: Backtest básico con motor Advanced."""
    logger.info("\n" + "=" * 70)
    logger.info("PRUEBA 1: Backtest Básico con AdvancedVectorBTEngine")
    logger.info("=" * 70)

    # Parámetros de producción recomendados
    params = {
        "min_rvol": 1.5,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "risk_dollars": 150,
        "max_stop_pct": 3.0,
        "max_exposure_pct": 0.25,
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
        "min_volume": 300000,
        "min_dollar_volume": 5000000,
        "signal_type": "breakout",
        "use_market_regime_filter": True,
        "require_spy_above_sma50": True,
        "max_vix_threshold": 35.0,
        "min_consolidation_days": 10,
        "rvol_danger": 3.0,
        "rvol_warning": 2.0,
    }

    universe = load_test_universe(max_tickers=10)

    try:
        # Crear motor
        logger.info("\n📊 Configurando motor...")
        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date="2023-01-01",
            end_date="2024-12-31",
            initial_capital=100000,
            **params,
        )

        # Cargar datos
        logger.info("📥 Cargando datos...")
        engine.load_data()

        # Ejecutar backtest
        logger.info("🚀 Ejecutando backtest...")
        results = engine.run_backtest()

        # Mostrar resultados
        logger.info("\n📈 RESULTADOS DEL BACKTEST:")
        logger.info(f"   Total Return: {results.get('total_return_pct', 0):.2f}%")
        logger.info(f"   Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        logger.info(f"   Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
        logger.info(f"   Total Trades: {results.get('total_trades', 0)}")
        logger.info(f"   Win Rate: {results.get('win_rate_pct', 0):.1f}%")
        logger.info(f"   Profit Factor: {results.get('profit_factor', 0):.2f}")

        return results

    except Exception as e:
        logger.error(f"❌ Error en backtest: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


def test_research_gate():
    """Prueba 2: Three-Phase Research Gate."""
    logger.info("\n" + "=" * 70)
    logger.info("PRUEBA 2: Three-Phase Research Gate Validation")
    logger.info("=" * 70)

    # Parámetros a validar
    params = {
        "min_rvol": 1.5,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "risk_dollars": 150,
        "max_stop_pct": 3.0,
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
    }

    universe = load_test_universe(max_tickers=15)

    try:
        # Crear Research Gate
        gate = ResearchGate()

        # Ejecutar validación completa
        logger.info("\n🔬 Iniciando validación de 3 fases...")
        result = gate.validate_strategy(
            engine_class=AdvancedVectorBTEngine,
            params=params,
            universe=universe,
            train_dates=("2022-01-01", "2023-12-31"),
            test_dates=("2024-01-01", "2024-12-31"),
            verbose=True,
        )

        # Mostrar resultados
        logger.info("\n📊 RESULTADOS DE VALIDACIÓN:")
        logger.info(
            f"   ✅ Discovery: {'PASÓ' if result.discovery_passed else 'FALLÓ'}"
        )
        logger.info(
            f"   ✅ Validation: {'PASÓ' if result.validation_passed else 'FALLÓ'}"
        )
        logger.info(
            f"   ✅ Production: {'PASÓ' if result.productionization_passed else 'FALLÓ'}"
        )
        logger.info(
            f"\n🎯 PROMOCIÓN: {'APROBADA' if result.promotion_approved else 'RECHAZADA'}"
        )

        if not result.promotion_approved:
            logger.info("\n❌ Razones de rechazo:")
            for reason in result.rejection_reasons:
                logger.info(f"   • {reason}")

        # Métricas detalladas
        logger.info(f"\n📈 Métricas Clave:")
        logger.info(f"   PBO Score: {result.pbo_score:.2%}")
        logger.info(f"   Bootstrap p5: {result.bootstrap_p5:.2f}%")
        logger.info(f"   Bootstrap p10: {result.bootstrap_p10:.2f}%")
        logger.info(f"   Max Drawdown: {result.max_drawdown_pct:.2f}%")

        return result

    except Exception as e:
        logger.error(f"❌ Error en validación: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


def test_stress_testing():
    """Prueba 3: Stress Testing Suite."""
    logger.info("\n" + "=" * 70)
    logger.info("PRUEBA 3: Stress Testing Suite")
    logger.info("=" * 70)

    # Parámetros de estrategia
    params = {
        "min_rvol": 1.5,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "risk_dollars": 150,
        "max_stop_pct": 3.0,
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
    }

    universe = load_test_universe(max_tickers=10)

    try:
        # Crear suite de stress testing
        suite = StressTestSuite(engine_class=AdvancedVectorBTEngine)

        # Ejecutar tests
        logger.info("\n🔥 Ejecutando stress tests...")
        results = suite.run_full_stress_test(
            params=params,
            universe=universe,
            test_dates=("2024-01-01", "2024-12-31"),
            verbose=True,
        )

        # Mostrar resultados
        logger.info("\n📊 RESULTADOS DE STRESS TESTING:")
        logger.info(f"   Baseline Return: {results.baseline_return:.2f}%")
        logger.info(f"\n💰 Cost Stress:")
        logger.info(f"   2x Costs Impact: {results.impact_2x_costs:+.2f}%")
        logger.info(f"   3x Costs Impact: {results.impact_3x_costs:+.2f}%")
        logger.info(f"   5x Costs Impact: {results.impact_5x_costs:+.2f}%")
        logger.info(f"\n💧 Liquidity Stress:")
        logger.info(f"   Wide Spreads: {results.impact_wider_spreads:+.2f}%")
        logger.info(f"   Extreme Spreads: {results.impact_extreme_spreads:+.2f}%")
        logger.info(f"\n🔥 Worst Case: {results.impact_worst_case:+.2f}%")
        logger.info(f"\n✅ ALL TESTS PASSED: {results.all_passed}")

        if not results.all_passed:
            logger.info("\n❌ Fallos:")
            for reason in results.failure_reasons:
                logger.info(f"   • {reason}")

        return results

    except Exception as e:
        logger.error(f"❌ Error en stress testing: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None


def test_robust_objective():
    """Prueba 4: Función de objetivo robusta."""
    logger.info("\n" + "=" * 70)
    logger.info("PRUEBA 4: Robust Objective Function")
    logger.info("=" * 70)

    # Parámetros
    params = {
        "min_rvol": 1.5,
        "min_adr": 2.0,
        "max_dist_sma20": 7.0,
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "risk_dollars": 150,
        "max_stop_pct": 3.0,
        "mode": "production",
        "fees": 0.001,
        "slippage": 0.001,
    }

    universe = load_test_universe(max_tickers=10)

    try:
        # Ejecutar backtest
        logger.info("\n📊 Ejecutando backtest...")
        engine = AdvancedVectorBTEngine(
            universe=universe, start_date="2024-01-01", end_date="2024-12-31", **params
        )
        engine.load_data()
        backtest_result = engine.run_backtest()

        # Calcular objetivo robusto
        logger.info("\n🧮 Calculando robust objective...")
        config = RobustObjectiveConfig(
            p5_weight=1.0, p10_weight=0.5, sharpe_weight=0.3, max_dd_penalty=2.0
        )

        robust_score = robust_objective_function(backtest_result, config)

        # Reporte completo
        logger.info("\n📋 Generando reporte de robustez...")
        report = calculate_comprehensive_robustness_report(backtest_result)

        logger.info(f"\n📈 ROBUST OBJECTIVE SCORE: {robust_score:.2f}")
        logger.info(f"\n📊 Bootstrap Percentiles:")
        logger.info(f"   p5: {report['bootstrap_percentiles']['p5']:+.2f}%")
        logger.info(f"   p10: {report['bootstrap_percentiles']['p10']:+.2f}%")
        logger.info(f"   p50: {report['bootstrap_percentiles']['p50']:+.2f}%")
        logger.info(f"\n📉 Drawdown Metrics:")
        logger.info(f"   Max DD: {report['drawdown_metrics']['max_dd_pct']:.2f}%")
        logger.info(f"   Avg DD: {report['drawdown_metrics']['avg_dd_pct']:.2f}%")
        logger.info(f"   DD Duration: {report['drawdown_metrics']['dd_duration']} días")
        logger.info(f"\n📈 Risk-Adjusted Metrics:")
        logger.info(f"   Sharpe: {report['risk_adjusted']['sharpe']:.2f}")
        logger.info(f"   Sortino: {report['risk_adjusted']['sortino']:.2f}")
        logger.info(f"   Calmar: {report['risk_adjusted']['calmar']:.2f}")
        logger.info(f"   Omega: {report['risk_adjusted']['omega']:.2f}")
        logger.info(
            f"\n🔍 Probabilidad de Pérdida: {report['probability_of_loss']:.2%}"
        )

        return robust_score, report

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return None, None


def main():
    """Función principal - ejecuta todas las pruebas."""
    logger.info("\n" + "=" * 70)
    logger.info("TESTING FRAMEWORK - Validación de Estrategias de Trading")
    logger.info("=" * 70)
    logger.info("\n⚠️  NOTA: Este script requiere datos descargados.")
    logger.info("   Si falla, ejecuta primero:")
    logger.info("   python3 manage_universe.py --download --universe universe")
    logger.info("")

    results = {}

    # Prueba 1: Backtest básico
    results["backtest"] = test_basic_backtest()

    # Prueba 2: Research Gate
    results["validation"] = test_research_gate()

    # Prueba 3: Stress Testing
    results["stress"] = test_stress_testing()

    # Prueba 4: Robust Objective
    results["robust_score"], results["robust_report"] = test_robust_objective()

    # Resumen final
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN DE PRUEBAS")
    logger.info("=" * 70)

    all_passed = all(
        [
            results["backtest"] is not None,
            results["validation"] is not None,
            results["stress"] is not None,
            results["robust_score"] is not None,
        ]
    )

    if all_passed:
        logger.info("\n✅ TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE")

        if results["validation"] and results["validation"].promotion_approved:
            logger.info("🎉 ESTRATEGIA APROBADA PARA PRODUCCIÓN")
        else:
            logger.info("⚠️  ESTRATEGIA NO CUMPLE TODOS LOS CRITERIOS")

        if results["stress"] and results["stress"].all_passed:
            logger.info("✅ RESISTENTE A ESCENARIOS DE STRESS")
        else:
            logger.info("⚠️  REQUIERE MEJORAS EN STRESS TESTING")

    else:
        logger.info("\n❌ ALGUNAS PRUEBAS FALLARON")
        logger.info("   Revisa los errores arriba")

    logger.info("\n" + "=" * 70)
    logger.info("Para usar en producción, integra estos tests en tu")
    logger.info("workflow de optimización (ver MIGRATION_THOR_TO_ADVANCED.md)")
    logger.info("=" * 70 + "\n")

    return results


if __name__ == "__main__":
    results = main()
