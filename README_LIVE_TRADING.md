# 🚀 Sistema de Trading en Vivo - Momentum Triad

## ¿Qué es esto?

Un sistema COMPLETO para llevar tu estrategia de momentum trading del backtest al mundo real. Incluye:

- ✅ Market health check automatizado
- ✅ Scanner de setups en tiempo real
- ✅ Gestión de posiciones y P&L tracking
- ✅ Workflow guiado paso a paso
- ✅ Documentación exhaustiva

## 🚀 Quick Start (5 minutos)

```bash
# 1. Setup inicial
./setup_live_trading.sh

# 2. Tu primera rutina matinal
python morning_workflow.py
```

Eso es todo! El sistema te guiará desde ahí.

## 📚 Documentación

### Empieza aquí (en orden):

1. **EMPIEZA_AQUI_LIVE_TRADING.txt** ⭐ (Léelo primero)
   - Overview completo del sistema
   - FAQ y comandos principales
   - Tu referencia rápida diaria

2. **QUICK_START_LIVE.md**
   - Ejemplo de tu primer día completo
   - Flujo desde 8 AM hasta cierre
   - Tips prácticos

3. **LIVE_TRADING_GUIDE.md** (Lectura profunda)
   - Guía exhaustiva de 40+ páginas
   - Todo sobre transición a live
   - Market health, risk management, troubleshooting

### Guías especializadas:

- **MARKET_FILTERS.md** - Entender filtros de salud del mercado
- **TRADE_LIFECYCLE_MASTERCLASS.md** - Gestión completa de trades
- **PATTERN_DETECTION_GUIDE.md** - Detección de los 3 Caminos

## 🛠️ Herramientas

### Workflow Matinal (Recomendado)

```bash
python morning_workflow.py
```

Ejecuta TODO en un solo comando:
- Market health check
- Review de posiciones
- Scan de nuevos setups
- Action plan específico

### Herramientas Individuales

```bash
# Solo health check
python market_health_check.py

# Solo scanner
python live_trading_scanner.py

# Ver posiciones
python position_tracker.py

# Actualizar precios
python position_tracker.py --update

# Añadir posición
python position_tracker.py --add AAPL 150.50 145.20 100 Camino1

# Cerrar posición
python position_tracker.py --close AAPL 155.00

# Ver historial
python position_tracker.py --history
```

## 📅 Rutina Diaria

| Hora | Comando | Descripción |
|------|---------|-------------|
| 8:00 AM | `python morning_workflow.py` | Rutina pre-market completa |
| 9:20 AM | Manual en broker | Colocar órdenes |
| 9:30 AM | `python position_tracker.py --update` | Monitor fills |
| 12:00 PM | `python daily_workflow.py mid-day` | Mid-day check |
| 4:00 PM | `python daily_workflow.py market-close` | EOD review |

## 🛡️ Market Health System

Antes de operar, el sistema verifica:

✅ **SPY > EMA20** (tendencia alcista)  
✅ **Breadth mejorando** (internos fuertes)  
✅ **GEX positivo** (volatilidad baja)

| Condición | Modo | Risk/Trade | Max Positions |
|-----------|------|------------|---------------|
| Excellent | 🚀 Aggressive | 2% | 5 |
| Good | 💪 Standard | 1.5% | 3-4 |
| Defensive | ⚠️ Defensive | 1% | 1-2 |
| Poor | ❌ No Trade | 0% | 0 |

**Regla de oro:** Si el market health dice NO-GO → NO operes.

## 💰 Gestión de Riesgo

Reglas NO negociables:

- ✅ Risk por trade: **1-2% máximo**
- ✅ Max posiciones: **3-5 simultáneas**
- ✅ Stop loss: **SIEMPRE definido antes de entrar**
- ✅ Max loss diario: **6%** (entonces STOP)
- ✅ Partial exit: **50% a +3R**

## ⚠️ Antes de Ir en Vivo

**Checklist obligatorio:**

- [ ] Backtest validado (win rate > 50%)
- [ ] Paper trading 2 semanas mínimo
- [ ] Plan de risk management definido
- [ ] Mentalmente preparado para pérdidas
- [ ] Entiendes los 3 Caminos perfectamente
- [ ] Watchlist preparada
- [ ] Broker cuenta fondeada

**Si no tienes 7/7 → Más práctica necesaria**

## 🎯 Filosofía del Sistema

```
"No es tradear todos los días,
 sino tradear los MEJORES días."
```

El sistema es **SELECTIVO**:
- Espera condiciones óptimas de mercado
- Solo genera setups de alta probabilidad
- Prioriza calidad sobre cantidad

**No hay setups = No hay trades → Esto es NORMAL y BUENO**

## 📊 Ejemplo de Uso

```bash
$ python morning_workflow.py

🛡️  MARKET HEALTH CHECK
========================
SPY: $605.50 (EMA20: $600.20) ✅
Breadth: ✅ Improving
GEX: ✅ Positive

🎯 VERDICT: AGGRESSIVE MODE
Max positions: 5 | Risk per trade: 2%

📍 NEW SETUPS FOUND: 2

1. AAPL - Camino 1 (Blue Sky)
   Entry: $150.50 | Stop: $145.20
   Action: Place BUY STOP order

2. TSLA - Camino 2 (VWAP Reclaim)
   Action: Set alert for VWAP cross

📋 ACTION PLAN:
• 9:20 AM: Place orders in broker
• 9:30 AM: Monitor fills
• 10:30 AM: Cancel unfilled orders
```

## 🆘 Troubleshooting

**"No data available"**
- Verifica conexión a internet
- Revisa que OpenBB está instalado

**"No setups found"**
- Esto es NORMAL
- El sistema es selectivo
- Mejor no operar que forzar trades malos

**"Market not favorable"**
- NO operes
- Es disciplina
- Espera mejores condiciones

## 🚀 Mejoras Futuras (Opcionales)

### Nivel 1: Esenciales
- [ ] Conexión a broker API (IB, Alpaca)
- [ ] Alertas SMS/Push notifications
- [ ] Dashboard web en tiempo real

### Nivel 2: Avanzadas
- [ ] Base de datos para trades
- [ ] ML para pattern detection
- [ ] Backtesting continuo automatizado

### Nivel 3: Profesional
- [ ] Multi-strategy portfolio
- [ ] Risk parity allocation
- [ ] Automated reporting

## 📱 Tips Pro

1. **Automatiza con cron**
   ```bash
   crontab -e
   0 8 * * 1-5 cd /path && python morning_workflow.py
   ```

2. **Dashboard en segundo monitor**
   ```bash
   streamlit run app.py
   ```

3. **Paper trade primero**
   - Interactive Brokers Paper Account
   - $100K virtual
   - Misma plataforma que live

## 📞 Soporte

Consulta la documentación:
- Preguntas generales → `EMPIEZA_AQUI_LIVE_TRADING.txt`
- Quick start → `QUICK_START_LIVE.md`
- Guía completa → `LIVE_TRADING_GUIDE.md`

## 📜 Licencia

Este sistema es para uso personal. Trade responsablemente.

---

**¡ÉXITO EN TU TRADING! 🚀**

*"Trade safe. Trade smart. Trade the plan."*
