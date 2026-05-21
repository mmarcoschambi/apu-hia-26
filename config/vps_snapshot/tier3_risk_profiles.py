"""
TIER 3: Risk Profiles - Presets para diferentes tolerancias al riesgo
======================================================================

Este archivo define 3 perfiles predefinidos que puedes copiar a
tier3_risk_management.py según tu tolerancia al riesgo.

IMPORTANTE: NO importes este archivo directamente. Copia el perfil
que quieras a tier3_risk_management.py y re-optimiza.

Workflow:
1. Elige perfil (CONSERVADOR, BALANCEADO, o AGRESIVO)
2. Copia valores a config/tier3_risk_management.py
3. Re-corre: python3 optimize_3tier.py --trials 300 --tickers 50 --keep-pct 60
4. Optuna encontrará TP1/TP2 óptimos para ESE perfil
"""

# ══════════════════════════════════════════════════════════════════════════════
# PERFIL 1: ULTRA-CONSERVADOR
# ══════════════════════════════════════════════════════════════════════════════
# Para: Capital pequeño, validación inicial, cuentas de retiro
# Drawdown esperado: 3-8%
# Return esperado: 5-12% anual
# Trades/año: ~100-200

ULTRA_CONSERVADOR = {
    # Risk Management
    "RISK_FRACTION": 0.0015,  # 0.15% del capital ($100k → $150)
    "MAX_EXPOSURE_PCT": 0.30,  # Máximo 30% invertido
    
    # RVOL Adjustments (muy defensivo)
    "RVOL_DANGER": 3.0,
    "RVOL_WARNING": 2.0,
    "RVOL_DANGER_SIZE": 0.25,   # Reduce a 25% en peligro
    "RVOL_WARNING_SIZE": 0.60,  # Reduce a 60% en advertencia
    
    # ADR Adjustments (muy defensivo)
    "ADR_HIGH": 6.0,
    "ADR_MED": 5.0,
    "ADR_HIGH_SIZE": 0.20,   # Reduce a 20%
    "ADR_MED_SIZE": 0.35,    # Reduce a 35%
    
    # Hard Limits
    "MAX_POSITION_PCT": 0.20,      # 20% máximo por posición
    "MAX_STOP_PCT_HARD": 0.06,     # 6% stop máximo
    "EARNINGS_DAYS": 7,            # 7 días antes earnings
    "EARNINGS_CUSHION": 3,
}

# ══════════════════════════════════════════════════════════════════════════════
# PERFIL 2: BALANCEADO (RECOMENDADO)
# ══════════════════════════════════════════════════════════════════════════════
# Para: Retail traders, cuentas medianas, balance riesgo/retorno
# Drawdown esperado: 8-15%
# Return esperado: 15-30% anual
# Trades/año: ~200-400

BALANCEADO = {
    # Risk Management
    "RISK_FRACTION": 0.005,  # 0.5% del capital ($100k → $500)
    "MAX_EXPOSURE_PCT": 0.50,  # Máximo 50% invertido
    
    # RVOL Adjustments (moderado)
    "RVOL_DANGER": 3.0,
    "RVOL_WARNING": 2.0,
    "RVOL_DANGER_SIZE": 0.40,   # Reduce a 40% en peligro
    "RVOL_WARNING_SIZE": 0.70,  # Reduce a 70% en advertencia
    
    # ADR Adjustments (moderado)
    "ADR_HIGH": 6.0,
    "ADR_MED": 5.0,
    "ADR_HIGH_SIZE": 0.35,   # Reduce a 35%
    "ADR_MED_SIZE": 0.50,    # Reduce a 50%
    
    # Hard Limits
    "MAX_POSITION_PCT": 0.25,      # 25% máximo por posición
    "MAX_STOP_PCT_HARD": 0.08,     # 8% stop máximo
    "EARNINGS_DAYS": 5,            # 5 días antes earnings
    "EARNINGS_CUSHION": 2,
}

# ══════════════════════════════════════════════════════════════════════════════
# PERFIL 3: AGRESIVO
# ══════════════════════════════════════════════════════════════════════════════
# Para: Cuentas grandes, traders experimentados, alta tolerancia al riesgo
# Drawdown esperado: 15-30%
# Return esperado: 30-60% anual
# Trades/año: ~300-600

AGRESIVO = {
    # Risk Management
    "RISK_FRACTION": 0.015,  # 1.5% del capital ($100k → $1500)
    "MAX_EXPOSURE_PCT": 0.70,  # Máximo 70% invertido
    
    # RVOL Adjustments (permisivo)
    "RVOL_DANGER": 3.5,        # Umbral más alto
    "RVOL_WARNING": 2.5,       # Umbral más alto
    "RVOL_DANGER_SIZE": 0.50,   # Reduce a 50% en peligro
    "RVOL_WARNING_SIZE": 0.75,  # Reduce a 75% en advertencia
    
    # ADR Adjustments (permisivo)
    "ADR_HIGH": 7.0,         # Umbral más alto
    "ADR_MED": 6.0,          # Umbral más alto
    "ADR_HIGH_SIZE": 0.50,   # Reduce a 50%
    "ADR_MED_SIZE": 0.65,    # Reduce a 65%
    
    # Hard Limits
    "MAX_POSITION_PCT": 0.30,      # 30% máximo por posición
    "MAX_STOP_PCT_HARD": 0.10,     # 10% stop máximo
    "EARNINGS_DAYS": 3,            # 3 días antes earnings
    "EARNINGS_CUSHION": 1,
}

# ══════════════════════════════════════════════════════════════════════════════
# EJEMPLO DE USO
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 70)
    print("TIER 3 RISK PROFILES")
    print("═" * 70)
    
    profiles = {
        "ULTRA-CONSERVADOR": ULTRA_CONSERVADOR,
        "BALANCEADO": BALANCEADO,
        "AGRESIVO": AGRESIVO,
    }
    
    capital = 100_000
    
    for name, profile in profiles.items():
        risk_dollars = int(capital * profile["RISK_FRACTION"])
        print(f"\n{name}:")
        print(f"  Risk Fraction: {profile['RISK_FRACTION'] * 100:.2f}%")
        print(f"  Risk per Trade: ${risk_dollars:,} (con ${capital:,} capital)")
        print(f"  Max Exposure: {profile['MAX_EXPOSURE_PCT'] * 100:.0f}%")
        print(f"  RVOL Danger Size: {profile['RVOL_DANGER_SIZE'] * 100:.0f}%")
        print(f"  ADR High Size: {profile['ADR_HIGH_SIZE'] * 100:.0f}%")
    
    print("\n" + "═" * 70)
    print("CÓMO USAR:")
    print("═" * 70)
    print("1. Elige un perfil")
    print("2. Copia los valores a config/tier3_risk_management.py")
    print("3. Re-optimiza: python3 optimize_3tier.py --trials 300 --tickers 50")
    print("═" * 70)
