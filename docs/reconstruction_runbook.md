# Runbook: Reconstrucción de Base de Datos y Backtest de Finviz VPS (Mayo 2026)

Este documento detalla los pasos para reconstruir la base de datos de precios históricos de los 910 tickers detectados en los snapshots de mayo de 2026, recalcular los rankings diarios y ejecutar el backtest sin bloqueos.

## Quick Path

Para ejecutar todo el pipeline de reconstrucción de forma asincrónica (evitando cortes de terminal o timeouts):

1. **Lanzar la descarga e hidratación en segundo plano**:
   ```bash
   nohup python3 scripts/rebuild_shadow_universe.py > outputs/logs/rebuild_universe.log 2>&1 &
   ```
   *Para monitorear el avance*: `tail -f outputs/logs/rebuild_universe.log`

2. **Regenerar los rankings de fuerza relativa (RS)**:
   *Una vez que termine el paso anterior con éxito*:
   ```bash
   python3 scripts/populate_rankings_daily.py --start 2026-05-01 --end 2026-05-29 --workers 2 --rs-only --overwrite
   ```

3. **Ejecutar el backtest sobre el universo completo de Finviz**:
   ```bash
   PYTHONPATH=. python3 scripts/backtest_via_signal_engine.py --start 2026-05-08 --end 2026-05-29 --universe-source shadow_finviz --exclude-sectors XLV --tag test_shadow_convergencia_full --e25-sizing --e25-version v2_atlas_informed
   ```

---

## Detalles del Proceso

| Etapa | Descripción | Razón Técnica |
|-------|-------------|---------------|
| **1. Descarga incremental (Corregida)** | Bajar el historial de los 910 tickers desde el `2025-01-01` en lotes de 40. | El bug anterior calculaba las medias móviles únicamente sobre el pedacito de 24 días descargados, generando `NaN`. Ahora se concatenan a la historia combinada. Descargar desde 2025 provee suficientes barras para la SMA200 y es 5 veces más rápido que descargar desde 2017. |
| **2. Rankings RS** | Generar la tabla de Fuerza Relativa diaria para los 910 tickers. | El motor de señal local requiere que la tabla `daily_rs_rankings` esté poblada para poder calcular la Fuerza Relativa de Kristjan Qullamaggie (`rs_composite`). |
| **3. Backtest** | Simular la ejecución de la watchlist cruda guardada en los `snapshot.json`. | Esto nos dará las señales reales que el VPS *debería haber visto* si su base de datos local y su red no hubiesen estado corruptas. |

## Checklist de Verificación

- [ ] Confirmar que el log `outputs/logs/rebuild_universe.log` termine con `Database reconstruction completed`.
- [ ] Confirmar con una consulta SQLite que no hay valores `NaN` en `ohlcv_cache` para columnas `sma20`, `sma50` y `sma200` en las fechas de mayo:
  ```bash
  python3 -c "import sqlite3; conn = sqlite3.connect('data/ticker_cache.db'); c = conn.cursor(); print(c.execute('SELECT COUNT(*) FROM ohlcv_cache WHERE date >= \"2026-05-14\" AND (sma20 IS NULL OR sma200 IS NULL)').fetchone())"
  ```
  *(Debería imprimir `(0,)`)*.
- [ ] Confirmar que el archivo `outputs/backtests/test_shadow_convergencia_full_trades.csv` se genera con los trades reales tomados en la ventana de simulación.

## Próximo Paso

Lanzar el comando del Paso 1 en background (`nohup`) para que la base de datos se reconstruya de forma autónoma.
