# Triad Momentum System - Quick Reference

## 📋 Daily Commands

### 1. Scan Watchlist (Pre-Market)
```bash
python3 example_scan.py
```
Escanea tu watchlist completa y genera señales para el día.

### 2. Analyze Single Symbol
```bash
python3 quick_analysis.py SYMBOL [ACCOUNT_SIZE]
```
Análisis profundo de un símbolo específico.

**Ejemplos:**
```bash
python3 quick_analysis.py RDDT
python3 quick_analysis.py NVDA 50000
python3 quick_analysis.py CEG 250000
```

### 3. Test System
```bash
python3 test_system.py
```
Verifica que el sistema funciona correctamente.

### 4. View Logs
```bash
tail -f logs/triad_$(date +%Y%m%d).log
```
Monitorea logs en tiempo real.

---

## 🎯 Los 3 Caminos (Quick Reference)

### Camino 1: Blue Sky Breakout 🚀
**Cuando:** Base + AVWAP convergen (< 2% de diferencia)

**Setup:**
- Entry: Base High + $0.05
- Stop: Base Low o Entry - 1 ADR
- Size: 100% (0.5% risk)
- Order: **BUY STOP** (automático)

**Acción:** Coloca orden pre-market y deja correr.

---

### Camino 2: VWAP Reclaim 🔄
**Cuando:** Gap down + mercado débil + precio recupera VWAP

**Setup:**
- Entry: Al cruzar VWAP hacia arriba
- Stop: **LOD (Low of Day)** ⚠️
- Size: 50% (0.25% risk)
- Order: **MANUAL WATCH**

**Acción:** Monitorea en vivo, compra cuando cruza VWAP.

---

### Camino 3: Safety Filter 🛡️
**Cuando:** AVWAP está > 5% arriba del precio actual

**Setup:**
- Entry: AVWAP + $0.05
- Stop: Entry - 1 ADR
- Size: 100% (0.5% risk)
- Order: **WAIT/ALERT**

**Acción:** NO comprar hoy. Alerta en AVWAP.

---

## 📊 Position Sizing Calculator

```python
from src.utils.risk_calculator import RiskCalculator

calc = RiskCalculator()
result = calc.calculate_position_size(
    account_size=100000,
    risk_pct=0.005,        # 0.5% for Camino 1 & 3
    entry_price=100.05,
    stop_loss=95.20,
    multiplier=1.0         # 0.5 for Camino 2
)

print(f"Buy {result['shares']} shares")
```

---

## 🔧 Configuration Files

### Edit Watchlist
`config/watchlist.py`

### Edit Parameters
`config/settings.py`
- `RISK_PER_TRADE = 0.005` (0.5%)
- `BLUE_SKY_OFFSET = 0.05` ($0.05)
- `AVWAP_TOLERANCE = 0.02` (2%)

---

## 📈 Signal Interpretation

### BUY_STOP
✅ **EJECUTAR** - Coloca orden automática

### MANUAL_WATCH
👀 **MONITOREAR** - Espera confirmación en vivo

### WAIT
⏳ **ESPERAR** - Alerta en el precio indicado

### NO_SETUP
⛔ **SKIP** - No hay setup hoy

---

## 🚨 Critical Rules

1. **Camino 2 = LOD Stop** (no negociable)
2. **Respeta el Safety Filter** (Camino 3)
3. **No fuerces trades** que no cumplen criterios
4. **Size correcto** = 0.5% para C1/C3, 0.25% para C2

---

## 📱 Integration with Trading Platform

### TradingView
1. Add "VWAP" indicator
2. Add "Anchored VWAP" (anchor to ATH)
3. Set alerts at key levels

### ThinkorSwim
```
/VWAP      # Intraday VWAP
Study > VWAP (anchored to high)
```

### Webull
- Indicators > VWAP
- Set price alerts

---

## 🐛 Common Issues

**"No setups found"**
- Normal! System is disciplined
- Don't force trades

**"Base not detected"**
- Stock not in consolidation
- Try again tomorrow

**"AVWAP too far above"**
- Safety Filter active
- Wait for AVWAP breakout

**"Market weak but no VWAP reclaim"**
- Price didn't recover
- Skip this one

---

## 📚 Full Documentation

- **README.md** - System overview
- **USAGE.md** - Detailed daily workflow
- **This file** - Quick reference

---

## 🎓 Learning Path

1. **Week 1:** Run `example_scan.py` daily, observe patterns
2. **Week 2:** Use `quick_analysis.py` to study individual setups
3. **Week 3:** Paper trade Camino 1 (easiest)
4. **Week 4:** Add Camino 2 (more active)
5. **Week 5+:** Full system with position sizing

---

## 💡 Pro Tips

- Run scanner **before market open** (9:00 AM ET)
- Keep **watchlist under 20** symbols (quality > quantity)
- **Log every trade** to review patterns
- **Respect the system** - no discretionary overrides
- **ATH AVWAP is the boss** - always check it first

---

**"No perseguimos precios; capturamos la liberación de energía cuando la oferta desaparece."**

🎯 **Disciplina > Predicción**
