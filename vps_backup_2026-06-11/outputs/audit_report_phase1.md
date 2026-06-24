# Fase 1: Auditoría del Scanner Live

## Check 1 — Kill-switch de Régimen

**Archivo auditado:** `live_scanner.py`

### Hallazgo:
- ✅ **EXISTS**: `MarketHealthChecker` class (línea ~147) con lógica de SPX/VIX
- ⚠️ **PARTIAL**: Usa `can_trade` boolean pero NO hay `blocked_mask` formal
- ❌ **MISSING**: No hay `market_regime` enum ni `regime_filter` vectorizado

### Código actual:
```python
# live_scanner.py ~ línea 254
if points >= 5:
    status = "🟢 GREEN LIGHT"
    can_trade = True
    max_positions = 4
elif points >= 3:
    status = "🟡 YELLOW LIGHT"
    can_trade = True
    max_positions = 2
else:
    status = "🔴 RED LIGHT"
    can_trade = False
    max_positions = 0
```

### Riesgo: **ALTO** 
El sistema tiene market health check pero NO bloquea entries formalmente con un mask. 
El `can_trade` se usa para logging pero no está claro que se aplique como filtro hard.

**Acción requerida:** Verificar que `can_trade=False` realmente detiene el scanning.

---

## Check 2 — Fees y Slippage

**Archivo auditado:** `live_scanner.py`

### Hallazgo:
- ❌ **MISSING**: NO hay `fee_rate`, `slippage_rate`, ni `commission` en todo el archivo
- ❌ **MISSING**: El cálculo de P&L no deduce costos de transacción
- ⚠️ **IMPLICIT**: `distance_to_pivot` se calcula pero sin ajustar por fees

### Búsqueda grep:
```bash
grep -r "fee_rate|slippage|commission" live_scanner*.py
# Resultado: No matches found
```

### Riesgo: **CRÍTICO**
El P&L del scanner live está **inflado** porque no descuenta:
- Commission fees (~0.1% entry + 0.1% exit = 0.2%)
- Slippage (~0.05-0.15% dependiendo de liquidez)
- Impacto total estimado: **25-35bps por trade**

**Acción requerida:** Agregar `fee_rate` y `slippage_rate` al scanner y aplicarlos en:
1. Cálculo de entry_price efectivo
2. Cálculo de P&L potencial
3. Filtro de setups (descartar si edge < fees + slippage)

---

## Check 3 — Parámetros Hardcodeados

**Archivo auditado:** `live_scanner.py`

### Parámetros identificados:

| Parámetro | Valor | Ubicación | Hardcodeado? |
|-----------|-------|-----------|--------------|
| `lookback_days` | 180 | `scan_universe()` | ✅ Sí |
| `max_setups` | 5 | `generate_focus_list()` | ✅ Sí |
| SPY SMA period | 50 | `check_market_health()` | ✅ Sí |
| VIX threshold | 20/25 | `check_market_health()` | ✅ Sí |
| SPX vol threshold | 15%/20% | `check_market_health()` | ✅ Sí |
| Points para GREEN | >=5 | `check_market_health()` | ✅ Sí |
| Points para YELLOW | >=3 | `check_market_health()` | ✅ Sí |
| Flat base range | <15% | `detect_flat_base()` | ✅ Sí |
| VCP contraction | <70% | `detect_vcp()` | ✅ Sí |

### Combo implícito actual:
El scanner live está operando con un **"combo agresivo"** con estos parámetros:
```python
COMBO_ACTUAL = {
    'name': 'combo_aggressive_live',
    'lookback_days': 180,
    'max_setups': 5,
    'spx_sma_period': 50,
    'vix_max': 25,
    'spx_vol_max': 20,
    'green_light_points': 5,
    'patterns': ['Cup & Handle', 'Flat Base', 'VCP'],
    'fee_rate': 0.0,  # ❌ NO IMPLEMENTADO
    'slippage_rate': 0.0  # ❌ NO IMPLEMENTADO
}
```

---

## Resumen de Hallazgos

| Check | Estado | Riesgo | Prioridad |
|-------|--------|--------|-----------|
| Kill-switch de régimen | ⚠️ Parcial | ALTO | P0 |
| Fees y slippage | ❌ Ausente | CRÍTICO | P0 |
| Parámetros hardcodeados | ⚠️ Identificados | MEDIO | P1 |

## Plan de Acción Inmediato

1. **P0**: Implementar `fee_rate` y `slippage_rate` en scanner
2. **P0**: Agregar `blocked_mask` formal que detenga entries cuando `can_trade=False`
3. **P1**: Extraer parámetros hardcodeados a YAML de configuración
4. **P1**: Crear estructura `configs/combos/` para gestión centralizada

---

**Fecha:** 2026-04-14
**Auditor:** Qwen Code Assistant
**Archivos auditados:** `live_scanner.py`, `live_scanner_avwap.py`, `live_trading_scanner.py`
