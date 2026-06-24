"""
TIER 3: Risk Management Parameters - FIJOS (NO OPTIMIZAR)
===========================================================

Estos parámetros de gestión de riesgo se fijan por principios institucionales
y experiencia de trading. NO se optimizan con Optuna para evitar overfitting.

Fuente: Análisis Winners vs Losers + Literatura de gestión de riesgo
"""

# ============================================================
# RVOL-BASED POSITION SIZING (Reduce exposición en stocks "hot")
# ============================================================
# Cuando RVOL supera estos umbrales, reducimos el tamaño de posición
# para proteger capital en trades de alto volumen relativo

RVOL_DANGER = 3.0  # Umbral de peligro: RVOL > 3.0x
RVOL_WARNING = 2.0  # Umbral de advertencia: RVOL > 2.0x

RVOL_DANGER_SIZE = (
    0.50  # Reducir a 50% del tamaño normal cuando RVOL > danger (was 0.40)
)
RVOL_WARNING_SIZE = (
    0.75  # Reducir a 75% del tamaño normal cuando RVOL > warning (was 0.65)
)

# ============================================================
# ADR-BASED POSITION SIZING (Reduce exposición en alta volatilidad)
# ============================================================
# Stocks con ADR muy alto son más volátiles y requieren menor exposición

ADR_HIGH = 6.0  # ADR > 6% considerado alta volatilidad
ADR_MED = 5.0  # ADR > 5% considerado media-alta volatilidad

ADR_HIGH_SIZE = (
    0.75  # Reducir a 75% cuando ADR > 6% (was 0.35 - Monster Stock strategy)
)
ADR_MED_SIZE = 0.85  # Reducir a 85% cuando ADR > 5% (was 0.40 - allow volatility)

# ============================================================
# EXPOSICIÓN MÁXIMA
# ============================================================
MAX_EXPOSURE_PCT = (
    0.65  # 65% max portfolio exposure (aligned with production_config.json)
)
MAX_POSITION_PCT = 0.25  # Máximo 25% en una sola posición (was 0.20)

# ============================================================
# EARNINGS FILTER
# ============================================================
EARNINGS_DAYS = 5  # No operar 5 días antes de earnings
EARNINGS_CUSHION = 2  # Cushión adicional post-earnings

# ============================================================
# STOP LOSS INSTITUCIONAL
# ============================================================
MAX_STOP_PCT_HARD = 0.08  # Hard cap: Nunca más del 8% de stop
RISK_FRACTION = 0.010  # Riesgo máximo: 1.0% del capital por trade (was 0.5%)

# ============================================================
# COMPOUNDING CONFIGURATION
# ============================================================
# Enable position sizing based on current equity (vs fixed dollar risk)
# When True: risk_dollars = current_equity * RISK_FRACTION (compounding enabled)
# When False: risk_dollars = fixed amount (no compounding)
COMPOUNDING_ENABLED = False  # Changed to False for better recovery in losing streaks


# ============================================================
# VALIDACIÓN
# ============================================================
def validate_tier3_params():
    """Validar que los parámetros Tier 3 sean coherentes."""
    errors = []

    # RVOL thresholds deben ser lógicos
    if RVOL_WARNING >= RVOL_DANGER:
        errors.append(
            f"RVOL_WARNING ({RVOL_WARNING}) debe ser < RVOL_DANGER ({RVOL_DANGER})"
        )

    # Size reductions deben ser menores a 1.0
    if RVOL_DANGER_SIZE >= 1.0 or RVOL_WARNING_SIZE >= 1.0:
        errors.append("RVOL size reductions deben ser < 1.0")

    # ADR thresholds deben ser lógicos
    if ADR_MED >= ADR_HIGH:
        errors.append(f"ADR_MED ({ADR_MED}) debe ser < ADR_HIGH ({ADR_HIGH})")

    # Exposición máxima razonable (institutional: up to 80%)
    if MAX_EXPOSURE_PCT > 0.80:
        errors.append(f"MAX_EXPOSURE_PCT ({MAX_EXPOSURE_PCT}) > 80% es muy agresivo")

    if errors:
        raise ValueError("Tier 3 Validation Errors:\n" + "\n".join(errors))

    return True


def get_tier3_config():
    """Retorna la configuración completa de Tier 3."""
    return {
        "rvol_danger": RVOL_DANGER,
        "rvol_warning": RVOL_WARNING,
        "rvol_danger_size": RVOL_DANGER_SIZE,
        "rvol_warning_size": RVOL_WARNING_SIZE,
        "adr_high": ADR_HIGH,
        "adr_med": ADR_MED,
        "adr_high_size": ADR_HIGH_SIZE,
        "adr_med_size": ADR_MED_SIZE,
        "max_exposure_pct": MAX_EXPOSURE_PCT,
        "max_position_pct": MAX_POSITION_PCT,
        "earnings_days": EARNINGS_DAYS,
        "earnings_cushion": EARNINGS_CUSHION,
        "max_stop_pct_hard": MAX_STOP_PCT_HARD,
        "risk_fraction": RISK_FRACTION,
        "compounding_enabled": COMPOUNDING_ENABLED,
    }


if __name__ == "__main__":
    # Validar al importar
    validate_tier3_params()
    print("✅ Tier 3 Risk Management Parameters Validated")
    print("\n📊 Configuración:")
    for key, value in get_tier3_config().items():
        print(f"   {key}: {value}")
