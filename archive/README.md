# Archivo del Proyecto Momentum-v2

Este directorio contiene scripts, documentos y datos que han sido archivados para limpiar el espacio de trabajo principal y enfocarse en la **Pipeline A+B Unificada**.

## Estructura

- `scripts/`: Scripts de utilidad de una sola vez, versiones legacy (como `optimize_combos.py`), debuggers y archivos `.bak`.
- `docs/`: Documentación histórica, guías de implementación de fases terminadas y notas de investigación.
- `logs_and_data/`: Resultados de backtests antiguos, reportes de gaps y logs de procesos previos.
- `legacy_dirs/`: Carpetas de experimentos concluidos o motores antiguos (`motor_viejo`, `batches`, etc.).

## Estado actual del motor (Core A+B)

El motor vigente reside en la raíz y se compone de:
- `optimize_3tier.py`: Optimización robusta basada en Optuna (Fase 3 actual).
- `live_trading_scanner.py`: Escáner de señales para trading real.
- `fill_db_metrics.py`: Poblado de métricas RS/ADR en la base de datos.
- `audit_data_gaps_smart.py`: Auditoría de paridad Live vs Backtest.
- `app.py`: Interfaz visual en Streamlit.

*Fecha de archivo: Abril 2026*
