# DECISIONS.md — Archivo de Decisiones de Arquitectura (Append-Only)

Este archivo registra las decisiones clave de arquitectura y el valor esperado en la configuración que las refleja.

| Fecha | Decisión | Config Path / Archivo Afectado | Valor de Configuración Esperado |
| :--- | :--- | :--- | :--- |
| 2026-05-10 | Excluir sector salud (XLV) de backtesting y escaneo en vivo | `config/production_config.json` -> `exclude_sectors` | `["XLV"]` |
| 2026-06-01 | Reemplazar sklearn Random Forest con LightGBM para scoring | `config/production_config.json` -> `ml_entry_filter.enabled` | `false` (iniciar apagado, habilitar vía flag) |
| 2026-06-05 | Separar entornos: Local con base de datos PIT, VPS sin base de datos pesada | `config/production_config.json` -> `universe_source.drift.reference_mode` | `"db_top_liquidity_200"` |
| 2026-07-15 | Iniciar shadow trading con E25 v2 Sizing (Atlas-Informed) | `config/production_config.json` -> `tier3_fixed.use_dynamic_extension_sizing` | `true` |
| 2026-07-16 | Implementar seguridad de escritura (Promotion Gates) y sanity limits | `scripts/optimize_combo.py` (bloqueo outputs/best_combos_run/) y `scripts/sync_combo_config.py` (requiere `--promote`, inyecta metadatos, valida `validation_passed=true` y aborta si `profit_factor >= 99.0` o `nan/inf`) | Bloqueo estricto de ruta en optimizador y uso explícito del flag `--promote` en el sync |
| 2026-07-17 | Salvaguarda UTF-8 para consola de Windows en scripts de integridad y sync | `scripts/check_git_duplicates.py` y `scripts/sync_combo_config.py` | `sys.stdout.reconfigure(encoding='utf-8')` implementado (verificación en Windows real pendiente) |
| 2026-07-17 | Advertencia: desincronización de `commit_head` en `dump_state.py` | `scripts/dump_state.py` | Causa no confirmada; monitorear desvíos en próximas sesiones. |
| 2026-07-20 | Ingesta Resiliente (Tenacity con Jitter + DLQ) & Harness SDD Native Bridge | `src/data/ticker_cache.py`, `scripts/live_trading_scanner.py`, `scripts/sdd_verify_wrapper.py`, `tests/test_quant_gate.py` | `@retry` con jitter exponencial, ruteo a `data/dlq_failures.json`, `PRAGMA journal_mode=WAL`, `sdd_verify_wrapper.py` con Popen streaming. **Paridad Byte a Byte:** Verificada contra baseline aislado de `main` (`SHA-256: 4D646DB6...1CA45E5F`, 158 trades exactos en `gold_standard_variant_e_trades.csv`). |
| 2026-07-22 | Corrección de KeyError (`setdefault`) y Sizing Dinámico en Sistema B (`backtest_via_signal_engine.py`) | `scripts/backtest_via_signal_engine.py` | **Hallazgo / Scope Creep declarado:** `main` puro crashea en el día 6 por `KeyError: 'tier1_strategy'` en `cfg_b` cuando `combo_stage2_breakout_config.json` no está promovido en `outputs/best_combos_run/`. El reemplazo quirúrgico por `cfg_b.setdefault("tier1_strategy", {})["risk_dollars"] = dynamic_risk_dollars` no solo previene el crash en `main`, sino que inyecta sizing dinámico (`total_equity * risk_pct`) en el Sistema B donde antes no existía la clave, explicando el MDD de `-41.95%` y `Return 2.55%` en la corrida Gold Standard 2023-2024. |
| 2026-07-24 | Fijar determinismo del motor en uniones de Sets (`sorted()`). Actualización de métricas Golden Baseline y Aceptación de Riesgo de Datos. | `universe_builder.py`, `backtest_via_signal_engine.py` | Nueva baseline matemática validada y determinística: **56 trades, 16.35% Return, -19.40% MDD** (reemplaza el falso 54/14.30%). El flag `data_quality_ok: false` originado por precios nulos del histórico (19k registros previos a la migración Parquet) se formaliza como **riesgo aceptado y conocido**, no constituyendo falla de migración y permitiendo el cierre de la Fase 2. |



