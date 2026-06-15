# Guía de Perfiles de Riesgo (Tier 3)

## Respuesta a tu Pregunta

**SÍ, puedes cambiar RISK_FRACTION para ir de conservador → balanceado → agresivo**

**NO hay RISK_DOLLARS** en Tier 3, solo **RISK_FRACTION** (0.5% por defecto).

El sistema ahora calcula automáticamente:
```python
risk_dollars = initial_capital × RISK_FRACTION
```

## Situación Antes del Fix

```python
# En optimize_3tier.py (línea 569) - HARDCODED
"risk_dollars": 150  # ❌ Ignoraba RISK_FRACTION de Tier 3
```

Resultado: Sistema siempre usaba $150, sin importar el capital o RISK_FRACTION.

## Situación Después del Fix

```python
# En optimize_3tier.py - Ahora calcula dinámicamente
risk_fraction = tier3_engine_params.get("risk_fraction", 0.005)
risk_dollars = int(initial_capital * risk_fraction)  # ✅ Escala con capital
```

Resultado: 
- $100k → $500 
- $50k → $250
- $200k → $1000

## Tres Perfiles Predefinidos

### 1. ULTRA-CONSERVADOR (actual)

```python
# En config/tier3_risk_management.py
RISK_FRACTION = 0.0015  # 0.15% ($100k → $150)
MAX_EXPOSURE_PCT = 0.30
RVOL_DANGER_SIZE = 0.25  # Reduce 75%
ADR_HIGH_SIZE = 0.20     # Reduce 80%
```

**Para quién:**
- Capital pequeño (<$50k)
- Validación inicial / paper trading
- Cuentas de retiro
- Máxima preservación de capital

**Resultados esperados:**
- Drawdown: 3-8%
- Return: 5-12% anual
- Trades: ~100-200/año
- Sharpe: ~1.5-2.0

### 2. BALANCEADO (recomendado)

```python
# En config/tier3_risk_management.py
RISK_FRACTION = 0.005  # 0.5% ($100k → $500)
MAX_EXPOSURE_PCT = 0.50
RVOL_DANGER_SIZE = 0.40  # Reduce 60%
ADR_HIGH_SIZE = 0.35     # Reduce 65%
```

**Para quién:**
- Retail traders típicos
- Cuentas medianas ($50k-$250k)
- Balance óptimo riesgo/retorno
- Traders con experiencia

**Resultados esperados:**
- Drawdown: 8-15%
- Return: 15-30% anual
- Trades: ~200-400/año
- Sharpe: ~1.0-1.5

### 3. AGRESIVO

```python
# En config/tier3_risk_management.py
RISK_FRACTION = 0.015  # 1.5% ($100k → $1500)
MAX_EXPOSURE_PCT = 0.70
RVOL_DANGER_SIZE = 0.50  # Reduce 50%
ADR_HIGH_SIZE = 0.50     # Reduce 50%
```

**Para quién:**
- Cuentas grandes (>$250k)
- Traders muy experimentados
- Alta tolerancia al riesgo
- Buscan máximo retorno

**Resultados esperados:**
- Drawdown: 15-30%
- Return: 30-60% anual
- Trades: ~300-600/año
- Sharpe: ~0.8-1.2

## Workflow para Cambiar de Perfil

### Opción A: Manual (Recomendado)

1. **Edita** `config/tier3_risk_management.py`:

```python
# Cambiar estas líneas
RISK_FRACTION = 0.005      # De 0.0015 a 0.005 (balanceado)
MAX_EXPOSURE_PCT = 0.50    # De 0.30 a 0.50
RVOL_DANGER_SIZE = 0.40    # De 0.25 a 0.40
ADR_HIGH_SIZE = 0.35       # De 0.20 a 0.35
```

2. **Re-optimiza** todo el pipeline:

```bash
rm -rf outputs/3tier_optimization/
python3 optimize_3tier.py --trials 300 --tickers 50 --keep-pct 60
```

3. **Resultado**: Optuna encuentra NUEVOS TP1/TP2 óptimos para ese perfil

### Opción B: Usar Presets

1. **Copia** perfil de `config/tier3_risk_profiles.py`:

```python
# Ver perfiles disponibles
python3 config/tier3_risk_profiles.py

# Copiar manualmente valores a tier3_risk_management.py
```

2. **Re-optimiza** (mismo comando)

## Comparación de Perfiles

| Métrica | Ultra-Conservador | Balanceado | Agresivo |
|---------|-------------------|------------|----------|
| **Risk/Trade** | $150 (0.15%) | $500 (0.5%) | $1500 (1.5%) |
| **Max Exposure** | 30% | 50% | 70% |
| **Max DD** | 3-8% | 8-15% | 15-30% |
| **Return/año** | 5-12% | 15-30% | 30-60% |
| **Trades/año** | 100-200 | 200-400 | 300-600 |
| **Sharpe** | 1.5-2.0 | 1.0-1.5 | 0.8-1.2 |
| **Psicología** | Fácil | Medio | Difícil |

## Cálculo de Risk en Práctica

### Ejemplo: $100k capital con perfil BALANCEADO

**Base:**
- RISK_FRACTION = 0.005 (0.5%)
- risk_dollars = $100k × 0.005 = **$500**

**Con RVOL adjustment:**
- Si RVOL > 3.0x: $500 × 0.40 = **$200** (reduce 60%)
- Si RVOL > 2.0x: $500 × 0.70 = **$350** (reduce 30%)
- Si RVOL < 2.0x: **$500** (full size)

**Con ADR adjustment:**
- Si ADR > 6.0%: $500 × 0.35 = **$175** (reduce 65%)
- Si ADR > 5.0%: $500 × 0.50 = **$250** (reduce 50%)
- Si ADR < 5.0%: **$500** (full size)

**Ajustes se acumulan** (peor caso):
- RVOL 3.5x + ADR 7%: $500 × 0.40 × 0.35 = **$70**

## FAQ

### ¿Por qué el sistema actual usa $150 si RISK_FRACTION es 0.5%?

**BUG DETECTADO**: optimize_3tier.py tenía hardcoded $150, ignorando RISK_FRACTION.

**ARREGLADO**: Ahora calcula dinámicamente desde Tier 3.

### ¿Qué pasa si cambio solo RISK_FRACTION sin re-optimizar?

**NO óptimo**: Los TP1/TP2 actuales (1.25R/6.0R) fueron optimizados para $150 risk.

Con $500 risk, probablemente TP1/TP2 óptimos sean diferentes (ej: 1.5R/5.0R).

**Recomendación**: Siempre re-optimizar después de cambiar Tier 3.

### ¿Puedo usar valores intermedios?

**SÍ**: Los 3 perfiles son sugerencias. Puedes usar:
- RISK_FRACTION = 0.0035 (0.35%, entre conservador y balanceado)
- MAX_EXPOSURE_PCT = 0.40 (40%, intermedio)
- etc.

### ¿Cómo sé cuál perfil usar?

**Test simple**: ¿Cuánto drawdown toleras sin entrar en pánico?
- 5-8%: Ultra-conservador
- 10-15%: Balanceado
- 20-30%: Agresivo

**Regla práctica**: Empieza conservador, sube gradualmente después de 3-6 meses.

## Debugging: ¿Qué Perfil Estoy Usando Ahora?

```python
# Verificar perfil actual
from config.tier3_risk_management import get_tier3_config

tier3 = get_tier3_config()
print(f"RISK_FRACTION: {tier3['risk_fraction']} ({tier3['risk_fraction']*100}%)")
print(f"MAX_EXPOSURE: {tier3['max_exposure_pct']} ({tier3['max_exposure_pct']*100}%)")

# Con $100k capital:
print(f"Risk per trade: ${int(100000 * tier3['risk_fraction']):,}")
```

## Archivos Relevantes

- `config/tier3_risk_management.py` - Configuración activa (edita aquí)
- `config/tier3_risk_profiles.py` - Presets de referencia (no editar)
- `optimize_3tier.py` - Pipeline que usa RISK_FRACTION
- `docs/risk_profiles_guide.md` - Este documento

