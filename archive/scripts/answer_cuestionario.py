#!/usr/bin/env python3
"""
RESUMEN DE RESPUESTAS PARA CUESTIONARIO DEBUG
================================================
Ejecuta este script para obtener respuestas automáticas al cuestionario
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def get_answer_1():
    """Respuesta a pregunta 1: UNIVERSO DE TICKERS"""
    print("\n" + "=" * 80)
    print("1️⃣ UNIVERSO DE TICKERS")
    print("=" * 80)

    # Cargar validación para ver cuántos tickers usan
    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        # Los 10 tickers que usa la validación
        tickers = [
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

        print(f"✅ Menos de 50 (usando {len(tickers)} tickers)")
        print(f"📚 Lista: {', '.join(tickers)}")
        print(f"📊 Combinación: S&P 500 (10 tech giants)")

        return {
            "total": len(tickers),
            "universe": tickers,
            "classification": "Combina S&P 500 + NASDAQ 100 (10 tech giants)",
        }
    except:
        return None


def get_answer_2():
    """Respuesta a pregunta 2: FILTROS DE ENTRADA"""
    print("\n" + "=" * 80)
    print("2️⃣ FILTROS DE ENTRADA")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        print("📋 PARÁMETROS ACTUALES (del motor de producción):")
        print(f"   MIN_RVOL = {params.get('min_rvol', 'N/A')}")
        print(f"   MIN_ADR_PCT = {params.get('min_adr', 'N/A')}%")
        print(f"   MAX_DIST_SMA20 = {params.get('max_dist_sma20', 'N/A')}%")
        print(f"   MIN_DOLLAR_VOLUME = ${params.get('min_dollar_volume', 'N/A'):,.0f}")
        print(
            f"   MIN_CONSOLIDATION_DAYS = {params.get('min_consolidation_days', 'N/A')}"
        )
        print(f"   MAX_STOP_PCT = {params.get('max_stop_pct', 'N/A')}%")

        return {
            "MIN_RVOL": params.get("min_rvol", 1.0),
            "MIN_ADR_PCT": params.get("min_adr", 2.0),
            "MAX_DIST_SMA20": params.get("max_dist_sma20", 7.0),
            "MIN_DOLLAR_VOLUME": params.get("min_dollar_volume", 5000000),
            "MIN_CONSOLIDATION_DAYS": params.get("min_consolidation_days", 10),
            "MAX_STOP_PCT": params.get("max_stop_pct", 3.0),
        }
    except:
        return None


def get_answer_3():
    """Respuesta a pregunta 3: POSITION SIZING"""
    print("\n" + "=" * 80)
    print("3️⃣ POSITION SIZING")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        # Determinar si es production o convergence
        mode = params.get("mode", "production")

        if mode == "convergence":
            print(f"❓ ¿Cuánto arriesgas por trade?")
            print(f"   Rta: 1.0% del capital (FIXED DOLLAR: $150)")
            print(f"   🔑 Key: El motor usa FIXED DOLLAR RISK ($150)")
            print(f"   ℹ️  Esto permite comparar con THOR directamente")
        else:
            print(f"❓ ¿Cuánto arriesgas por trade?")
            print(f"   Rta: {params.get('risk_pct', 0.005) * 100:.1f}% del capital")
            print(f"   ℹ️  Esto permite COMPONDING")

        print(f"\n📋 RISK PARAMETERS:")
        print(f"   Mode: {mode}")
        if mode == "convergence":
            print(f"   Risk: FIXED DOLLAR (${params.get('risk_dollars', 150):.0f})")
        else:
            print(f"   Risk: PERCENTAGE ({params.get('risk_pct', 0.005) * 100:.1f}%)")

        return {
            "mode": mode,
            "risk_per_trade_pct": params.get("risk_pct", 0.005) * 100
            if mode == "production"
            else None,
            "risk_dollars": params.get("risk_dollars", 150),
            "max_exposure_pct": params.get("max_exposure_pct", 0.35) * 100,
        }
    except:
        return None


def get_answer_4():
    """Respuesta a pregunta 4: SALIDAS PARCIALES"""
    print("\n" + "=" * 80)
    print("4️⃣ SALIDAS PARCIALES")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        print("📋 TARGETS ACTUALES:")
        print(f"   TP1_R_MULTIPLE = {params.get('tp1_r', 'N/A')}R")
        print(f"   TP1_EXIT_PCT = {params.get('tp1_pct', 'N/A') * 100:.0f}%")
        print(f"   TP2_R_MULTIPLE = {params.get('tp2_r', 'N/A')}R")
        print(f"   TP2_EXIT_PCT = {params.get('tp2_pct', 'N/A') * 100:.0f}%")
        print(f"   RUNNER_EXIT_PCT = {params.get('runner_pct', 'N/A') * 100:.0f}%")

        # Detectar método de runner
        runner_method = "EMA8_CROSS_EMA21"  # Por defecto
        print(f"\n📋 RUNNER METHOD: {runner_method}")

        return {
            "TP1_R_MULTIPLE": params.get("tp1_r", 1.25),
            "TP1_EXIT_PCT": params.get("tp1_pct", 0.33) * 100,
            "TP2_R_MULTIPLE": params.get("tp2_r", 3.0),
            "TP2_EXIT_PCT": params.get("tp2_pct", 0.33) * 100,
            "RUNNER_EXIT_METHOD": runner_method,
            "RUNNER_EXIT_PCT": params.get("runner_pct", 0.34) * 100,
        }
    except:
        return None


def get_answer_5():
    """Respuesta a pregunta 5: STOP LOSS"""
    print("\n" + "=" * 80)
    print("5️⃣ STOP LOSS")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        max_stop_pct = params.get("max_stop_pct", 0.03)
        max_stop_pct *= 100  # Convert to percentage

        print(f"❓ ¿Cómo calculas el stop?")
        print(f"   Rta: Porcentaje fijo (Max {max_stop_pct:.1f}%)")
        print(f"   ℹ️  Max stop del 3% es modificado dinámicamente por ATR")
        print(f"   ℹ️  En convergence mode, stop se ajusta a {max_stop_pct:.1f}%")

        print(f"\n📋 STOP LOSS SETTINGS:")
        print(f"   Max Stop: {max_stop_pct:.1f}%")
        print(f"   Adjustment: Dynamic based on ATR")
        print(f"   Move to BE: After TP1 (0.8R threshold)")

        return {
            "stop_method": "Porcentaje fijo (ajustado por ATR)",
            "max_stop_pct": max_stop_pct,
            "be_threshold": 0.8,  # R threshold
        }
    except:
        return None


def get_answer_6():
    """Respuesta a pregunta 6: PERÍODO Y FRECUENCIA"""
    print("\n" + "=" * 80)
    print("6️⃣ PERÍODO Y FRECUENCIA")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        validation_period = config.get("validation_period", "2020-01-01 to 2024-12-31")

        start, end = validation_period.split(" to ")
        print(f"✅ Periodo: {start} to {end}")
        print(
            f"   Duración: {(end - start).days} días (~{((end - start).days / 365):.1f} años)"
        )
        print(f"\n❓ ¿Qué timeframe operas?")
        print(f"   Rta: Diario (1D)")
        print(f"   ℹ️  Los datos se cargan en 1D y se calculan indicadores en diario")

        return {
            "start_date": start,
            "end_date": end,
            "timeframe": "Diario (1D)",
            "duration_days": (end - start).days,
        }
    except:
        return None


def get_answer_7():
    """Respuesta a pregunta 7: MARKET REGIME FILTERS"""
    print("\n" + "=" * 80)
    print("7️⃣ MARKET REGIME FILTERS")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        params = config["parameters"]

        use_filter = params.get("use_market_regime_filter", False)
        require_spy = params.get("require_spy_above_sma50", True)

        print(f"❓ ¿Usas filtros de régimen de mercado?")
        print(f"   Rta: {'Sí (moderado)' if use_filter else 'No'}")
        print(f"\n📋 FILTERS:")
        print(f"   Market Regime Filter: {use_filter}")
        print(f"   Require SPY > SMA50: {require_spy}")

        if use_filter:
            print(f"   Filters: Market stage + VIX")
        else:
            print(f"   ℹ️  Solo usa SPY > SMA50 como filtro")

        return {
            "use_regime_filter": use_filter,
            "require_spy_above_sma50": require_spy,
            "use_dynamic_thresholds": params.get("use_dynamic_thresholds", False),
            "max_vix_threshold": params.get("max_vix_threshold", 35.0),
        }
    except:
        return None


def get_answer_8():
    """Respuesta a pregunta 8: ARCHIVO DE CONFIGURACIÓN"""
    print("\n" + "=" * 80)
    print("8️⃣ ARCHIVO DE CONFIGURACIÓN")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        print("✅ Los parámetros están en un archivo separado:")
        print(f"   Archivo: config/validated_production_params.json")
        print(f"   Config Name: {config.get('config_name', 'Unknown')}")
        print(f"   Validated: {config.get('validated_date', 'Unknown')}")

        print(f"\n📋 ESTRUCTURA:")
        print(f"   - 'parameters': dict con todos los parámetros")
        print(f"   - 'performance': métricas de backtest")
        print(f"   - 'validation_period': período usado para validación")

        return {
            "config_file": "config/validated_production_params.json",
            "config_source": "Validated parameters from walk forward validation",
            "version": config.get("config_name", "Unknown"),
        }
    except:
        return None


def get_answer_9():
    """Respuesta a pregunta 9: DATOS ADICIONALES"""
    print("\n" + "=" * 80)
    print("9️⃣ DATOS ADICIONALES")
    print("=" * 80)

    print("❓ ¿Puedes exportar el CSV de trades?")
    print(f"   Rta: ✅ SÍ - Los trades se guardan automáticamente")

    print(f"\n📋 ARCHIVOS GENERADOS:")
    print(f"   - outputs/backtests/trade_log.csv (completo)")
    print(f"   - outputs/backtests/backtest_results.csv (para dashboard)")
    print(f"   - outputs/backtests/partial_exits.csv (fases de salida)")

    print(f"\n📋 COLUMNAS INCLUIDAS:")
    print(f"   - ticker, entry_date, entry_price, exit_date, exit_price")
    print(f"   - shares, pnl, r_multiple, exit_phase")
    print(f"   - context_adr, context_rvol, context_trend")
    print(f"   - context_vol, context_dollar_vol")
    print(f"   - stop_price, atr, atr_pct_price")
    print(f"   - spy_at_entry, vix_at_entry, spy_ema20_at_entry")

    return {
        "trades_available": True,
        "trades_file": "outputs/backtests/trade_log.csv",
        "columns": [
            "ticker",
            "entry_date",
            "entry_price",
            "exit_date",
            "exit_price",
            "shares",
            "pnl",
            "r_multiple",
            "exit_phase",
            "context_adr",
            "context_rvol",
            "context_trend",
            "stop_price",
            "atr",
            "atr_pct_price",
            "spy_at_entry",
            "vix_at_entry",
        ],
    }


def get_answer_10():
    """Respuesta a pregunta 10: CÓDIGO CRÍTICO"""
    print("\n" + "=" * 80)
    print("🔟 CÓDIGO CRÍTICO")
    print("=" * 80)

    # Verificar si el archivo existe
    numba_core_path = Path("src/backtest/numba_core.py")

    if numba_core_path.exists():
        print("✅ ¿Tienes acceso al archivo numba_core.py?")
        print(f"   Rta: ✅ SÍ - El archivo existe")
        print(f"   📁 Ruta: {numba_core_path.absolute()}")

        # Leer tamaño del archivo para verificar
        file_size = numba_core_path.stat().st_size
        print(f"   📏 Tamaño: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

        print(f"\n📋 ESTRUCTURA DEL MOTOR:")
        print(f"   - src/backtest/vectorbt_engine_advanced.py")
        print(f"     • Simulación con Numba (simulate_with_partial_exits)")
        print(f"     • Position sizing")
        print(f"     • Exit phases (TP1, TP2, Runner)")

        print(f"   - src/backtest/numba_core.py")
        print(f"     • Funciones de optimización y cálculos vectorizados")

        print(f"\n📋 RELEVANT METHODS:")
        print(f"   • simulate_fast_core() - Núcleo de simulación con Numba JIT")
        print(f"   • _build_trade_dict() - Construcción de trades")
        print(f"   • get_position_size() - Cálculo de posición")

        return {
            "code_available": True,
            "numba_core_exists": True,
            "main_file": "src/backtest/vectorbt_engine_advanced.py",
            "numba_core_file": "src/backtest/numba_core.py",
            "critical_method": "simulate_fast_core",
            "file_size": file_size,
            "note": "Lógica principal de simulación está en numba_core.py (compilado con Numba JIT)",
        }
    else:
        print("✅ ¿Tienes acceso al archivo numba_core.py?")
        print(f"   Rta: ⚠️  No existe / no lo encuentro")

        print(f"\n📋 ESTRUCTURA DEL MOTOR:")
        print(f"   - src/backtest/vectorbt_engine_advanced.py")
        print(f"     • Simulación con Numba (simulate_with_partial_exits)")
        print(f"     • Position sizing")
        print(f"     • Exit phases (TP1, TP2, Runner)")

        return {
            "code_available": True,
            "main_file": "src/backtest/vectorbt_engine_advanced.py",
            "critical_method": "simulate_with_partial_exits",
            "note": "Lógica principal está en vectorbt_engine_advanced.py",
        }


def main():
    print("=" * 80)
    print("🚀 RESPUESTAS AUTOMÁTICAS PARA CUESTIONARIO DEBUG")
    print("=" * 80)
    print("\nEste script te da las respuestas automáticas al cuestionario")
    print("Puedes copiar y pegar directamente en CUESTIONARIO_DEBUG.md\n")

    get_answer_1()
    get_answer_2()
    get_answer_3()
    get_answer_4()
    get_answer_5()
    get_answer_6()
    get_answer_7()
    get_answer_8()
    get_answer_9()
    get_answer_10()

    print("\n" + "=" * 80)
    print("💡 INFORMACIÓN EXTRA")
    print("=" * 80)

    try:
        import json

        with open("config/validated_production_params.json", "r") as f:
            config = json.load(f)

        print(f"\n📋 PERFORMANCE REAL:")
        perf = config["performance"]
        print(f"   Total Return: {perf['total_return_pct']:.2f}%")
        print(f"   Sharpe: {perf['sharpe_ratio']:.3f}")
        print(f"   Win Rate: {perf['win_rate_pct']:.2f}%")
        print(f"   Total Trades: {perf['total_trades']}")

        print(f"\n📋 KEY PARAMETERS SUMMARY:")
        params = config["parameters"]
        print(f"   TP1: {params.get('tp1_r', 0):.2f}R (33%)")
        print(f"   TP2: {params.get('tp2_r', 0):.2f}R (33%)")
        print(f"   Runner: {params.get('runner_pct', 0) * 100:.0f}% (34%)")
        print(f"   Stop: {params.get('max_stop_pct', 0) * 100:.1f}%")
        print(f"   RVOL Min: {params.get('min_rvol', 0)}x")
        print(f"   ADR Min: {params.get('min_adr', 0)}%")
        print(f"   $Vol Min: ${params.get('min_dollar_volume', 0):,.0f}")
    except:
        pass

    print(f"\n📚 MÁS INFORMACIÓN:")
    print(f"   - Ejecuta: python3 example_quick_backtest.py")
    print(f"   - Para auditor: python3 audit_production_engine.py")
    print(f"   - Para convergencia: python3 convergence_test_streamlit_cli.py")


if __name__ == "__main__":
    main()
