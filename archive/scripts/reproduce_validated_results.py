#!/usr/bin/env python3
"""
REPRODUCE VALIDATED RESULTS - Backtest con EXACTAMENTE los mismos parámetros
"""

import sys
import json
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


def reproduce_validated_results():
    """Reproduce resultados validados con exactitud"""
    print("\n" + "=" * 80)
    print("🔬 REPRODUCING VALIDATED RESULTS")
    print("=" * 80)

    # Cargar config validada
    with open("config/validated_production_params.json", "r") as f:
        config = json.load(f)

    print(f"\n📋 Config Name: {config['config_name']}")
    print(f"📅 Validation Period: {config['validation_period']}")

    # Parámetros validados
    params = config["parameters"]

    print("\n🎯 Parámetros validados:")
    print(f"   signal_type: any")
    print(f"   min_rvol: {params['min_rvol']}")
    print(f"   min_adr: {params['min_adr']}")
    print(f"   min_volume: {params['min_volume']}")
    print(f"   min_dollar_volume: {params['min_dollar_volume']}")
    print(f"   risk_dollars: ${params['risk_dollars']}")
    print(f"   max_dist_sma20: {params['max_dist_sma20']}")
    print(f"   max_stop_pct: {params['max_stop_pct']}%")
    print(f"   tp1_r: {params['tp1_r']}R")
    print(f"   tp2_r: {params['tp2_r']}R")
    print(f"   tp1_pct: {params['tp1_pct'] * 100:.0f}%")
    print(f"   tp2_pct: {params['tp2_pct'] * 100:.0f}%")
    print(f"   runner_pct: {params['runner_pct'] * 100:.0f}%")
    print(f"   use_phases: {params['use_phases']}")
    print(f"   require_spy_above_sma50: {params.get('require_spy_above_sma50', False)}")

    # PERÍODO VALIDADO: Usar el mismo que validó bien
    validation_period = config["validation_period"]  # "2020-01-01 to 2024-12-31"
    start_date = validation_period.split(" to ")[0]
    end_date = validation_period.split(" to ")[1]

    print(f"\n📅 Período: {start_date} to {end_date}")

    # Universe validado (deberías usar el mismo)
    universe = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "NVDA",
        "TSLA",
        "META",
        "AMZN",
        "NFLX",
        "AMD",
        "AVGO",
    ]

    print(f"🎯 Universe: {len(universe)} tickers")
    print(f"   {', '.join(universe)}")

    # Crear engine con EXACTAMENTE los mismos parámetros
    print("\n" + "-" * 80)
    print("🚀 EJECUTANDO BACKTEST (Advanced Engine)")
    print("-" * 80)

    engine = AdvancedVectorBTEngine(
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000,
        signal_type="any",  # Compatible con validación
        **params,
    )

    result = engine.run_backtest()

    # Mostrar resultados
    print("\n" + "=" * 80)
    print("📊 BACKTEST RESULTS")
    print("=" * 80)

    print(f"\n🔬 Comparison with Validated:")
    print(f"   {'Metric':<20} | {'Validated':<15} | {'Reproduced':<15}")
    print("-" * 80)

    # Métricas comparables
    validated_perf = config["performance"]

    metrics = [
        ("Sharpe Ratio", validated_perf["sharpe_ratio"], result.get("sharpe_ratio", 0)),
        (
            "Total Return %",
            validated_perf["total_return_pct"],
            result.get("total_return", 0) * 100,
        ),
        (
            "Annualized Return %",
            validated_perf["annualized_return_pct"],
            result.get("annualized_return", 0) * 100,
        ),
        ("Total Trades", validated_perf["total_trades"], result.get("total_trades", 0)),
        ("Win Rate %", validated_perf["win_rate_pct"], result.get("win_rate", 0) * 100),
        (
            "Max Drawdown %",
            validated_perf["max_drawdown_pct"],
            result.get("max_drawdown", 0) * 100,
        ),
    ]

    for metric_name, validated, reproduced in metrics:
        match = (
            "✅"
            if abs(validated - reproduced) < 0.01
            else "❌"
            if abs(validated - reproduced) > 0.1
            else "⚠️"
        )
        print(
            f"   {metric_name:<20} | {validated:>15.3f} | {reproduced:>15.3f}  {match}"
        )

    print("\n" + "=" * 80)

    # Si hay divergencia significativa
    sharpe_diff = abs(validated_perf["sharpe_ratio"] - result.get("sharpe_ratio", 0))
    if sharpe_diff > 0.1:
        print("\n🔴 DIVERGENCIA SIGNIFICATIVA DETECTADA!")
        print("\n🔍 Causas posibles:")
        print("   1. El período de backtest es diferente al validado")
        print("   2. El universo de tickers es diferente")
        print("   3. Las features avanzadas están activadas/desactivadas diferente")
        print("   4. La configuración de signal_type es diferente")
        print("\n💡 Soluciones:")
        print("   • Verifica que app.py use EXACTAMENTE estos parámetros")
        print("   • Verifica que el período sea 2020-01-01 to 2024-12-31")
        print("   • Verifica que el universo sea correcto")
    else:
        print("\n✅ CONVERGENCIA CONFIRMADA!")
        print("   Los resultados reproducen la validación exitosamente")

    # Check R-multiple
    if "trades" in result and len(result["trades"]) > 0:
        trades_df = pd.DataFrame(result["trades"])

        if all(col in trades_df.columns for col in ["entry_price", "stop_price"]):
            trades_df["r_multiple"] = (
                trades_df["entry_price"] - trades_df["stop_price"]
            ) / trades_df["stop_price"]

            print(f"\n📊 R-Multiple Analysis:")
            print(f"   Mean R: {trades_df['r_multiple'].mean():.3f}R")
            print(f"   Std R: {trades_df['r_multiple'].std():.3f}R")
            print(f"   Zero R: {(trades_df['r_multiple'] == 0).sum()} trades")

            if (trades_df["r_multiple"] == 0).all():
                print("\n🔴 CRITICAL: All trades have R=0!")
                print("   Esto indica un BUG en el cálculo de position sizing")
                print("   O max_stop_pct es demasiado grande")

    return result


if __name__ == "__main__":
    reproduce_validated_results()
