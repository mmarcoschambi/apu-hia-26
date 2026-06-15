# Release Note — Sector ETF Filter

## Resumen
Se ha activado formalmente el filtro de sector en producción tras completar la validación walk-forward (OOS). El filtro bloquea entradas en tickers cuyo ETF sectorial correspondiente esté cotizando por debajo de su SMA de 20 días (con un margen opcional).

## Configuración en Producción
- **Archivo:** `config/production_config.json`
- **Feature Flag:** `"use_sector_etf_filter": true`
- **Parámetros:**
  - `sector_etf_sma_period`: 20
  - `sector_etf_dist_threshold`: 0.0 (Cruce binario validado OOS)

## Evidencia y Validación
- **Experimento:** `experiments/sector_filter_walkforward.py`
- **Reporte Final:** `outputs/experiments/sector_filter_walkforward_20260503_213402.json`
- **Resultados OOS (Oct 2025 - Abr 2026):**
  - Delta Sharpe 10d: **+0.386**
  - Delta Sharpe 20d: **+0.278**
  - Delta Sharpe 5d: **+0.260**
- **Commit de Activación:** `52231b8`

## Protocolo de Monitoreo y Rollback (15-20 ruedas)
Se observará el impacto operativo en el pipeline de Paper Trading. Se activará un **Rollback** inmediato si se cumple cualquiera de las siguientes condiciones:

1. **Caída Severa de Throughput:** La mediana de señales diarias cae por debajo del 50% del baseline previo (indicando que el filtro es demasiado restrictivo para el régimen actual).
2. **Deterioro de Calidad OOS:** El Sharpe, Expectancy o Profit Factor observado en Paper Trading es significativamente inferior al baseline histórico reciente.
3. **Bloqueo Total Anómalo:** Días con 0 señales cuando el sistema sin filtro habría producido múltiples setups de alta calidad.
4. **Bugs de Mapping:** Evidencia de tickers de alta calidad bloqueados erróneamente por falta de mapping GICS/ETF o data corrupta.

### Acción de Rollback
- Modificar `config/production_config.json` -> `"use_sector_etf_filter": false`.
- Mantener la infraestructura en el engine para futuros experimentos.

---
*Implementado por: Gemini CLI (Senior Trading System Engineer)*
*Fecha: 2026-05-03*
