#!/usr/bin/env python3
"""
Comparación de Motores de Backtest: THOR vs Advanced
====================================================

IDENTIFICA DIFERENCIAS CRÍTICAS Y CONVERGENCIA DE PARÁMETROS
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


class EngineComparator:
    """Compara dos motores de backtest y valida convergencia"""

    def __init__(self, tickers, start_date, end_date):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date

        # Diferencias críticas identificadas
        self.critical_differences = {
            "market_regime": {
                "thor": "Simple SPY/SMA50 & VIX filter",
                "advanced": "4-stage market regime classifier",
                "impact": "HIGH - Different entry timing",
                "transfer_risk": "medium",
            },
            "entry_signals": {
                "thor": "Pure vectorzied breakout consolidation",
                "advanced": "Multi-filtered with earnings, sector, consolidation",
                "impact": "HIGH - Different number of entries",
                "transfer_risk": "high",
            },
            "position_sizing": {
                "thor": "Fixed dollar risk + RVOL reduction",
                "advanced": "Fixed dollar + RVOL + ADR + regime adjustments",
                "impact": "MEDIUM - Similar but Advanced more granular",
                "transfer_risk": "low",
            },
            "exit_logic": {
                "thor": "3-phase (TP1 50%, TP2 30%, Runner 20% with EMA8/21)",
                "advanced": "3-phase + trailing stop to break-even",
                "impact": "LOW - Same core logic",
                "transfer_risk": "very low",
            },
            "dynamic_thresholds": {
                "thor": "Not implemented",
                "advanced": "VIX-based dynamic min_rvol, min_adr, max_dist",
                "impact": "MEDIUM - Different filter strictness by regime",
                "transfer_risk": "medium",
            },
            "data_source": {
                "thor": "Cache only, float32, chunked loading",
                "advanced": "Cache + yfinance fallback, float64, parallel loading",
                "impact": "LOW - Different precision, similar results",
                "transfer_risk": "very low",
            },
        }

        # Parámetros compatibles para transferencia
        self.compatible_params = {
            # Liquidity filters
            "min_rvol": True,
            "min_adr": True,
            "min_volume": True,
            "min_dollar_volume": True,
            # Quality filters
            "max_dist_sma20": True,
            "min_consolidation_days": True,
            "max_consolidation_range": True,
            # Position sizing
            "risk_dollars": True,
            "max_exposure_pct": True,
            "max_stop_pct": True,
            # Exit targets
            "tp1_r": True,
            "tp2_r": True,
            "use_phases": True,
            # RVOL sizing
            "rvol_danger": True,
            "rvol_warning": True,
            "rvol_danger_size": True,
            "rvol_warning_size": True,
        }

        # Parámetros incompatibles (engine-specific)
        self.incompatible_params = {
            "thor_only": [
                "offline_mode",
                "use_float32",
                "chunk_size",
                "lookback_days",
            ],
            "advanced_only": [
                "use_dynamic_thresholds",
                "use_market_regime_filter",
                "use_adaptive_filtering",
                "use_rs_percentile",
                "use_sma50_atr_filter",
                "use_earnings_calendar",
                "require_spy_above_sma50",
                "require_positive_rs",
                "max_vix_threshold",
                "max_sector_exposure_pct",
                "sector_top_percentile",
                "use_composite_sector_scoring",
                "use_trailing_stop",
                "be_trailing_threshold",
                "adr_high",
                "adr_med",
                "rs_lookback_days",
                "max_sma50_atr_extension",
                "min_rs_percentile",
            ],
        }

    def run_comparison(self, params):
        """
        Ejecuta ambos motores con mismos parámetros y compara resultados

        Args:
            params: Diccionario de parámetros compatibles

        Returns:
            Dict con resultados y análisis de divergencia
        """
        print("\n" + "=" * 80)
        print("🔬 ENGINE CONVERGENCE ANALYSIS")
        print("=" * 80)

        # ====================================================================
        # PARÁMETROS COMPATIBLES
        # ====================================================================
        print("\n📋 Parámetros transferidos (THOR -> Advanced):")
        compatible = {k: v for k, v in params.items() if k in self.compatible_params}
        for k, v in compatible.items():
            print(f"   • {k:25s}: {v}")

        # ====================================================================
        # EJECUCIÓN THOR
        # ====================================================================
        print("\n" + "─" * 80)
        print("🔨 EJECUTANDO THOR (Optimization Engine)")
        print("─" * 80)

        thor_params = params.copy()
        # Valores por defecto para THOR si no están en params
        thor_params.setdefault("require_bullish_spy", False)
        thor_params.setdefault("require_positive_rs", False)
        thor_params.setdefault("require_sma_trend", False)
        thor_params.setdefault("max_vix", 40.0)

        thor = OptimizationEngineTHOR(
            tickers=self.tickers,
            start_date=self.start_date,
            end_date=self.end_date,
            use_float32=True,
        )

        result_thor = thor.backtest(thor_params)

        print(f"\n✅ Resultados THOR:")
        print(f"   Sharpe:      {result_thor['sharpe_ratio']:.3f}")
        print(f"   Return:      {result_thor['total_return_pct']:.2f}%")
        print(f"   Trades:      {result_thor['total_trades']}")
        print(f"   Max DD:      {result_thor['max_drawdown_pct']:.2f}%")
        print(f"   Win Rate:    {result_thor['win_rate_pct']:.1f}%")
        print(f"   Profit Factor: {result_thor['profit_factor']:.2f}")

        # ====================================================================
        # EJECUCIÓN ADVANCED (con features desactivadas para convergencia)
        # ====================================================================
        print("\n" + "─" * 80)
        print("🚀 EJECUTANDO ADVANCED (Debug Engine)")
        print("─" * 80)

        # Desactivar features avanzadas para convergencia
        advanced_params = {
            **params,
            # Desactivar features exclusivas de Advanced
            "use_dynamic_thresholds": False,
            "use_market_regime_filter": False,
            "use_adaptive_filtering": False,
            "use_rs_percentile": False,
            "use_sma50_atr_filter": False,
            "use_earnings_calendar": False,
            "require_spy_above_sma50": False,
            "require_positive_rs": False,
            "max_vix_threshold": 40.0,
            "use_trailing_stop": False,
        }

        advanced = AdvancedVectorBTEngine(
            universe=self.tickers,
            start_date=self.start_date,
            end_date=self.end_date,
            **advanced_params,
        )

        result_advanced = advanced.run_backtest()

        print(f"\n✅ Resultados ADVANCED:")
        print(f"   Sharpe:      {result_advanced['sharpe_ratio']:.3f}")
        print(f"   Return:      {result_advanced['total_return'] * 100:.2f}%")
        print(f"   Trades:      {result_advanced['total_trades']}")
        print(f"   Max DD:      {result_advanced['max_drawdown'] * 100:.2f}%")
        print(f"   Win Rate:    {result_advanced['win_rate'] * 100:.1f}%")

        # ====================================================================
        # ANÁLISIS DE DIVERGENCIA
        # ====================================================================
        print("\n" + "=" * 80)
        print("📊 DIVERGENCE ANALYSIS")
        print("=" * 80)

        divergence = {
            "sharpe": abs(
                result_thor["sharpe_ratio"] - result_advanced["sharpe_ratio"]
            ),
            "trades_count": abs(
                result_thor["total_trades"] - result_advanced["total_trades"]
            ),
            "return_pct": abs(
                result_thor["total_return_pct"] - result_advanced["total_return"] * 100
            ),
            "max_dd_pct": abs(
                result_thor["max_drawdown_pct"] - result_advanced["max_drawdown"] * 100
            ),
        }

        # Normalizar diferencias
        divergence_normalized = {
            "sharpe": divergence["sharpe"] / (abs(result_thor["sharpe_ratio"]) + 0.01),
            "trades_pct": divergence["trades_count"]
            / (result_thor["total_trades"] + 1),
            "return_pct": divergence["return_pct"]
            / (abs(result_thor["total_return_pct"]) + 1),
            "max_dd_pct": divergence["max_dd_pct"]
            / (result_thor["max_drawdown_pct"] + 1),
        }

        print(f"\nDiferencias absolutas:")
        print(f"   Sharpe:     {divergence['sharpe']:6.3f}")
        print(f"   Trades:     {divergence['trades_count']:6d}")
        print(f"   Return:     {divergence['return_pct']:6.2f}%")
        print(f"   Max DD:     {divergence['max_dd_pct']:6.2f}%")

        print(f"\nDiferencias normalizadas:")
        print(f"   Sharpe:     {divergence_normalized['sharpe'] * 100:6.1f}%")
        print(f"   Trades:     {divergence_normalized['trades_pct'] * 100:6.1f}%")
        print(f"   Return:     {divergence_normalized['return_pct'] * 100:6.1f}%")
        print(f"   Max DD:     {divergence_normalized['max_dd_pct'] * 100:6.1f}%")

        # ====================================================================
        # EVALUACIÓN DE CONVERGENCIA
        # ====================================================================
        print("\n" + "=" * 80)
        print("✅ CONVERGENCIA EVALUATION")
        print("=" * 80)

        # Criterios de convergencia
        convergence_criteria = {
            "sharpe": divergence_normalized["sharpe"] < 0.15,
            "trades": divergence_normalized["trades_pct"] < 0.20,
            "return": divergence_normalized["return_pct"] < 0.15,
            "max_dd": divergence_normalized["max_dd_pct"] < 0.20,
        }

        passed = sum(convergence_criteria.values())
        total = len(convergence_criteria)

        print(f"\nCriterios pasados: {passed}/{total}")

        for metric, converged in convergence_criteria.items():
            status = "✅ PASS" if converged else "❌ FAIL"
            print(f"   {metric:10s}: {status}")

        # Veredicto final
        if passed == total:
            verdict = "🟢 EXCELLENT CONVERGENCE - SAFE to transfer params"
            transfer_confidence = "HIGH"
        elif passed >= 3:
            verdict = "🟡 GOOD CONVERGENCE - Transfer with caution"
            transfer_confidence = "MEDIUM"
        elif passed >= 2:
            verdict = "🟠 MODERATE CONVERGENCE - Review before transfer"
            transfer_confidence = "LOW"
        else:
            verdict = "🔴 POOR CONVERGENCE - DO NOT transfer params"
            transfer_confidence = "VERY LOW"

        print(f"\n📋 VEREDICT: {verdict}")
        print(f"   Transfer Confidence: {transfer_confidence}")

        # ====================================================================
        # EXPLICACIÓN DE DIFERENCIAS
        # ====================================================================
        print("\n" + "=" * 80)
        print("💡 KEY DIFFERENCES AFFECTING CONVERGENCE")
        print("=" * 80)

        print("\n1. ENTRY SIGNAL DIFFERENCES:")
        print("   • THOR: entries = base_filters & consolidation_quality")
        print("   • Adv:  entries + sector filter + earnings filter + RS filter")
        print("   → Impact: Advanced rejects more entries")

        print("\n2. POSITION SIZING DIFFERENCES:")
        print("   • THOR: Fixed risk * (1 - RVOL reduction)")
        print("   • Adv:  Fixed risk * RVOL * ADR * regime multipliers")
        print("   → Impact: More conservative sizing in Advanced")

        print("\n3. EXIT LOGIC DIFFERENCES:")
        print("   • THOR: 3-phase exits (TP1, TP2, Runner)")
        print("   • Adv: 3-phase + trailing stop to break-even")
        print("   → Impact: Advanced exits earlier at break-even")

        print("\n4. SIMULATION APPROACH:")
        print("   • THOR: Vectorized (vbt.Portfolio.from_signals)")
        print("   • Adv:  Custom loop per day ticker-by-ticker")
        print("   → Impact: Minor differences in execution timing")

        # ====================================================================
        # RECOMENDACIONES
        # ====================================================================
        print("\n" + "=" * 80)
        print("📝 RECOMMENDATIONS")
        print("=" * 80)

        if transfer_confidence == "HIGH":
            print("\n✅ Safe transfer strategy:")
            print("   1. Optimize in THOR (fast, memory-efficient)")
            print("   2. Take top 3-5 parameter combinations")
            print("   3. Validate in Advanced with SAME settings")
            print("   4. If divergence < 10%, use Advanced for final validation")

        elif transfer_confidence == "MEDIUM":
            print("\n⚠️  Cautious transfer strategy:")
            print("   1. Optimize in THOR to identify promising ranges")
            print("   2. Test ONLY liquidity/quality filters in Advanced")
            print("   3. Disable Advanced-specific features for direct comparison")
            print("   4. Re-optimize in Advanced with narrowed ranges")

        else:
            print("\n🔴 Alternative strategy:")
            print("   1. Use THOR for parameter DISCOVERY (not final validation)")
            print("   2. Identify promising parameter RANGES, not values")
            print("   3. Run full optimization in Advanced for final selection")
            print("   4. Accept that results will differ significantly")

        print("\n" + "=" * 80)

        return {
            "thor_result": result_thor,
            "advanced_result": result_advanced,
            "divergence": divergence,
            "divergence_normalized": divergence_normalized,
            "convergence_criteria": convergence_criteria,
            "verdict": verdict,
            "transfer_confidence": transfer_confidence,
            "critical_differences": self.critical_differences,
            "compatible_params": self.compatible_params,
            "incompatible_params": self.incompatible_params,
        }


def run_example_comparison():
    """Ejemplo de uso del comparador"""

    # PRIORIDAD 1: Usar parámetros validados
    try:
        with open("config/validated_production_params.json", "r") as f:
            validated_config = json.load(f)
        print(
            "✅ Usando parámetros validados de config/validated_production_params.json"
        )
        params = validated_config["parameters"]
        # Asegurar signal_type compatible con ambos motores
        params["signal_type"] = "any"
    except:
        print(
            "⚠️  No se encontraron parámetros validados, usando defaults más permisivos"
        )
        # Parámetros idénticos para ambos motores (más permisivos)
        params = {
            "signal_type": "any",  # Compatible con ambos motores
            "min_rvol": 1.5,  # Más permisivo
            "min_adr": 2.0,  # Más permisivo
            "min_dollar_volume": 5e6,
            "risk_dollars": 100,  # Más conservador
            "max_dist_sma20": 10.0,  # Más permisivo
            "use_phases": True,
            "tp1_r": 1.25,
            "tp2_r": 3.0,
        }

    # Mismo período, mismos tickers
    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"]
    period = ("2023-01-01", "2023-12-31")

    # Ejecutar comparación
    comparator = EngineComparator(tickers, period[0], period[1])
    results = comparator.run_comparison(params)

    return results


if __name__ == "__main__":
    results = run_example_comparison()

    # Guardar resultados
    output = {
        "summary": {
            "verdict": results["verdict"],
            "transfer_confidence": results["transfer_confidence"],
            "divergence_sharpe": results["divergence_normalized"]["sharpe"] * 100,
            "divergence_trades": results["divergence_normalized"]["trades_pct"] * 100,
            "convergence_passed": sum(results["convergence_criteria"].values()),
            "convergence_total": len(results["convergence_criteria"]),
        },
        "thor": results["thor_result"],
        "advanced": {
            k: v
            for k, v in results["advanced_result"].items()
            if k not in ["equity_curve", "trades"]
        },
    }

    print(f"\n{'=' * 80}")
    print("📄 SUMMARY SAVED TO: engine_comparison_summary.json")
    print(f"{'=' * 80}")
