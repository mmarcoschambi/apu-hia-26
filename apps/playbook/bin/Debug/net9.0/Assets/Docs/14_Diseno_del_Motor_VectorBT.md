# 14. Diseño del Motor VectorBT y Pruebas Unitarias

El capítulo establece los pilares para el aseguramiento de la integridad matemática del motor de simulaciones y señales operativas.

## 14.1. Protegiendo la Calidad con Pruebas Unitarias

La infraestructura institucional se apoya en una suite exhaustiva de validación por unidad, con el mandato de prevenir regresiones sobre el comportamiento del motor VectorBT y los simuladores del portafolio.

> ✔️ **ÉXITO**: 🚀 **Métrica de Baseline vigente: 255/255 pruebas superadas íntegramente (100% green).**

## 14.2. Protocolos de Validación del Agente

Para garantizar la inmunidad ante fallos de integración, todo agente debe ser conminado a ratificar sus desarrollos conforme al siguiente esquema de consola:

*   Exija de forma excluyente la validación en entorno local mediante el despliegue de `pytest` para certificar la estabilidad de la lógica implementada:
    ```bash
    pytest                     # Ejecución íntegra de la suite de validación.
    pytest tests/test_e25_sizing.py  # Ejecución dirigida hacia un test unitario particular.
    ```

*   En la circunstancia técnica donde el pre-commit hook del sistema Git colapse localmente debido a una saturación de la longitud de argumentos (`Argument list too long` asociado a volúmenes pesados por snapshots), se instruirá al agente el uso de la directiva `--no-verify` al ejecutar commit y envío a la rama principal:
    ```bash
    git commit -m "[Módulo] ..." --no-verify
    git push origin <rama> --no-verify
    ```

---

## 14.3. Prompt para Modalidad Strict TDD

Instrucción estandarizada para forzar la adopción del marco metodológico de validación:

```markdown
Requiero la implementación técnica de la presente funcionalidad sometiéndose taxativamente a los pilares de la metodología TDD (Test-Driven Development):
1. **Red**: Codifique en primera instancia las pruebas unitarias pertinentes en el directorio `tests/` y certifique que su ejecución arroje resultados fallidos (ausencia de lógica).
2. **Green**: Redacte el código productivo mínimo en `src/` indispensable para sobrepasar positivamente la barrera de las pruebas instauradas.
3. **Refactor**: Proceda a sanear, estructurar y optimizar el código, reasegurando perennemente que la suite de tests mantenga una evaluación de éxito total (100% verde).

Es condición ineludible ejecutar `pytest` ante la conclusión de cada estadio a fines de documentar y auditar la transición de estados.
```