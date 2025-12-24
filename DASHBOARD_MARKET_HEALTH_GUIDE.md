# 📊 Dashboard Streamlit - Market Health Integration

## ✅ Nueva Funcionalidad Implementada

La app de Streamlit ahora incluye **Market Health Check en tiempo real** visible en la parte superior del dashboard.

---

## 🚀 Cómo Usar

### Iniciar el Dashboard

```bash
streamlit run app.py
```

O usar el script automático:

```bash
./run_dashboard.sh
```

El dashboard se abrirá automáticamente en tu navegador en `http://localhost:8501`

---

## 📊 Qué Verás

### Market Health Section (Parte Superior)

**Siempre visible al abrir la app:**

```
🛡️ MARKET HEALTH CHECK
════════════════════════════════════════════════

┌─────────────┬─────────────┬─────────────┬─────────────┐
│  SPY Trend  │   Breadth   │ Volatility  │     GEX     │
├─────────────┼─────────────┼─────────────┼─────────────┤
│  $605.50    │  Improving  │  Favorable  │  Positive   │
│  +0.88%     │             │             │             │
│  ✅ Above   │  ✅ Strong  │  ✅ VIX<20  │  ✅ Low Vol │
│    EMA20    │             │             │    Grind    │
└─────────────┴─────────────┴─────────────┴─────────────┘

Health Score: 7/7 (100%) ▓▓▓▓▓▓▓

🚀 AGGRESSIVE MODE - Excellent conditions
   Full size (2% risk), all 3 Caminos, focus on leading sectors

🎯 TOP SECTORS TODAY
────────────────────────────────────────────────
#1 Technology        XLK    +2.35%
#2 Consumer Discr.   XLY    +1.80%
#3 Financial         XLF    +1.25%
```

### Auto-Refresh

El Market Health Check se actualiza automáticamente cuando:
- Recargas la página
- Cambias filtros en el sidebar
- Ejecutas un nuevo backtest

### Interpretación

**Health Score:**
- **7/7 o 6/7:** 🚀 Aggressive - Operar con confianza
- **5/7 o 4/7:** 💪 Standard - Ser selectivo
- **3/7 o 2/7:** ⚠️ Defensive - Ultra selectivo
- **1/7 o 0/7:** ❌ No Trade - Ir a cash

**Métricas:**

| Indicador | Significado |
|-----------|-------------|
| **SPY Trend** | Si SPY > EMA20 → Tendencia alcista |
| **Breadth** | Si mejorando → Internos fuertes |
| **Volatility** | Si VIX < 20 y estable → Favorable |
| **GEX** | Si positivo → Grind alcista, baja vol |

**Sectores:**
- Top 3 sectores se actualizan cada día
- Solo opera en stocks de estos sectores para máxima probabilidad

---

## 🎯 Workflow Integrado

### Paso 1: Abrir Dashboard
```bash
streamlit run app.py
```

### Paso 2: Revisar Market Health (Arriba)

**Si dice "NO TRADE MODE":**
- ❌ No ejecutar backtest
- ❌ No buscar setups
- Esperar mejores condiciones

**Si dice "AGGRESSIVE/STANDARD/DEFENSIVE":**
- ✅ Proceder con análisis
- Ajustar risk según el modo
- Priorizar sectores líderes mostrados

### Paso 3: Usar Dashboard Normal

El resto del dashboard funciona igual:
- **Tab "Dashboard General":** Métricas, gráficos, análisis de trades
- **Tab "PnL Calendar":** Calendario de rendimiento

### Paso 4: Ejecutar Backtest (Sidebar)

Con el market health visible:
1. Ingresa símbolos o watchlist
2. Configura fechas y parámetros
3. Click "EJECUTAR BACKTEST"
4. Los resultados aparecen abajo

---

## 💡 Casos de Uso

### Uso 1: Morning Check (Pre-Market)

```bash
# 8:00 AM
streamlit run app.py

# Revisar Health Check arriba
# Decision tree:
- Score 6-7? → Buscar setups agresivamente
- Score 4-5? → Buscar setups selectivamente
- Score 0-3? → Skip o defensive
```

### Uso 2: Durante Market Hours

```bash
# App abierta en segundo monitor
# Auto-actualiza al recargar página (F5)
# Monitor health score mientras tradeas
```

### Uso 3: EOD Review

```bash
# 4:00 PM
# Revisar:
1. ¿Cómo estuvo el health score hoy?
2. ¿Tus trades fueron en sectores líderes?
3. ¿El modo coincidió con tu agresividad?
```

---

## 🛠️ Personalización (Opcional)

### Cambiar Auto-Refresh Interval

Editar `app.py` línea ~250:

```python
# Añadir auto-refresh cada 5 minutos
import time
time.sleep(300)
st.rerun()
```

### Cambiar Thresholds

Editar `src/core/market_context.py`:

```python
# VIX threshold
VIX_THRESHOLD = 20  # Default

# Sector top N
TOP_N_SECTORS = 3  # Default
```

### Ocultar Market Health

Si quieres solo backtest sin health:

Comentar líneas 266-387 en `app.py`:

```python
# --- MARKET HEALTH CHECK (Siempre visible) ---
# st.header("🛡️ Market Health Check")
# ...
```

---

## 🔧 Troubleshooting

### "Error loading market health"

**Causa:** No se puede conectar a data provider

**Solución:**
1. Verificar conexión a internet
2. Verificar OpenBB está instalado: `pip install openbb`
3. App seguirá funcionando, solo sin health check

### "Sector data not available"

**Causa:** Mercado cerrado o fines de semana

**Solución:**
- Normal, la data de sectores se actualiza durante market hours
- Health check seguirá funcionando con data disponible

### Dashboard no carga

```bash
# Reinstalar dependencias
pip install -r requirements.txt

# Verificar streamlit
streamlit --version

# Correr con debug
streamlit run app.py --logger.level=debug
```

---

## 📊 Ventajas del Dashboard con Health Check

### Antes (Sin Health Check):

```
❌ Ejecutabas backtest sin saber condiciones
❌ No sabías si el mercado era favorable
❌ No veías sectores líderes
❌ Decision making basado solo en backtest
```

### Ahora (Con Health Check):

```
✅ Ves condiciones de mercado ANTES de operar
✅ Sabes exactamente qué modo usar (Aggressive/Standard/etc)
✅ Ves sectores líderes del día
✅ Decision making informado con contexto completo
```

---

## 🎯 Tips Pro

### Tip 1: Segundo Monitor

```
Monitor 1: Trading platform (broker)
Monitor 2: Streamlit dashboard con health check
```

Keeps market context visible todo el tiempo.

### Tip 2: Screenshot Pre-Market

```bash
# Captura health check cada mañana
# Guarda para journal
# Compara con resultados EOD
```

### Tip 3: Correlation Analysis

```
Después de 2 semanas:
1. Exporta tus trades
2. Compara win rate en:
   - Days con health score 6-7
   - Days con health score 4-5
   - Days con health score 0-3

Verás la diferencia!
```

### Tip 4: Sector Rotation Tracking

```
Trackea qué sector es #1 cada día
Identifica rotaciones:
- Tech → Energy (risk-off)
- Financials → Tech (risk-on)

Ajusta watchlist según sectores persistentes
```

---

## 🚀 Comandos Rápidos

```bash
# Iniciar dashboard
streamlit run app.py

# Iniciar con puerto específico
streamlit run app.py --server.port 8502

# Iniciar sin auto-open browser
streamlit run app.py --server.headless true

# Ver logs
streamlit run app.py --logger.level=debug
```

---

## 📝 Checklist de Uso Diario

**Cada mañana (8:00 AM):**

- [ ] Abrir dashboard: `streamlit run app.py`
- [ ] Revisar Health Score (arriba)
- [ ] Anotar top 3 sectores
- [ ] Decidir modo: Aggressive/Standard/Defensive/No-Trade
- [ ] Si favorable → Ejecutar scanner (terminal)
- [ ] Si no favorable → Skip trading

**Durante el día:**

- [ ] Dashboard abierto en segundo monitor
- [ ] Refresh (F5) periódicamente para ver updates
- [ ] Verificar que trades están en sectores líderes

**EOD (4:00 PM):**

- [ ] Revisar health score del día
- [ ] Comparar con tus resultados
- [ ] Journal: ¿seguí el modo recomendado?

---

## ✅ Resumen

**El dashboard ahora tiene:**

✅ Market Health Check siempre visible
✅ Health Score 0-7 en tiempo real
✅ SPY, Breadth, VIX, GEX metrics
✅ Top 3 sectores líderes del día
✅ Modo recomendado (Aggressive/Standard/Defensive/No-Trade)
✅ Auto-actualizable
✅ Integrado con backtest existente

**Para usar:**

```bash
streamlit run app.py
# Revisar health check arriba
# Tomar decisiones informadas
```

---

**Última actualización:** Diciembre 2024

**Dashboard mejorado y operativo** ✅
