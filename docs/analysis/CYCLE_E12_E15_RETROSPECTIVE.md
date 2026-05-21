# Retrospectiva Estratégica: Ciclo de Experimentos E12 - E15

Este documento recopila las lecciones aprendidas, hallazgos técnicos y las decisiones de diseño fundamentales del ciclo de experimentos **E12 a E15** en el sistema **Momentum V2**.

---

## 🎯 El Objetivo Original
El propósito de este ciclo era intentar superar el **Gold Standard** (Variant E Fija, Sharpe 0.76 IS, MDD -15.6% en el período 2023-2024) mediante la incorporación de lógicas de gestión dinámica según el régimen de mercado.

---

## 🔍 Bitácora del Ciclo: ¿Qué Encontramos?

### 🧪 E12 — Switch Dinámico de Régimen (Ataque/Defensa)
* **Hipótesis:** Alternar dinámicamente el uso de filtros temáticos (`use_theme_group_filter`) y de sectores según la salud de mercado.
* **El Problema:** La implementación rompió silenciosamente la invariante de la **Variant E**. Al desactivar el filtro temático en régimen fuerte, el sistema pasó a comprar cualquier señal genérica.
* **Resultado:** El doble de trades en el backtest, pero con la mitad de la calidad (degradación masiva de Sharpe).
* **Lección Crítica:** Cualquier alteración del flujo o loop principal puede quebrar supuestos del modelo de manera silenciosa. El monitoreo riguroso de la cantidad de trades es nuestra primera línea de defensa.

### 🧪 E13 — Gestión de Salida Adaptativa (Stops y Breakeven Dinámicos)
* **Hipótesis:** Ajustar trailing stops y niveles de breakeven en base al régimen de entrada.
* **El Problema:** Se ejecutó sobre el motor distorsionado de E12 sin que se hubiese detectado el fallo de la Variant E en ese momento. Los resultados fueron inválidos por definición.
* **Lección Crítica:** Antes de medir cualquier nueva variable o experimento, se debe verificar y reproducir con exactitud el baseline del Gold Standard sobre la misma base de código.

### 🧪 E14 — Filtro ATR en Entrada (Calidad de Señal)
* **Hipótesis:** Filtrar entradas donde el riesgo del stop (`entry - stop`) superara un factor del ATR (1.5x a 2.5x).
* **El Problema:** La primera corrida omitió la flag `--variant-e`. Al corregirse, el filtro de 2.5x ATR demostró bloquear tanto trades malos como buenos de manera indiscriminada. No fue capaz de diferenciar un stop mal ubicado de un stop ancho pero legítimo en tickers de alta volatilidad y alta convicción.
* **Resultado:** Reducción drástica del tamaño de la muestra sin mejoras estadísticas reales en el Sharpe.

### 🧪 E15 — VIX Circuit Breaker (Cierre Forzado en Pánico)
* **Hipótesis:** Forzar el cierre inmediato de todas las posiciones abiertas en la apertura si el VIX del día anterior superaba 40.0.
* **El Comportamiento:** Excelente comportamiento técnico. En el crash de Marzo de 2020, el sistema ejecutó salidas quirúrgicas en la apertura del 9 de marzo (salvando un total de $424 en pérdidas por ejecución) y congeló la cuenta en efectivo ($97,215), conteniendo el drawdown del crash en un insignificante **-5.66%**.
* **El Límite Estructural:** A pesar del éxito en contener el crash de 2020, el drawdown total del período 2019-2020 se reportó en **-31.37%**. Esto evidenció que el sangrado real de la cuenta ocurrió por un lento goteo de stop-outs ordinarios entre septiembre de 2019 y febrero de 2020, período donde el VIX era extremadamente bajo (< 20).
* **Lección Crítica:** Ningún protector de cola extrema (tail-risk) puede solucionar pérdidas causadas por fricción lateral de señales mediocres en mercados de rango.

---

## 🚦 Conclusión Estratégica: ¿Por qué Detenemos la Optimización Aquí?

Cuatro experimentos consecutivos en el laboratorio sin superar los criterios conjuntos del **Gold Standard** (Sharpe 0.76, MDD -16.7% IS) aportan evidencia contundente: **el sistema ha alcanzado su techo matemático en datos históricos**.

Intentar solucionar el goteo lateral de finales de 2019 mediante filtros aún más restrictivos o capas adicionales en la entrada nos arrojaría inevitablemente al terreno del **sobre-ajuste (curve-fitting)**: el modelo se vería artificialmente perfecto en el pasado, pero perdería toda su robustez en el futuro.

---

## 🛰️ El Camino Hacia Adelante: Fase 3 de Paper Trading

El sistema se estabiliza oficialmente en el **Gold Standard puro (Variant E)**. 

### ¿Qué pasa con el Experimento E16 (Sizing Dinámico)?
Si en el futuro (después de acumular datos en vivo) se decide reabrir la investigación en el laboratorio, la única dirección limpia y no explorada es el **Sizing Dinámico Puro** (escalar el capital expuesto por trade según régimen, sin alterar la lógica de entradas ni salidas). Sin embargo, esto solo se justificará si el **Shadow Mode** revela un problema específico que amerite volver a optimizar.

El foco completo del proyecto se desplaza ahora a la **validación en vivo (Fase 3)** en el VPS, monitoreando la salud y el *drift* de las señales reales.
