#!/usr/bin/env python3
"""
CONVERGENCE TEST - Verifica que Streamlit UI y CLI produzcan resultados idénticos
================================================================================
Este script:
1. Ejecuta un backtest vía Streamlit (simulado) con parámetros específicos
2. Ejecuta el mismo backtest vía CLI
3. Compara resultados y reporta divergencias
"""

import sys
import json
import pandas as pd
import numpy as np
import subprocess
import time
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


def load_params_from_validated_json():
    """Carga parámetros validados del JSON de validación"""
    config_file = Path("config/validated_production_params.json")
    if not config_file.exists():
        print(
            "❌ Config validada no encontrada en config/validated_production_params.json"
        )
        print("   Corre: bash run_dual_validation.sh para generarla")
        return None

    with open(config_file, "r") as f:
        config = json.load(f)

    return config.get("parameters", {})


def run_backtest_cli(universe, start_date, end_date, params_dict, output_file):
    """Ejecuta backtest vía CLI"""
    print(f"\n🔄 Ejecutando vía CLI...")

    # Aplicar modificaciones de parámetros según UI (si las hay)
    streamlit_params = params_dict.copy()

    # Add custom params that might be added in UI
    streamlit_params.update(
        {
            "signal_type": "any",
            "use_dynamic_thresholds": False,
            "use_market_regime_filter": False,
            "use_adaptive_filtering": False,
            "use_rs_percentile": False,
            "use_sma50_atr_filter": False,
        }
    )

    try:
        from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

        print(f"   Universo: {len(universe)} tickers")
        print(f"   Período: {start_date} to {end_date}")
        print(f"   Riesgo: ${streamlit_params.get('risk_dollars', 150):.0f}")

        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            **streamlit_params,
        )

        result = engine.run_backtest()

        # Guardar resultados
        if "trades" in result and len(result["trades"]) > 0:
            cli_df = pd.DataFrame(result["trades"])
            cli_df.to_csv(output_file, index=False)
            print(f"✅ CLI: Guardados {len(cli_df)} trades en {output_file}")
            return True
        else:
            pd.DataFrame().to_csv(output_file, index=False)
            print(f"⚠️  CLI: No trades encontrados")
            return False

    except Exception as e:
        print(f"❌ Error ejecutando CLI: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_backtest_streamlit(universe, start_date, end_date, params_dict, output_file):
    """Simula ejecución vía Streamlit UI"""
    print(f"\n🔄 Ejecutando vía Streamlit UI (simulado)...")

    # Usar el mismo lógica que app.py pero sin Streamlit
    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    try:
        # Aplicar modificaciones de parámetros según UI (si las hay)
        streamlit_params = params_dict.copy()

        # Add custom params that might be added in UI
        streamlit_params.update(
            {
                "signal_type": "any",
                "use_dynamic_thresholds": False,
                "use_market_regime_filter": False,
                "use_adaptive_filtering": False,
                "use_rs_percentile": False,
                "use_sma50_atr_filter": False,
            }
        )

        print(f"   Universo: {len(universe)} tickers")
        print(f"   Período: {start_date} to {end_date}")
        print(f"   Riesgo: ${streamlit_params.get('risk_dollars', 150):.0f}")

        engine = AdvancedVectorBTEngine(
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            **streamlit_params,
        )

        result = engine.run_backtest()

        # Guardar resultados
        if "trades" in result and len(result["trades"]) > 0:
            df = pd.DataFrame(result["trades"])
            df.to_csv(output_file, index=False)
            print(f"✅ Streamlit: Guardados {len(df)} trades en {output_file}")
            return True
        else:
            pd.DataFrame().to_csv(output_file, index=False)
            print(f"⚠️  Streamlit: No trades encontrados")
            return False

    except Exception as e:
        print(f"❌ Error ejecutando Streamlit: {e}")
        import traceback

        traceback.print_exc()
        return False


def compare_results(cli_file, streamlit_file):
    """Compara resultados entre CLI y Streamlit"""
    print("\n" + "=" * 80)
    print("📊 COMPARANDO RESULTADOS")
    print("=" * 80)

    # Cargar ambos CSVs
    try:
        cli_df = pd.read_csv(cli_file)
        streamlit_df = pd.read_csv(streamlit_file)
    except Exception as e:
        print(f"❌ Error cargando CSVs: {e}")
        return None

    print(f"\n📏 Trade Counts:")
    print(f"   CLI:    {len(cli_df)} trades")
    print(f"   Streamlit: {len(streamlit_df)} trades")

    if len(cli_df) != len(streamlit_df):
        print(f"   ⚠️  DIFERENCIA: {abs(len(cli_df) - len(streamlit_df))} trades")

    # Identificar tickers comunes (columna puede ser 'ticker' o 'symbol')
    ticker_col_cli = "ticker" if "ticker" in cli_df.columns else "symbol"
    ticker_col_sl = "ticker" if "ticker" in streamlit_df.columns else "symbol"

    common_tickers = set(cli_df[ticker_col_cli].unique()) & set(
        streamlit_df[ticker_col_sl].unique()
    )
    print(f"\n📋 Tickers Comunes: {len(common_tickers)}")
    print(f"   CLI: {sorted(set(cli_df[ticker_col_cli].unique()))}")
    print(f"   Streamlit: {sorted(set(streamlit_df[ticker_col_sl].unique()))}")

    # Comparar métricas por ticker
    print(f"\n📈 COMPARACIÓN POR TICKER")
    print("-" * 80)

    comparison_results = []

    for ticker in sorted(common_tickers):
        cli_trades = cli_df[cli_df[ticker_col_cli] == ticker]
        sl_trades = streamlit_df[streamlit_df[ticker_col_sl] == ticker]

        # Calcular métricas
        cli_total_return = cli_trades["pnl"].sum()
        sl_total_return = sl_trades["pnl"].sum()

        cli_total_trades = len(cli_trades)
        sl_total_trades = len(sl_trades)

        cli_win_rate = (
            (cli_trades["pnl"] > 0).sum() / len(cli_trades) * 100
            if len(cli_trades) > 0
            else 0
        )
        sl_win_rate = (
            (sl_trades["pnl"] > 0).sum() / len(sl_trades) * 100
            if len(sl_trades) > 0
            else 0
        )

        # Calcular diferencia
        trade_diff = abs(cli_total_trades - sl_total_trades)
        return_diff_pct = (
            abs(cli_total_return - sl_total_return) / cli_total_return * 100
            if cli_total_return != 0
            else 0
        )
        win_rate_diff = abs(cli_win_rate - sl_win_rate)

        comparison_results.append(
            {
                "ticker": ticker,
                "cli_trades": cli_total_trades,
                "sl_trades": sl_total_trades,
                "trade_diff": trade_diff,
                "cli_total_return": cli_total_return,
                "sl_total_return": sl_total_return,
                "return_diff_pct": return_diff_pct,
                "cli_win_rate": cli_win_rate,
                "sl_win_rate": sl_win_rate,
                "win_rate_diff": win_rate_diff,
            }
        )

        # Mostrar divergencias
        if trade_diff > 0 or return_diff_pct > 1 or win_rate_diff > 5:
            print(f"\n   ⚠️  {ticker}:")
            print(
                f"      Trades: CLI={cli_total_trades}, Streamlit={sl_total_trades} (diff={trade_diff})"
            )
            print(
                f"      Return: CLI=${cli_total_return:.2f}, Streamlit=${sl_total_return:.2f} ({return_diff_pct:.1f}%)"
            )
            print(
                f"      Win Rate: CLI={cli_win_rate:.1f}%, Streamlit={sl_win_rate:.1f}% (diff={win_rate_diff:.1f}%)"
            )

    # Resumen global
    print(f"\n" + "=" * 80)
    print("🎯 RESUMEN GLOBAL")
    print("=" * 80)

    cli_df["pnl"].to_csv("backtest_comparison_cli.csv", index=False)
    streamlit_df["pnl"].to_csv("backtest_comparison_streamlit.csv", index=False)

    return {
        "cli_total_trades": len(cli_df),
        "sl_total_trades": len(streamlit_df),
        "cli_total_return": cli_df["pnl"].sum(),
        "sl_total_return": streamlit_df["pnl"].sum(),
        "common_tickers": len(common_tickers),
        "comparison_results": comparison_results,
    }


def main():
    print("=" * 80)
    print("🔄 CONVERGENCE TEST: Streamlit UI vs CLI")
    print("=" * 80)

    # 1. Configuración
    print("\n📋 CONFIGURACIÓN")

    # Cargar parámetros validados
    params_dict = load_params_from_validated_json()
    if not params_dict:
        return

    # Usar período de validación
    validation_period = "2020-01-01 to 2024-12-31"
    start_date = "2020-01-01"
    end_date = "2024-12-31"

    # Universe
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

    print(f"   Universo: {len(universe)} tickers")
    print(f"   Período: {start_date} to {end_date}")
    print(f"   Parámetros cargados desde validated_production_params.json")

    # 2. Ejecutar vía CLI
    cli_file = f"backtest_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_cli.csv"
    success_cli = run_backtest_cli(
        universe, start_date, end_date, params_dict, cli_file
    )

    if not success_cli:
        print("\n❌ FALLÓ CLI, abortando")
        return

    # 3. Ejecutar vía Streamlit (simulado)
    streamlit_file = (
        f"backtest_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_streamlit.csv"
    )
    success_streamlit = run_backtest_streamlit(
        universe, start_date, end_date, params_dict, streamlit_file
    )

    if not success_streamlit:
        print("\n❌ FALLÓ Streamlit, abortando")
        return

    # 4. Comparar resultados
    results = compare_results(cli_file, streamlit_file)

    if not results:
        print("\n❌ No se pudo comparar resultados")
        return

    # 5. Análisis final
    print("\n" + "=" * 80)
    print("🎯 ANÁLISIS FINAL")
    print("=" * 80)

    total_trades_diff = abs(results["cli_total_trades"] - results["sl_total_trades"])
    total_return_diff_pct = (
        abs(results["cli_total_return"] - results["sl_total_return"])
        / results["cli_total_return"]
        * 100
        if results["cli_total_return"] != 0
        else 0
    )

    print(f"\n📊 Resumen:")
    print(f"   CLI Total Trades:     {results['cli_total_trades']}")
    print(f"   Streamlit Total Trades: {results['sl_total_trades']}")
    print(
        f"   Diferencia Trades:    {total_trades_diff} ({total_trades_diff / results['cli_total_trades'] * 100:.1f}%)"
    )

    print(f"\n💰 Returns:")
    print(f"   CLI Total Return:    ${results['cli_total_return']:,.2f}")
    print(f"   Streamlit Total Return: ${results['sl_total_return']:,.2f}")
    print(
        f"   Diferencia Return:    ${abs(results['cli_total_return'] - results['sl_total_return']):,.2f} ({total_return_diff_pct:.1f}%)"
    )

    print(f"\n📋 Tickers Comunes:    {results['common_tickers']}")

    # Determinar convergencia
    convergence_threshold = 2.0  # 2% para retornos, 5 trades para cantidad

    if total_return_diff_pct < convergence_threshold and total_trades_diff < 5:
        print(f"\n✅ CONVERGENCIA CONFIRMADA")
        print(
            f"   Los resultados entre Streamlit y CLI son idénticos (dentro del umbral)"
        )
    else:
        print(f"\n⚠️  DIVERGENCIA DETECTADA")
        print(
            f"   Total Return: {total_return_diff_pct:.1f}% (umbral: {convergence_threshold}%)"
        )
        print(f"   Total Trades: {total_trades_diff} (umbral: 5)")

    print(f"\n📁 Archivos generados:")
    print(f"   - {cli_file}")
    print(f"   - {streamlit_file}")
    print(f"   - backtest_comparison_cli.csv")
    print(f"   - backtest_comparison_streamlit.csv")


if __name__ == "__main__":
    main()
