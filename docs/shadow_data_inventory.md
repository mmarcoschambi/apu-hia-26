# Shadow Data Inventory — Sandbox Historico

> Issue: #30 | Rama: feat/audit-shadow-data-inventory
> Fecha: 2026-06-04 | Auditor: Orquestador IA

---

## 1. Triad Scanner Logs

### Archivos existentes

| Archivo | Fecha | Lineas | Tamanio | Senales | Actions |
|---------|-------|--------|---------|---------|---------|
| `logs/triad_20251219.log` | 2025-12-19 | 2,385 | 204 KB | 48 | 47x NO_SETUP, 1x BUY_STOP |
| `logs/triad_20251224.log` | 2025-12-24 | 26 | 8 KB | 1 | 1x NO_SETUP |
| `logs/triad_20251229.log` | 2025-12-29 | 1,362 | 124 KB | 20 | 20x NO_SETUP |
| `logs/triad_20260501.log` | 2026-05-01 | 0 | 0 B | 0 | empty |
| `logs/triad_20260504.log` | 2026-05-04 | 0 | 0 B | 0 | empty |
| `logs/triad_20260505.log` | 2026-05-05 | 32,035 | 2.7 MB | 478 | 478x NO_SETUP |
| `logs/triad_20260506.log` | 2026-05-06 | 4,286 | 364 KB | 63 | 63x NO_SETUP |
| `logs/triad_20260507.log` | 2026-05-07 | 2,059 | 192 KB | 23 | 23x NO_SETUP |
| `logs/triad_20260508.log` | 2026-05-08 | 0 | 0 B | 0 | empty |
| `logs/triad_20260521.log` | 2026-05-21 | 0 | 0 B | 0 | empty |
| `logs/triad_20260604.log` | 2026-06-04 | 0 | 0 B | 0 | empty |

### Formato

Log estructurado timestamp + modulo + nivel:
```
2026-05-05 13:00:27,589 - src.core.scanner - INFO - Action: NO_SETUP
2026-05-05 13:00:27,589 - src.core.scanner - INFO - Action: BUY_STOP
```

### Campos detectables por senal

- **Ticker**: linea `Scanning <TICKER>`
- **Timestamp**: fecha/hora del scan
- **Action**: NO_SETUP, BUY_STOP (1 solo caso historico)
- **Position Size**: % del standard
- **Reasoning**: texto libre de causa
- **Indicadores**: Base detected, AVWAP, ATH, Distance to AVWAP, Intraday VWAP, Above VWAP, Gap Down
- **Market Context**: SPY price/EMA, QQQ, VIX, Top 3 Sectors, Gap/Change

### Rango de fechas
- Con datos: 2025-12-19 a 2026-05-07 (discontinuo, solo ~6 dias con datos reales)
- GAPs: 2025-12-30 a 2026-04-30 (~4 meses sin datos), mayo 2026 salta dias

### Volumen
- ~48 + 1 + 20 + 478 + 63 + 23 = ~633 senales totales
- Solo **1 senal actionable (BUY_STOP)** en toda la serie historica

---

## 2. signals_a_today.csv

### Ubicacion
`data/signals_a_today.csv`

### Formato
CSV con 14 columnas, 50 lineas (header + 49 registros):

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| `signal_date` | date | Fecha de la senal |
| `ticker` | str | Simbolo |
| `signal_price` | float | Precio al momento de la senal |
| `entry_price_actual` | float | Precio de entrada real |
| `slippage_pct` | float | Diferencia % entre signal y entry |
| `entry_score` | float | Score compuesto (0-1) |
| `rs_percentile` | float | Percentil RS (0-100) |
| `rvol` | float | Volumen relativo |
| `adr_pct` | float | Average Daily Range % |
| `dist_sma20` | float | Distancia % a SMA20 |
| `dollar_vol_M` | float | Volumen en dolares (millones) |
| `stop_price` | float | Precio de stop loss |
| `tp1` | float | Take profit 1 |
| `tp2` | float | Take profit 2 |

### Fechas
- **2024-01-03**: 5 registros (MSTR, URI, TFC, HIMX, SEDG, SEE)
- **2026-04-24**: 44 registros

### Problemas detectados
- Contiene **tickers duplicados/alias aparentes**: CYBR/CYBR2, ELPW/ELRA/ELRC/ELRE, CAKE/CAKR, BBBB/BBBY, BLMN/BLMT, BEPC/BEPH/BEPI, EAXR/EB/EBBGF/EBBNF, JLMI/JLL, KIM/KMX/KSS/KSU, BTC1/BTCM
- Sugiere que el CSV fue generado con datos de prueba/test o con alias de tickers
- Solo 2 fechas distintas: no es un acumulador diario

### Acumulacion
NO acumula dias. Contiene solo **2 batches** (2024-01-03 y 2026-04-24). Probablemente sobrescribe o es manual.

---

## 3. cron_finviz_monitor.log

### Ubicacion
`logs/vps/cron_finviz_monitor.log`

### Formato
Log plano con timestamp + nivel. Generado por cron en VPS. Contiene:

#### Secciones por corrida
1. **Cabecera**: `PAPER FINVIZ - PRE-MARKET`, fecha, modo PRODUCTION
2. **Config**: risk FIXED_DOLLAR, periodo de backtest, universo N tickers
3. **Cache check**: caché SQL, screener cache
4. **Regime filter**: SPY > SMA50, VIX check
5. **Hot Sectors table**: 11 sectores (XLK..XLU) con ranking, cambio, tradeable/blocked
6. **HIGH QUALITY SETUPS**: ticker, RS, breakout status, break level, dist SMA20, RVOL
7. **Exit distribution**: STOP/TP1/TP2/RUNNER counts
8. **Alerts**: near-threshold candidates with proximity_score

### Fechas cubiertas
2026-05-08 a 2026-05-19 (ultimo contenido visible ~12 dias)

### Columnas detectables (sector rotation)
```
Sector | Indicador | Ranking previo→actual | Performance % | Estado
```

### Columnas detectables (high quality setups)
```
Ticker | RS | Breakout? | Break level | Dist SMA20 % | RVOL | Waiting threshold
```

### Volumen
9,344 lineas, 844 KB. ~12 dias de ejecucion continua.

### Observacion
Contiene error generalizado `no such column: sma20` en la cache SQL, lo que fuerza descarga masiva de 590 tickers por yfinance en cada corrida.

---

## 4. Paper Trading Logs

### Archivos existentes

| Archivo | Fecha | Lineas | Tamanio | Signals | Contenido |
|---------|-------|--------|---------|---------|-----------|
| `logs/paper_trading_20260409.log` | 2026-04-09 | 584 | 48 KB | 0 | Pre-market checks (placeholder, 0 senales) |
| `logs/paper_trading_20260415.log` | 2026-04-15 | 113 | 9.5 KB | 0 | Pre-market checks (0 senales, solo candidatos) |
| `logs/paper_trading_20260416.log` | 2026-04-16 | 748 | 65 KB | 0 | Pre-market completo: watchlist, alerts, ranking |
| `logs/paper_trading_20260417.log` | 2026-04-17 | 189 | 17 KB | 0 | Pre-market checks (0 senales) |

### Formato
Log con timestamp + nivel, bloques de ~6 pasos:

```
[DATETIME] [INFO] ================
[DATETIME] [INFO] PRE-MARKET CHECKS
[DATETIME] [INFO] 📅 Date: 2026-04-16
[DATETIME] [INFO] 🎯 Active strategies: ['combo_pure_momentum']
[DATETIME] [INFO]   [1/6] Checking data cache...
[DATETIME] [INFO]   [2/6] Validating regime filter (SPY>SMA50)...
[DATETIME] [INFO]   [3/6] Loading universe...
[DATETIME] [INFO]   [4/6] Checking combo configs & validation status...
[DATETIME] [INFO]   [5/6] Generating signals...
[DATETIME] [INFO]   [6/6] Saving watchlist...
```

### Senales detectables (solo ranking, no entradas)
- `score=0.XXX RS=XX%` por ticker
- Proximity_score para candidatos near-threshold
- NO hay entradas reales (BUY/SELL/ORDER) en ningun archivo

### Rango de fechas
Solo 4 dias en abril 2026: 09, 15, 16, 17. Gaps evidentes: 10-14, 18-30.

---

## 5. Analisis de Completitud

### Metricas globales

| Fuente | Registros totales | Acciones reales | Rango temporal | Formato parseable |
|--------|-------------------|-----------------|----------------|-------------------|
| Triad logs | ~633 senales | 1 (BUY_STOP) | 6 dias en 4 meses | SI (regex) |
| signals_a_today.csv | 49 entradas | 49 entradas | 2 fechas | SI (CSV) |
| cron_finviz_monitor.log | ~12 dias de corridas | 0 directas | 2026-05-08 a 05-19 | SI (regex) |
| Paper trading logs | 0 senales | 0 | 4 dias en abril | Parcial (solo ranking) |

### Gaps identificados

1. **Triad logs**: ~4 meses sin datos (2025-12-30 a 2026-04-30). Mayo 2026 salta dias (solo 3 dias con datos de 11 archivos)
2. **signals_a_today.csv**: Solo 2 fechas, no es fuente confiable para reconstruccion diaria
3. **Paper trading logs**: Solo 4 dias en abril, sin entradas reales
4. **cron_finviz_monitor.log**: Mejor cobertura continua pero solo ~12 dias
5. **Ninguna fuente** tiene columna de universo/sector (pedido en issue)
6. **No hay logs de ejecucion de trades** (solo pre-market scans y alertas)

### Que fuente es mas completa

**cron_finviz_monitor.log** es la fuente mas rica para reconstruccion porque:
- Cobertura diaria continua (~12 dias)
- Incluye sector rotation, high quality setups, exit distributions
- Tiene el contexto de configuracion de produccion
- Incluye alertas near-threshold

Sin embargo, para senales reales dia a dia, la mejor fuente combinada es **signals_a_today.csv + Triad logs** porque:
- signals_a_today.csv tiene precios de entrada reales con stops y take profits
- Triad logs tienen el contexto de escaneo ticker por ticker

### Recomendacion de fuente primaria para ETL (issue siguiente)

**Fuente primaria: cron_finviz_monitor.log**

Razon:
1. Unico archivo con cobertura continua multi-dia
2. Formato consistentemente parseable (regex sobre log lines)
3. Contiene tanto metrica de mercado (sectores) como senales individuales (high quality setups)
4. Incluye exit distributions que permiten tracking de performance
5. Es el archivo que VPS genera activamente (seguimiento en vivo)

**Fuente secundaria: signals_a_today.csv** para los precios de entrada reales con stops/TPs (aunque los datos parecen tener problemas de calidad con alias de tickers).

**No recomendar como fuente primaria:**
- Triad logs: demasiado esporadicos, ~99.9% NO_SETUP sin valor de reconstruccion
- Paper trading logs: 0 senales reales, solo ranking de candidatos

---

## 6. Next Step Completed: ETL Shadow Sandbox

### Resumen
Se implemento el ETL shadow (`src/shadow/etl.py`) que parsea `cron_finviz_monitor.log` y produce dataset estructurado en `outputs/shadow_sandbox/`.

### Output generado
- `outputs/shadow_sandbox/finviz_runs/<date>/setups.csv` — setups de alta calidad con sector mapping y estado shadow
- `outputs/shadow_sandbox/finviz_runs/<date>/sectors.csv` — rotacion sectorial (formato hot sectors + money flow)
- `outputs/shadow_sandbox/finviz_runs/<date>/alerts.csv` — alertas near-threshold (no disponibles en ventana actual)
- `outputs/shadow_sandbox/finviz_runs/<date>/run_context.json` — configuracion de produccion
- `outputs/shadow_sandbox/summary.md` — resumen global y por dia
- `outputs/shadow_sandbox/data_quality.json` — reporte de calidad por corrida

### Resultados sobre datos reales
- **8 dias** de corridas detectados (2026-05-08 a 2026-05-19)
- **2 dias con setups** (2026-05-18 y 2026-05-19)
- **2 setups totales** (ADM → XLB, NXPI → XLK), ambos candidatos shadow aptos
- **0 filtrados por XLV** (ningun setup en healthcare)
- **1 warning de cache** (`no such column: sma20` en 2026-05-08)
- **Join con signals_a_today.csv**: disponible pero sin matches en ventana actual

### Parse tolerance verificada
- ✅ Dos formatos de sector (HOT SECTORS simple y SECTOR MONEY FLOW con emojis)
- ✅ WATCHLIST DIAGNOSTIC ignorado (formato multi-linea no parseable)
- ✅ Varias corridas intra-dia acumuladas en un mismo run
- ✅ Bloques incompletos tolerados
- ✅ Dedup de setups duplicados dentro del mismo dia
- ✅ Tickers no mapeados reportados en quality report

### Tests
19 tests en `tests/test_shadow_etl.py` (unitarios + integracion con log real).
