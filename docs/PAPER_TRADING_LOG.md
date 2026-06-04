# Paper Trading Log — combo_pure_momentum

## Inicio: 2026-05-09
**Status:** PAPER_TRADING_ACTIVE  
**Capital paper:** $100,000  
**Protocolo:** Etapa 6 del ciclo de investigación

---

## Parámetros en producción (congelados)

| Parámetro | Valor | Tier |
|---|---|---|
| min_rvol | 1.5 | Tier 2 |
| min_adr | 1.2 | Tier 2 |
| max_positions | 6 | Tier 3 |
| max_position_pct | 20% | Tier 3 |
| max_exposure_pct | 75% | Tier 3 |
| be_threshold_r | 1.0R | Tier 3 |
| tp1_pct / tp2_pct / runner | 50/30/20% | Tier 1 |
| regime_blocked | [4] | Tier 2 |
| vix_max | 30.0 | Tier 2 |

**Regla de freeze:** ningún parámetro se modifica durante Etapa 6 sin volver a Etapa 2.

---

## Criterios GO → Etapa 7 (Producción real)

| Métrica | Umbral mínimo | Ventana |
|---|---|---|
| Señales/semana | ≥ 2 | 4 semanas seguidas |
| Win rate paper | ≥ 45% | 20+ trades |
| Slippage observado | ≤ 30bps vs. precio señal | Promedio |
| Latencia señal→ejecución | < 15 min pre-market | Todos los días |
| Consistencia señal vs. backtest | > 70% overlap semanal | 4 semanas |
| Sin errores críticos en pipeline | 0 crashes | 4 semanas |

**Criterio de descarte (vuelta a Etapa 4):**
- Win rate paper < 35% en 20+ trades → revisar parámetros
- Slippage > 50bps → revisar timing de ejecución
- 0 señales en 10 días hábiles seguidos con régimen OK → revisar filtros

---

## Registro semanal

### Semana 1 — 2026-05-09 al 2026-05-16

| Fecha | Señales | Watchlist | Régimen | RVOL fix | Notas |
|---|---|---|---|---|---|
| 2026-05-09 | PENDIENTE | — | — | Aplicado | Inicio formal Etapa 6 |

---

## Problemas conocidos y resolución

| Problema | Causa | Fix | Estado |
|---|---|---|---|
| RVOL=1.0 en todas las señales | `avg_volume_20` no pre-calculado en DB del VPS | Cálculo raw inline en `paper_finviz.py` | ✅ 2026-05-09 |
| `is_promotable=False` en todo watchlist | Dependía de RVOL real | Se resuelve con fix RVOL | ✅ 2026-05-09 |

---

## Historial de experimentos previos (Etapas 1-5)

| Experimento | Hipótesis | Resultado |
|---|---|---|
| #1 RVOL gate | RVOL en entrada mejora Sharpe | NO-GO — redundante con min_rvol Tier2 |
| #2 RS percentile | RS > percentil mejora selectividad | NO-GO — redundante con PIT universe |
| #3 max_consolidation_range | Rango < 10% mejora calidad | NO-GO — destruye perfil de R |
| #4 be_threshold_r | Breakeven más agresivo | NO-GO — no robusto en WF |
| #5 Breadth gate | Filtro de amplitud de mercado | NO-GO — Sharpe OOS medio = -0.086 |
| #6 ATR contraction | Compresión de volatilidad | NO-GO |
| #7 HTF señal alternativa | Polo 50%/120d + flag → más runners | NO-GO backtest, pivotó a screener operativo |
