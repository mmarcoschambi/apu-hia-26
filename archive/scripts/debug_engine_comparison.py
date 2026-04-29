#!/usr/bin/env python3
"""
DEBUG ENGINE COMPARISON - Verifica sincronía entre motores
"""

import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.optimization_engine_thor import OptimizationEngineTHOR
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine


def load_validated_params():
    """Carga parámetros validados"""
    try:
        with open("config/validated_production_params.json", "r") as f:
            validated_config = json.load(f)
        print("✅ Usando parámetros validados de validated_production_params.json")
        return validated_config["parameters"]
    except Exception as e:
        print(f"⚠️  Error cargando params validados: {e}")
        return None


def debug_engine_initialization():
    """Debug inicialización de motores"""
    print("\n" + "=" * 80)
    print("🔬 ENGINE INITIALIZATION DEBUG")
    print("=" * 80)

    params = load_validated_params()
    if not params:
        return

    print("\n📋 Parámetros:")
    for key, value in params.items():
        print(f"   • {key:25s}: {value}")

    # Configuración de prueba
    tickers = ["NVDA", "TSLA", "AAPL"]
    start_date = "2024-01-01"
    end_date = "2024-06-30"

    print(f"\n🎯 Test Config:")
    print(f"   Tickers: {tickers}")
    print(f"   Period: {start_date} to {end_date}")

    # THOR Engine
    print("\n" + "-" * 80)
    print("🔨 THOR ENGINE INITIALIZATION")
    print("-" * 80)

    thor_params = params.copy()
    thor_params["signal_type"] = "any"  # Compatible con ambos motores
    thor_params.setdefault("require_bullish_spy", False)
    thor_params.setdefault("require_positive_rs", False)
    thor_params.setdefault("require_sma_trend", False)
    thor_params.setdefault("max_vix", 40.0)

    try:
        thor = OptimizationEngineTHOR(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            offline_mode=True,
            use_float32=True,
        )

        print(f"\n✅ THOR inicializado:")
        print(f"   Valid tickers: {len(thor.valid_tickers)}")
        print(
            f"   Shape close: {thor.close.shape if thor.close is not None else 'None'}"
        )
        print(
            f"   Shape volume: {thor.volume.shape if thor.volume is not None else 'None'}"
        )

        # Check data quality
        if thor.close is not None:
            print(f"\n📊 Data Quality:")
            print(f"   Nulls in close: {thor.close.isnull().sum().sum()}")
            print(f"   Nulls in volume: {thor.volume.isnull().sum().sum()}")
            print(f"   Date range: {thor.close.index[0]} to {thor.close.index[-1]}")

        # Check indicators
        print(f"\n📈 Indicators (calculated on demand):")
        print(f"   sma20: {'✅' if thor._sma20 is not None else '❌ (lazy)'}")
        print(f"   rvol: {'✅' if thor._rvol is not None else '❌ (lazy)'}")
        print(f"   adr: {'✅' if thor._adr is not None else '❌ (lazy)'}")

    except Exception as e:
        print(f"\n❌ Error inicializando THOR: {e}")
        import traceback

        traceback.print_exc()

    # Advanced Engine
    print("\n" + "-" * 80)
    print("🚀 ADVANCED ENGINE INITIALIZATION")
    print("-" * 80)

    advanced_params = params.copy()
    advanced_params["signal_type"] = "any"  # Compatible

    try:
        advanced = AdvancedVectorBTEngine(
            universe=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            signal_type="any",
            # Desactivar features exclusivas para convergencia
            use_dynamic_thresholds=False,
            use_market_regime_filter=False,
            use_adaptive_filtering=False,
            use_rs_percentile=False,
            use_sma50_atr_filter=False,
            use_earnings_calendar=False,
            require_spy_above_sma50=False,
            require_positive_rs=False,
            **{
                k: v
                for k, v in advanced_params.items()
                if k
                not in [
                    "use_dynamic_thresholds",
                    "use_market_regime_filter",
                    "use_adaptive_filtering",
                    "use_rs_percentile",
                    "use_sma50_atr_filter",
                    "use_earnings_calendar",
                    "require_spy_above_sma50",
                    "require_positive_rs",
                ]
            },
        )

        advanced.load_data()

        print(f"\n✅ Advanced inicializado:")
        print(f"   Shape close: {advanced.close.shape}")
        print(f"   Shape volume: {advanced.volume.shape}")

        # Check data quality
        print(f"\n📊 Data Quality:")
        print(f"   Nulls in close: {advanced.close.isnull().sum().sum()}")
        print(f"   Nulls in volume: {advanced.volume.isnull().sum().sum()}")
        print(f"   Date range: {advanced.close.index[0]} to {advanced.close.index[-1]}")

        # Check indicators
        print(f"\n📈 Indicators:")
        print(f"   sma20: {'✅' if advanced.sma_20 is not None else '❌'}")
        print(
            f"   rvol: {'✅' if hasattr(advanced, 'rvol') and advanced.rvol is not None else '❌'}"
        )
        print(f"   adr_pct: {'✅' if advanced.adr_pct is not None else '❌'}")

    except Exception as e:
        print(f"\n❌ Error inicializando Advanced: {e}")
        import traceback

        traceback.print_exc()


def debug_entry_signals():
    """Debug: Compara señales de entrada entre motores"""
    print("\n" + "=" * 80)
    print("🎯 ENTRY SIGNALS DEBUG")
    print("=" * 80)

    params = load_validated_params()
    if not params:
        return

    tickers = ["NVDA", "TSLA", "AAPL"]
    start_date = "2024-01-01"
    end_date = "2024-06-30"

    thor_params = params.copy()
    thor_params["signal_type"] = "any"

    # THOR
    try:
        thor = OptimizationEngineTHOR(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            offline_mode=True,
        )

        thor_result = thor.backtest(thor_params)

        print(f"\n🔨 THOR Entry Signals:")
        print(f"   Total trades: {thor_result.get('total_trades', 0)}")
        print(f"   Unique entry dates: {thor_result.get('entry_dates_count', 'N/A')}")

        if "trades_df" in thor_result and not thor_result["trades_df"].empty:
            trades = thor_result["trades_df"]
            print(f"\n   First 5 entries:")
            print(
                f"   {trades[['ticker', 'entry_date', 'entry_price', 'exit_type']].head()}"
            )

    except Exception as e:
        print(f"❌ Error en THOR: {e}")

    # Advanced
    try:
        advanced = AdvancedVectorBTEngine(
            universe=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_capital=100000,
            signal_type="any",
            use_dynamic_thresholds=False,
            use_market_regime_filter=False,
            use_adaptive_filtering=False,
            use_rs_percentile=False,
            use_sma50_atr_filter=False,
            use_earnings_calendar=False,
            require_spy_above_sma50=False,
            require_positive_rs=False,
            **{
                k: v
                for k, v in params.items()
                if k
                not in [
                    "use_dynamic_thresholds",
                    "use_market_regime_filter",
                    "use_adaptive_filtering",
                    "use_rs_percentile",
                    "use_sma50_atr_filter",
                    "use_earnings_calendar",
                    "require_spy_above_sma50",
                    "require_positive_rs",
                ]
            },
        )

        advanced.load_data()
        adv_result = advanced.run_backtest()

        print(f"\n🚀 Advanced Entry Signals:")
        print(f"   Total trades: {adv_result.get('total_trades', 0)}")

        if "trades" in adv_result and len(adv_result["trades"]) > 0:
            trades_df = pd.DataFrame(adv_result["trades"])
            print(f"\n   First 5 entries:")
            # Mostrar columnas disponibles primero
            print(f"   Available columns: {list(trades_df.columns)}")
            # Mostrar columnas que existen
            display_cols = [
                c
                for c in ["symbol", "ticker", "entry_date", "entry_price", "exit_type"]
                if c in trades_df.columns
            ]
            if display_cols:
                print(f"   {trades_df[display_cols].head()}")

    except Exception as e:
        print(f"❌ Error en Advanced: {e}")


def main():
    print("\n" + "=" * 80)
    print("🐛 ENGINE COMPARISON DEBUG TOOL")
    print("=" * 80)
    print("\nEste script ayuda a identificar problemas de sincronía entre motores")
    print("para entender por qué los resultados difieren significativamente.")

    debug_engine_initialization()
    debug_entry_signals()

    print("\n" + "=" * 80)
    print("✅ DEBUG COMPLETE")
    print("=" * 80)
    print("\n💡 Próximos pasos:")
    print("   1. Revisar si ambos motores tienen los mismos datos")
    print("   2. Verificar que los indicadores sean consistentes")
    print("   3. Comparar el número de señales generadas")
    print("   4. Si THOR tiene 0 trades, relajar los filtros")


if __name__ == "__main__":
    main()
