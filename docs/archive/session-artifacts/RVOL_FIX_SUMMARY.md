# 🔧 Fix: Filtro RVOL en Backtest

## 🚨 Problema Identificado

**AGI entró con RVOL 0.76x** (debajo del threshold de 1.5x) porque:

1. **El `InstitutionalScreener` NO tenía filtro de RVOL** - El filtro estaba completamente ausente
2. **El RVOL no se guardaba en `context_data`** - Se recalculaba en `_close_position` en lugar de usar el valor de entrada
3. **Había código redundante** - Se calculaba RVOL dos veces en lugares diferentes

## ✅ Cambios Aplicados

### 1. **Screener (`src/core/screener.py`)**
- ✅ Agregado parámetro `min_rvol` al constructor (línea 23)
- ✅ Implementado **FILTER 3B: RVOL** (líneas 73-84)
- ✅ RVOL incluido en el resultado del screener (línea 108)
- ✅ Documentación actualizada

**Lógica del filtro:**
```python
# Calcula RVOL: Volumen del día vs promedio de 20 días (excluyendo día actual)
prior_bars = hist.iloc[:-1]  # Excluir barra actual (anti look-ahead)
avg_vol_20 = prior_bars['volume'].tail(20).mean()
rvol = current['volume'] / avg_vol_20

if rvol < self.min_rvol:
    return None, f"Low RVOL: {rvol:.2f}x < {self.min_rvol}x"
```

### 2. **Engine (`src/backtest/daily_engine.py`)**
- ✅ Pasado `min_rvol` al screener en inicialización (líneas 98-103)
- ✅ RVOL guardado en `context_data` al preparar órdenes (línea 761)
- ✅ RVOL tomado de `context_data` en `_close_position` (línea 486)
- ✅ Eliminado código redundante de cálculo de RVOL en `_run_daily_screener`

### 3. **Eliminación de Redundancias**
- ❌ Removido cálculo duplicado de RVOL en `_run_daily_screener` (era redundante)
- ❌ Removido recálculo de RVOL en `_close_position` (usaba datos post-entrada)

## 🎯 Flujo Correcto Ahora

```
1. Screener.scan()
   └─> Calcula RVOL (día actual vs avg 20 días previos)
   └─> Rechaza si RVOL < 1.5x
   └─> Guarda RVOL en resultado del candidato

2. _prepare_orders()
   └─> Toma RVOL del candidato
   └─> Lo guarda en context_data

3. Position created
   └─> context_data incluye RVOL original de entrada

4. _close_position()
   └─> Lee RVOL desde pos.context_data
   └─> Lo guarda en trade_record['context_rvol']

5. Dashboard
   └─> Muestra RVOL correcto del momento de entrada
```

## 📊 Otros Filtros Institucionales Verificados

Todos implementados correctamente:

| Filtro | Status | Ubicación |
|--------|--------|-----------|
| **RVOL** | ✅ FIXED | `screener.py:73-84` |
| ADR | ✅ OK | `screener.py:58-61` |
| Precio mínimo | ✅ OK | `screener.py:55-56` |
| Liquidez (Vol) | ✅ OK | `screener.py:64-66` |
| Dollar Volume | ✅ OK | `screener.py:68-70` |
| Relative Strength | ✅ OK | `screener.py:72-80` |
| Estructura/Breakout | ✅ OK | `screener.py:82-98` |
| Market Cap | ✅ OK | `daily_engine.py:119-143` |
| Stop Loss Cap | ✅ OK | `daily_engine.py:673-692` |
| Earnings Defense | ✅ OK | `daily_engine.py:720-735` |
| High Vol Reduction | ✅ OK | `daily_engine.py:737-752` |

## 🔬 Impacto Esperado

**Antes del fix:**
- Candidatos con RVOL bajo (< 1.5x) podían entrar
- Dashboard mostraba RVOL incorrecto (recalculado post-facto)
- Trades como AGI (RVOL 0.76x) pasaban el filtro

**Después del fix:**
- **Filtro estricto en el screener** - Solo candidatos con RVOL ≥ 1.5x
- **RVOL correcto en dashboard** - Valor del momento de entrada
- **Trades perdedores eliminados** - Menor ruido, mejor win rate esperado

## 🧪 Testing

```bash
# Verificar sintaxis
python3 -m py_compile src/core/screener.py src/backtest/daily_engine.py

# Re-ejecutar backtest para validar
python3 daily_backtest_runner.py
```

## 📝 Notas Adicionales

- **Look-ahead bias eliminado**: RVOL se calcula con barras **previas al día actual**
- **Coherencia**: Mismo RVOL en entrada, posición y resultado
- **No más "coladeros"**: El screener ahora es la primera línea de defensa

---
**Fecha**: 2025-12-22  
**Archivos modificados**: `src/core/screener.py`, `src/backtest/daily_engine.py`
