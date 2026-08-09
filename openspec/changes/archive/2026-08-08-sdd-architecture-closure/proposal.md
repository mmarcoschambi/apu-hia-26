# Proposal: SDD/FSM Architecture Closure

## Intent
Cerrar la deriva de arquitectura (drift) entre los estándares de gobernanza del proyecto y las ejecuciones automatizadas, materializando reglas inmutables en la memoria del orquestador y saneando el pipeline de validación para garantizar determinismo estricto.

## Scope
- **In-Scope**:
  - Remoción de exclusiones ciegas de testing y clarificación de baselines en `SYSTEM_CONTEXT.md`.
  - Migración atómica de `.cache/local_memory.json` a un esquema versionado.
  - Saneamiento del Playbook (eliminación de bypass de QA y documentación de incidentes).
  - Parcheo estructural de la skill `codely-plan-create-github` (incluyendo frontmatter).
- **Out-of-Scope**:
  - Modificación de lógica de señales o backtesting en `src/`.
