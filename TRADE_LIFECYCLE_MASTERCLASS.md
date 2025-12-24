# 🎓 Masterclass: El Ciclo de Vida de un Trade (Triad Protocol)

Esta guía explica qué ocurre "bajo el capó" del sistema Triad Momentum, desde la configuración inicial hasta el reporte final en el dashboard. Entender esto es clave para interpretar las métricas correctamente.

## 1. La Configuración (El ADN del Trade)

Antes de que exista el trade, el sistema define sus reglas fundamentales en `config/settings.py` y `src/strategies/triad_protocol.py`.

*   **Riesgo Base:**
    *   **Camino 1 (Blue Sky):** 0.5% del capital total.
    *   **Camino 2 (VWAP Reclaim):** 0.25% del capital total (Mitad de riesgo por ser contra-tendencia intradía).
*   **ADR (Average Daily Range):** Se calcula la volatilidad promedio de los últimos 20 días. Si una acción se mueve un 4% diario, el sistema adapta el tamaño del Stop Loss a ese "ritmo" natural.

---

## 2. El Nacimiento (Entry Logic)

El cerebro del sistema (`TriadStrategy.analyze`) escanea el mercado diariamente. Cuando encuentra una oportunidad, define los parámetros iniciales. Aquí nace el **STOP_LOSS**.

### A. Camino 1: Blue Sky Breakout (Continuidad)
*   **La Lógica:** La acción rompe una "Base" (resistencia) justo cuando el precio promedio histórico (AVWAP) converge. No hay resistencias por encima.
*   **Entrada:** `Base High` + 0.05 (Para confirmar el rompimiento y evitar trampas).
*   **Stop Loss Inicial:** El sistema compara dos precios y elige el **más alto (más seguro)**:
    1.  El mínimo de la estructura base (`base_low`).
    2.  El precio de entrada menos 1 ADR (`Entry - 1 ADR`).

### B. Camino 2: VWAP Reclaim (Oportunidad Táctica)
*   **La Lógica:** El mercado abre débil (Gap Down), pero las instituciones entran a defender el precio, empujándolo de nuevo por encima del precio promedio ponderado (VWAP).
*   **Entrada:** Precio actual al cruzar el VWAP hacia arriba.
*   **Stop Loss Inicial:** El mínimo absoluto de la sesión de hoy (`session_low`). Si pierde este nivel, la defensa falló.

---

## 3. La Ejecución y Gestión (El Motor Cuántico)

Una vez dentro, el archivo `src/core/triad_openbb.py` toma el control con una "Máquina de Estados". Cada día que pasa, el sistema evalúa la posición:

### Fase A: La Protección (Hard Stop)
*   **Condición:** ¿El precio mínimo de hoy (`low`) tocó mi Stop Loss?
*   **Acción:** Venta total inmediata.
*   **Métrica Dashboard:** `Stop Loss (ENTRY)`
*   **Resultado:** Pérdida controlada (-1R aprox).

### Fase B: Primer Objetivo (TP1 - Risk Off)
*   **Condición:** El precio sube **1.5 veces** el riesgo inicial (1.5R).
*   **Acción 1:** Vender el **40%** de la posición para asegurar ganancias.
*   **Acción 2:** **MOVER STOP LOSS A BREAKEVEN**. El nuevo stop es `Entrada * 1.005` (cubre comisiones). A partir de aquí, es imposible perder dinero.
*   **Métrica Dashboard:** `TP1 (1.5R)`

### Fase C: El Tiempo (TP2 - Momentum)
*   **Condición:** Han pasado **4 días** desde la entrada. El momentum explosivo suele durar 3-5 días.
*   **Acción:** Vender otro **30%** de la posición.
*   **Métrica Dashboard:** `TP2 (Time/Mom)`

### Fase D: El "Runner" (Dejar correr)
*   **Situación:** Queda un 30% de la posición "gratis" (ya se cobró ganancia).
*   **Regla de Salida:** Cruce de medias móviles exponenciales (EMA).
    *   Si la **EMA 8** (rápida) cruza por debajo de la **EMA 21** (lenta), la tendencia a corto plazo murió.
*   **Acción:** Venta final del remanente.
*   **Métrica Dashboard:** `Runner Exit (EMA 8/21 Cross)`

---

## 4. Interpretando las Métricas del Dashboard

Cuando veas los resultados en la App o el HTML, esto significan los números:

| Métrica | Definición Real en Código | Explicación |
| :--- | :--- | :--- |
| **Entrada** | `signal['entry_price']` | Precio exacto del trigger. |
| **Salida** | `final_exit_price` | Precio de cierre de la *última* parte de la posición (Runner o Stop). |
| **Retorno %** | `realized_pnl_pct` | **Suma Ponderada:** No es simple resta. Es `(GananciaTP1 * 0.4) + (GananciaTP2 * 0.3) + (GananciaRunner * 0.3)`. Refleja el crecimiento real de la cuenta. |
| **Días** | `exit_date - entry_date` | Días naturales con capital comprometido. |
| **Riesgo/Beneficio** | `Return / Risk` | Cuántas veces ganaste lo que arriesgaste (R-Multiple). |

---

## 5. Resumen Visual para la App

Si implementas un gráfico en tu aplicación, usa esta leyenda para el "Tooltip" del Stop Loss:

> "El Stop Loss es dinámico. Empieza protegiendo la estructura técnica (Mínimo del día/base). Al ganar 1.5R, sube automáticamente a Breakeven (Riesgo 0). Finalmente, persigue el precio (Trailing) guiado por la EMA 8 para exprimir la tendencia."
