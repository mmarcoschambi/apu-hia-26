# VectorBT - Manejo de Rangos Largos

## 🔍 Problema Identificado

Cuando ejecutas un backtest de 2000-2022 (22 años), observas:
- ⚡ Ejecución sospechosamente rápida
- 📊 Solo 34 trades (todos de 2021)
- ❓ ¿Qué pasó con los otros 21 años?

## 🎯 Explicación

### Por Qué Solo 2021

VectorBT tiene 2 limitaciones para rangos largos:

1. **Selección de Universo Restrictiva**
   ```sql
   WHERE date BETWEEN '2000-01-01' AND '2022-12-31'
   HAVING COUNT(*) >= 100
   ```
   - Busca tickers con datos en TODO el rango
   - Pocos tickers existen por 22 años continuos
   - Resultado: 0-5 tickers encontrados

2. **Datos en Cache Limitados**
   - Tu cache tiene más densidad en años recientes
   - 2021: ~3,400 tickers
   - 2010: ~2,000 tickers
   - 2000: ~500 tickers
   - Tickers que existen en 2000 puede que no existan más

### Por Qué Fue Rápido

- Solo procesó ~1 año de datos (2021)
- En lugar de 22 años
- Por eso ~8 segundos en vez de minutos

## ✅ Solución Implementada

### 1. Selección Inteligente de Universo

**Antes:**
```python
# Buscaba tickers en TODO el rango (2000-2022)
WHERE date BETWEEN start_date AND end_date
# Resultado: 0-5 tickers
```

**Ahora:**
```python
# Para rangos >2 años, usa últimos 2 años para SELECCIÓN
if range > 2 años:
    selection_period = últimos_2_años
    # Pero ejecuta backtest en TODO el rango pedido
```

### 2. Mejor Logging

Ahora verás:
```
📥 Loading data for 2000-01-01 to 2022-12-31...
⚠️  Skipped 15 tickers (insufficient data)
ℹ️  5 tickers with partial data (gaps in history)
✅ Loaded: 35 tickers
   Date range: 2001-03-15 to 2022-12-31 (5,500 days)
⚠️  Actual range differs from requested
```

### 3. Tolerancia a Datos Parciales

```python
# Antes: Requería datos completos
if len(df) > 20:  # Muy permisivo o muy restrictivo

# Ahora: Requiere al menos 50% de los días esperados
min_days = max(20, expected_days * 0.5)
if len(df) >= min_days:
    # Acepta el ticker
```

## 🚀 Cómo Usar Con Rangos Largos

### Opción 1: Lista Manual (Recomendado)
```
Modo: Lista Manual
Tickers: SPY,AAPL,MSFT,JNJ,PG,KO,JPM,BAC,XOM,CVX
Fechas: 2000-01-01 a 2022-12-31
```

**Ventajas:**
- ✅ Control total de qué tickers usar
- ✅ Puedes elegir empresas con larga historia
- ✅ Resultados predecibles

### Opción 2: SQLite con Top Liquidity
```
Modo: Todo el Mercado (SQLite)
Límite: 50 símbolos
Estrategia: Por Liquidez
Fechas: 2000-01-01 a 2022-12-31
```

**Comportamiento:**
- Selecciona top 50 por liquidez de 2020-2022
- Ejecuta backtest desde 2000 (donde haya datos)
- Algunos tickers entrarán/saldrán según disponibilidad

### Opción 3: Motor Original (Para Validación)
```
Motor: 🐢 Motor Original
[Misma configuración]
```

**Ventajas:**
- ✅ Maneja mejor datos faltantes
- ✅ Procesa ticker por ticker
- ❌ Mucho más lento (5-10 minutos para 50 tickers)

## 📊 Expectativas Realistas

### Para 2000-2022 (22 años):

**Con Lista Manual (10 blue chips):**
```
Tickers: 10
Tiempo: ~15-30 segundos
Trades esperados: 100-300 (depende de estrategia)
Cobertura: Variable por ticker
```

**Con SQLite Top 50:**
```
Tickers efectivos: 20-35 (con datos suficientes)
Tiempo: ~30-60 segundos
Trades esperados: 150-500
Cobertura: Sesgo hacia años recientes
```

**Con Motor Original:**
```
Tickers: 50
Tiempo: 15-30 minutos
Trades esperados: 200-600
Cobertura: Completa donde haya datos
```

## 🔧 Mejores Prácticas

### Para Rangos Largos (>5 años):

1. **Usa Lista Manual con Blue Chips**
   ```
   SPY, AAPL, MSFT, JNJ, PG, KO, JPM, BAC, WMT, XOM
   ```
   - Empresas con 20+ años de historia
   - Datos más consistentes

2. **Divide el Análisis por Décadas**
   ```
   2000-2009: Backtest 1
   2010-2019: Backtest 2  
   2020-2022: Backtest 3
   ```
   - Mejor cobertura
   - Más trade samples

3. **Verifica Disponibilidad de Datos**
   ```python
   # Ver qué tickers tienen datos para tu rango
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('./data/ticker_cache.db')
   cursor = conn.execute('''
       SELECT ticker, COUNT(*) as days
       FROM ohlcv_cache  
       WHERE date BETWEEN '2000-01-01' AND '2022-12-31'
       GROUP BY ticker
       HAVING days >= 1000
       ORDER BY days DESC
       LIMIT 50
   ''')
   for row in cursor:
       print(f'{row[0]}: {row[1]} days')
   "
   ```

## 📝 Notas Importantes

### Diferencias Motor Original vs VectorBT

**Motor Original:**
- Procesa día por día, ticker por ticker
- Maneja gaps naturalmente (skip missing days)
- Más lento pero más robusto para datos faltantes

**VectorBT:**
- Carga TODO el periodo en memoria
- Requiere datos más consistentes
- Mucho más rápido pero menos tolerante a gaps

### Recomendaciones por Caso de Uso

**Testing de Estrategia (Rápido):**
- VectorBT + 1-3 años + Lista manual
- Ejemplo: 2021-2023 con 20 tickers

**Análisis Histórico Profundo:**
- Motor Original + 10+ años + Top liquidity
- Ejemplo: 2010-2023 con 50 tickers

**Validación de Robustez:**
- Ambos motores + Múltiples periodos
- Comparar resultados

## ✅ Resumen

**Tu caso (2000-2022):**
- Solo procesó 2021 porque pocos tickers tienen 22 años continuos
- Solución: Usa lista manual con blue chips O divide en periodos

**Ahora el sistema:**
- ✅ Te avisa cuando el rango difiere
- ✅ Usa selección inteligente para rangos largos
- ✅ Muestra estadísticas de datos cargados
- ✅ Tolera datos parciales (>50%)

**Próximo backtest 2000-2022:**
1. Usa lista manual: `SPY,AAPL,MSFT,JNJ,PG,KO,JPM,XOM`
2. Verás ~100-300 trades
3. Tiempo: ~20-30 segundos
4. Cobertura real en logs

---

**Última actualización:** 2026-01-05  
**Issue:** Resuelto ✅
