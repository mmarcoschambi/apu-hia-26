# 6. Ciclo de Vida del Ticket (Protocolo ScrumBan)

El presente capítulo instaura el flujo algorítmico y metodológico obligatorio aplicable a toda modificación en el código fuente de Momentum V2. Esta directiva garantiza que el repositorio base se mantenga exento de entropía estructural y archivos redundantes o huérfanos.

## 6.1. Diagrama de Flujo del Proceso

El ciclo operativo debe comprender de forma estandarizada todas las fases, partiendo de la conceptualización de los requerimientos técnicos y finalizando con la homologación e integración de la solución en el repositorio matriz.

## 6.2. Fase 1: Apertura y Branching

**Regla Institucional:** Se prohíbe tajantemente la escritura de código o generación de nuevas lógicas sin un registro (ticket) activo en la plataforma GitHub. Este principio funda la base de la trazabilidad a lo largo del proceso de desarrollo.

**💻 Comandos Obligatorios de Consola:**

```bash
gh issue list --state open       # Consultar los requerimientos abiertos en el backlog.
gh issue view <ID>               # Inspeccionar formalmente los criterios de aceptación.
git checkout -b feat/<ID>-name   # Instanciar una rama de trabajo aislada y limpia.
```

**💬 Prompt de Inicialización de Contexto:**

```markdown
Estimado equipo o sistema automatizado: 
Vamos a iniciar formalmente el desarrollo del Issue #<ID>.
Por favor, apéguese a las siguientes directrices:
1. Examine `SYSTEM_CONTEXT.md` para asimilar el roadmap y los módulos en producción.
2. Analice `AGENTS.md` para garantizar el alineamiento estricto con las restricciones algorítmicas de la institución.
3. Posiciónese en la rama funcional `feat/<ID>-<nombre-corto>`.
4. Evalúe el impacto en los archivos referenciados y emita una propuesta de implementación por pasos antes de redactar código.
```

## 6.3. Fase 2: Planificación y Diseño (SDD)

**Regla Institucional:** Previo a alterar el entorno productivo, el encargado del desarrollo (humano o agente) debe presentar una arquitectura funcional detallada del diseño técnico. Dicha previsión minimiza la ocurrencia de roturas de dependencias y refactorizaciones ciegas.

**🔍 Verificación Estructural:**

Corresponde realizar una evaluación a través de `SYSTEM_CONTEXT.md` a fin de demarcar la arquitectura canónica. Asimismo, se debe auditar el grado de impacto previsible sobre el motor de simulación o el módulo de escaneo en tiempo real (Live Scanner).

**💬 Prompt de Control de Planificación:**

```markdown
Proceda con la lectura de los módulos afectados vinculados a la propuesta del Issue #<ID>.
Previamente a cualquier alteración en el código base, requiero lo siguiente:
1. Resuma cómo dichos módulos se interconectan lógicamente con el sistema global.
2. Constate si se requiere la intervención en componentes críticos (ej. `signal_engine.py`) o si resulta pertinente trabajar dentro de módulos de prueba/scratch.
3. Documente anticipadamente los casos de prueba unitaria que darán validación matemática y lógica a estos cambios.
```

## 6.4. Fase 3: TDD Red (Desarrollo de Pruebas)

**Regla Institucional:** La normativa exige redactar o parametrizar el marco de prueba (Test) de manera anticipada al código de negocio (Fase RED). Si no existe una falla documentada en el entorno de pruebas, se asume que no existe comprensión certera sobre la solución demandada.

**💻 Comandos Obligatorios de Consola:**

```bash
pytest tests/test_modulo_especifico.py  # Ejecuta el test diseñado (el resultado esperado es el fallo).
```

**💬 Prompt para Inducción de TDD Red:**

```markdown
Requiero la implementación de esta funcionalidad adhiriéndose estrictamente al marco metodológico TDD:
1. Desarrolle, como paso inicial, los test unitarios pertinentes dentro del directorio `tests/`, garantizando que cubran los criterios técnicos expuestos.
2. Ejecute pytest y certifique el fallo consecuente de la prueba (estado RED validado).
3. Absténgase de escribir cualquier línea en el directorio productivo `src/` hasta nueva orden.
```

## 6.5. Fase 4: Implementación (TDD Green)

**Regla Institucional:** El desarrollo dentro de `src/` debe constar exclusivamente de la lógica mínima requerida para lograr el pase positivo de las pruebas unitarias (Fase GREEN). Con el hito completado, se procederá a refactorizar de manera segura.

**📂 Estructura Arquitectónica Homologada:**

- **Módulos de Producción:** Ubicación exclusiva en `src/` (ejemplo: `src/signals/`, `src/backtest/`).
- **Validación Matemática:** Ubicación en `tests/` (ejemplo: `tests/test_signal_engine.py`).
- **Desarrollo Exploratorio:** Estrictamente confinados al directorio temporal `scratch/`.

**💬 Prompt de Paso a Verde:**

```markdown
Validado el estado de fallo (RED):
1. Proceda con la implementación del código lógico y matemático mínimo requerido en el entorno `src/` para alcanzar el pase de la prueba.
2. Considere que el código de producción debe insertarse obligatoriamente en un subdirectorio bajo `src/`, prohibiéndose ubicar lógicas aisladas en la raíz del repositorio.
3. Ejecute pytest de forma iterativa y evidencie la superación íntegra (100% verde) de la suite analizada.
```

## 6.6. Fase 5: Documentación y Memoria Local

**Regla Institucional:** Cualquier progreso que carezca de trazabilidad en los archivos de memoria institucional, carece de existencia empírica en las operaciones subsecuentes. La documentación robusta del estado arquitectónico previene la acumulación de deuda técnica.

**📂 Registros Requeridos para Actualización:**

- **Registro Histórico de Decisiones (Local Memory):** Almacenado en `.cache/local_memory.json` para sustentar la trazabilidad de ScrumBan.
- **Definiciones del Sistema:** Cambios en arquitectura y rutas deben reflejarse en `SYSTEM_CONTEXT.md`.

**💬 Prompt de Registro Arquitectónico:**

```markdown
Finalizada la integración técnica y validadas las pruebas:
1. Anexe un nuevo registro histórico en el archivo `.cache/local_memory.json` de conformidad con el formato institucional (incluyendo los campos timestamp, title, type, scope, topic_key y content).
2. De haberse incurrido en alteraciones estructurales o relativas al mapa de archivos, asiente dichos eventos en la sección pertinente de `SYSTEM_CONTEXT.md`.
```

## 6.7. Fase 6: Commit y Cierre

**Regla Institucional:** Culminar la fase operativa asumiendo una nomenclatura convencional en los registros (commits) y cerrar el incidente abierto en la plataforma GitHub aportando las métricas o validaciones obtenidas durante el proceso.

**💻 Comandos Recomendados de Consola:**

```bash
git commit -m "[Signals] Agregar filtro de volumen. Fixes #ID"
git push origin feat/ID-nombre
gh issue comment <ID> --body "[OK] Sistema evaluado y homologado dentro de la rama técnica..."
gh issue close <ID>
```

**💬 Prompt de Finalización:**

```markdown
Efectúe un commit convencional respetando la taxonomía institucional: `[Módulo] Breve descripción del cambio técnico. Fixes #<ID>`.
Si los procesos automatizados pre-commit generaran errores locales originados exclusivamente por saturación de argumentos, está autorizado el uso del parámetro `--no-verify` al ejecutar las instrucciones commit y push.
```