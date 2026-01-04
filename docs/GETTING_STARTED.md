# 🚀 Getting Started - Triad Momentum System

## Installation (5 minutos)

```bash
# 1. Navigate to the project
cd /home/marcos/trade/momentum-v2

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Test the system
python3 test_system.py
```

✅ Si ves "System working!" - estás listo.

---

## Your First Scan (2 minutos)

### 1. Edit your watchlist

Abre `example_scan.py` y personaliza:

```python
watchlist = [
    'RDDT',   # Tus símbolos aquí
    'NVDA',
    'TSLA',
]
```

### 2. Run the scanner

```bash
python3 example_scan.py
```

### 3. Interpret results

Busca la sección **ACTIONABLE SETUPS**.

---

## Understanding Your First Signal

### Ejemplo de Output:

```
RDDT - BLUE_SKY
  Action: BUY_STOP
  Entry: $100.05
  Stop: $95.20
  Risk: 4.85%
  Size: 100%
```

**Esto significa:**

1. **RDDT** tiene un setup de **Camino 1** (Blue Sky Breakout)
2. **Coloca una orden:**
   - Type: Buy Stop Limit
   - Stop Price: $100.05
   - Limit Price: $100.50 (un poco arriba)
3. **Stop Loss:** $95.20
4. **Position Size:** Calcula con 0.5% de riesgo

---

## Position Sizing (CRÍTICO)

### Opción 1: Calculadora Automática

```bash
python3 quick_analysis.py RDDT 100000
```
(100000 = tu tamaño de cuenta)

Te dará:
```
📊 POSITION SIZING ($100,000 account)
  Shares: 103
  Capital: $10,305.15
  Risk Amount: $499.55
  Risk %: 0.50%
```

### Opción 2: Manual

```
Riesgo_Deseado = $500 (0.5% de $100k)
Entry = $100.05
Stop = $95.20
Riesgo_Por_Acción = $100.05 - $95.20 = $4.85

Acciones = $500 / $4.85 = 103 shares
```

---

## Daily Workflow (10 minutos/día)

### Pre-Market (9:00 AM ET)

```bash
# Scan watchlist
python3 example_scan.py
```

**Para cada señal BUY_STOP:**
1. Coloca la orden en tu broker
2. Configura el stop loss
3. Calcula y anota el position size

**Para cada señal MANUAL_WATCH:**
1. Abre el gráfico M5/M15
2. Añade el indicador VWAP
3. Prepárate para entrar manualmente

### During Market (9:30 - 10:30 AM)

**Camino 1 (BUY_STOP):**
- Deja que la orden ejecute sola
- Si no ejecuta al mediodía → Cancela

**Camino 2 (MANUAL_WATCH):**
- Espera el flush matutino
- Cuando precio cruce VWAP → Compra
- Stop en LOD inmediatamente

### After Market (4:00 PM+)

**Si tienes posición:**
- Revisa el movimiento del día
- Ajusta mental stops (no físicos aún)
- Planifica salida para mañana

**Si no entraste:**
- Revisa por qué no hubo setups
- Actualiza watchlist si es necesario

---

## Common Questions

### ¿Cuántos símbolos debo escanear?
**10-20 máximo.** Calidad > Cantidad.

### ¿Qué pasa si no hay setups?
**Normal.** El sistema es disciplinado. Algunos días no hay nada.

### ¿Puedo modificar los parámetros?
**Sí,** pero primero entiende el sistema. Edit `config/settings.py`.

### ¿Funciona en bear market?
**Mejor en bull market.** Momentum requiere tendencia alcista general.

### ¿Dónde coloco take profit?
**No hay regla fija.** Usa trailing stop o objectives técnicos (R:R 2:1 mínimo).

---

## Week 1 Challenge

**Objetivo:** Familiarizarte sin arriesgar dinero.

1. **Día 1-2:** Run `example_scan.py` cada mañana. Solo observa.

2. **Día 3-4:** Usa `quick_analysis.py` para estudiar cada setup a fondo.

3. **Día 5:** Paper trade (simulador) tu primer setup de Camino 1.

4. **Fin de semana:** Revisa logs y tus notas. ¿Entiendes los 3 Caminos?

---

## Next Steps

Una vez domines lo básico:

- [ ] Paper trade por 2 semanas
- [ ] Real trade con size pequeño (0.1% risk)
- [ ] Incrementa gradualmente a 0.5%
- [ ] Estudia `USAGE.md` para detalles avanzados
- [ ] Lee `QUICKREF.md` para referencia rápida

---

## Need Help?

1. **Check logs:** `tail -f logs/triad_YYYYMMDD.log`
2. **Re-read docs:** README.md, USAGE.md, QUICKREF.md
3. **Test components:** Individual indicators in `src/indicators/triad.py`

---

## Important Reminders

⚠️ **Este es un sistema mecánico** - No uses discreción
⚠️ **Size correcto = Sobrevivir** - No skippees el position sizing
⚠️ **Los stops son sagrados** - Especialmente LOD en Camino 2
⚠️ **Práctica primero** - Paper trade hasta que domines

---

## Success Metrics

Después de 1 mes, deberías poder:

✅ Identificar los 3 Caminos sin pensar
✅ Calcular position size en < 30 segundos
✅ Saber si un setup es válido en < 1 minuto
✅ Ejecutar sin dudar cuando hay señal
✅ NO ejecutar cuando no hay señal

---

🎯 **"Disciplina > Predicción"**

El sistema no predice el futuro. Captura probabilidad cuando la estructura lo permite.

**¡Ahora empieza tu Week 1 Challenge!**

```bash
python3 example_scan.py
```
