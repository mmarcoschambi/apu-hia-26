#!/usr/bin/env python3
"""
🔧 FASE 1: Baseline Convergence Test
====================================

Objetivo: Verificar que THOR y Advanced dan resultados similares
con los mismos parámetros base (sin features exclusivos de Advanced).

Métrica objetivo: Divergencia < 20% en Sharpe, Trades, Win Rate, Return
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACIÓN BASELINE: Advanced SIN features exclusivas
# =============================================================================

params_baseline = {
    # Core parameters (transferibles)
    'signal_type': 'breakout',
    'min_rvol': 2.0,
    'min_adr': 2.5,
    'risk_dollars': 150,
    'max_dist_sma20': 12.5,
    'min_consolidation_days': 10,
    'max_stop_pct': 7.0,
    'tp1_r': 1.5,
    'tp2_r': 3.0,
    'use_phases': True,
    'min_dollar_volume': 5e6,
    'max_exposure_pct': 0.25,

    # RVOL sizing (SINCRONIZAR - THOR usa estos valores)
    'rvol_warning': 2.0,
    'rvol_danger': 3.0,
    'rvol_warning_size': 65,   # THOR usa 65
    'rvol_danger_size': 30,    # THOR usa 30

    # Advanced features (DESACTIVAR TODOS)
    'use_dynamic_thresholds': False,        # ❌ OFF
    'use_market_regime_filter': False,      # ❌ OFF
    'use_adaptive_filtering': False,        # ❌ OFF
    'use_earnings_calendar': False,         # ❌ OFF
    'require_spy_above_sma50': False,       # ❌ OFF (CRÍTICO)
    'require_positive_rs': False,           # ❌ OFF
    'use_trailing_stop': False,             # ❌ OFF (mantener exits iguales)
    'use_rs_percentile': False,             # ❌ OFF
    'use_sma50_atr_filter': False,          # ❌ OFF
    'require_bullish_spy': False,           # ❌ OFF (THOR param)
    'require_sma_trend': False,             # ❌ OFF (THOR param)
    'max_vix': 40.0,                        # THOR default
    'offline_mode': True,
}

# Test con mismo universo y período
tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']
period = ('2023-01-01', '2023-12-31')


def run_thor_baseline():
    """Ejecutar THOR Engine con configuración baseline"""
    print("=" * 70)
    print("🔧 TEST 1: THOR Engine (Baseline)")
    print("=" * 70)

    thor = OptimizationEngineTHOR(
        tickers=tickers,
        start_date=period[0],
        end_date=period[1],
        use_float32=True,
        chunk_size=50
    )

    result_thor = thor.backtest(params_baseline)

    print(f"Sharpe Ratio:  {result_thor['sharpe_ratio']:.3f}")
    print(f"Total Return:  {result_thor['total_return_pct']:.2f}%")
    print(f"Total Trades:  {result_thor['total_trades']}")
    print(f"Unique Entries: {result_thor.get('unique_entries', 'N/A')}")
    print(f"Win Rate:      {result_thor['win_rate_pct']:.1f}%")
    print(f"Max Drawdown:  {result_thor['max_drawdown_pct']:.2f}%")
    print(f"Profit Factor: {result_thor['profit_factor']:.2f}")

    return thor, result_thor


def run_advanced_baseline():
    """Ejecutar Advanced Engine con configuración baseline"""
    print("\n" + "=" * 70)
    print("🔬 TEST 2: Advanced Engine (Baseline - Features OFF)")
    print("=" * 70)

    advanced = AdvancedVectorBTEngine(
        universe=tickers,
        start_date=period[0],
        end_date=period[1],
        **params_baseline
    )

    result_advanced = advanced.run_backtest()

    # Convertir al formato esperado para comparación
    result_advanced_converted = {
        'sharpe_ratio': result_advanced['sharpe_ratio'],
        'total_return': result_advanced['total_return'],
        'total_return_pct': result_advanced['total_return'] * 100,
        'total_trades': result_advanced['total_trades'],
        'win_rate': result_advanced['win_rate'] * 100,
        'win_rate_pct': result_advanced['win_rate'] * 100,
        'max_drawdown': abs(result_advanced['max_drawdown']),
        'max_drawdown_pct': abs(result_advanced['max_drawdown']) * 100,
        'profit_factor': 0,  # No viene en Advanced
    }

    print(f"Sharpe Ratio:  {result_advanced_converted['sharpe_ratio']:.3f}")
    print(f"Total Return:  {result_advanced_converted['total_return_pct']:.2f}%")
    print(f"Total Trades:  {result_advanced_converted['total_trades']}")
    print(f"Win Rate:      {result_advanced_converted['win_rate_pct']:.1f}%")
    print(f"Max Drawdown:  {result_advanced_converted['max_drawdown_pct']:.2f}%")
    print(f"Annualized Return:  {result_advanced['annualized_return']*100:.2f}%")

    return advanced, result_advanced_converted


def analyze_convergence(result_thor, result_advanced):
    """Analizar convergencia entre motores"""
    print("\n" + "=" * 70)
    print("📊 CONVERGENCIA BASELINE")
    print("=" * 70)

    # Calcular divergencias
    divergence = {
        'sharpe': abs(result_thor['sharpe_ratio'] - result_advanced['sharpe_ratio']),
        'trades': abs(result_thor['total_trades'] - result_advanced['total_trades']),
        'return': abs(result_thor['total_return_pct'] - result_advanced['total_return_pct']),
        'win_rate': abs(result_thor['win_rate_pct'] - result_advanced['win_rate_pct']),
        'max_dd': abs(result_thor['max_drawdown_pct'] - result_advanced['max_drawdown_pct']),
    }

    # Evaluar convergencia
    convergence_results = {}

    for metric, diff in divergence.items():
        if metric == 'trades':
            status = "✅ OK" if diff <= 2 else ("⚠️ CHECK" if diff <= 5 else "❌ CRITICAL")
        elif metric in ['win_rate', 'return', 'max_dd']:
            status = "✅ OK" if diff < 10 else ("⚠️ CHECK" if diff < 20 else "❌ CRITICAL")
        else:  # sharpe
            status = "✅ OK" if diff < 0.2 else ("⚠️ CHECK" if diff < 0.5 else "❌ CRITICAL")

        convergence_results[metric] = {'diff': diff, 'status': status}
        print(f"{metric:12s}: {diff:6.2f}  {status}")

    print("=" * 70)

    # Tabla comparativa
    print("\n📊 TABLA COMPARATIVA")
    print("-" * 70)
    print(f"{'Métrica':<15s} {'THOR':>12s} {'Advanced':>12s} {'Divergencia':>12s} {'Status':>10s}")
    print("-" * 70)

    metrics_map = {
        'Sharpe': ('sharpe_ratio', '{:.3f}'),
        'Return (%)': ('total_return_pct', '{:.2f}%'),
        'Trades': ('total_trades', '{:d}'),
        'Win Rate (%)': ('win_rate_pct', '{:.1f}%'),
        'Max DD (%)': ('max_drawdown_pct', '{:.2f}%'),
        'Profit Factor': ('profit_factor', '{:.2f}'),
    }

    for label, (key, fmt) in metrics_map.items():
        thor_val = result_thor.get(key, 0)
        adv_val = result_advanced.get(key, 0)
        diff = abs(thor_val - adv_val)
        # Si no hay profit_factor en Advanced, no mostrar divergencia crítica
        if key == 'profit_factor' and adv_val == 0:
            status = "N/A"
        else:
            status = convergence_results.get(key, {}).get('status', 'N/A')

        print(f"{label:<15s} {fmt:>12s} {fmt:>12s} {fmt:>12s} {status:>10s}".format(
            thor_val, adv_val, diff, status
        ))

    print("-" * 70)

    # Interpretación
    print("\n📋 INTERPRETACIÓN:")

    critical_count = sum(1 for r in convergence_results.values() if "CRITICAL" in r['status'])
    warning_count = sum(1 for r in convergence_results.values() if "CHECK" in r['status'])
    ok_count = sum(1 for r in convergence_results.values() if "OK" in r['status'])

    if critical_count == 0:
        print("✅ EXCELENTE - Motores alineados en baseline")
        print("   → Proceder a FASE 2: Activar features progresivamente")
        return True
    elif warning_count <= 2:
        print("⚠️ ACEPTABLE - Pequeñas diferencias detectadas")
        print(f"   → {warning_count} métricas con divergencia moderada")
        print("   → Revisar implementation de entry signals")
        return None
    else:
        print("❌ CRÍTICO - Motores NO alineados")
        print(f"   → {critical_count} métricas CRÍTICAS, {warning_count} con warnings")
        print("   → Revisar DIFERENCIAS DE IMPLEMENTACIÓN")
        print("   → Posibles causas:")
        print("      1. Entry signal logic diferente")
        print("      2. Position sizing calculation diferente")
        print("      3. Exit logic diferente (3-phase implementation)")
        print("      4. Data loading diferente (missing tickers?)")
        return False


def debug_implementations(thor, advanced):
    """Debug si hay divergencia crítica"""
    print("\n" + "=" * 70)
    print("🔍 DEBUG: Comparación de Implementaciones")
    print("=" * 70)

    # 1. Comparar datos cargados
    print("\n1️⃣ DATA COMPARISON:")
    print(f"   THOR close shape:   {thor.close.shape}")
    print(f"   Advanced close shape: {advanced.close.shape}")
    print(f"   Columns match: {set(thor.close.columns) == set(advanced.close.columns)}")
    print(f"   Date match: {thor.close.index[0] == advanced.close.index[0]} to {thor.close.index[-1] == advanced.close.index[-1]}")

    # 2. Comparar RVOL (últimos 5 días, primeros 3 tickers)
    thor_rvol = thor.rvol.iloc[-5:, :3].values.flatten()
    adv_rvol = advanced.rvol.iloc[-5:, :3].values.flatten()
    print(f"\n2️⃣ RVOL SAMPLE (last 5 days, first 3 tickers):")
    print(f"   THOR:    {thor_rvol}")
    print(f"   Advanced: {adv_rvol}")
    rvol_match = np.allclose(thor_rvol, adv_rvol, rtol=0.1)
    print(f"   Match:   {rvol_match} ✅" if rvol_match else f"   Match:   {rvol_match} ❌")

    # 3. Comparar ADR (últimos 5 días, primeros 3 tickers)
    thor_adr = thor.adr.iloc[-5:, :3].values.flatten()
    adv_adr = advanced.adr_pct.iloc[-5:, :3].values.flatten()
    print(f"\n3️⃣ ADR SAMPLE (last 5 days, first 3 tickers):")
    print(f"   THOR:    {thor_adr}")
    print(f"   Advanced: {adv_adr}")
    adr_match = np.allclose(thor_adr, adv_adr, rtol=0.1)
    print(f"   Match:   {adr_match} ✅" if adr_match else f"   Match:   {adr_match} ❌")

    # 4. Comparar SMA20 (últimos 5 días, primeros 3 tickers)
    thor_sma20 = thor.sma20.iloc[-5:, :3].values.flatten()
    adv_sma20 = advanced.sma_20.iloc[-5:, :3].values.flatten()
    print(f"\n4️⃣ SMA20 SAMPLE (last 5 days, first 3 tickers):")
    print(f"   THOR:    {thor_sma20}")
    print(f"   Advanced: {adv_sma20}")
    sma20_match = np.allclose(thor_sma20, adv_sma20, rtol=0.01)
    print(f"   Match:   {sma20_match} ✅" if sma20_match else f"   Match:   {sma20_match} ❌")

    # 5. Resumen de diferencias en indicadores
    print(f"\n5️⃣ INDICATOR MEANS (full dataset):")
    print(f"   {'Metric':<15s} {'THOR':>12s} {'Advanced':>12s} {'Diff':>12s}")
    print(f"   {'-'*60}")
    print(f"   {'RVOL':<15s} {thor.rvol.mean().mean():>12.2f} {advanced.rvol.mean().mean():>12.2f} {abs(thor.rvol.mean().mean() - advanced.rvol.mean().mean()):>12.3f}")
    print(f"   {'ADR':<15s} {thor.adr.mean().mean():>12.2f} {advanced.adr_pct.mean().mean():>12.2f} {abs(thor.adr.mean().mean() - advanced.adr_pct.mean().mean()):>12.3f}")
    print(f"   {'Close':<15s} {thor.close.mean().mean():>12.2f} {advanced.close.mean().mean():>12.2f} {abs(thor.close.mean().mean() - advanced.close.mean().mean()):>12.3f}")

    print("\n" + "=" * 70)

    # Diagnosis
    print("\n📋 DIAGNOSIS:")
    issues = []
    if not rvol_match:
        issues.append("❌ RVOL calculation differs - check vol_sma20 implementation")
    if not adr_match:
        issues.append("❌ ADR calculation differs - check rolling period")
    if not sma20_match:
        issues.append("❌ SMA20 calculation differs - check rolling window")

    if not issues:
        print("✅ All indicators match - issue likely in entry/exit logic or position sizing")
    else:
        for issue in issues:
            print(f"   {issue}")

    print("=" * 70)


def main():
    """Función principal"""
    print("\n" + "=" * 70)
    print("🔧 FASE 1: BASELINE CONVERGENCE TEST")
    print("=" * 70)
    print(f"📅 Period: {period[0]} to {period[1]}")
    print(f"🎯 Tickers: {', '.join(tickers)}")
    print("=" * 70)

    # Ejecutar THOR
    thor, result_thor = run_thor_baseline()

    # Ejecutar Advanced
    advanced, result_advanced = run_advanced_baseline()

    # Analizar convergencia
    converged = analyze_convergence(result_thor, result_advanced)

    # Si no converge, hacer debug
    if converged is False:
        debug_implementations(thor, advanced)

    print("\n" + "=" * 70)
    print("📋 RESUMEN FINAL")
    print("=" * 70)

    if converged is True:
        print("✅ BASELINE CONVERGED - Proceed to FASE 2")
        print("   Run: python scripts/impact_analysis.py")
    elif converged is None:
        print("⚠️ BASELINE PARTIAL - Review warnings before proceeding")
        print("   Recommended: Debug entry signal logic")
    else:
        print("❌ BASELINE FAILED - Do NOT proceed to FASE 2")
        print("   Fix implementation differences first")

    print("=" * 70)


if __name__ == '__main__':
    main()