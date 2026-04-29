#!/usr/bin/env python3
"""
AUDITOR DE MOTOR DE PRODUCCIÓN
===============================
Muestra todos los parámetros y configuración del motor vectorbt_engine_advanced.py
útil para entender cómo opera el motor antes de ejecutar backtests.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def display_advanced_engine_params():
    """Muestra todos los parámetros disponibles del motor"""
    print("=" * 80)
    print("⚙️  MOTOR DE PRODUCCIÓN: Advanced VectorBT Engine")
    print("=" * 80)

    # Cargar parámetros validados
    config_file = Path("config/validated_production_params.json")
    if config_file.exists():
        with open(config_file, "r") as f:
            validated = json.load(f)

        print(f"\n📋 CONFIGURACIÓN VALIDADA:")
        print(f"   Config: {validated.get('config_name', 'Unknown')}")
        print(f"   Validated: {validated.get('validated_date', 'Unknown')}")
        print(
            f"   Sharpe: {validated.get('performance', {}).get('sharpe_ratio', 0):.3f}"
        )
        print(
            f"   Total Return: {validated.get('performance', {}).get('total_return_pct', 0):.2f}%"
        )
        print(
            f"   Total Trades: {validated.get('performance', {}).get('total_trades', 0)}"
        )
    else:
        print(f"\n⚠️  No hay config validada en config/validated_production_params.json")

    print(f"\n" + "=" * 80)
    print("🎯 PARÁMETROS DEL MOTOR (ALL SETTINGS)")
    print("=" * 80)

    # Definir todas las opciones posibles
    params_def = {
        # === UNIVERSO Y FECHAS ===
        "universe": ["Lista de tickers", "Ej: ['AAPL', 'MSFT', 'NVDA']"],
        "start_date": ["Fecha inicio", "Ej: '2020-01-01'"],
        "end_date": ["Fecha fin", "Ej: '2024-12-31'"],
        "initial_capital": ["Capital inicial", "$100,000"],
        "mode": ["Modo de operación", "production (porcentaje) o convergence (fijo)"],
        # === FILTROS DE LIQUIDEZ ===
        "min_volume": ["Mínimo volumen diario", "300,000 shares"],
        "min_dollar_volume": ["Mínimo volumen en dólares", "$5,000,000"],
        "min_adr": ["Mínimo ADR (%)", "2.0"],
        "min_rvol": ["Mínimo RVOL (rel. volume)", "1.0x"],
        "rvol_danger": ["RVOL nivel peligro", "3.0x"],
        "rvol_warning": ["RVOL nivel advertencia", "2.0x"],
        "rvol_danger_size": ["Tamaño al peligro (%)", "30%"],
        "rvol_warning_size": ["Tamaño a advertencia (%)", "65%"],
        # === FILTROS TÉCNICOS ===
        "max_dist_sma20": ["Distancia máxima de SMA20 (%)", "7.0%"],
        "min_consolidation_days": ["Días mínimos de consolidación", "10"],
        "max_stop_pct": ["Stop loss máximo (%)", "3.0%"],
        # === POSITION SIZING ===
        "risk_pct": ["Riesgo por trade (%)", "0.5%"],
        "risk_dollars": ["Riesgo en dólares fijos", "$150"],
        "max_exposure_pct": ["Exposición máxima (%)", "35%"],
        # === TARGETS Y SALIDAS PARCIALES ===
        "tp1_r": ["TP1 R-Multiple", "1.25R"],
        "tp2_r": ["TP2 R-Multiple", "3.0R"],
        "tp1_pct": ["TP1 exit percentage", "33%"],
        "tp2_pct": ["TP2 exit percentage", "33%"],
        "runner_pct": ["Runner exit percentage", "34%"],
        # === FILTROS AVANZADOS ===
        "use_market_regime_filter": ["Filtro régimen de mercado", "False"],
        "require_spy_above_sma50": ["Requerir SPY > SMA50", "True"],
        "max_vix_threshold": ["Umbral máximo VIX", "35.0"],
        "use_dynamic_thresholds": ["Usar umbrales dinámicos por VIX", "False"],
        "block_trades_in_stage3": ["Bloquear trades en stage 3", "True"],
        "block_trades_in_stage4": ["Bloquear trades en stage 4", "True"],
        # === SECTOR ROTATION ===
        "use_composite_sector_scoring": ["Usar sector scoring", "False"],
        "sector_top_percentile": ["Top % sectores", "40%"],
        "require_positive_rs": ["Requerir RS positivo", "False"],
        # === EMERGING FEATURES ===
        "use_rs_percentile": ["IBD-style RS ranking", "False"],
        "min_rs_percentile": ["Mínimo RS percentile", "80.0"],
        "use_sma50_atr_filter": ["Filtro SMA50/ATR", "False"],
        "max_sma50_atr_extension": ["Extensión máxima SMA50/ATR", "2.0x"],
        "use_adaptive_filtering": ["Adaptive filter engine", "False"],
        # === EARNINGS CALENDAR ===
        "use_earnings_calendar": ["Filtro earnings", "False"],
        "earnings_days": ["Días antes earnings", "5"],
        "earnings_cushion": ["Cushion earnings (%)", "10.0"],
        # === TRAILING STOP ===
        "use_trailing_stop": ["Trailing stop", "False"],
        "be_trailing_threshold": ["BE threshold R", "0.8"],
        # === SIGNAL TYPE ===
        "signal_type": ["Tipo de señal", "'breakout' o 'any'"],
    }

    # Mostrar parámetros
    for param, (desc, default) in params_def.items():
        print(f"\n📌 {param}:")
        print(f"   {desc}")
        print(f"   Default: {default}")

    print(f"\n" + "=" * 80)
    print("🔧 FORMA DE USO (CLI)")
    print("=" * 80)

    print("""
# Ejemplo 1: Backtest simple
python3 -c "
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

engine = AdvancedVectorBTEngine(
    universe=['AAPL', 'MSFT', 'NVDA'],
    start_date='2020-01-01',
    end_date='2024-12-31',
    initial_capital=100000,
    risk_pct=0.5,  # 0.5% risk per trade
    min_rvol=1.0,
    min_adr=2.0,
    min_dollar_volume=5000000,
    max_dist_sma20=7.0,
    max_stop_pct=3.0,
    tp1_r=1.25,
    tp2_r=3.0,
    signal_type='any'
)

result = engine.run_backtest()
print(f'Total Return: {result[\"total_return\"]*100:.2f}%')
print(f'Total Trades: {result[\"total_trades\"]}')
"
""")

    print("=" * 80)
    print("📊 HERRAMIENTAS ÚTILES")
    print("=" * 80)

    print("""
1. reproduce_validated_results.py
   - Reproduce exactamente los resultados de la validación

2. verify_engine_equivalence.py
   - Verifica que la optimización rápida produce los mismos resultados que producción

3. convergence_test_streamlit_cli.py
   - Compara Streamlit UI vs CLI resultados
""")

    # Mostrar ejemplos de parámetros usados en Streamlit
    print("=" * 80)
    print("🎯 PARÁMETROS DEL STREAMLIT UI")
    print("=" * 80)

    streamlit_params = {
        "max_dist_sma20": "7.0",
        "min_rvol": "1.0",
        "min_adr": "2.0",
        "min_volume": "300000",
        "min_dollar_volume": "5000000",
        "rvol_danger": "3.0",
        "rvol_warning": "2.0",
        "rvol_danger_size": "30",
        "rvol_warning_size": "65",
        "adr_high": "6.0",
        "adr_med": "5.0",
        "max_stop_pct": "3.0",
        "min_consolidation_days": "10",
        "earnings_days": "5",
        "earnings_cushion": "10.0",
        "tp1_r": "1.25",
        "tp2_r": "3.0",
        "require_spy_above_sma50": "True",
    }

    for param, value in streamlit_params.items():
        print(f"   {param}: {value}")

    print(f"\n" + "=" * 80)
    print("💡 CONSEJOS PARA AUDITAR")
    print("=" * 80)

    print("""
1. Verifica los parámetros del cuestionario:
   - Ve CUESTIONARIO_DEBUG.md
   - Identifica qué parámetros están afectando tus resultados

2. Usa reproduce_validated_results.py:
   python3 reproduce_validated_results.py
   → Esto te dirá si los resultados actuales coinciden con la validación

3. Prueba parámetros diferentes:
   - Afloja filtros (aumenta min_rvol, reduce max_dist_sma20)
   - Modifica targets (cambia tp1_r, tp2_r)
   - Verifica cómo afecta cada parámetro a los resultados

4. Comparar con THOR:
   - Usa mode='convergence' para igualar lógica con THOR
   - Verifica en debug-convergence.py cómo se comparan
""")


def main():
    display_advanced_engine_params()


if __name__ == "__main__":
    main()
