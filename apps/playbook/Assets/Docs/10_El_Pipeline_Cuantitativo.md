# 10. El Pipeline Cuantitativo

El presente capítulo instaura la metodología de validación estructural adoptada por el fondo para ponderar y asimilar nuevas hipótesis cuantitativas, asegurando rigurosamente que las alteraciones conceptuales no comprometan el motor basal ni la estabilidad de las operaciones en vivo.

## 10.1. El Pipeline Cuantitativo Profesional (QUANT-FEATURE.md)

Este es el flujo de trabajo analítico y procedimental estandarizado para la investigación y promoción de señales estadísticas.

## 10.2. Las 4 Etapas del Ciclo de Investigación

Toda nueva lógica técnica debe cursar, ineludiblemente, las siguientes cuatro etapas de maduración.

### 10.2.1. La Sandbox (Investigación y Ablación)

*   **Entorno de Ejecución:** Alojada en `experiments/` (empleando cuadernos de Jupyter o scripts confinados tales como `run_walkforward_hybrid.py`).
*   **Objetivo Científico:** Demostrar matemáticamente si la hipótesis planteada (por ejemplo, evaluar un filtro de convergencia relativo a la SMA20) ostenta ventaja estadística cruda (edge).
*   **Regla Institucional de Criba:** Si el postulado teórico no demuestra rendimiento positivo frente a configuraciones de salidas simples o rígidas (ej. asumiendo un holding incondicional de 10 días), **se desecha de inmediato**. Está proscrito intentar compensar una hipótesis inherentemente deficiente mediante sobre-optimización.

### 10.2.2. Integración al Core (El Enchufe)

*   **Entorno de Ejecución:** Módulo central ubicado en `src/backtest/vectorbt_engine_advanced.py` y parametrización en `config/defaults.py`.
*   **Objetivo Científico:** Incorporar funcionalmente la hipótesis previamente validada al código matricial oficial a través de un **Feature Flag** o bandera condicional (ej. `use_new_filter = True/False`).
*   **Regla Institucional de Arquitectura:** **NUNCA duplique el motor de ejecución** bajo pretexto investigativo. El mantenimiento de un único punto de verdad operativa (single source of truth) es de acatamiento obligatorio.

### 10.2.3. Optimización y La Guillotina (ResearchGate)

*   **Entorno de Ejecución:** Despliegue mediante el módulo `optimize_3tier.py` y evaluación de robustez tipo walk-forward.
*   **Objetivo Científico:** Delegar en el optimizador (Optuna) la determinación de los parámetros ideales para la gestión de riesgo y escalamiento de salidas (TP1, TP2, Runner). Posteriormente, la fase ResearchGate somete la estrategia a fricción máxima: comisiones dobles, deslizamiento (slippage) y pruebas de tensión estructural para dictaminar la métrica PBO (Probability of Backtest Overfitting).
*   **Regla Institucional de Riesgo:** Si el coeficiente PBO arroja un valor superior al 50% (Estado REJECTED), el algoritmo es automáticamente repudiado. El fondo únicamente compromete capital sobre modelos que cuenten con certificación **APPROVED**.

### 10.2.4. Producción (Live Trading)

*   **Entorno de Ejecución:** Dominio del escáner activo `live_trading_scanner.py` orquestado por el fichero `production_config.json`.
*   **Objetivo Operativo:** El escáner productivo (Live Scanner) asume el rol de ejecutor estrictamente determinista (robot no pensante), circunscribiéndose a aplicar las lógicas matemáticas certificadas y congeladas durante la Etapa 3. Queda terminantemente vetada cualquier manipulación lógica en fase de producción.

---

## 10.3. Prompt de Guía en la Sandbox (Etapa 1 - Hipótesis)

Instrucción estandarizada para enmarcar la inducción de nuevas premisas algorítmicas en el entorno confinado:

```markdown
Demando la evaluación científica de la presente hipótesis cuantitativa:
Hipótesis: <Describir la hipótesis, ej. 'Penalizar activos a menos del 1% de su SMA20 en el Sistema B'>

Por favor, ajústese estrictamente a la Etapa 1 (Sandbox) del ciclo de investigación:
1. Construya un script de ablación aislado en el directorio `experiments/` (ej. `experiments/shadow_sma20_research.py`).
2. Consuma la matriz de datos proveniente de `data/ticker_cache.db` y aplique la lógica en estado puro (queda prohibida la alteración de dependencias en `src/`).
3. Efectúe una simulación controlada asumiendo un holding fijo de 10 días para auditar la presencia de ventaja matemática (edge) real, priorizando el Win Rate y el Profit Factor Out-of-Sample versus la medición base (baseline).
4. Elabore un informe concluyente sustentando si la proposición alcanza los estándares para promocionar a la Etapa 2 (Integración al Core).
```