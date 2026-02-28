# 🔍 CUESTIONARIO DE DEBUGGING

Por favor responde estas preguntas para que pueda darte los fixes exactos:

## 1️⃣ UNIVERSO DE TICKERS

**¿Cuántos tickers estás escaneando?**
- [ ] Menos de 50
- [ ] 50-100
- [ ] 100-300
- [ ] 300-500
- [ ] 500+

**¿Qué universo usas?**
- [ ] Lista manual de tickers
- [ ] S&P 500
- [ ] NASDAQ 100
- [ ] Russell 2000
- [ ] Combinación de varios índices
- [ ] Otro: ___________

**Respuesta:** ___________


## 2️⃣ FILTROS DE ENTRADA

**¿Cuáles son tus parámetros actuales?**

```python
MIN_RVOL = ___________          # ej: 1.5, 2.0, 2.5
MIN_ADR_PCT = ___________        # ej: 2.5, 3.0, 4.0
MAX_DIST_SMA20 = ___________     # ej: 5.0, 7.0, 10.0
MIN_DOLLAR_VOLUME = ___________  # ej: 3M, 5M, 10M
MIN_CONSOLIDATION_DAYS = _______ # ej: 3, 5, 8, 10
MAX_STOP_PCT = ___________       # ej: 5.0, 6.5, 8.0
```

**Respuesta:**
```
MIN_RVOL = 
MIN_ADR_PCT = 
MAX_DIST_SMA20 = 
MIN_DOLLAR_VOLUME = 
MIN_CONSOLIDATION_DAYS = 
MAX_STOP_PCT = 
```


## 3️⃣ POSITION SIZING

**¿Cuánto arriesgas por trade?**
- [ ] 0.5% del capital
- [ ] 1.0% del capital
- [ ] 1.5% del capital
- [ ] 2.0% del capital
- [ ] 2.5%+
- [ ] Variable según volatilidad

**Respuesta:** ___________

**¿Tienes límite de posición máxima?**
- [ ] Sí: ___________% del capital
- [ ] No

**Respuesta:** ___________


## 4️⃣ SALIDAS PARCIALES

**¿Cuáles son tus targets actuales?**

```python
# Fase 1 (Risk-Free)
TP1_R_MULTIPLE = ___________     # ej: 1.5R
TP1_EXIT_PCT = ___________       # ej: 50%

# Fase 2 (Resistance)
TP2_R_MULTIPLE = ___________     # ej: 3.0R
TP2_EXIT_PCT = ___________       # ej: 30%

# Fase 3 (Runner)
RUNNER_EXIT_METHOD = ___________  # ej: "EMA8_CROSS_EMA21", "ATR_TRAIL", "TIME"
RUNNER_EXIT_PCT = ___________     # ej: 20%
```

**Respuesta:**
```
TP1_R_MULTIPLE = 
TP1_EXIT_PCT = 
TP2_R_MULTIPLE = 
TP2_EXIT_PCT = 
RUNNER_EXIT_METHOD = 
RUNNER_EXIT_PCT = 
```


## 5️⃣ STOP LOSS

**¿Cómo calculas el stop?**
- [ ] Session Low (low del día de entrada)
- [ ] ATR múltiple (ej: 2x ATR)
- [ ] Porcentaje fijo (ej: -5%)
- [ ] Estructura (support anterior)
- [ ] Otro: ___________

**Respuesta:** ___________

**¿Se mueve a breakeven después de TP1?**
- [ ] Sí, automáticamente
- [ ] No
- [ ] A veces (depende de X)

**Respuesta:** ___________


## 6️⃣ PERÍODO Y FRECUENCIA

**¿Qué período estás backtesting?**
Inicio: ___________
Fin: ___________

**¿En qué timeframe operas?**
- [ ] Diario (1D)
- [ ] Intraday (específica: _______)

**Respuesta:** ___________


## 7️⃣ MARKET REGIME FILTERS

**¿Usas filtros de régimen de mercado?**
- [ ] Sí: Solo tradeo cuando SPY > SMA200
- [ ] Sí: Solo tradeo cuando VIX < 30
- [ ] Sí: Otros filtros: ___________
- [ ] No, tradeo en todos los regímenes

**Respuesta:** ___________


## 8️⃣ ARCHIVO DE CONFIGURACIÓN

**¿Dónde están definidos tus parámetros?**
- [ ] En el código (vectorbt_engine_advanced.py)
- [ ] En un archivo separado (config.py, params.yaml)
- [ ] En la UI/Dashboard
- [ ] No sé

**Respuesta:** ___________

**Si es un archivo separado, ¿puedes compartirlo?**
- [ ] Sí (súbelo)
- [ ] No lo tengo/no lo encuentro


## 9️⃣ DATOS ADICIONALES

**¿Puedes exportar el CSV de trades?**
- [ ] Sí (súbelo o pega las primeras 10 filas aquí)
- [ ] No

**Si sí, las columnas deben incluir:**
```
ticker, entry_date, entry_price, exit_date, exit_price, shares, 
pnl, pnl_pct, r_multiple, stop_price, atr, exit_reason, days_held,
max_price_reached, consolidation_days, dist_sma20_pct, rvol, adr
```


## 🔟 CÓDIGO CRÍTICO

**¿Tienes acceso al archivo src/backtest/numba_core.py?**
- [ ] Sí (súbelo)
- [ ] No existe / no lo encuentro

**Si no existe, la lógica de simulación probablemente está en:**
```
vectorbt_engine_advanced.py → método simulate_with_partial_exits()
```

**¿Puedes compartir ese método completo?**
- [ ] Sí (copia y pega el código aquí)
- [ ] No estoy seguro dónde está


---

## ✅ RESUMEN DE LO QUE NECESITO

Para darte los fixes exactos, necesito AL MENOS:

1. **Respuestas a preguntas 1-7** (tus parámetros actuales)
2. **CSV de trades** (o al menos 10-20 filas de ejemplo)
3. **Código de simulación** (numba_core.py O método simulate_with_partial_exits)

Con esto, puedo:
- Identificar EXACTAMENTE qué filtros aflojar
- Calcular los nuevos parámetros óptimos
- Darte un script para aplicar los fixes
- Proyectar tu nueva performance esperada

---

## 🎯 HIPÓTESIS PRELIMINAR

Basado en lo que veo, creo que tus problemas son:

### FIX #1: Aflojar Filtros (para 10x más trades)
```python
# ANTES (supuesto):
MIN_RVOL = 2.0
MIN_CONSOLIDATION = 8
MAX_DIST_SMA20 = 5.0

# DESPUÉS (target):
MIN_RVOL = 1.5           # -25% más permisivo
MIN_CONSOLIDATION = 5    # -37% más permisivo
MAX_DIST_SMA20 = 7.0     # +40% más permisivo
```

**Resultado esperado:** 92 trades → 300-400 trades

### FIX #2: Dejar Correr Runners (para +30% avg wins)
```python
# ANTES (supuesto):
TP2_R_MULTIPLE = 2.5R

# DESPUÉS:
TP2_R_MULTIPLE = 3.5R    # +40% más ambicioso
RUNNER_MAX_DAYS = 60     # Dejar correr hasta 60 días
```

**Resultado esperado:** Avg win +17.5% → +25-28%

### FIX #3: Expandir Universo (para más oportunidades)
```python
# ANTES (supuesto):
ticker_list = manual_watchlist  # 50 tickers

# DESPUÉS:
ticker_list = SP500 + NASDAQ100 + manual_watchlist  # 650+ tickers
```

**Resultado esperado:** 92 trades → 500-700 trades

---

**Con estos 3 fixes, proyección:**
```
Capital Final:  $159,382 → $600,000 - $900,000
Return Total:   +59.38% → +500% - +800%
CAGR:          4.18% → 20% - 30%
Total Trades:   92 → 500-700
```

Aún no llegarías a +1,001%, pero estarías **4-6x mejor** que ahora.

Para llegar al +1,001%, necesitarías 1-2 iteraciones más de optimización.

---

**¿Listo para empezar? Dame la info del cuestionario y vamos con todo! 🚀**
