# Cierre de Experimento Breadth (#5b)

## Veredicto Técnico: NO-GO
El experimento de Breadth no cumple los criterios mínimos para implementación en producción.

## Resultados Walk-Forward
| Threshold | Folds positivos | Folds anómalos | Sharpe medio OOS válidos |
|-----------|-----------------|----------------|--------------------------|
| Baseline  | 7/15 (47%)      | 2              | −0.810                   |
| 0.45      | 8/15 (53%)      | 1              | −0.086                   |
| 0.50      | 9/15 (60%)      | 1              | −0.144                   |
| 0.55      | 9/15 (60%)      | 3              | −0.077                   |

## Análisis del Fracaso
1. **Bug de Diseño en WF Original:** El Walk-Forward original utilizaba un OOS fijo, lo que no representaba un escenario real de despliegue. Al corregir a un Walk-Forward real (expanding window), los resultados se degradaron significativamente.
2. **Sharpe OOS Negativo:** Ningún threshold de breadth logró alcanzar un Sharpe medio OOS positivo en los folds válidos.
3. **Ganancia Relativa vs. Nivel Absoluto:** Aunque el filtro mejora el sistema en ~0.7 Sharpe relativo al baseline, el nivel absoluto no cruza el cero. Esto significa que el filtro mitiga pérdidas pero no es capaz de generar un edge positivo consistente por sí mismo sobre la base actual.

## Conclusión Estructural
El concepto de Breadth tiene lógica técnica, pero requiere un sistema base con Sharpe OOS positivo para que el filtro aporte valor incremental real. En el universo actual de breakout, la ganancia marginal no justifica la complejidad adicional y el riesgo de overfitting (PBO).

---
*Fecha: 8 de mayo de 2026*
*Estado: Cerrado / Archivo*
