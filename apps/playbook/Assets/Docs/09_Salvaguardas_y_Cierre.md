# 9. Salvaguardas y Cierre Operativo

Este capítulo define las salvaguardas institucionales destinadas a resguardar el conocimiento adquirido y las resoluciones técnicas, previniendo la pérdida de contexto entre distintas sesiones operativas.

## 9.1. Historial de Avances y Decisiones (local_memory.json)

El registro maestro de memoria institucional es cargado en tiempo real desde el archivo `.cache/local_memory.json`. Su propósito es documentar inmutablemente las decisiones de arquitectura, los descubrimientos analíticos y las refactorizaciones consolidadas en cada sesión.

> ⚠️ **ADVERTENCIA**: [WARN] No se encontró el archivo `.cache/local_memory.json` en el repositorio.
>
> 💡 **INFO**: El archivo `local_memory.json` se reporta vacío. Es perentorio su restablecimiento.

## 9.2. Prompt para Registro de Decisiones y Avances

Instrucción mandataria para requerir a cualquier agente técnico la materialización formal del hito concluido:

```markdown
Finalizada exitosamente la presente tarea, se requiere el asiento formal en nuestra base documental. Por favor, incorpore un nuevo registro a `.cache/local_memory.json`.
Dicha entrada debe adoptar estrictamente el siguiente esquema de objeto JSON:
{
  "timestamp": "<fecha_utc_actual>",
  "title": "<Título descriptivo de la decisión, bugfix o pattern>",
  "type": "bugfix | discovery | pattern | decision | architecture",
  "scope": "project",
  "topic_key": "<identificador-estable-del-tema>",
  "content": "<Descripción detallada de qué se hizo, por qué y qué aprendimos en esta sesión>"
}
```