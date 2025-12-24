# ⚡ QUICK START: Tu Primer Día de Trading en Vivo

## 🎯 Objetivo
Guía ultra-rápida para empezar a usar el sistema HOY MISMO.

---

## 📋 Pre-Requisitos (5 minutos)

```bash
# 1. Ejecutar setup
./setup_live_trading.sh

# 2. Editar tu watchlist
nano acciones_activas.csv
# Añade los tickers que quieres monitorear (uno por línea)

# 3. Verificar que todo funciona
python market_health_check.py --help
```

---

## 🌅 RUTINA DE LA MAÑANA (8:00 AM)

### Opción 1: Todo Automático (Recomendado)

```bash
python morning_workflow.py
```

Esto ejecutará:
1. ✅ Health check del mercado
2. ✅ Revisión de posiciones existentes
3. ✅ Scan de nuevos setups
4. ✅ Plan de acción específico

**Output:** Te dirá exactamente qué hacer hoy.

### Opción 2: Paso a Paso Manual

```bash
# Paso 1: ¿Está el mercado favorable?
python market_health_check.py

# Si dice "GO" → Continúa
# Si dice "NO-GO" → No operes hoy (disciplina!)

# Paso 2: Escanear setups
python live_trading_scanner.py

# Paso 3: Ver tus posiciones actuales
python position_tracker.py
```

---

## 📊 DURANTE EL MERCADO (9:30 AM - 4:00 PM)

### 9:20 AM - Colocar Órdenes

Basado en el output del scanner:

**Para cada setup BUY_STOP:**
1. Abrir tu broker (Interactive Brokers, TD Ameritrade, etc.)
2. Crear orden:
   - Tipo: **Buy Stop Limit**
   - Stop Price: **[Precio del scanner]**
   - Limit Price: **[Stop + $0.50]**
   - Quantity: **[Calculado según tu risk]**
   - Duration: **Day Order**

**Para cada setup MANUAL_WATCH:**
1. Configurar alerta en TradingView
2. Monitor durante market hours

### 9:30 AM - Monitor Fills

```bash
# Actualizar precios cada 5-15 min
python position_tracker.py --update
```

### 10:30 AM - Cancelar Unfilled

Si alguna orden no se llenó en la primera hora:
- Cancelar la orden
- El setup no se activó = no es para hoy

### 12:00 PM - Mid-Day Check

```bash
python daily_workflow.py mid-day
```

### 4:00 PM - EOD Review

```bash
python daily_workflow.py market-close
```

---

## 💼 GESTIÓN DE POSICIONES

### Añadir Posición (cuando entras a un trade)

```bash
python position_tracker.py --add SYMBOL ENTRY STOP SHARES CAMINO

# Ejemplo:
python position_tracker.py --add AAPL 150.50 145.20 100 Camino1
```

### Actualizar Precios (durante el día)

```bash
python position_tracker.py --update
```

### Cerrar Posición (cuando sales del trade)

```bash
python position_tracker.py --close SYMBOL EXIT_PRICE

# Ejemplo:
python position_tracker.py --close AAPL 155.00
# Notas: "Take profit at +3R"
```

### Ver Historial

```bash
python position_tracker.py --history
```

---

## 🎓 EJEMPLO COMPLETO - DÍA TÍPICO

### 8:00 AM - Llego a la computadora

```bash
$ python morning_workflow.py

🛡️  MARKET HEALTH CHECK
========================
✅ SPY above EMA20
✅ Breadth improving
✅ Positive GEX

🎯 VERDICT: AGGRESSIVE MODE
Max positions: 5
Risk per trade: 2%

📍 STEP 2: EXISTING POSITIONS
Currently holding:
- NVDA: +$450 (+2.1R)

📍 STEP 3: NEW SETUPS
Found 2 actionable setups:
- AAPL: Camino 1 (Blue Sky) - BUY STOP $150.50
- TSLA: Camino 2 (VWAP Reclaim) - MANUAL WATCH

📋 ACTION PLAN:
1. Place buy stop for AAPL at $150.50
2. Set alert for TSLA VWAP cross
3. Monitor NVDA (consider partial exit at +3R)
```

### 9:20 AM - Coloco órdenes en mi broker

**En Interactive Brokers:**
- Order Type: Buy Stop Limit
- Symbol: AAPL
- Stop: $150.50
- Limit: $151.00
- Qty: 100 shares
- TIF: Day

### 9:30 AM - Apertura

```bash
$ python position_tracker.py --update

🔄 Updating prices...
  NVDA: $525.30 (was $520.00)
  
💼 ACTIVE POSITIONS
NVDA: Entry $500 → Current $525.30
P&L: +$2,530 (+5.06%) | +2.3R
```

### 9:45 AM - Mi buy stop se ejecutó

```bash
# Registrar en el tracker
$ python position_tracker.py --add AAPL 150.50 145.20 100 Camino1

✅ Position added: AAPL
   Entry: $150.50 x 100 shares = $15,050.00
   Stop: $145.20
   Risk: $530.00
```

### 12:00 PM - Check del mediodía

```bash
$ python position_tracker.py --update

💼 ACTIVE POSITIONS
NVDA: Entry $500 → Current $528 | +$2,800 (+5.6%) | +2.5R ✅
AAPL: Entry $150.50 → Current $152 | +$150 (+1%) | +0.3R ⚪
```

### 3:00 PM - NVDA alcanza +3R

Decision: Vender 50% para asegurar ganancia

**En el broker:** Vender 50 shares de NVDA a $530

```bash
# Actualizar en tracker (cerrar parcial)
$ python position_tracker.py --close NVDA 530.00
# Notes: "Partial exit 50% at +3R, rest running"
```

### 4:00 PM - Cierre del mercado

```bash
$ python daily_workflow.py market-close

🌆 END OF DAY REVIEW
====================

💼 ACTIVE POSITIONS
AAPL: Entry $150.50 → Current $151.80 | +$130 | +0.25R

📜 CLOSED TRADES (Today)
🟢 WIN | NVDA | Partial exit
   $500 → $530 | P&L: +$1,500 (+6%) | +3R

📊 STATISTICS
Today's P&L: +$1,630
Win rate (this week): 75%

📝 JOURNAL PROMPTS
1. What setups did I see today?
2. What did I execute and why?
...
```

---

## 🎯 REGLAS SIMPLES (Nunca las Rompas)

1. **SIEMPRE** verificar market health antes de escanear
   ```bash
   python market_health_check.py
   ```
   Si dice NO-GO → NO operes.

2. **SIEMPRE** definir stop loss ANTES de entrar

3. **SIEMPRE** calcular position size basado en risk
   ```
   Shares = (Account * Risk%) / (Entry - Stop)
   ```

4. **NUNCA** arriesgar más de 2% por trade

5. **NUNCA** tener más de 5 posiciones simultáneas

6. **NUNCA** operar si perdiste 6% en el día (STOP)

7. **SIEMPRE** registrar trades en el tracker

8. **SIEMPRE** journal al final del día

---

## 🚨 Troubleshooting

### "No data available"
- Verifica tu conexión a internet
- Revisa que OpenBB está funcionando
- Algunos tickers pueden no tener data

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Market closed"
- El scanner funciona mejor durante market hours
- Pre-market (8-9:30 AM) funciona para scan inicial
- After-hours (4-8 PM) para review

### "No setups found"
- Esto es NORMAL
- El sistema es selectivo
- Mejor no operar que forzar trades malos

---

## 📱 Pro Tips

### Tip 1: Automatiza con Cron

```bash
# Ejecutar health check automáticamente cada día a las 8:00 AM
crontab -e

# Añadir:
0 8 * * 1-5 cd /path/to/momentum-v2 && python morning_workflow.py
```

### Tip 2: Alertas por SMS

Instalar Twilio para recibir SMS cuando:
- Nuevo setup encontrado
- Stop loss tocado
- Profit target alcanzado

```bash
pip install twilio
# Configurar en config/settings.py
```

### Tip 3: Dashboard en Segundo Monitor

```bash
streamlit run app.py
```
Abrir en navegador → Dejar en segundo monitor con auto-refresh

### Tip 4: Paper Trading Primero

Usar Interactive Brokers Paper Trading:
- Misma plataforma que live
- $100,000 virtual
- Practica 2 semanas antes de live

---

## 📚 Siguiente Paso

Una vez que hayas operado 1 semana:

1. **Leer la guía completa:**
   ```bash
   less LIVE_TRADING_GUIDE.md
   ```

2. **Optimizar tu estrategia:**
   - Ajustar watchlist según tus resultados
   - Refinar risk management
   - Implementar broker API

3. **Revisar estadísticas:**
   ```bash
   python position_tracker.py --history
   ```
   - ¿Win rate > 50%?
   - ¿Avg R > 1.5?
   - ¿Siguiendo el plan?

---

## ✅ Checklist: ¿Estás Listo?

- [ ] Backtest validado (win rate > 50%)
- [ ] Setup técnico funcionando
- [ ] Watchlist preparada
- [ ] Broker cuenta fondeada
- [ ] Plan de risk management definido
- [ ] Mental preparado para pérdidas
- [ ] 2 semanas de paper trading completadas

Si tienes 7/7 ✅ → **¡Estás listo para live trading!**

Si no → **Sigue practicando con paper trading**

---

**¡Éxito en tu trading! 🚀**

*"The goal is not to trade every day, but to trade the best days."*
