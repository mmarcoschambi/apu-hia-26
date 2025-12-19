# 🛡️ Market Regime Filters

## Objetivo

**Evitar comprar en mercado bajista** - Solo operar longs cuando las condiciones de mercado son favorables.

---

## 📊 Filtros Implementados

### 1. Filtro Principal: SPY > EMA 20 OR Breadth Improving

**Solo se permiten LONGS si se cumple AL MENOS UNO:**

```
✓ SPY > EMA20  (tendencia alcista confirmada)
   O
✓ Breadth improving  (% de stocks por encima de SMA20 está subiendo)
```

**Lógica:**
- Si SPY está por debajo de EMA20 → Mercado en pullback/corrección
- Si Breadth no está mejorando → Internos débiles
- **Ambas señales negativas = NO OPERAR LONGS**

### 2. Filtro Avanzado: Positive GEX (Gamma Exposure)

**Para entradas más agresivas, se requiere:**

```
✓ Filtro Principal PASSED
   Y
✓ GEX positivo estimado  (volatilidad baja + grind alcista)
```

**Características de GEX positivo:**
- ATR declinando (volatilidad comprimiéndose)
- SPY > EMA10 (uptrend de corto plazo)
- Mercado "grinding" hacia arriba con movimientos pequeños

---

## 🔍 Cómo Funciona

### Cuando Scaneas

```bash
python3 example_scan.py
```

**El sistema ahora:**

1. **Revisa SPY/QQQ primero**
   - Calcula EMA20 de SPY
   - Evalúa tendencia de breadth
   - Estima régimen GEX

2. **Si el filtro FALLA:**
   ```
   ❌ NO LONGS ALLOWED
   Reason: SPY $598.50 below EMA20 $605.20 AND breadth not improving
   ```
   → **No genera señales de compra**

3. **Si el filtro PASA:**
   ```
   ✅ Market favorable for longs
   Proceed with Camino analysis...
   ```
   → Continúa con análisis de los 3 Caminos

---

## 📈 Detalles Técnicos

### SPY > EMA20

```python
SPY_EMA20 = SPY.Close.ewm(span=20).mean()

if SPY_current > SPY_EMA20:
    ✓ Uptrend confirmed
else:
    ✗ In pullback/correction
```

**Razón:** EMA20 es un indicador probado de tendencia de mediano plazo.

### Breadth Improving

**Proxy implementado:**

```python
1. Calcula SMA20 para SPY y QQQ
2. Verifica si ambos están above their SMA20
3. Compara precio promedio de últimos 5 días vs 5 días anteriores

if (SPY > SMA20 AND QQQ > SMA20) OR (recent_5d > previous_5d):
    ✓ Breadth improving
```

**Razón:** Cuando el mercado tiene internos fuertes, la mayoría de acciones suben. Esto es un mercado favorable para momentum.

### Positive GEX

**Estimación basada en características:**

```python
ATR(5) declining  →  Volatilidad comprimiéndose
SPY > EMA10       →  Short-term uptrend

if atr_declining AND spy_above_ema10:
    ✓ Positive GEX regime (dealer hedging pushes market up)
```

**Razón:** Cuando dealers tienen gamma positiva, hedgean vendiendo en subidas y comprando en caídas, lo que **amortigua la volatilidad** y crea grinds alcistas.

---

## 🎯 Uso Práctico

### Modo Conservador (Default)

```python
# Solo requiere uno:
if spy_above_ema20 OR breadth_improving:
    → Allow longs
```

**Usa esto cuando:**
- Estás iniciando con el sistema
- Prefieres menos trades pero más selectivos
- El mercado está volátil

### Modo Agresivo (Opcional)

```python
# Requiere ambos:
if (spy_above_ema20 OR breadth_improving) AND positive_gex:
    → Allow aggressive longs
```

**Usa esto cuando:**
- Tienes experiencia con el sistema
- Quieres aprovechar grinds de baja volatilidad
- Buscas Camino 1 con máxima probability

---

## 📊 Ejemplos

### Ejemplo 1: Market Favorable

```
SPY: $605.50
EMA20: $600.20
Above EMA20: ✓ YES

Breadth improving: ✓ YES
Positive GEX: ✓ YES

VERDICT: ✅ LONGS ALLOWED + AGGRESSIVE OK
```

**Acción:** Buscar setups de los 3 Caminos normalmente.

### Ejemplo 2: Pullback Shallow

```
SPY: $598.50
EMA20: $600.20
Above EMA20: ✗ NO

Breadth improving: ✓ YES (ascending)
Positive GEX: ✗ NO

VERDICT: ✅ LONGS ALLOWED (defensive mode)
```

**Acción:** Operar solo setups de alta calidad (Blue Sky perfecto).

### Ejemplo 3: Corrección

```
SPY: $590.00
EMA20: $605.20
Above EMA20: ✗ NO

Breadth improving: ✗ NO
Positive GEX: ✗ NO

VERDICT: ❌ NO LONGS
```

**Acción:** CASH. Esperar a que mejoren condiciones.

---

## ⚙️ Configuración

### Ver Estado Actual

```bash
python3 << 'EOF'
from src.data.market_data import MarketDataProvider
from src.core.market_context import MarketContext

provider = MarketDataProvider()
mc = MarketContext(provider)
context = mc.analyze_indices()

print(f"SPY above EMA20: {context['spy_above_ema20']}")
print(f"Breadth improving: {context['breadth_improving']}")
print(f"Positive GEX: {context['positive_gex']}")
print(f"\nLongs allowed: {context['market_favorable_for_longs']}")
print(f"Aggressive OK: {context['allow_aggressive_entries']}")
EOF
```

### Ajustar Sensibilidad

Edita `config/settings.py`:

```python
# Más conservador (requiere ambos)
REQUIRE_BOTH_FILTERS = True

# Más agresivo (solo uno)
REQUIRE_BOTH_FILTERS = False  # Default
```

---

## 🧪 Backtesting con Filtros

**Los filtros están integrados en el backtest:**

```bash
python3 backtest_runner.py
```

Ahora el backtest:
1. Calcula SPY EMA20 en cada fecha histórica
2. Evalúa si breadth estaba mejorando
3. Solo genera señales si el filtro pasaba

**Resultado:** Win rate mejorado porque evitamos operar en mercados bajistas.

---

## 📚 Referencias

- **EMA20:** Indicador clásico de tendencia mediana (Mark Minervini usa EMA21)
- **Breadth:** Concepto de internos de mercado (% stocks > SMA)
- **GEX:** Gamma exposure de opciones SPX (SpotGamma, SqueezeMetrics)

---

## ⚠️ Notas Importantes

1. **Breadth es una aproximación:** 
   - Ideal sería tener data de NYSE/NASDAQ breadth real
   - Usamos proxy con SPY/QQQ por simplicidad
   - Funciona bien en práctica

2. **GEX es estimado:**
   - Data real de GEX requiere API de pago (SqueezeMetrics $500+/mes)
   - Nuestra estimación usa proxies (ATR + EMA10)
   - Suficientemente preciso para filtering

3. **Default es conservador:**
   - Mejor pecar de conservador que perder en mercado bajista
   - Puedes ajustar si tienes experiencia

---

## 🎯 Resumen

| Condición | Resultado |
|-----------|-----------|
| SPY > EMA20 | ✅ Allow longs |
| SPY < EMA20 pero breadth ↑ | ✅ Allow longs (defensive) |
| SPY < EMA20 y breadth ↓ | ❌ NO LONGS |
| + Positive GEX | ✅ Aggressive setups OK |

**Regla de oro:** "When in doubt, sit it out" → El filtro te mantiene fuera cuando las probabilidades son bajas.

---

**Última actualización:** Diciembre 2024
