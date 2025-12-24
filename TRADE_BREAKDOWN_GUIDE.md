# 📊 Trade Breakdown Guide - Análisis Completo de Operaciones

## 🎯 Objetivo
Documentar CADA trade con un desglose completo que incluya:
1. **Pre-Trade Checklist** - Configuración antes de entrar
2. **Entry Context** - Contexto de mercado al momento de entrada
3. **Partial Exits** - Salidas escalonadas (Fase 1, 2, 3)
4. **Final Exit** - Cierre completo con P&L total

---

## 📋 ESTRUCTURA DE UN TRADE COMPLETO

### 1. PRE-TRADE CHECKLIST (Antes de Entrar)

Estos son los parámetros que se verifican ANTES de ejecutar la entrada:

```yaml
Symbol: AAPL
Entry Date: 2024-01-15
Signal Type: BLUE_SKY

🔍 PRE-TRADE CONFIGURATION:
  ├─ Entry Price:      $180.00
  ├─ Initial Stop:     $175.00
  ├─ R (Risk):         $5.00
  ├─ Position Size:    100 shares
  ├─ Initial Risk:     $500 (100 × $5)
  ├─ Account Equity:   $100,000
  ├─ Risk %:           0.5%
  └─ Entry Stage:      FULL (or QUARTER si hay earnings)

📊 MARKET CONTEXT (Entry Day):
  ├─ RVOL:             2.15x ✅ (> 1.5x threshold)
  ├─ Trend:            Uptrend ✅ (Price > SMA20)
  ├─ SMA 20:           $178.50
  ├─ Current Price:    $180.00
  ├─ ADR (20d avg):    $4.50 (2.5% del precio)
  ├─ Avg Volume:       45.2M
  ├─ Entry Volume:     97M (2.15x RVOL)
  └─ SPY Context:      Favorable (SPY > EMA20)

🎯 TAKE PROFIT TARGETS:
  ├─ TP1 (+1R):        $185.00 (Fase 1: 50%)
  ├─ TP2 (+2.5R):      $192.50 (Fase 2: 30%)
  └─ Runner:           20% trail con EMA 8/21

✅ FILTERS PASSED:
  ├─ RVOL Filter:      ✅ 2.15x > 1.5x
  ├─ Trend Filter:     ✅ Uptrend (Price > SMA20)
  ├─ Volume Filter:    ✅ Institutional volume
  └─ Market Context:   ✅ SPY favorable
```

---

### 2. FASE 1 - CONVERSIÓN A RISK-FREE (+1R)

**Trigger:** Precio alcanza +1R ($185.00)

```yaml
📅 Exit Date: 2024-01-16 (1 día held)
💰 Exit Price: $185.23
📦 Shares Sold: 50 (50% de posición)
💵 PnL Partial: +$261.50 (50 × $5.23)
📈 Return: +2.9%

🔄 ADJUSTMENTS:
  ├─ Stop Loss: $175 → $180 (BREAKEVEN) ✅
  ├─ Position: 100 → 50 shares
  └─ Status: RISK-FREE (no puede perder dinero)

📊 POSITION STATUS:
  ├─ Capital Secured: $9,000 (50 shares × $180)
  ├─ Profit Locked: +$261.50
  ├─ Remaining: 50 shares @ $180 cost basis
  └─ Risk: $0 (stop at breakeven)
```

---

### 3. FASE 2 - TOMA DE BENEFICIOS EN RESISTENCIA (+2.5R)

**Trigger:** Precio alcanza +2.5R ($192.50) o ADR completo

```yaml
📅 Exit Date: 2024-01-18 (3 días held total)
💰 Exit Price: $193.45
📦 Shares Sold: 30 (30% de posición ORIGINAL)
💵 PnL Partial: +$403.50 (30 × $13.45)
📈 Return: +7.5%

🎯 TRIGGER: +2.5R Resistance level reached

📊 POSITION STATUS:
  ├─ Total Profit So Far: +$665 (Fase 1 + Fase 2)
  ├─ Remaining: 20 shares (runner)
  ├─ Cost Basis: $180 (breakeven)
  └─ Risk: $0 (still at breakeven stop)
```

---

### 4. FASE 3 - RUNNER TRAILING STOP (EMA 8/21)

**Trigger:** EMA 8 cruza por debajo de EMA 21

```yaml
📅 Exit Date: 2024-01-25 (10 días held total)
💰 Exit Price: $198.20
📦 Shares Sold: 20 (último 20% - runner)
💵 PnL Partial: +$364 (20 × $18.20)
📈 Return: +10.1%

🏁 EXIT REASON: EMA 8 crossed below EMA 21 (trend change)

📊 TRADE COMPLETION:
  ├─ Entry: $180.00 (100 shares)
  ├─ Exits:
  │   ├─ Fase 1: $185.23 (50 sh) → +$261.50
  │   ├─ Fase 2: $193.45 (30 sh) → +$403.50
  │   └─ Fase 3: $198.20 (20 sh) → +$364.00
  ├─ Total PnL: +$1,029.00
  ├─ Total Return: +10.3% (weighted avg)
  ├─ R-Multiple: +2.06R ($1,029 / $500 risk)
  ├─ Days Held: 10
  └─ Status: ✅ WINNING TRADE
```

---

## 📊 REGISTROS GENERADOS

### A. Trade Record Principal (backtest_results.csv)

```csv
symbol,entry_date,exit_date,entry_price,exit_price,initial_shares,shares,pnl,return_pct,signal_type,tp1_executed,tp2_executed,final_shares_pct,R_inicial,adr_valor,entry_stage,initial_stop_loss,context_rvol,context_trend,context_price,context_sma20,reason
AAPL,2024-01-15,2024-01-25,180.00,198.20,100,20,1029.00,10.3,BLUE_SKY,True,True,20.0,5.00,4.50,FULL,175.00,2.15,Uptrend,180.00,178.50,FASE_3_EMA_CROSS
```

### B. Partial Exits Records (partial_exits.csv)

```csv
symbol,phase,exit_date,entry_date,entry_price,exit_price,shares_sold,shares_remaining,pct_sold,pnl,return_pct,reason,signal_type,R_inicial,adr_valor,context_rvol,context_trend
AAPL,FASE_1,2024-01-16,2024-01-15,180.00,185.23,50,50,50.0,261.50,2.9,TP1: +1R Risk-Free Conversion,BLUE_SKY,5.00,4.50,2.15,Uptrend
AAPL,FASE_2,2024-01-18,2024-01-15,180.00,193.45,30,20,30.0,403.50,7.5,TP2: +2.5R Resistance,BLUE_SKY,5.00,4.50,2.15,Uptrend
```

---

## 🔍 ANÁLISIS POR TRADE

### Ejemplo: Trade AGI (2023-11-28) - RECHAZADO

```yaml
Symbol: AGI
Entry Date: 2023-11-28 (ATTEMPTED)
Signal Type: BLUE_SKY (REJECTED)

❌ PRE-TRADE FILTERS FAILED:

📊 MARKET CONTEXT:
  ├─ RVOL:             1.39x ❌ (< 1.5x threshold)
  ├─ Trend:            Uptrend ✅
  ├─ Current Price:    $14.36
  ├─ SMA 20:           $13.85
  └─ Avg Volume:       2.9M

🚫 REJECTION REASON:
   "REJECTED Blue Sky: RVOL (1.39x) is below 1.5x threshold.
    Need RVOL > 1.5x (ideally > 2.0x) for institutional confirmation."

📝 TRADE STATUS: NOT EXECUTED
   ├─ Filtered Out: ✅
   ├─ Risk Avoided: $500 (potential loss prevented)
   └─ System Health: Working as designed
```

---

## 📈 BENEFICIOS DE ESTE SISTEMA

### 1. **Transparencia Total**
- Cada decisión es auditable
- Pre-trade checklist documenta configuración
- Partial exits registradas individualmente

### 2. **Análisis Profundo**
- Puedes ver qué % de trades llegó a cada fase
- Identificar patrones en salidas exitosas
- Optimizar triggers de cada fase

### 3. **Accountability**
- Trade record principal muestra resultado final
- Partial exits CSV muestra la progresión
- Logs detallan cada paso en tiempo real

### 4. **Optimización**
- Comparar trades con/sin TP1/TP2
- Analizar si runners aportan valor
- Ajustar porcentajes de salida por fase

---

## 🧪 QUERIES DE ANÁLISIS

### Trades que llegaron a risk-free (TP1)
```python
df[df['tp1_executed'] == True]
```

### Trades con runner completo (Fase 3)
```python
df[(df['tp1_executed'] == True) & (df['tp2_executed'] == True) & (df['final_shares_pct'] == 20)]
```

### Distribución de salidas
```python
df['final_shares_pct'].value_counts()
# 100% = Solo stop loss (no llegó a TP1)
# 50%  = Llegó a TP1 pero no a TP2
# 20%  = Completó todas las fases
```

### P&L por fase
```python
partial_df.groupby('phase')['pnl'].sum()
```

---

## 📝 LOGS EN PRODUCCIÓN

Durante el backtest, verás logs como:

```
✅ FASE 1: AAPL - 50% vendido en +1R ($185.23), Stop → BE, PnL: $261.50
✅ FASE 2: AAPL - 30% vendido en +2.5R ($193.45), PnL: $403.50
🏁 FASE 3: AAPL - cerrado por EMA_CROSS ($198.20), Total: +$1,029
```

```
🚫 REJECTED Blue Sky: AGI - RVOL (1.39x) < 1.5x threshold
```

---

## 🎯 PRÓXIMOS PASOS

1. **Ejecutar backtest** y generar ambos CSVs
2. **Analizar partial_exits.csv** para ver progresión
3. **Comparar métricas** por fase (¿qué fase genera más profit?)
4. **Optimizar triggers** si es necesario
5. **Crear dashboard** para visualizar salidas parciales

---

✨ **Sistema completo de tracking y análisis listo para producción**
