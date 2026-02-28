#!/usr/bin/env python3
"""
EJEMPLO RÁPIDO - Ejecuta backtest rápido con parámetros específicos
================================================================
Este script muestra cómo usar el motor de producción con parámetros
que coinciden con los de la UI de Streamlit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def example_backtest():
    """Ejemplo de backtest con parámetros Streamlit UI"""
    print("=" * 80)
    print("⚡ EJEMPLO RÁPIDO - Motor de Producción (Streamlit UI Params)")
    print("=" * 80)

    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    # Parámetros que usa la UI de Streamlit
    print("\n📋 Configuración:")
    print("   Universo: 10 tickers tech")
    print("   Período: 2020-01-01 to 2024-12-31")
    print("   Capital: $100,000")
    print("   Risk: 0.5%")

    # UNIVERSE (10 tickers tech)
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

    # FECHAS
    start_date = "2020-01-01"
    end_date = "2024-12-31"

    # FILTROS STREAMLIT UI (PROFESSIONAL)
    params = {
        "initial_capital": 100000,
        "risk_pct": 0.005,  # 0.5%
        # Filtración de liquidez (PROFESSIONAL)
        "min_volume": 300000,  # 300k shares min
        "min_dollar_volume": 5000000,  # $5M min
        "min_adr": 2.0,  # 2% min
        "min_rvol": 1.0,  # 1x min
        # Filtros técnicos
        "max_dist_sma20": 7.0,  # 7% max extension
        "max_stop_pct": 3.0,  # 3% stop max
        "min_consolidation_days": 10,
        # Targets (VALIDATED)
        "tp1_r": 1.25,  # 1.25R
        "tp2_r": 3.0,  # 3.0R
        "tp1_pct": 0.33,  # 33%
        "tp2_pct": 0.33,  # 33%
        "runner_pct": 0.34,  # 34%
        # Filtros market regime (PROFESSIONAL)
        "require_spy_above_sma50": True,
        "use_market_regime_filter": False,
        "max_vix_threshold": 35.0,
        # Filtración VIX
        "use_dynamic_thresholds": False,
        # Sector rotation (PROFESSIONAL)
        "use_composite_sector_scoring": False,
        # Outbound features
        "use_rs_percentile": False,
        "use_sma50_atr_filter": False,
        "use_adaptive_filtering": False,
        "use_trailing_stop": False,
        # Filtro signal
        "signal_type": "any",  # Close > SMA20
        "mode": "production",
    }

    # Crear engine
    print("\n🚀 Iniciando motor...")
    engine = AdvancedVectorBTEngine(
        universe=universe, start_date=start_date, end_date=end_date, **params
    )

    # Cargar datos
    print("📥 Cargando datos...")
    engine.load_data()

    # Ejecutar backtest
    print("🔄 Ejecutando backtest...")
    results = engine.run_backtest()

    # Mostrar resultados
    print("\n" + "=" * 80)
    print("📊 RESULTADOS")
    print("=" * 80)

    metrics = [
        ("Total Return %", "total_return"),
        ("Annualized Return %", "annualized_return"),
        ("Sharpe Ratio", "sharpe_ratio"),
        ("Total Trades", "total_trades"),
        ("Win Rate %", "win_rate"),
        ("Max Drawdown %", "max_drawdown"),
        ("Avg Return %", "avg_return"),
    ]

    print(f"\n{'Métrica':<20} | {'Valor':<15}")
    print("-" * 80)

    for metric_name, metric_key in metrics:
        value = results.get(metric_key, 0)
        if metric_name in ["Total Trades", "Avg Return"]:
            print(f"{metric_name:<20} | {value:<15}")
        else:
            print(f"{metric_name:<20} | {value * 100:<15.2f}")

    # Verificar si hay trades
    if "trades" in results and len(results["trades"]) > 0:
        trades_df = results["trades"]

        print(f"\n📈 TRADES")
        print("-" * 80)
        print(f"Total Trades: {len(trades_df)}")
        print(f"Columns: {list(trades_df.columns)}")
        if "ticker" in trades_df.columns:
            print(f"Unique Tickers: {trades_df['ticker'].nunique()}")
        if "entry_date" in trades_df.columns:
            print(
                f"Date Range: {trades_df['entry_date'].min()} to {trades_df['entry_date'].max()}"
            )

        print(f"\nExit Phases:")
        if "exit_phase" in trades_df.columns:
            phase_counts = trades_df["exit_phase"].value_counts()
            for phase, count in phase_counts.items():
                print(f"  {phase}: {count} ({count / len(trades_df) * 100:.1f}%)")

        print(f"\nAvg Return:")
        if "return_pct" in trades_df.columns:
            print(f"  Mean: {trades_df['return_pct'].mean():.3f}%")
            print(f"  Std: {trades_df['return_pct'].std():.3f}%")

        print(f"\nBiggest Winners:")
        if "return_pct" in trades_df.columns:
            sorted_trades = trades_df.nlargest(5, "return_pct")
            for idx, row in sorted_trades.iterrows():
                symbol = row.get("symbol", "Unknown")
                entry_date = row.get("entry_date", "Unknown")
                ret = row.get("return_pct", 0)
                pnl = row.get("pnl", 0)
                print(f"  {symbol} ({entry_date}): {ret:.2f}% (${pnl:.2f})")

        print(f"\nBiggest Losers:")
        if "return_pct" in trades_df.columns:
            sorted_trades = trades_df.nsmallest(5, "return_pct")
            for idx, row in sorted_trades.iterrows():
                symbol = row.get("symbol", "Unknown")
                entry_date = row.get("entry_date", "Unknown")
                ret = row.get("return_pct", 0)
                pnl = row.get("pnl", 0)
                print(f"  {symbol} ({entry_date}): {ret:.2f}% (${pnl:.2f})")

        # Guardar a CSV
        output_file = "example_backtest_results.csv"
        trades_df.to_csv(output_file, index=False)
        print(f"\n✅ Trades guardados en {output_file}")

    else:
        print("\n⚠️  No se encontraron trades")
        print("   Esto podría significar:")
        print("   1. Los filtros son demasiado estrictos")
        print("   2. El período no tiene suficientes datos")
        print("   3. Los parámetros no están bien configurados")


def example_convergence_mode():
    """Ejemplo de backtest en modo convergence (igual que THOR)"""
    print("\n" + "=" * 80)
    print("🔄 EJEMPLO MODO CONVERGENCE (igual que THOR)")
    print("=" * 80)

    from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

    universe = ["AAPL", "MSFT", "NVDA", "TSLA", "AMD"]
    start_date = "2020-01-01"
    end_date = "2024-12-31"

    # PARÁMETROS CONVERGENCE (igual que THOR)
    params = {
        "initial_capital": 100000,
        "mode": "convergence",  # Fixed dollar risk
        "risk_dollars": 150.0,  # $150 fixed risk
        "max_dist_sma20": 7.0,
        "min_rvol": 1.0,
        "min_adr": 2.0,
        "min_dollar_volume": 5000000,
        "max_stop_pct": 3.0,
        "tp1_r": 1.25,
        "tp2_r": 3.0,
        "tp1_pct": 0.33,
        "tp2_pct": 0.33,
        "runner_pct": 0.34,
        "signal_type": "any",
        "use_dynamic_thresholds": False,
    }

    print(f"\n📋 Parámetros Convergence:")
    print(f"   Mode: convergence (fixed $150 risk)")
    print(f"   TP1: 1.25R (33%)")
    print(f"   TP2: 3.0R (33%)")
    print(f"   Runner: 34%")

    engine = AdvancedVectorBTEngine(
        universe=universe, start_date=start_date, end_date=end_date, **params
    )

    print("🔄 Ejecutando...")
    engine.load_data()
    results = engine.run_backtest()

    print(f"\n📊 Return: {results['total_return'] * 100:.2f}%")


if __name__ == "__main__":
    # Ejemplo 1: Streamlit UI params
    example_backtest()

    # Ejemplo 2: Convergence mode (THOR compatible)
    # Uncomment to test:
    # example_convergence_mode()
