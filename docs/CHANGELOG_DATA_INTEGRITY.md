# Changelog de Integridad de Datos — Momentum V2

Documentación sistemática de anomalías técnicas, incidentes de datos y mitigaciones de seguridad implementadas.

---

## [2026-06-30] Incidente de Drift Gate del Universo y Saneamiento de Junio

### 1. Descripción del Problema
Durante el análisis de track record de la Joya (E25 Shadow), se detectó que el mes de junio de 2026 estaba prácticamente desierto de setups y triggers en las watchlists del VPS (cayendo de cientos por día en mayo a 1-4 por día en junio), a pesar de que el régimen de mercado general (SPY > SMA50) estaba activo y saludable.

### 2. Causa Raíz
Se descubrieron dos causas raíces técnicas e independientes:
1. **Error de Diseño Matemático en el Drift Gate (`universe_drift_audit.py`):** El auditor de drift usaba Jaccard Distance para comparar el tamaño del universo "live" de Finviz (~600 tickers) con el del universo de referencia de la DB local (limitado a 200). Matemáticamente, la divergencia mínima posible por diferencia de tamaños de conjuntos era del 66.67%. Al tener un límite rígido del 15% de divergencia máxima en producción, el portón se bloqueaba con un falso positivo el 100% de los días en que Finviz funcionaba correctamente.
2. **Laguna de Rankings Diarios en el VPS:** El VPS no tenía configurado ningún cron job para poblar la tabla `daily_rs_rankings`. El 16 de junio, tras la última corrida manual, las inserciones cesaron. La falta de rankings obligaba al VPS a operar en modo fallback e invalidaba el ma_status de los setups por discrepancias técnicas de base de datos en el premarket.

### 3. Mitigación e Implementación
1. **Fix del Drift Gate:** Se modificó `src/paper/universe_drift_audit.py` para medir el drift usando la cobertura real del universo de referencia: $100.0 - \text{live\_coverage\_pct}$. El gate ahora pasa si Finviz contiene al menos el 85% de los tickers líquidos de referencia, independientemente del tamaño total devuelto por el scraper.
2. **Saneamiento y Automatización del VPS:**
   - Se inyectaron por SSH los rankings de junio en el VPS.
   - Se automatizó en el crontab del VPS la generación diaria de rankings de lunes a viernes a las 18:00 NY:
     `0 18 * * 1-5 scripts/populate_rankings_daily.py --workers 2`
3. **Backfill de Junio y Replay:** Se programó `scripts/backfill_june_shadow.py` para reconstruir retrospectivamente los setups de junio cruzando los snapshots de Finviz con el historial técnico y de tendencia recalculado de forma limpia en local.
4. **Resultados Cuantitativos Consolidados (Mayo + Junio):**
   - Candidatos permitidos: 4,637.
   - Triggers reales confirmados (High >= Breakout): **1,583 trades** (1,249 en mayo + 334 en junio).
   - Tasa de trigger promedio: **34.14%**.

### 4. Salvaguardas y Regresiones
- Se agregó el test unitario de regresión matemática `tests/test_drift_gate_regression.py` para evitar que la lógica del drift gate vuelva a cambiar a Jaccard.
- Se implementó la alerta temprana `scripts/health_check_daily.py` integrada con Telegram para monitorear diariamente la presencia de snapshots, rankings e integridad del drift.
