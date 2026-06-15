# Playbook de Desarrollo: Gentle AI + SDD + ScrumBan (2026)

Este manual define el estándar de ingeniería y flujo operativo del **Sistema Quant v2** para maximizar la eficiencia en el uso de modelos de lenguaje, proteger la ventana de contexto y asegurar un desarrollo robusto bajo ScrumBan y Spec-Driven Development (SDD).

---

## Quick Path: Ciclo de Vida de un Ticket

1. **Contexto e Inicio (ScrumBan Fase 1)**
   - Revisar backlog: `gh issue list --state open`
   - Leer criterios de aceptación del ticket: `gh issue view <ID>`
   - Crear rama de desarrollo: `git checkout -b feat/<ID>-<nombre-corto>` (o usar `/sdd-new` para inicializar).

2. **Planeamiento (SDD)**
   - Correr `/sdd-ff` para automatizar las fases de Proposal, Spec, Design y Tasks, o interactuar paso a paso en modo `/sdd-new`.
   - Generar la propuesta técnica y de pruebas unitarias.

3. **Implementación y QA (SDD + ScrumBan Fase 2)**
   - Implementar los cambios (Strict TDD si el proyecto tiene tests configurados).
   - Validar suite completa local: `PYTHONPATH=. pytest tests/`

4. **Cierre y Documentación (ScrumBan Fase 3)**
   - Confirmar solo los cambios relevantes del ticket (evitar mezclar estados).
   - Commitear con formato convencional: `fix(modulo): descripción. Fixes #$(ticket)` (ej: `feat(shadow): ...`)
   - Subir cambios a GitHub: `git push origin HEAD --no-verify` (si falla pre-commit por cuotas de API).
   - Comentar y cerrar ticket:
     ```bash
     gh issue comment <ID> --body "✅ Build completado. Veredicto: ..."
     gh issue close <ID>
     ```

---

## División de Labores: Orquestador vs. Subagentes

El orquestador coordina pero **no ejecuta código directamente** para mantener la ventana de contexto liviana.

| Actividad | Método Recomendado | Razón Técnica |
| :--- | :--- | :--- |
| **Búsqueda rápida en el repo** (1-3 archivos) | **Orquestador directo (Inline/Grep)** | Rápido, no quema contexto. Ej: buscar `ta.sma` en un archivo Pine. |
| **Exploración profunda** (4+ archivos) | **Subagent (`sdd-explore`)** | Evita llenar el hilo principal de código y detalles irrelevantes de lectura. |
| **Escribir un archivo mecánico** | **Orquestador directo** | Cambio atómico de una sola línea o plantilla sencilla. |
| **Modificar múltiples archivos** | **Subagent (`sdd-apply`)** | Separa el análisis complejo de la escritura y previene corrupción de estado. |
| **Correr tests, builds o lints** | **Subagent (`sdd-verify`)** | Aísla la ejecución y previene el consumo excesivo de tokens por logs largos. |

---

## Directivas Mandatorias y Buenas Prácticas (Nico 2026)

### 1. Guardado Proactivo en Engram
Tras cada tarea o decisión, yo (el agente) me pregunto: *¿Tomé una decisión? ¿Fijé un bug? ¿Aprendí algo no obvio? ¿Establecí una convención?*
Si la respuesta es afirmativa, grabamos inmediatamente en Engram para persistir el contexto entre sesiones utilizando una clave estable (`topic_key`).

> [!TIP]
> En este proyecto usamos una memoria local auxiliar en `.cache/local_memory.json` para registrar el ScrumBan local en Git, complementando el sistema de Engram.

### 2. Estricto Modo TDD
Si el proyecto cuenta con entorno de pruebas configurado, se activa **Strict TDD Mode**:
1. **Red**: Escribir los tests según las especificaciones y verificar que fallen.
2. **Green**: Escribir el mínimo código de producción necesario para que los tests pasen.
3. **Refactor**: Refactorizar y limpiar el código asegurando que no se rompan las pruebas.

---

## Ejemplo Práctico: Buscar uso de SMA 13 en TradingView

Supongamos que querés saber cómo se usa la SMA 13 en el indicador. 

### 1. Consulta rápida (Inline/MCP)
Como solo requiere inspeccionar la carpeta de scripts de TradingView, no usamos un subagente de exploración. Ejecutamos una herramienta de búsqueda directo en el chat principal:
```bash
grep -n "13" tradingview/bugatti_momentum.pine
```
**Resultado en segundos:**
- Línea 85: `sma_13  = ta.sma(close, 13)`
- Línea 185: `trend_int = (sma_13 / sma_65) * 100.0` (Cálculo de Trend Intensity con umbral en 105.0).

### 2. Guardar aprendizaje en Engram
```json
{
  "title": "Documentar cálculo de Trend Intensity en TradingView",
  "type": "discovery",
  "topic_key": "tradingview/trend-intensity",
  "content": "Se identificó que la SMA 13 se utiliza junto con la SMA 65 para calcular la Trend Intensity en bugatti_momentum.pine con la fórmula (SMA13 / SMA65) * 100."
}
```

---

## Checklist de Calidad para el Cierre de Ticket

- [ ] ¿Los tests corrieron al 100% sin nuevos fallos?
- [ ] ¿Los cambios commiteados corresponden **únicamente** al ticket actual?
- [ ] ¿Se guardó la memoria del avance de sesión en Engram o cache local?
- [ ] ¿El ticket en GitHub quedó comentado y cerrado correctamente?
- [ ] ¿La rama fue subida y está lista para Pull Request?
