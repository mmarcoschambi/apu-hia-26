# DECISIONS.md — Archivo de Decisiones de Arquitectura (Append-Only)

Este archivo registra las decisiones clave de arquitectura y el valor esperado en la configuración que las refleja.

| Fecha | Decisión | Config Path / Archivo Afectado | Valor de Configuración Esperado |
| :--- | :--- | :--- | :--- |
| 2026-05-10 | Excluir sector salud (XLV) de backtesting y escaneo en vivo | `config/production_config.json` -> `exclude_sectors` | `["XLV"]` |
| 2026-06-01 | Reemplazar sklearn Random Forest con LightGBM para scoring | `config/production_config.json` -> `ml_entry_filter.enabled` | `false` (iniciar apagado, habilitar vía flag) |
| 2026-06-05 | Separar entornos: Local con base de datos PIT, VPS sin base de datos pesada | `config/production_config.json` -> `universe_source.drift.reference_mode` | `"db_top_liquidity_200"` |
| 2026-07-15 | Iniciar shadow trading con E25 v2 Sizing (Atlas-Informed) | `config/production_config.json` -> `tier3_fixed.use_dynamic_extension_sizing` | `true` |
