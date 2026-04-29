#!/usr/bin/env python3
"""
DIAGNÓSTICO - Probar parámetros manualmente
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.backtest.optimization_engine_v6_pro import OptimizationEngineV6_PRO
from config.tier3_risk_management import get_tier3_config
import json

# Cargar configuraciones
# Usar filtros balanceados en lugar de los derivados (que son muy restrictivos)
tier2_config = json.load(open("config/tier2_filters_balanced.json"))
tier3_config = get_tier3_config()

# Parámetros óptimos de Tier 1 (del reporte)
tier1_params = {
    "tp1_r": 2.0,
    "tp2_r": 4.0,
    "tp1_pct": 0.3,
    "tp2_pct": 0.5,
    "runner_pct": 0.2,
    "max_stop_pct": 0.06,
    "risk_dollars": 250,
    "use_phases": True,
}

# Combinar todos los parámetros
params = {
    **tier1_params,
    # Tier 2
    "min_rvol": tier2_config["min_rvol"],
    "min_adr": tier2_config["min_adr"],
    "max_dist_sma20": tier2_config["max_dist_sma20"],
    "min_consolidation_days": tier2_config["min_consolidation_days"],
    "min_dollar_volume": tier2_config.get("min_dollar_volume", 3_000_000),
    "min_volume": 200000,
    "require_sector_strength": tier2_config.get("require_sector_strength", True),
    "sector_top_percentile": tier2_config.get("sector_top_percentile", 0.40),
    # Tier 3
    "rvol_danger": tier3_config["rvol_danger"],
    "rvol_warning": tier3_config["rvol_warning"],
    "rvol_danger_size": tier3_config["rvol_danger_size"],
    "rvol_warning_size": tier3_config["rvol_warning_size"],
    "adr_high": tier3_config["adr_high"],
    "adr_med": tier3_config["adr_med"],
    "adr_high_size": tier3_config["adr_high_size"],
    "adr_med_size": tier3_config["adr_med_size"],
    "max_exposure_pct": tier3_config["max_exposure_pct"],
    "earnings_days": tier3_config["earnings_days"],
    "use_earnings_filter": True,
    # Otros
    "signal_type": "vcp",
    "max_consolidation_range": 15.0,
    "require_positive_rs": False,
    "min_rs": 50.0,
    "rs_lookback": "21d",
    "require_bullish_spy": False,
    "max_vix": 40.0,
}

print("=" * 70)
print("DIAGNÓSTICO DE PARÁMETROS")
print("=" * 70)
print("\n📊 Parámetros a probar:")
for k, v in params.items():
    print(f"  {k}: {v}")

print("\n" + "=" * 70)
print("EJECUTANDO BACKTEST DE PRUEBA...")
print("=" * 70)

# Probar con un universo pequeño
engine = OptimizationEngineV6_PRO(
    tickers=["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"],
    start_date="2023-01-01",
    end_date="2023-06-30",
    initial_capital=100000,
    lookback_days=365,
    offline_mode=True,
)

stats = engine.backtest(params)

print("\n" + "=" * 70)
print("RESULTADOS:")
print("=" * 70)
if stats:
    print(f"Total Trades: {stats.get('total_trades', 0)}")
    print(f"Win Rate: {stats.get('win_rate_pct', 0):.2f}%")
    print(f"Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}")
    print(f"Total Return: {stats.get('total_return_pct', 0):.2f}%")
    print(f"Max Drawdown: {stats.get('max_drawdown_pct', 0):.2f}%")
    print(f"Profit Factor: {stats.get('profit_factor', 0):.2f}")
else:
    print("❌ No se obtuvieron estadísticas")

print("\n" + "=" * 70)
print("COMPARACIÓN CON PARÁMETROS DEFAULT:")
print("=" * 70)

# Probar con parámetros mínimos/default
default_params = {
    "signal_type": "any",
    "min_rvol": 1.0,
    "min_adr": 1.0,
    "max_dist_sma20": 10.0,
    "max_stop_pct": 0.07,
    "risk_dollars": 150,
    "use_phases": False,
    "max_exposure_pct": 0.25,
}

stats_default = engine.backtest(default_params)

if stats_default:
    print(f"Total Trades: {stats_default.get('total_trades', 0)}")
    print(f"Win Rate: {stats_default.get('win_rate_pct', 0):.2f}%")
    print(f"Sharpe Ratio: {stats_default.get('sharpe_ratio', 0):.2f}")
    print(f"Total Return: {stats_default.get('total_return_pct', 0):.2f}%")
else:
    print("❌ No se obtuvieron estadísticas con defaults")
