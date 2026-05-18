# Plan de Verificación E11: Divergencia Temática

## Estado de Implementación (2026-05-18)
La variante ganadora del sandbox `theme_group_etf_correlation_sandbox.py` (Variante E) ha sido promovida a la infraestructura core del sistema para su validación en **Shadow Mode**.

### Regla de Oro (Variante E)
```python
variant_e_accepted = theme_above_sma20 AND NOT sector_etf_ok
```
*   **Theme OK**: El índice temático (Equal-Weighted) debe estar por encima de su SMA de 20 días.
*   **Sector NO**: El ETF sectorial correspondiente debe estar por DEBAJO de su SMA de 20 días.
*   **Filo (Edge)**: Captura la rotación de capital hacia nichos fuertes durante debilidad sectorial generalizada.

## Cambios Realizados
1.  **Lógica Centralizada**: Creación de `src/signals/thematic_logic.py`.
    *   Cálculo robusto de índices EW con manejo de NaNs por fecha.
    *   Evaluación matemática de la divergencia (Variante E) reutilizable por todos los agentes.
2.  **Shadow Logger**: Refactorizado `src/paper/shadow_logger.py` para usar la lógica core.
    *   Ahora loguea explícitamente `sector_etf_ok`, `theme_dist` y `theme_vs_sector`.
3.  **Scanner de Producción**: Actualizado `scripts/daily_scan.py`.
    *   Inyección de métricas temáticas reales en los archivos `combined.csv` y `rejection_audit.csv`.
4.  **Capa Visual y Alertas**:
    *   **Telegram**: `telegram_views.py` ahora muestra "Theme RS" (RS del índice vs sector) y estado del sector con iconos visuales (🟢/🔴).
    *   **Terminal GUI**: Inclusión de la columna "Theme RS" en la tabla de diagnóstico.
    *   **Multi-tema**: Lógica de selección del "mejor tema operativo" basada en desempeño relativo (ej: NVDA elegirá el tema con mejor RS si pertenece a varios).

## Protocolo de Verificación Operativa
Para la promoción definitiva a **Producción** (`use_theme_group_filter: true`), se deben cumplir los siguientes hitos:

1.  **Muestra Mínima**: Acumular 15 rondas reales en Shadow Mode.
2.  **KPIs del Filtro**:
    *   **Profit Factor (PF)**: > 3.0 en señales filtradas por Divergencia.
    *   **Win Rate (WR)**: > 55%.
    *   **Horizonte**: Evaluar principalmente a 20 días (`fwd_20d`), dado que el edge es para swing trades de largo aliento.
3.  **Throughput**: Confirmar que el filtro no reduce excesivamente el volumen operativo (Sniper setup, ~30% retención esperada).

## Guía de Auditoría
Los registros para verificar este plan se encuentran en:
*   `outputs/shadow_theme_filter/`: JSONs detallados de cada evaluación.
*   `outputs/live_signals/YYYY-MM-DD/rejection_audit.csv`: Comparativa de señales bloqueadas/permitidas por el filtro.

---
**Documentación de Ingeniería - Momentum V2**
