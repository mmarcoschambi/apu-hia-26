# 🎯 AJUSTE DE TAMAÑO DE POSICIÓN POR VOLATILIDAD (ADR)

## ✅ Estado: IMPLEMENTADO Y ACTIVO

## 📋 Regla Implementada

```
"Si el ADR es > 5-6%, tu tamaño de posición debe ser 1/3 o 1/4 de lo normal"
```

## 🔧 Lógica de Implementación

### Umbrales de ADR:

```
ADR ≤ 5.0%   → Tamaño normal (100%)
ADR > 5.0%   → Tamaño reducido a 1/3 (33%)
ADR > 6.0%   → Tamaño reducido a 1/4 (25%)
```

### Razón:

> "Mayor volatilidad = Mayor riesgo de stop loss
> Reducir el tamaño protege el capital mientras
> mantienes exposición al trade"

## 📊 Ejemplos Prácticos

### ✅ CASO 1: Volatilidad Normal
```
Symbol: AAPL
ADR: 2.5%
Capital: $50,000
Risk: 1% ($500)
Entry: $180.00
Stop: $175.00
Risk per share: $5.00

Shares calculadas: 100 shares
→ Sin reducción (ADR < 5%)
→ Position value: $18,000
→ Risk: $500 (1%)
```

### ⚠️ CASO 2: Alta Volatilidad (ADR 5-6%)
```
Symbol: NVDA
ADR: 5.5%
Capital: $50,000
Risk: 1% ($500)
Entry: $500.00
Stop: $480.00
Risk per share: $20.00

Shares calculadas: 25 shares
→ REDUCCIÓN A 1/3
→ Shares finales: 8 shares (25 × 0.33)
→ Position value: $4,000 (en vez de $12,500)
→ Risk reducido: ~$160 (en vez de $500)

Log: "HIGH_VOLATILITY (ADR 5.5%) - Size reduced to 1/3 (67% reduction) (25->8)"
```

### 🔴 CASO 3: Muy Alta Volatilidad (ADR >6%)
```
Symbol: TSLA
ADR: 7.2%
Capital: $50,000
Risk: 1% ($500)
Entry: $250.00
Stop: $238.00
Risk per share: $12.00

Shares calculadas: 41 shares
→ REDUCCIÓN A 1/4
→ Shares finales: 10 shares (41 × 0.25)
→ Position value: $2,500 (en vez de $10,250)
→ Risk reducido: ~$120 (en vez de $500)

Log: "HIGH_VOLATILITY (ADR 7.2%) - Size reduced to 1/4 (75% reduction) (41->10)"
```

## 🎓 Filosofía del Ajuste

### Por Qué Reducir Tamaño:

1. **Protección de Capital**
   - Mayor ADR = Mayor probabilidad de stop out
   - Reducir tamaño = Sobrevivir volatilidad normal

2. **Mantener Exposición**
   - No cancelamos el trade (como con Weak trend)
   - Reducimos el tamaño para participar con menor riesgo

3. **Riesgo Proporcional**
   - Stocks más volátiles requieren más "breathing room"
   - Tamaño menor compensa el riesgo adicional

### Diferencia vs Otros Filtros:

```
Weak Trend → RECHAZAR trade (0% exposición)
Low RVOL   → RECHAZAR trade (0% exposición)
High ADR   → REDUCIR tamaño (25-33% exposición)
```

## 📝 Implementación en Código

### Archivo: `src/backtest/daily_engine.py` (líneas 544-558)

```python
# --- HIGH VOLATILITY CHECK (ADR) ---
adr_note = ""
if adr_pct > 5.0:  # ADR threshold
    if adr_pct > 6.0:
        # Very high volatility: reduce to 1/4
        reduction_factor = 0.25
        reduction_desc = "1/4 (75% reduction)"
    else:
        # High volatility: reduce to 1/3
        reduction_factor = 0.33
        reduction_desc = "1/3 (67% reduction)"
    
    original_shares = sizing['shares']
    sizing['shares'] = int(original_shares * reduction_factor)
    adr_note = f"HIGH_VOLATILITY (ADR {adr_pct:.1f}%) - Size reduced to {reduction_desc} ({original_shares}->{sizing['shares']})"
```

## 🔍 Orden de Aplicación de Filtros

El sistema aplica filtros en cascada:

```
1. FILTROS DE RECHAZO (NO TRADE):
   ✓ Trend == 'Weak' → RECHAZAR
   ✓ RVOL < 1.5x → RECHAZAR

2. FILTROS DE REDUCCIÓN (TRADE CON MENOS TAMAÑO):
   ✓ Earnings en 5 días → Reducir a 1/4
   ✓ ADR > 5% → Reducir a 1/3
   ✓ ADR > 6% → Reducir a 1/4

3. EJECUTAR TRADE
   Con tamaño ajustado final
```

## 💡 Combinación de Reducciones

Si un trade tiene múltiples factores de riesgo:

```
Ejemplo: Earnings + ADR Alto
─────────────────────────────
Symbol: NVDA
ADR: 5.8%
Earnings: En 3 días
Shares calculadas: 100

Reducción por Earnings: 100 × 0.25 = 25 shares
Reducción por ADR: 25 × 0.33 = 8 shares

Shares finales: 8 (reducción del 92%)
Log: "EARNINGS_RISK (3d away) - Size reduced 75% (100->25) | HIGH_VOLATILITY (ADR 5.8%) - Size reduced to 1/3 (67% reduction) (25->8)"
```

## 📊 Impacto Esperado

### Trades de Alta Volatilidad:

**ANTES (sin ajuste):**
```
• ADR 6%+ con tamaño completo
• Stop loss frecuente por volatilidad normal
• Pérdidas grandes en días volátiles
```

**DESPUÉS (con ajuste):**
```
• ADR 6%+ con tamaño reducido (25%)
• Sobrevive volatilidad normal del stock
• Pérdidas controladas
• Mantiene exposición al upside
```

## 🎯 Casos de Uso Reales

### Stocks Típicos por ADR:

```
BAJA VOLATILIDAD (ADR 1-3%):
• JNJ, PG, KO, WMT
→ Tamaño completo

VOLATILIDAD MEDIA (ADR 3-5%):
• AAPL, MSFT, GOOGL
→ Tamaño completo

ALTA VOLATILIDAD (ADR 5-6%):
• NVDA, AMD, NFLX
→ Tamaño reducido a 1/3

MUY ALTA VOLATILIDAD (ADR >6%):
• TSLA, penny stocks, biotechs
→ Tamaño reducido a 1/4
```

## ⚙️ Ajuste de Parámetros

Los umbrales se pueden modificar en `daily_engine.py`:

```python
# Umbrales actuales:
if adr_pct > 5.0:  # Cambiar a 4.0 para ser más conservador
    if adr_pct > 6.0:  # Cambiar a 5.5 para ser más conservador
```

### Opciones de Reducción:

```python
# Actuales:
reduction_factor = 0.33  # 1/3
reduction_factor = 0.25  # 1/4

# Más conservador:
reduction_factor = 0.20  # 1/5
reduction_factor = 0.10  # 1/10

# Menos conservador:
reduction_factor = 0.50  # 1/2
```

## 🔍 Cómo Verificar

### En los Logs del Backtest:
```
Busca líneas como:
HIGH_VOLATILITY (ADR 5.8%) - Size reduced to 1/3 (67% reduction) (100->33)
HIGH_VOLATILITY (ADR 7.2%) - Size reduced to 1/4 (75% reduction) (50->12)
```

### En los Resultados:
```python
# Ver ADR de trades ejecutados
import pandas as pd
df = pd.read_csv('backtest_results.csv')

# Calcular ADR promedio
print(f"ADR promedio: {df['context_adr'].mean():.2f}%")

# Ver distribución
print(df['context_adr'].describe())

# Trades con ADR alto
high_adr = df[df['context_adr'] > 5.0]
print(f"Trades con ADR > 5%: {len(high_adr)}")
```

## 📚 Referencias

Este ajuste está basado en:
- Van Tharp: "Position Sizing"
- Mark Minervini: "Trade Like a Stock Market Wizard"
- Principio: "Risk is proportional to volatility"

## ✅ Checklist de Implementación

- [✅] Cálculo de ADR en daily_engine
- [✅] Detección de ADR > 5%
- [✅] Reducción a 1/3 (ADR 5-6%)
- [✅] Reducción a 1/4 (ADR > 6%)
- [✅] Logging de ajustes
- [✅] Combinación con otros filtros
- [✅] Documentación completa

## 🚀 Próximos Pasos

1. Ejecutar nuevo backtest para ver ajustes
2. Revisar logs de reducciones
3. Ajustar umbrales si es necesario
4. Comparar performance vs tamaño fijo

---

**NOTA:** Esta regla se aplica DESPUÉS de los filtros de rechazo (Trend/RVOL). Solo afecta trades que ya pasaron los filtros de calidad.
