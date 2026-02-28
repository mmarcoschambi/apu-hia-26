# Sistema de 3 Tiers - Bugatti Trading System

## Resumen

Se ha implementado una arquitectura de 3 tiers para prevenir overfitting y mejorar la robustez del sistema de trading.

## Estructura de Tiers

### TIER 3: Risk Management (FIJO)
**Archivo:** `config/tier3_risk_management.py`

Parámetros fijos por principios institucionales - NO se optimizan:

```python
RVOL_DANGER = 3.0          # Umbral de peligro
RVOL_WARNING = 2.0         # Umbral de advertencia
RVOL_DANGER_SIZE = 0.30    # Reducir a 30% cuando RVOL > danger
RVOL_WARNING_SIZE = 0.65   # Reducir a 65% cuando RVOL > warning

ADR_HIGH = 6.0             # ADR > 6% = alta volatilidad
ADR_MED = 5.0              # ADR > 5% = media volatilidad
MAX_EXPOSURE_PCT = 0.35    # Máximo 35% invertido
```

### TIER 2: Filtros de Calidad (DERIVADO ESTADÍSTICAMENTE)
**Script:** `derive_tier2_filters.py`  
**Output:** `config/tier2_filters_derived.json`

Se analiza Winners vs Losers para encontrar umbrales óptimos:
- `min_rvol`: RVOL mínimo para entrar
- `max_dist_sma20`: Extensión máxima permitida
- `min_consolidation_days`: Calidad VCP

**Uso:**
```bash
python derive_tier2_filters.py --trades-file outputs/backtests/trades_immediate_entry.csv
```

### TIER 1: Parámetros de Estrategia (OPTIMIZAR CON OPTUNA)
**Script:** `bugatti_optuna_tier1.py`

Espacio de búsqueda reducido a solo 4-5 parámetros:

| Parámetro | Valores | Descripción |
|-----------|---------|-------------|
| `tp1_r` | 1.0, 1.25, 1.5, 1.75, 2.0 | R-multiple para TP1 |
| `tp2_r` | 2.5, 3.0, 3.5, 4.0 | R-multiple para TP2 |
| `tp1_pct` | 0.30, 0.40, 0.50 | % en TP1 |
| `tp2_pct` | 0.30, 0.40, 0.50 | % en TP2 |
| `runner_pct` | Derived | % restante (constraint: suma=1) |
| `max_stop_pct` | 4.0, 5.0, 6.0, 7.0 | Stop máximo % |
| `risk_dollars` | 150, 200, 250 | Riesgo $ por trade |

**Uso:**
```bash
python bugatti_optuna_tier1.py --trials 100 --tickers 50
```

## Flujo de Trabajo

1. **Fijar Tier 3:** Ya configurado en `config/tier3_risk_management.py`

2. **Derivar Tier 2:**
   ```bash
   python derive_tier2_filters.py --trades-file <trades.csv>
   ```
   Esto genera `config/tier2_filters_derived.json`

3. **Optimizar Tier 1:**
   ```bash
   python bugatti_optuna_tier1.py --trials 100 --tickers 50
   ```
   Solo optimiza parámetros de estrategia, Tier 2 y Tier 3 permanecen fijos.

## Beneficios

✅ **Reduce overfitting:** De 15+ parámetros a solo 4-5  
✅ **Mayor robustez:** Tier 2 derivado estadísticamente de datos reales  
✅ **Mejor exploración:** Con 100 trials, Optuna explora adecuadamente 4-5 parámetros  
✅ **Separación clara:** Cada tier tiene su propósito definido  

## Comparación: Antes vs Después

### Antes (bugatti_optuna.py)
- 15+ parámetros en espacio de búsqueda
- 50 trials = solo 3.3 trials por parámetro promedio
- Overfitting en filtros

### Después (bugatti_optuna_tier1.py)
- 4-5 parámetros en espacio de búsqueda
- 100 trials = 20-25 trials por parámetro
- Filtros derivados estadísticamente (robustos)
- Risk management fijado (principios institucionales)
