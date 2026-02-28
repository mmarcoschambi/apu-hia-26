"""
Config Permisiva para Igualar Exposición SPY

Objetivo: Max 95% exposición, menos filtros, más trades
"""

CONFIG = {
    "tier1_strategy": {
        "tp1_r": 1.5,
        "tp2_r": 3.5,
        "tp1_pct": 0.5,
        "tp2_pct": 0.4,
        "runner_pct": 0.1,
        "max_stop_pct": 8.0,
        "risk_dollars": 2000,  # Aumentado de 1000 a 2000 para más exposición
    },
    "tier2_filters": {
        "min_rvol": 0.8,  # Bajar de 1.25 a 0.8
        "min_adr": 1.5,   # Bajar de 2.47 a 1.5
        "max_dist_sma20": 20.0,  # Subir de 13.7 a 20
        "min_dollar_volume": 10000000,  # Bajar de 20M a 10M
        "min_volume": 50000,  # Bajar de 100k a 50k
        "min_consolidation_days": 3,  # Bajar de 10 a 3
    },
    "tier3_risk": {
        "rvol_danger": 4.0,  # Subir umbral (menos reducción)
        "rvol_warning": 3.0,
        "rvol_danger_size": 0.75,  # Reducir menos (75% vs 50%)
        "rvol_warning_size": 0.90,  # Reducir menos (90% vs 75%)
        "max_exposure_pct": 0.95,  # Aumentado a 95%
        "max_position_pct": 0.35,  # Aumentado a 35%
        "compounding_enabled": False,
    }
}

print("⚠️  CONFIGURACIÓN AGRESIVA - IGUALAR EXPOSICIÓN SPY")
print()
print("Cambios clave:")
print("  • Max Exposure: 65% → 95%")
print("  • Risk per trade: $1000 → $2000")
print("  • Filtros más permisivos")
print("  • Menos reducción por RVOL/ADR")
print()
print("Esto aumentará:")
print("  ✅ Número de trades (más exposición)")
print("  ✅ Capital invertido simultáneamente")
print("  ✅ Riesgo total (similar a SPY)")
print("  ✅ Potencial de retorno")
print()
print("Pero también:")
print("  ⚠️ Mayor drawdown potencial")
print("  ⚠️ Más volatilidad")
print("  ⚠️ Necesita monitoreo")
