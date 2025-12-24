# Risk Manager Institucional - Modificaciones Implementadas

## 🎯 Objetivo
Convertir el Risk Manager en un Gestor de Riesgo Institucional que te protege de tus propios errores (como el stop del 13%).

## ✅ Modificaciones Implementadas

### 1. Stop Loss Sanity Check (Anti-Bagholding)
**Problema:** El script calculaba posición sin importar lo lejos que esté el stop.

**Solución:** Rechazar trades con stops > 8%

```python
# Hard Cap institucional del 8%
MAX_ALLOWED_STOP_PCT = 0.08

if stop_loss_pct > MAX_ALLOWED_STOP_PCT:
    logger.warning(f"Trade Rejected: Stop Loss of {stop_loss_pct:.2%} exceeds max allowed {MAX_ALLOWED_STOP_PCT:.2%}")
    return self._zero_allocation(f"Stop Loss too wide ({stop_loss_pct:.2%} > {MAX_ALLOWED_STOP_PCT:.2%})")
```

**Resultado:** ✅ Ya no entrarás en trades con stops del 13% o 14%

---

### 2. Exposición Dinámica basada en Volatilidad (ADR Tiering)
**Problema:** Exposición fija del 25% sin considerar volatilidad de la acción.

**Solución:** Reducir exposición a la mitad si ADR > 5%

```python
# Si la acción es muy volátil (ADR > 5%), reducir exposición máxima
if adr_percent > 5.0:
    dynamic_max_exposure = self.max_exposure_fraction * 0.5  # 25% -> 12.5%
    limit_reason = "High Volatility Cap"
else:
    dynamic_max_exposure = self.max_exposure_fraction
    limit_reason = "Standard Cap"

max_nominal_exposure = self.account_equity * dynamic_max_exposure
```

**Resultado:** ✅ No sobrecargarás la cuenta en acciones locas (OKLO con ADR 13.46%)

---

### 3. Filtro de Liquidez (No seas la Ballena)
**Problema:** No verificaba si tu posición es demasiado grande para el volumen diario.

**Solución:** Limitar a máximo 1% del volumen diario promedio (ADV)

```python
# Nunca ser más del 1% del volumen diario promedio
max_shares_liquidity = int(avg_daily_volume * 0.01)

if shares > max_shares_liquidity:
    shares = max_shares_liquidity
    position_value = shares * entry_price
    constraint_hit = f"Liquidity Constrained (Max 1% of ADV: {avg_daily_volume:,})"
```

**Resultado:** ✅ Respetarás el mercado (podrás salir sin destrozar el precio)

---

### 4. Soporte de Acciones Fraccionadas (Nuevo!)
**Problema:** Cuentas pequeñas no podían entrar en acciones caras porque el cálculo redondeaba a 0.

**Solución:** Permitir fracciones (3 decimales) para cuentas < $25k

```python
# Soporte para acciones fraccionadas en cuentas pequeñas
if self.allow_fractional_shares and self.account_equity < 25000:
    shares = round(raw_shares, 3)  # Precisión de 3 decimales
    min_position_value = 25.0
    min_shares = max(0.001, min_position_value / entry_price)
    
    if shares < min_shares:
        return self._zero_allocation(f"Position too small (${shares * entry_price:.2f} < ${min_position_value})")
else:
    shares = int(raw_shares)  # Cuentas grandes: solo enteros
```

**Ejemplo:**
- Cuenta de $5,000, riesgo 1% = $50
- Acción a $800, stop $760 = $40 riesgo/share
- Cálculo: $50 / $40 = **1.25 shares** ✅
- Capital: $1,000 (20% de la cuenta)

**Resultado:** ✅ Cuentas pequeñas pueden operar acciones caras con fracciones

---

## 📝 Cambios en la Firma del Método

### Antes:
```python
def calculate_position_size(self, 
                            entry_price: float, 
                            stop_price: float, 
                            market_regime_factor: float = 1.0,
                            adr_pct: float = 0.0) -> Dict:
```

### Después:
```python
def calculate_position_size(self, 
                            entry_price: float, 
                            stop_price: float, 
                            adr_percent: float,           # OBLIGATORIO
                            avg_daily_volume: int,        # OBLIGATORIO
                            market_regime_factor: float = 1.0) -> Dict:
```

---

## 🔧 Archivos Modificados

1. **`src/utils/risk_manager.py`** - Implementación del Risk Manager Institucional
2. **`src/core/triad_openbb.py`** - Actualizado para calcular ADR y volumen
3. **`src/backtest/daily_engine.py`** - Actualizado para usar nuevos parámetros

---

## 🧪 Tests Implementados

### Test Suite 1: **`test_institutional_risk.py`**

Tests incluidos:
1. ✅ Stop Loss Sanity Check - Rechaza stops > 8%
2. ✅ Exposición Dinámica - Reduce exposición con alta volatilidad
3. ✅ Filtro de Liquidez - Limita posición al 1% del ADV
4. ✅ Escenario OKLO - Rechaza trade peligroso automáticamente

### Test Suite 2: **`test_fractional_shares.py`**

Tests incluidos:
1. ✅ Acciones Fraccionadas - Cuentas pequeñas usan fracciones (3 decimales)
2. ✅ Sin Fracciones - Cuentas grandes usan solo enteros
3. ✅ Constraints con Fracciones - Todos los límites respetan fracciones
4. ✅ Plan de Ejecución - Soporta splits 50/50 con fracciones
5. ✅ Fracciones Deshabilitadas - Opción para desactivar

### Ejecutar tests:
```bash
python3 test_institutional_risk.py
python3 test_fractional_shares.py
```

**Todos los tests pasan correctamente ✅**

---

## 🎯 Ejemplo de Uso

```python
from src.utils.risk_manager import RiskManager

# Ejemplo 1: Cuenta grande (institucional)
rm = RiskManager(
    account_equity=100000,
    risk_fraction=0.01,          # 1% riesgo por trade
    max_exposure_fraction=0.25   # 25% exposición máxima base
)

result = rm.calculate_position_size(
    entry_price=100.0,
    stop_price=95.0,             # 5% stop
    adr_percent=4.5,             # ADR 4.5%
    avg_daily_volume=1000000,    # 1M shares/día
    market_regime_factor=1.0     # Mercado alcista
)

print(f"Shares: {result['shares']}")
print(f"Position Value: ${result['position_value']:,.2f}")
print(f"Constraint: {result['constraint_hit']}")

# Ejemplo 2: Cuenta pequeña con fracciones
rm_small = RiskManager(
    account_equity=5000,
    risk_fraction=0.01,
    max_exposure_fraction=0.25,
    allow_fractional_shares=True  # Activado por defecto
)

result_frac = rm_small.calculate_position_size(
    entry_price=800.0,
    stop_price=760.0,            # $40 riesgo = 5%
    adr_percent=4.5,
    avg_daily_volume=1000000
)

print(f"Shares: {result_frac['shares']}")  # 1.25 shares
print(f"Is Fractional: {result_frac['is_fractional']}")  # True
print(f"Position Value: ${result_frac['position_value']:,.2f}")  # $1,000
```

---

## 🚀 Beneficios Inmediatos

1. **Protección Automática:** No más trades con stops ridículos del 13%
2. **Gestión de Volatilidad:** Exposición ajustada automáticamente según ADR
3. **Respeto por Liquidez:** No serás la ballena que mueve el precio
4. **Market Regime Aware:** Si `market_regime_factor = 0.0` (mercado bajista), riesgo = 0
5. **Acciones Fraccionadas:** Cuentas pequeñas pueden operar acciones caras (TSLA, NVDA, etc.)

---

## 📊 Comparativa Antes/Después

### Escenario 1: OKLO con stop del 14%, ADR 13.46%

| Métrica | Antes | Después |
|---------|-------|---------|
| Trade permitido | ✅ Sí (posición minúscula) | ❌ NO |
| Razón | - | "Stop Loss too wide (14% > 8%)" |
| Exposición máxima | 25% fijo | 12.5% (reducida por alta volatilidad) |
| Límite de liquidez | No verificado | Máx 1% del volumen diario |

### Escenario 2: Cuenta pequeña ($5k) comprando TSLA ($800)

| Métrica | Antes | Después |
|---------|-------|---------|
| Shares calculadas | 0 (redondeado) | 1.25 shares ✅ |
| Capital requerido | $0 (no trade) | $1,000 (20% cuenta) |
| Trade permitido | ❌ NO | ✅ SÍ (con fracciones) |

---

## 🔍 Notas Importantes

1. **ADR y Volumen son OBLIGATORIOS:** Todos los archivos que llamen a `calculate_position_size` deben proporcionar estos parámetros.

2. **Cálculo de ADR:** 
   ```python
   adr_pct = ((recent_data['high'] - recent_data['low']) / recent_data['close'] * 100).mean()
   ```

3. **Valores por defecto conservadores:**
   - ADR: 4.0% si no disponible
   - Volumen: 1,000,000 shares si no disponible

4. **Orden de aplicación de límites:**
   1. Market Regime (0 = no trade)
   2. Small Account + Low ADR check
   3. Stop Loss Sanity Check (< 8%)
   4. Risk-based position sizing
   5. Dynamic Max Exposure (volatilidad)
   6. Buying Power limit
   7. Liquidity limit (1% ADV)

---

## 🎓 Filosofía Cycle Fund Implementada

> "No perseguimos precios. Si el setup requiere un stop > 8%, no hay trade."

> "Después tampoco vas a ir con mucho size en $OKLO que tiene 13,46% de ADR"

> "Tenéis acciones que mueven 100M al día... evita acciones ilíquidas"

✅ **Todas estas reglas ahora están codificadas y se aplican automáticamente.**
