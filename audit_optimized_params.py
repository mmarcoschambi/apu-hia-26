#!/usr/bin/env python3
"""
AUDITORÍA DE PARÁMETROS ÓPTIMOS
=================================
Explica cómo se eligieron los parámetros óptimos en run_dual_validation.sh
"""

import sys
import json
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def explain_stop_loss_format():
    """Explica el formato correcto de MAX_STOP_PCT"""
    print("=" * 80)
    print("📊 EXPLICACIÓN DEL STOP LOSS FORMATO")
    print("=" * 80)

    try:
        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]
        max_stop_pct = params.get("max_stop_pct", 6.0)

        print(f"\n✅ Valor cargado: {max_stop_pct}")

        print(f"\n📋 FORMATO CORRECTO:")
        print(f"   1. Porcentaje: {max_stop_pct}%")
        print(f"   2. Decimal: {max_stop_pct / 100:.4f}")
        print(f"   3. Fórmula en numba_core.py:")
        print(f"      stop_dist = curr_close * max_stop_pct")
        print(f"      Ejemplo: $100 × 0.06 = $6 stop distance")
        print(f"      Ejemplo: $50 × 0.06 = $3 stop distance")

        print(f"\n🧮 EJEMPLOS PRÁCTICOS:")
        print(f"   Trade a $150:")
        print(f"     Stop distance = $150 × 0.06 = $9")
        print(f"     Stop price = $150 - $9 = $141")
        print(f"     R = ($150 - $141) / $141 = 0.064R (6.4R per trade)")
        print()
        print(f"   Trade a $50:")
        print(f"     Stop distance = $50 × 0.06 = $3")
        print(f"     Stop price = $50 - $3 = $47")
        print(f"     R = ($50 - $47) / $47 = 0.064R (6.4R per trade)")

        print(f"\n⚠️  ANTERIORMENTE ESTABAMOS CONFUNDIDOS:")
        print(f"   ❌ INCORRECTO: 600.0% (esto significaría stop a 6x el precio)")
        print(f"   ✅ CORRECTO: 6.0% = 0.06 decimal (stop a 6% del precio)")

        return {
            "max_stop_pct_percent": max_stop_pct,
            "max_stop_pct_decimal": max_stop_pct / 100,
            "formula": "stop_dist = curr_close * max_stop_pct",
        }

    except Exception as e:
        print(f"❌ Error cargando parámetros: {e}")
        return None


def explain_optimization_process():
    """Explica cómo se optimizan los parámetros"""
    print("\n" + "=" * 80)
    print("🔧 PROCESO DE OPTIMIZACIÓN DE PARÁMETROS")
    print("=" * 80)

    print(f"\n📋 CÓMO SE GENERARON LOS PARÁMETROS:")
    print(f"\n1️⃣ WALK FORWARD OPTIMIZATION:")
    print(f"   Motor: V6_PRO (rápido)")
    print(f"   Universo: 40 tickers liquid leaders")
    print(f"   Windows: 12 months train, 3 months test")
    print(f"   Walk-forward: 3-6 months")
    print(f"   Trials: 50 configs por window")

    print(f"\n2️⃣ VALIDATION WITH ADVANCED:")
    print(f"   Motor: Advanced (producción)")
    print(f"   Validación: Top 5 configs")
    print(f"   Período: 2020-01-01 to 2024-12-31")
    print(f"   Goal: Verificar que funcionen en producción")

    print(f"\n3️⃣ OPTIMIZACIÓN TP DISTRIBUTION:")
    print(f"   Presets disponibles:")
    print(f"      • optimize: Busca óptimo automático (default)")
    print(f"      • classic: 50% TP1, 30% TP2, 20% Runner (tradicional)")
    print(f"      • balanced: 33% TP1, 33% TP2, 34% Runner (equilibrado)")
    print(f"      • aggressive_runner: 25% TP1, 30% TP2, 45% Runner (home runs)")
    print(f"      • conservative: 40% TP1, 35% TP2, 25% Runner (asegura)")
    print(f"      • extreme: 20% TP1, 30% TP2, 50% Runner (máx runner)")

    print(f"\n📊 CRITERIOS DE SELECCIÓN:")

    # Cargar resultados de walk forward si existen
    if Path("outputs/walk_forward_results.json").exists():
        with open("outputs/walk_forward_results.json", "r") as f:
            wf_results = json.load(f)

        print(f"\n   - Sharpe Ratio: Prioridad máxima")
        print(f"   - Total Return: Segunda prioridad")
        print(f"   - Win Rate: Tercera prioridad")
        print(f"   - Max Drawdown: Limitar riesgo")
        print(f"   - Trade Frequency: Balancear cantidad/quality")

    else:
        print(f"\n   - Sharpe Ratio: Prioridad máxima")
        print(f"   - Total Return: Segunda prioridad")
        print(f"   - Win Rate: Tercera prioridad")
        print(f"   - Max Drawdown: Limitar riesgo")


def display_optimized_parameters():
    """Muestra los parámetros óptimos actual"""
    print("\n" + "=" * 80)
    print("🎯 PARÁMETROS ÓPTIMOS ACTUALES")
    print("=" * 80)

    try:
        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]
        perf = config["performance"]

        print(f"\n📊 PERFORMANCE:")
        print(f"   Total Return: {perf['total_return_pct']:.2f}%")
        print(f"   Sharpe Ratio: {perf['sharpe_ratio']:.3f}")
        print(f"   Win Rate: {perf['win_rate_pct']:.2f}%")
        print(f"   Max Drawdown: {perf['max_drawdown_pct']:.2f}%")
        print(f"   Total Trades: {perf['total_trades']}")

        print(f"\n🎛️  FILTROS DE ENTRADA:")
        print(f"   MIN_RVOL: {params.get('min_rvol', 'N/A')}")
        print(f"   MIN_ADR_PCT: {params.get('min_adr', 'N/A')}%")
        print(f"   MAX_DIST_SMA20: {params.get('max_dist_sma20', 'N/A')}%")
        print(f"   MIN_DOLLAR_VOLUME: ${params.get('min_dollar_volume', 'N/A'):,.0f}")
        print(
            f"   MIN_CONSOLIDATION_DAYS: {params.get('min_consolidation_days', 'N/A')}"
        )
        print(f"   MAX_STOP_PCT: {params.get('max_stop_pct', 'N/A')}%")

        print(f"\n🎯 TARGETS Y EXITS:")
        print(
            f"   TP1: {params.get('tp1_r', 0):.2f}R ({params.get('tp1_pct', 0) * 100:.0f}%)"
        )
        print(
            f"   TP2: {params.get('tp2_r', 0):.2f}R ({params.get('tp2_pct', 0) * 100:.0f}%)"
        )
        print(f"   Runner: {params.get('runner_pct', 0) * 100:.0f}%")

        print(f"\n💼 POSITION SIZING:")
        print(f"   Mode: {params.get('mode', 'N/A')}")
        if params.get("mode") == "convergence":
            print(f"   Risk: ${params.get('risk_dollars', 0):.0f} fixed")
        else:
            print(f"   Risk: {params.get('risk_pct', 0) * 100:.1f}% equity")

        print(f"\n🔍 MARKET REGIME:")
        print(f"   SPY > SMA50: {params.get('require_spy_above_sma50', False)}")
        print(
            f"   Market Regime Filter: {params.get('use_market_regime_filter', False)}"
        )

        return {"params": params, "performance": perf}

    except Exception as e:
        print(f"❌ Error cargando parámetros: {e}")
        return None


def compare_with_presets():
    """Compara con presets TP disponibles"""
    print("\n" + "=" * 80)
    print("📊 COMPARACIÓN CON PRESETS TP")
    print("=" * 80)

    try:
        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        tp_presets = {
            "classic": {
                "tp1_pct": 0.50,
                "tp2_pct": 0.30,
                "runner_pct": 0.20,
                "tp1_r": 1.5,
                "tp2_r": 3.0,
            },
            "balanced": {
                "tp1_pct": 0.33,
                "tp2_pct": 0.33,
                "runner_pct": 0.34,
                "tp1_r": 1.5,
                "tp2_r": 3.0,
            },
            "aggressive_runner": {
                "tp1_pct": 0.25,
                "tp2_pct": 0.30,
                "runner_pct": 0.45,
                "tp1_r": 1.25,
                "tp2_r": 3.0,
            },
            "conservative": {
                "tp1_pct": 0.40,
                "tp2_pct": 0.35,
                "runner_pct": 0.25,
                "tp1_r": 1.25,
                "tp2_r": 3.0,
            },
            "extreme": {
                "tp1_pct": 0.20,
                "tp2_pct": 0.30,
                "runner_pct": 0.50,
                "tp1_r": 1.25,
                "tp2_r": 3.0,
            },
        }

        current_tp1_pct = params.get("tp1_pct", 0)
        current_tp2_pct = params.get("tp2_pct", 0)
        current_runner_pct = params.get("runner_pct", 0)

        print(f"\n🎯 TP DISTRIBUTION ACTUAL:")
        print(f"   TP1: {current_tp1_pct * 100:.0f}%")
        print(f"   TP2: {current_tp2_pct * 100:.0f}%")
        print(f"   Runner: {current_runner_pct * 100:.0f}%")
        print(
            f"   ⬇️  Total: {current_tp1_pct + current_tp2_pct + current_runner_pct * 100:.0f}%"
        )

        print(f"\n📋 COMPARACIÓN CON PRESETS:")

        for preset_name, preset_values in tp_presets.items():
            tp1_diff = abs(current_tp1_pct - preset_values["tp1_pct"])
            tp2_diff = abs(current_tp2_pct - preset_values["tp2_pct"])
            runner_diff = abs(current_runner_pct - preset_values["runner_pct"])

            match = (
                "✅"
                if (tp1_diff < 0.05 and tp2_diff < 0.05 and runner_diff < 0.05)
                else "❌"
            )

            print(f"\n   {match} {preset_name}:")
            print(
                f"      TP1: {preset_values['tp1_pct'] * 100:.0f}% | TP2: {preset_values['tp2_pct'] * 100:.0f}% | Runner: {preset_values['runner_pct'] * 100:.0f}%"
            )
            print(
                f"      Diferencias: TP1={tp1_diff * 100:.1f}%, TP2={tp2_diff * 100:.1f}%, Runner={runner_diff * 100:.1f}%"
            )

        # Detectar si está optimizado o en preset
        if (
            current_tp1_pct == 0.33
            and current_tp2_pct == 0.33
            and current_runner_pct == 0.34
        ):
            print(f"\n💡 DETECTADO: {preset_name.upper()} preset")
        else:
            print(f"\n💡 DETECTADO: OPTIMIZED (no coincide con ningún preset)")

    except Exception as e:
        print(f"❌ Error comparando: {e}")


def explain_parameter_reasons():
    """Explica por qué se eligieron cada parámetro"""
    print("\n" + "=" * 80)
    print("💡 RAZONES DE LOS PARÁMETROS OPTIMIZADOS")
    print("=" * 80)

    print(f"\n🎯 TP DISTRIBUTION:")
    print(f"   TP1 (33%): Garantiza ganancias minimas, reduce riesgo de drawdown")
    print(f"   TP2 (33%): Captura momentum sostenido, compensa TP1 parcial")
    print(f"   Runner (34%): Permite home runs, aumenta avg R-multiple")

    print(f"\n🎯 FILTROS:")
    print(f"   MIN_RVOL (1.0x): Asegura volumen real, elimina stocks quietos")
    print(f"   MIN_ADR (1.5%): Mínimo volatilidad necesaria")
    print(f"   MAX_DIST_SMA20 (9.0%): Permite entradas tempranas pero no tarde")
    print(f"   MIN_DOLLAR_VOLUME ($5M): Asegura liquidez para entradas/salidas")
    print(f"   MIN_CONSOLIDATION (10 days): VCP quality, reduce noise")

    print(f"\n🎯 STOP LOSS:")
    print(f"   MAX_STOP (6.0%): Balancea riesgo/recompensa")
    print(f"      - < 3%: Muy conservador, pierde muchos home runs")
    print(f"      - > 6%: Demasiado agresivo, drawdown alto")
    print(f"      - 6.0%: Optimizado para Sharpe máximo")

    print(f"\n🎯 POSITION SIZING:")
    print(f"   Mode: production (0.5% equity)")
    print(f"      - Permite compounding a lo largo del tiempo")
    print(f"      - Cápnar drawdown: 0.5% × 35% exposure = 0.175% max risk/trade")

    print(f"\n🎯 MARKET REGIME:")
    print(f"   SPY > SMA50: Filtra market bear")
    print(f"      - Aumenta Sharpe: evita draws en market malos")
    print(f"      - Reduce noise: solo tradea en tendencia alcista")


def show_walk_forward_results():
    """Muestra resultados de walk forward si existen"""
    print("\n" + "=" * 80)
    print("📊 WALK FORWARD RESULTS")
    print("=" * 80)

    if Path("outputs/walk_forward_results.json").exists():
        with open("outputs/walk_forward_results.json", "r") as f:
            wf_results = json.load(f)

        print(f"\n📁 Archivo: outputs/walk_forward_results.json")

        # Mostrar top configs por Sharpe
        print(f"\n🏆 TOP 5 CONFIGS POR SHARPE:")

        sorted_configs = sorted(
            wf_results.get("configs", []),
            key=lambda x: x.get("sharpe", 0),
            reverse=True,
        )[:5]

        for i, config in enumerate(sorted_configs, 1):
            sharpe = config.get("sharpe", 0)
            total_return = config.get("total_return", 0) * 100
            win_rate = config.get("win_rate", 0) * 100
            trades = config.get("total_trades", 0)

            print(
                f"   {i}. Sharpe: {sharpe:.3f} | Return: {total_return:.2f}% | Win Rate: {win_rate:.2f}% | Trades: {trades}"
            )

        # Mostrar período de validación
        validation_period = wf_results.get("validation_period", "N/A")
        print(f"\n📅 Período de validación:")
        print(f"   {validation_period}")

    else:
        print(f"\n⚠️  No se encontraron walk forward results")
        print(f"   Ejecuta: bash run_dual_validation.sh")


def main():
    print("=" * 80)
    print("🔍 AUDITORÍA DE PARÁMETROS ÓPTIMOS")
    print("=" * 80)

    # 1. Explicar stop loss
    stop_loss_info = explain_stop_loss_format()

    # 2. Explicar proceso de optimización
    explain_optimization_process()

    # 3. Mostrar parámetros óptimos
    param_info = display_optimized_parameters()

    # 4. Comparar con presets
    compare_with_presets()

    # 5. Explicar razones
    explain_parameter_reasons()

    # 6. Mostrar walk forward results
    show_walk_forward_results()

    print("\n" + "=" * 80)
    print("💡 RECOMENDACIONES")
    print("=" * 80)

    print(f"\n🎯 PARA USAR ESTOS PARÁMETROS:")
    print(f"   1. Copy: python3 answer_cuestionario.py > respuestas.txt")
    print(f"   2. Use: python3 example_quick_backtest.py")
    print(f"   3. Validate: python3 convergence_test_streamlit_cli.py")

    print(f"\n🎯 PARA OPTIMIZAR OTROS PRESETS:")
    print(f"   bash run_dual_validation.sh --tp-preset balanced")
    print(f"   bash run_dual_validation.sh --tp-preset aggressive_runner")
    print(f"   bash run_dual_validation.sh --tp-preset conservative")


if __name__ == "__main__":
    main()
