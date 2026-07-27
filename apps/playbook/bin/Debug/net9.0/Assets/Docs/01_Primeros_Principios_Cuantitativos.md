# 1. Primeros Principios Cuantitativos

El presente capítulo expone la descomposición física y matemática de la operativa institucional de Momentum V2. El objetivo primordial radica en comprender la ventaja estadística (*edge*), la gestión de riesgos y el escalamiento del capital desde sus bases teóricas y matemáticas fundamentales.

## 1.1. Ecuación Fundamental del Retorno

La viabilidad de todo sistema cuantitativo se fundamenta en la expectativa matemática de ganancias por cada unidad de capital arriesgada. La formulación del valor esperado (*EV*) se define a continuación:

Donde:
*   ***WR* (Win Rate):** Porcentaje histórico de operaciones rentables (ejemplo: 0.50).
*   ***AvgWin* (Ganancia Promedio):** Retorno porcentual promedio generado en posiciones ganadoras.
*   ***AvgLoss* (Pérdida Promedio):** Retorno porcentual promedio incurrido en posiciones perdedoras.

> 💡 **INFO**: El principio de asimetría dicta que si se controla rigurosamente el *AvgLoss* mediante la ejecución firme de paradas de pérdida (*stop losses*), no se requiere un *WR* del 80% para lograr rentabilidad sostenida. Un *WR* del 50% combinado con un ratio de riesgo-beneficio (R:R o *AvgWin* / *AvgLoss*) de 2.0 es matemáticamente suficiente para generar un valor esperado sustancialmente positivo.

---

## 1.2. Los Dos Sistemas Activos en Paper

[Reservado para la descripción operativa de los regímenes de simulación activa.]

---

## 1.3. Simulador de Expectativa Matemática y Salidas (Exits)

La optimización de parámetros requiere someter el sistema a pruebas dinámicas para evaluar cómo las distintas estrategias de salida impactan en el valor esperado de la cartera institucional. Resulta indispensable comparar la eficacia de un sistema con salidas totales en objetivos fijos (como la actual configuración de "Joya") versus la implementación de salidas fraccionadas y dinámicas mediante tramos de seguimiento o *Runners* (como los utilizados en el Sistema A o "Atlas").

---

## 1.4. Anatomía de un Trade Paso a Paso (Integración con Telemetría y Logs)

La siguiente sección detalla la secuencia algorítmica y operativa mediante la cual se origina, ejecuta y liquida una posición en los servidores de producción (VPS), integrando los reportes automatizados de Telegram y las auditorías derivadas de las validaciones retrospectivas (backtests).

### 1.4.1. Comportamiento Gráfico y Dashboard Multicriterio

La operativa se respalda en el análisis cuantitativo de la acción del precio y su interacción con las medias móviles institucionales, complementado por nuestro panel integral en TradingView (`bugatti_momentum.pine`).

**Screener Qullamaggie**

• MA Stack: 🟢 ALIGNED
• RS Percentile: 🟢 92.1%
• Trend Intensity: 🟢 112

**Stage 2 Minervini**

• Stage 2 Criterios: 🟢 7/7
• Trend Direction: 🟢 BULLISH
• Vol. Expansion: 🟢 PASS

**Tier 2 & Sector (XLK/SMH)**

• RVOL (1.25x): 🟢 PASS
• ADR% (3.5%): 🟢 PASS
• Sector ETF > SMA20: 🟢 YES

**Señal Compuesta (Composite Signal)**

[Validación final unificada de los módulos de señal.]

### 1.4.2. Sistema A: Torneo de Combos y Rupturas

*   **Universo Original:** Comprende los componentes del índice S&P 500 y activos de alta liquidez con un volumen medio diario negociado dentro del Top 200 (evaluación temporal Point In Time).
*   **Primer Principio del Edge:** Capitalizar la ineficiencia generada por la sub-reacción institucional (anomalía de momentum) en activos hiper-líquidos, ejecutando entradas precisas durante el punto de ruptura estructural (breakouts, VCP, ATH).

### 1.4.3. Estructura de Salidas del Sistema A

*   **TP1 / TP2 (Cierres Parciales Fijos):** Su objetivo es materializar ganancias prefijadas de forma ágil para proteger el *Win Rate* ante reversiones a corto plazo.
*   **El Runner (Tramo Residual):** Consiste en mantener una fracción de la posición abierta y gestionada mediante un *Trailing Stop* dinámico, con el fin de maximizar la exposición a tendencias de fondo extendidas. Este componente constituye el núcleo del rendimiento extraordinario en mercados direccionales.

### 1.4.4. Sistema B: Joya E25 (Russell Shadow)

*   **Universo de Trabajo:** Constituido por el índice Russell 1000, con exclusión sistemática del sector salud (XLV).
*   **Primer Principio del Edge:** Expandir el espectro de activos elegibles a 1000 emisores, aplicando un régimen de filtros restrictivos. La exclusión del sector salud (XLV) se fundamenta en su nivel estadístico de ruido estructural, evidenciado durante el desarrollo de backtests institucionales.

### 1.4.5. Flujo de Control de Riesgo de la Joya E25

*   **Dimensionamiento de la Posición (Position Sizing):** El capital asignado no es un valor nominal fijo. El sistema recalcula la exposición empleando el *Average True Range* (ATR) para garantizar que la volatilidad asumida (el riesgo monetario por operación) sea invariablemente idéntica en cada entrada.
*   **Límite de Concentración (Ticker Cap 20%):** Se impone una restricción algorítmica donde ningún activo individual o consolidado sectorial podrá sobrepasar el 20% de la exposición bruta del portafolio global.
*   **Salida Plana:** La liquidación de la posición se efectúa sobre el 100% de la tenencia al alcanzar objetivos temporales predefinidos o límites de pérdida (*Stop Loss*), prescindiendo, en su versión actual, del desescalamiento progresivo.

> ✔️ **ÉXITO**: Expectativa POSITIVA. El sistema posee un diseño robusto y es estadísticamente rentable a largo plazo.

> ❌ **ERROR**: Expectativa NEGATIVA. El sistema expone el capital a pérdida sostenida a lo largo del tiempo.

> ⚠️ **ADVERTENCIA**: En los presentes parámetros, el entorno no demuestra beneficios adicionales estadísticamente significativos.

### 1.4.6. Fase 1: Reporte de Pre-Mercado

*   **Operativa en Entorno de Producción (VPS):** La tarea programada (cron) inicia el motor de procesamiento en horario de apertura previa, generando el **Premarket Brief / Reporte consolidado**. Dicho informe expone el régimen macro, las métricas de amplitud sectorial y la lista primaria de activos candidatos.
*   **Auditoría de Registros (Logs):** Se extrae información del log real (`snapshot.json`) que evidencia la detección de activos que satisfacen los umbrales institucionales de liquidez y volumen operado.
*   **Métricas del Período:**
    *   *Régimen de Mercado:* Alcista (Bullish) — validado si SPY > SMA200.
    *   *Candidatos Primarios:* `QCOM`, `TSM`, `SMH`.

**📋 Trazabilidad del Pre-Market (Extraído de `snapshot.json`):**

<div style='background-color:#7f1d1d; color:#fca5a5; padding:8px 12px; border-radius:6px; font-weight:bold; text-align:center;'>[FAIL] BLOCKED (Wait Open)</div>

<div style='background-color:#064e3b; color:#6ee7b7; padding:8px 12px; border-radius:6px; font-weight:bold; text-align:center;'>[BOLT] SIGNAL LONG</div>

### 1.4.7. Fase 2: Watchlist Sectorizada al Market Open

*   **Dinámica en Tiempo Real:** En la apertura oficial del mercado (09:30 EST), el escáner del servidor de producción emite la **Watchlist oficial, clasificada por jerarquía sectorial**. Esta estructura organizativa facilita la sincronización de disparadores de ruptura (*breakout triggers*) con mínima latencia, ya sea para supervisión del gestor o para ejecución automatizada.
*   **Estructura y Priorización:** Agrupa los candidatos según el desempeño de su ETF subyacente e incluye el Score derivado de aprendizaje automático (ML) junto con la métrica ADR% para asignar prioridad algorítmica a las oportunidades.

**📋 Parámetros de Apertura:**

### 1.4.8. Fase 3: Trigger de Entrada e Inyección de Riesgo

*   **Detección e Ingreso:** A modo de ejemplo, a las 09:35 EST el sistema detecta que `QCOM` perfora la banda de ruptura en `$215.11` con el volumen relativo parametrizado (RVOL), enviando la orden de disparo al motor.
*   **Cálculo desde Primeros Principios (Sizing):**
    El módulo `risk_manager.py` computa dinámicamente el tamaño del lote utilizando la métrica de volatilidad (ATR). Este diseño estricto certifica que el capital expuesto ascienda exactamente al **1.0%** del patrimonio en la eventualidad de ejecución del *Stop Loss*.

### 1.4.9. Fase 4: Post-Market y Portfolio Ledger

*   **Conciliación al Cierre:** Al finalizar la sesión, el motor algorítmico asienta el estado de todas las operaciones abiertas en la base de datos (`active_positions.json`) y procesa el saldo contable correspondiente al corte de las 16:30 EST.
*   **Monitorización Institucional (VPS):** Se computa de manera agregada la exposición por sectores para verificar el estricto cumplimiento normativo, evitando que cualquier agrupación de activos viole el umbral de riesgo Ticker Cap estipulado en un 20% para el día posterior.

**📋 Estado del Portafolio al Cierre:**

### 1.4.10. Fase 5: Ejecución de Exits y Scaling Out

*   **Procedimiento de Escalamiento (Sistema A):**
    1.  **Ejecución del TP1:** Cuando el valor del activo logra una revalorización del 10% hasta los **$236.62**, se procede a la liquidación algorítmica de 1/3 de la tenencia. Concomitantemente, el nivel de Stop Loss para la posición remanente (2/3) se ajusta al precio promedio de apertura (*Break Even*), neutralizando el riesgo de pérdida contable sobre el capital principal.
    2.  **Ejecución del TP2:** Conforme el precio continúa su tendencia positiva hasta los **$258.13** (+20%), se instruye la liquidación del segundo tercio.
    3.  **Clausura del Tramo Runner:** El último tercio es gestionado libremente por el sistema de rastreo direccional. Al ascender a $285.40 y evidenciar posteriormente un quiebre negativo bajo la Media Móvil Exponencial de 8 períodos (EMA 8), el sistema cierra la posición definitivamente, concretando la salida del *runner* a un precio de $285.40 (+32.68% de rentabilidad).

**📋 Resumen de Liquidación de la Operación (Registro Histórico):**

> ✔️ **ÉXITO**: 🔥 **Retorno Combinado Neto del Trade: +20.89%**