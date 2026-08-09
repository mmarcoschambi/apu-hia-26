# Spec: SDD/FSM Architecture Closure

## Requirements

### Requirement: REQ-1 - Reconciliación de Pipeline y Baseline
El pipeline operativo DEBE ejecutar la suite de integridad global sin excepciones, y la documentación core DEBE reflejar el congelamiento matemático del sistema diferenciando contextos.

#### Scenario: SCEN-1 - Alineación de umbrales y exclusiones
- **Given** la suite de testing global y el archivo `SYSTEM_CONTEXT.md`
- **When** se ejecuta la validación automatizada completa
- **Then** el reporte de ejecución incluye a `test_integrity`, y `SYSTEM_CONTEXT.md` declara explícitamente que el baseline de la Variante E (2.55% / -41.95%) es un contexto completamente separado del baseline global histórico completo (96.12% return / -35.09% MDD).

### Requirement: REQ-2 - Memoria de Gobernanza Activa y Segura
El orquestador DEBE persistir y recuperar reglas operativas a través de la memoria local usando un esquema fuertemente tipado sin pérdida de historial.

#### Scenario: SCEN-2 - Recuperación y validación de Memoria
- **Given** la memoria de persistencia local `.cache/local_memory.json` migrada a diccionario
- **When** el validador mecánico realiza el chequeo post-migración
- **Then** el validador certifica la existencia del campo `schema_version: "1.0"`, preserva exactamente el conteo histórico de entradas (22 previas, 25 totales) y recupera exitosamente las 3 nuevas reglas operativas insertadas.

### Requirement: REQ-3 - Playbook Pragmático y Estricto
El playbook DEBE prohibir explícitamente el bypass de calidad y estipular los incidentes operativos documentados en un formato determinista.

#### Scenario: SCEN-3 - Matriz Determinista de "Code Smells"
- **Given** la documentación de procesos `docs/playbook_sdd_scrumban.md`
- **When** se evalúa la integridad del manual
- **Then** el documento carece de instrucciones y racionalizaciones que inciten a evadir validaciones y contiene una matriz exacta de 5 entradas bajo el esquema `[Señal, Riesgo, Acción Obligatoria]`.

### Requirement: REQ-4 - Puente Arquitectónico Codely-OpenSpec
El planificador Codely DEBE integrarse mediante un adaptador local, entregando el control estrictamente al loop OpenSpec/Gentle-AI.

#### Scenario: SCEN-4 - Redirección del Hand-off Funcional
- **Given** la skill `codely-plan-create-github`
- **When** el runtime lee el frontmatter y el agente emite instrucciones
- **Then** tanto el runtime (descripción) como el hand-off del agente dirigen al operador a ejecutar explícitamente comandos OpenSpec (como `/sdd-ff` o `/sdd-new`) para la fase seleccionada, sin referencia residual a la skill hermana implementadora.
