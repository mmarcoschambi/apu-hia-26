# Guía de Uso Diario - Triad Protocol

## Flujo de Trabajo Diario

### Pre-Market (Antes de las 9:30 AM ET)

1. **Actualiza tu watchlist** en `example_scan.py`:
```python
watchlist = ['RDDT', 'CEG', 'AAPL', 'NVDA', 'TSLA']
```

2. **Ejecuta el scanner**:
```bash
python3 example_scan.py
```

3. **Revisa los resultados**:
   - **BUY_STOP**: Setup de Camino 1 (Blue Sky) → Coloca la orden antes del open
   - **MANUAL_WATCH**: Setup de Camino 2 (VWAP Reclaim) → Monitorea en vivo
   - **WAIT**: Camino 3 (Safety) → Alerta en el precio indicado

### Durante Market Hours (9:30 AM - 4:00 PM ET)

#### Para Camino 1 (Blue Sky Breakout)
- **Ya colocaste el Buy Stop pre-market**
- Si ejecuta → Deja correr con stop en Base Low
- Si no ejecuta al mediodía → Cancela la orden

#### Para Camino 2 (VWAP Reclaim)
1. **Espera el flush matutino** (primera hora)
2. **Monitorea el VWAP** en tu plataforma:
   - TradingView: Indicador "VWAP"
   - ThinkorSwim: `/VWAP`
   - Webull: "VWAP" en indicadores
3. **Entrada manual** cuando el precio cruza ARRIBA del VWAP
4. **Stop Loss**: Low of Day (LOD) - Este stop es CRÍTICO

#### Para Camino 3 (Safety Filter)
- **NO entres en la base pequeña**
- **Coloca alerta** en el precio AVWAP
- **Espera** a que rompa el AVWAP antes de considerar entrada

## Interpretación de Resultados

### Ejemplo 1: Blue Sky Breakout (RDDT)
```
RDDT - BLUE_SKY
  Action: BUY_STOP
  Entry: $100.05
  Stop: $95.20
  Risk: 4.85%
  Size: 100%
```

**Acción**:
1. Coloca Buy Stop Limit en $100.05 / Limit $100.50
2. Stop Loss en $95.20
3. Tamaño: Riesgo estándar 0.5%
4. Deja correr - no microgestionar

### Ejemplo 2: VWAP Reclaim (CEG)
```
CEG - VWAP_RECLAIM
  Action: MANUAL_WATCH
  Entry: $272.50 (VWAP actual)
  Stop: $268.00 (LOD)
  Risk: 1.65%
  Size: 50%
```

**Acción**:
1. NO colocar orden automática
2. Abrir gráfico M5 o M15
3. Esperar a que precio cruce VWAP hacia arriba
4. Comprar manualmente al cierre de esa vela
5. Stop en LOD - **no negociable**
6. Tamaño: Mitad del riesgo normal (0.25%)

### Ejemplo 3: Safety Filter (Anticipation Trap)
```
SYMBOL - SAFETY_CHECK
  Action: WAIT
  Entry: $55.05 (AVWAP)
  Stop: N/A
  Reason: AVWAP is 10% above price. Waiting for AVWAP breakout...
```

**Acción**:
1. NO tocar hoy
2. Ignorar la ruptura de la base pequeña en $50
3. Colocar alerta en $55
4. Revisar mañana si la estructura sigue válida

## Position Sizing

Usa el calculador de riesgo:

```bash
cd /home/marcos/trade/momentum-v2
python3 src/utils/risk_calculator.py
```

O en Python:
```python
from src.utils.risk_calculator import RiskCalculator

calc = RiskCalculator()

result = calc.calculate_position_size(
    account_size=100000,      # Tu cuenta
    risk_pct=0.005,           # 0.5% para Camino 1 y 3
    entry_price=100.05,
    stop_loss=95.20,
    multiplier=1.0            # 0.5 para Camino 2
)

print(f"Comprar {result['shares']} acciones")
```

## Gestión de la Posición

### Camino 1 (Blue Sky)
- **Stop**: Base Low o Entry - 1 ADR (el más alto)
- **Salida**: Trailing stop o objetivo técnico (R:R mínimo 2:1)
- **Mentalidad**: "Déjalo correr" - estos pueden ser +20-50%

### Camino 2 (VWAP Reclaim)
- **Stop**: LOD (Low of Day) - **NUNCA mover este stop**
- **Salida**: Más conservadora - R:R 1.5:1 o 2:1
- **Mentalidad**: "Protege rápido" - es una recuperación, no una explosión

### Camino 3 (Safety)
- **Stop**: Entry - 1 ADR
- **Salida**: Similar a Camino 1
- **Mentalidad**: "Confirma fuerza" - esperas confirmación antes de entrar

## Checklist Pre-Ejecución

Antes de presionar COMPRAR:

- [ ] ¿He identificado el Camino correcto?
- [ ] ¿El AVWAP está donde creo que está?
- [ ] ¿El mercado (SPY/QQQ) justifica este Camino?
- [ ] ¿Calculé el tamaño de posición correctamente?
- [ ] ¿Sé EXACTAMENTE dónde está mi stop?
- [ ] ¿Tengo un plan de salida?

## Troubleshooting

### "No actionable setups found"
- **ESTO ES NORMAL** - El sistema es disciplinado
- La mayoría de los días no hay setups perfectos
- No fuerces operaciones

### "AVWAP muy lejos del precio"
- Respeta el Safety Filter
- NO anticipes el breakout
- Espera pacientemente

### "Gap down pero sin VWAP reclaim"
- No todas las caídas se recuperan
- Si no recupera VWAP en la primera hora → Skip
- Vuelve a scanear al día siguiente

## Logs y Debugging

Los logs detallados están en:
```
logs/triad_YYYYMMDD.log
```

Para ver en tiempo real:
```bash
tail -f logs/triad_$(date +%Y%m%d).log
```

## Próximo Nivel

Una vez domines el sistema básico:

1. **Añade más indicadores de contexto**:
   - Volumen relativo
   - Sector strength
   - Correlaciones

2. **Optimiza parámetros** en `config/settings.py`

3. **Backtesting** con datos históricos

4. **Automatización** con broker API

---

## Reglas de Oro

1. **"Respetamos al Jefe Final (AVWAP ATH)"**
2. **Camino 2 = Stop en LOD** (no negociable)
3. **No fuerces setups** que no existen
4. **Disciplina > Predicción**

**"No perseguimos precios; capturamos la liberación de energía cuando la oferta desaparece."**
