# Umbrales Dinámicos y Filtros de Mercado

## 🎯 Resumen

Se ha implementado un sistema de **umbrales dinámicos basados en VIX** y **filtros de mercado (SPY > SMA50, VIX < 35)** en el motor de backtest `AdvancedVectorBTEngine`.

## 📊 Características Implementadas

### 1. Umbrales Dinámicos según VIX

Los umbrales de entrada se ajustan automáticamente según la volatilidad del mercado:

| VIX | Descripción | Min RVOL | Min ADR | Max SMA20 | Max Stop |
|------|-------------|-----------|---------|------------|----------|
| < 15 | Mercado tranquilo (Ej: 2019) | 1.5x | 3.0% | 6.0% | 7.0% |
| 15-25 | Mercado normal (Ej: 2021) | 1.8x | 3.5% | 5.5% | 6.5% |
| > 25 | Mercado volátil (Ej: 2020, 2022) | 2.0x | 4.0% | 5.0% | 6.0% |

**Beneficios:**
- ✅ Más permisivo en mercados tranquilos (capturar más setups)
- ✅ Más selectivo en mercados volátiles (evitar falsos breakouts)
- ✅ Ajuste automático de stops según volatilidad

### 2. Filtro SPY > SMA50

**Condición:** Solo opera cuando el precio de SPY está por encima de su SMA50.

**Lógica:**
```
if spy_price <= spy_sma50:
    return False  # NO operar
```

**Rationale:**
- SMA50 actúa como filtro de tendencia a mediano plazo
- Permite operar en Stage 1 (Bull) y Stage 2 (Consolidation)
- Bloquea entradas en Stage 3 (Distribution) y Stage 4 (Bear)

### 3. Filtro VIX < 35

**Condición:** No operar si el VIX supera el umbral configurado (default: 35).

**Lógica:**
```
if vix_value > max_vix_threshold:  # default 35
    return False  # NO operar
```

**Rationale:**
- Evita operar en periodos de alta volatilidad extrema
- Protege contra gaps impredecibles y whipsaws
- Configurable via parámetro `max_vix_threshold`

## 🔧 Implementación

### Funciones Nuevas

```python
def get_dynamic_thresholds(current_vix: float) -> Dict[str, float]:
    """
    Ajusta umbrales según volatilidad del mercado (VIX).

    Returns:
        - min_rvol: Umbral mínimo de RVOL
        - min_adr: Umbral mínimo de ADR
        - max_dist_sma20: Distancia máxima desde SMA20
        - max_stop_pct: Stop loss máximo permitido
    """


def should_trade_long(spy_price: float, spy_sma50: float, vix_value: float) -> bool:
    """
    Determina si se debe operar en largo.

    Returns:
        True si SPY > SMA50 AND VIX < 35
    """
```

### Parámetros Nuevos en AdvancedVectorBTEngine

```python
use_dynamic_thresholds: bool = False,  # Activar umbrales dinámicos
max_vix_threshold: float = 35.0,    # Max VIX para permitir trading
```

### Integración en app.py

Se agregó una nueva sección en el sidebar:

```python
with st.sidebar.expander("🌍 Market Regime", expanded=False):
    use_dynamic_thresholds = st.checkbox("📊 Umbrales Dinámicos (VIX)", value=False)
    
    if use_dynamic_thresholds:
        max_vix_threshold = st.slider("Max VIX para operar", 20.0, 50.0, 35.0, 1.0)
        st.info("✅ Además, solo opera cuando SPY > SMA50 (Stage 1-2)")
```

## 🚀 Uso

### En la UI de Streamlit

1. Habilitar "📊 Umbrales Dinámicos (VIX)"
2. Ajustar el slider "Max VIX para operar" (default: 35)
3. Ejecutar el backtest

### Programático

```python
from src.backtest.vectorbt_engine_advanced import AdvancedVectorBTEngine

engine = AdvancedVectorBTEngine(
    universe=tickers,
    start_date="2020-01-01",
    end_date="2023-12-31",
    # ... otros parámetros ...
    use_dynamic_thresholds=True,  # ACTIVAR umbrales dinámicos
    max_vix_threshold=35.0,      # Configurar max VIX
)

results = engine.run_backtest()
```

## 📈 Efecto Esperado

### Ventajas

1. **Adaptabilidad:** Se adapta automáticamente a diferentes condiciones de mercado
2. **Protección:** Filtra periodos de alta volatilidad y downtrends
3. **Eficiencia:** Evita trades en condiciones adversas (Stage 3-4)

### Trade-offs

- ⚠️ **Menos trades en periodos volátiles:** Puede reducir el número total de operaciones
- ⚠️ **Requiere datos de SPY y VIX:** Necesita que estos datos estén disponibles en el cache
- ⚠️ **Más complejidad:** Agrega una capa adicional de lógica de filtrado

## 🧪 Testing

Ejecutar el archivo de prueba:

```bash
python3 test_dynamic_thresholds.py
```

**Tests incluidos:**
1. ✅ Función `get_dynamic_thresholds()` con diferentes valores de VIX
2. ✅ Función `should_trade_long()` con varias condiciones de mercado
3. ✅ Integración con `AdvancedVectorBTEngine.__init__`

## 📊 Ejemplos de Uso

### Escenario 1: Mercado Alcista Tranquilo (2019)

```
VIX: 12 → Umbral relajado
- Min RVOL: 1.5x (permite más setups)
- Max SMA20: 6.0% (permite más espacio)
- SPY > SMA50: ✅ Permite trading
```

### Escenario 2: Mercado Volátil (2020)

```
VIX: 40 → Filtro activo
- SPY > SMA50: ✅ Pero...
- VIX (40) > 35: ❌ BLOQUEA todos los trades
```

### Escenario 3: Mercado en Distribución (2022)

```
VIX: 28 → Umbral estricto
- Min RVOL: 2.0x (solo setups de alta calidad)
- SPY ($380) ≤ SMA50 ($400): ❌ BLOQUEA todos los trades
```

## 📝 Notas Técnicas

1. **Performance:** Los umbrales dinámicos se calculan en tiempo real durante el loop de simulación
2. **Cache:** Se usan series de pandas pre-calculadas para minimizar overhead
3. **Fallback:** Si los datos de VIX no están disponibles, usa umbrales estáticos (configurados vía parámetros)
4. **Logging:** Se registran los umbrales aplicados en cada fecha para debugging

## 🔍 Referencias

- Archivo: `src/backtest/vectorbt_engine_advanced.py`
- UI: `app.py` (líneas 734-790)
- Tests: `test_dynamic_thresholds.py`
- Documentación: `DYNAMIC_THRESHOLDS_IMPLEMENTATION.md` (este archivo)

## ✅ Checklist de Implementación

- [x] Función `get_dynamic_thresholds()`
- [x] Función `should_trade_long()`
- [x] Parámetros `use_dynamic_thresholds` y `max_vix_threshold` en `AdvancedVectorBTEngine`
- [x] Cálculo de SMA50 de SPY si no existe
- [x] Aplicación de umbrales dinámicos en filtros de RVOL y ADR
- [x] Aplicación de umbrales dinámicos en max_dist_sma20
- [x] Aplicación de umbrales dinámicos en max_stop_pct
- [x] Filtro SPY > SMA50 en generación de entries
- [x] Filtro VIX < max_vix_threshold en generación de entries
- [x] UI en Streamlit con checkbox y slider
- [x] Logging de umbrales aplicados
- [x] Tests unitarios
- [x] Documentación

---

**Última actualización:** 16 Enero 2026
**Autor:** OpenCode
**Versión:** 1.0
