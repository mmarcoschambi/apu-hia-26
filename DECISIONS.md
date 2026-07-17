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
| 2026-07-17 | Corregir cálculo de `total_trades` en vectorbt avanzado | `src/backtest/vectorbt_engine_advanced.py` | `total_trades` mapea a posiciones de entrada reales ejecutadas y no a señales de entrada únicas |
| 2026-07-17 | Unificación de cargadores de configuración de producción | `src/config/dynamic_config.py` y `src/config/config_loader.py` | `dynamic_config.py` delega la carga en `config_loader.py` con validación de schema centralizada |
| 2026-07-17 | Inyección de período y tamaño de universo reales en el optimizador | `scripts/optimize_combo.py` | `export_combo_result` escribe `period` y `universe_size` reales, evitando defaults erróneos |
| 2026-07-17 | Blindaje de gate de validación por default en optimizador | `scripts/optimize_combo.py` | `validation_passed` inicializa en `False` para bloquear la promoción silenciosa de corridas sin validación real |
| 2026-07-17 | Activación formal de ejecución real de capital | `config/combos/combo_pure_momentum.json` | `capital_enabled` cambiado de `false` a `true` tras mitigar falsos positivos y anomalías en Optuna |
| 2026-07-17 | Normalización de claves en la rúbrica del comité de inversiones | `config/ic_rubric.yaml` | Unificación homogénea de los campos `capital_enabled` y `paper_trading_capital_usd` en todos los combos |
