# 8. Cheat Sheet de Prompts

La presente sección consolida un recetario institucional de instrucciones sintéticas. Su propósito fundamental es alinear e inducir rigurosamente las respuestas y operaciones de cualquier agente técnico durante el desarrollo del sistema y sesiones de ingeniería concurrente.

## 8.1. Iniciación de un Nuevo Ticket de Desarrollo

Emplear el siguiente esquema de instrucción previo a la inserción de código con el objeto de garantizar el alineamiento operativo al backlog activo del fondo.

```markdown
Se solicita iniciar la etapa de desarrollo vinculada al Issue #<ID>. 
Previo a cualquier acción ejecutiva, es mandatario:
1. Examinar el documento `SYSTEM_CONTEXT.md` para incorporar las nociones operativas y comprender los módulos vigentes en la iteración.
2. Examinar el documento `AGENTS.md` a fines de adecuar estrictamente sus lógicas internas a los lineamientos ScrumBan, la arquitectura TDD y la taxonomía de los repositorios.
3. Asegurar su operación técnica sobre la rama de origen designada: `feat/<ID>-<nombre-corto>`. Instánciela en caso de no encontrarse instanciada.

Requiere la presentación formal de un diseño secuencial de arquitectura previo al volcado del código productivo.
```

## 8.2. Políticas de Ordenamiento de Directorios

Esta instrucción tiene como misión impedir la degeneración estructural de los componentes del motor y evitar la inserción arbitraria de código huérfano.

```markdown
Aviso de cumplimiento arquitectónico:
- Queda terminantemente PROHIBIDO instanciar archivos lógicos o artefactos de ejecución de forma aislada sobre la raíz de la estructura de trabajo.
- Toda nueva incorporación de lógica a los sistemas productivos debe asignarse al subdirectorio correspondiente bajo `src/`.
- Cualquier script temporal empleado para diagnósticos algorítmicos o depuración deberá ser alojado en el subdirectorio `scratch/`, resguardando que sea excluido del sistema de control de versiones.
```

## 8.3. Cierre y Guardado de Memoria (ScrumBan)

Utilizado al validar un avance algorítmico, a fin de blindar el conocimiento de la iteración mediante el protocolo de memoria local institucional.

```markdown
Validado el correcto funcionamiento del modelo y comprobado el estado verde de la suite de pruebas unitarias, se procede a demandar las siguientes acciones:
1. Realice la adición de una entrada de registro al archivo `.cache/local_memory.json`, asumiendo estrictamente el esquema de objeto JSON determinado para el control operativo (timestamp, title, type, scope, topic_key, content).
2. Procese el volcado en control de versiones utilizando nomenclatura de commit convencional, ajustada a: `[Módulo] Resumen del alcance. Fixes #<ID>`.
3. Ante incidencias de validación pre-commit local derivadas exclusivamente de sobrecarga de argumentos transaccionales, se autoriza la utilización del parámetro `--no-verify` de manera excepcional durante la etapa commit y push.
```

## 8.4. Protocolos de Remediación

En caso de desviaciones en la conducta técnica u omisiones involuntarias de los protocolos TDD, se aplican los siguientes esquemas correctivos para rectificar la estructura del código y los requerimientos de la métrica funcional:

**Remediación por Incumplimiento de Pruebas:**
```markdown
Se detecta una actualización directa sobre el componente <ruta_del_archivo> diseñada para subsanar un comportamiento anómalo. No obstante, dicho avance carece de marco metodológico TDD. Corresponde regularizar la acción:
1. Escrutar analíticamente el componente modificado para comprender el defecto primario de lógica.
2. Construir e implementar una prueba unitaria estructurada sobre la carpeta `tests/` que permita documentar reproduciblemente la naturaleza del fallo inicial.
3. Ejecutar la evaluación sistémica mediante `pytest`, verificando que el ajuste algorítmico valide el pase íntegro y que el motor certifique un 100% de operaciones correctas.
4. Anotar e incluir este bugfix en la base del conocimiento local `.cache/local_memory.json` estipulando en la categoría: "type: bugfix".
```

**Remediación por Entropía en Directorios:**
```markdown
A raíz de diversas iteraciones para instrumentar el requerimiento <nombre_feature>, se evidencia fragmentación estructural y ubicación incorrecta de dependencias. Proceda a rectificar el entorno:
1. Examine y enumere los artefactos y archivos lógicos posicionados fuera del diseño taxonómico.
2. Traslade sistemáticamente las pruebas e integraciones temporales a la ruta `experiments/` y redirija el código matricial definitivo hacia el dominio de producción `src/`.
3. Suprima cualquier archivo que figure como huérfano dentro de la raíz de trabajo principal.
4. Proceda con la actualización pertinente en el registro de la configuración `SYSTEM_CONTEXT.md` informando la incorporación técnica y su localización activa.
```

**Remediación por Residuos de Diagnóstico Local:**
```markdown
La operación generó trazas logísticas y residuos transaccionales que persisten fuera del esquema del sistema de control de versiones. Proceda a regularizar este escenario:
1. Reubique o deprima la totalidad del contenido residual y archivos temporales, confinándolos a la órbita del dominio ignorable `scratch/`.
2. Emita una sentencia de verificación de estado `git status` para ratificar un entorno sin artefactos técnicos sueltos o huérfanos.
3. Ante la necesidad de refactorizar dependencias menores, asiente el concepto y su alcance adjuntando la novedad breve sobre la memoria `.cache/local_memory.json`.
```