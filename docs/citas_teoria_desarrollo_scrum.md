# Fundamentación Teórica y Mapeo Epistemológico Cruzado
## Trabajo Práctico: Gestión de Proyectos con Scrum e Inteligencia Artificial (HIA 2026)

**Carrera:** Analista Programador Universitario (APU) - Facultad de Ingeniería, UNJu  
**Cátedra:** Herramientas Informáticas Avanzadas  
**Profesor Adjunto:** Ing. Alfredo R. Espinoza  

---

## 📌 Propósito de este Documento

Este documento constituye la **base epistemológica y el marco de fundamentación teórica exclusiva** del Trabajo Práctico. Su objetivo es articular rigurosamente cada decisión técnica, artefacto, evento y práctica ágil implementada en el proyecto con la bibliografía obligatoria de la cátedra:

1. **[Cátedra-HIA]** *Herramientas Informáticas en el Proceso de Gestión* — Ing. Alfredo R. Espinoza (Páginas 1 a 8).
2. **[Scrum-Master]** *Scrum Master - Temario Troncal v3.052* — Marta Palacio, Scrum Manager® (Páginas 1 a 80).
3. **[Enunciado-TP]** *Gestión de Proyectos con Scrum 2026* — HIA, APU (Páginas 1 a 3).

---

## 📑 Tabla de Mapeo Teórico Cruzado por Dimensión del Proyecto

| Dimensión del TP | Concepto Teórico Aplicado | Fuente Bibliográfica | Cita Textual y Referencia de Página | Aplicación Concreta en el TP 2026 |
| :--- | :--- | :--- | :--- | :--- |
| **1. Paradigma Metodológico** | Modelo Iterativo e Incremental vs Cascada | **[Cátedra-HIA]** p. 2; **[Scrum-Master]** pp. 11-12 | *"La metodología Agile es una forma de gestión de proyectos... de tipo iterativo y creciente en el que las tareas se agrupan en pequeñas etapas repetitivas conocidas como iteraciones, donde los requisitos y soluciones van evolucionando con el tiempo"* (Espinoza, p. 2). | Se adopta Scrum puro para la plataforma de microservicios contenerizados en Docker, estructurado en Sprints de 2 semanas donde cada iteración entrega un incremento desplegable. |
| **2. Selección de Herramienta** | Gestión de Tableros Scrum / Kanban | **[Cátedra-HIA]** pp. 6-8; **[Scrum-Master]** p. 68 | *"Jira Software está enfocado principalmente a la gestión de proyectos que utilizan metodologías ágiles y su funcionamiento está basado en el uso de tableros... Trello se basa en la metodología de trabajo japonesa Kanban... cada columna representa un estado en el proceso"* (Espinoza, pp. 6-7). | Se selecciona **GitHub Projects + Trello** por combinar tableros ágiles con integración nativa al repositorio Git, trazabilidad directa de ramas/commits/PRs y costo $0 para el equipo académico. |
| **3. Pilares Empíricos** | Transparencia, Inspección y Adaptación | **[Scrum-Master]** p. 62 | *"Scrum se basa en el control de procesos empírico. El empirismo asegura que el conocimiento procede de la experiencia y de tomar decisiones basándose en lo que se conoce... Tres pilares sustentan toda implementación: Transparencia, Inspección y Adaptación."* | - **Transparencia:** Tablero público con WIP visible.<br>- **Inspección:** Dailies y Sprint Review.<br>- **Adaptación:** Retrospectiva y ajuste continuo de backlog. |
| **4. Estructura de Roles** | Comprometidos vs Implicados (Fábula del Cerdo y la Gallina) | **[Scrum-Master]** pp. 33-36 | *"En un plato de huevos con jamón, la gallina está implicada, pero el cerdo está comprometido... El equipo scrum está formado por las personas comprometidas: Product Owner, Scrum Master y Developers."* | - **Product Owner (Marcos):** Dueño del valor de negocio y priorización pura (sin desarrollo técnico).<br>- **Scrum Master (Integrante 2):** Facilitador, coach y backend developer.<br>- **Developers (Integrantes 2 y 3):** Construcción técnica de la plataforma Docker. |
| **5. Product Backlog y Épicas** | Artefacto Vivo y Emergente | **[Scrum-Master]** pp. 37-39; **[Cátedra-HIA]** p. 6 | *"El Product Backlog es una lista ordenada de todo lo que se conoce que es necesario en el producto. Es la única fuente de requisitos para cualquier cambio a realizarse... Nunca está completo. Es dinámico y evoluciona constantemente."* | Estructuración de 5 Épicas tecnológicas nativas en Docker y 15 Historias de Usuario con formato estándar (*Como... Quiero... Para...*) priorizadas por valor de negocio. |
| **6. Criterios de Calidad** | Definición de Hecho (DoD) y Criterios de Aceptación | **[Scrum-Master]** pp. 42-43 | *"La Definición de Hecho (Definition of Done) es una comprensión compartida por el equipo de lo que significa que el trabajo esté completado... Si un ítem no cumple la DoD, no se puede presentar en la Review ni considerarse parte del Incremento."* | Cada Historia posee Criterios de Aceptación expresados en lenguaje Gherkin (*Dado/Cuando/Entonces*) y la DoD exige validación de `docker compose config`, pruebas pasando, revisión por pares y cierre estricto de puertos (`expose 3306`). |
| **7. Estimación Ágil** | Story Points, Planning Poker y Fibonacci | **[Scrum-Master]** pp. 54-57 | *"Los Story Points miden el esfuerzo relativo combinando volumen de trabajo, complejidad técnica e incertidumbre o riesgo... Se utiliza la serie de Fibonacci modificada (1, 2, 3, 5, 8, 13...) para evitar falsas precisiones."* | Estimación de las 15 Historias de Usuario mediante Planning Poker con baraja Fibonacci, totalizando 48 Story Points (26 SP comprometidos para el Sprint 1). |
| **8. Evento: Daily Scrum** | Inspección Diaria y Timeboxing | **[Scrum-Master]** pp. 48-49 | *"La Daily Scrum es una reunión diaria de 15 minutos para el equipo de desarrollo... No es una reunión de reporte de estado al jefe, sino de sincronización entre pares respondiendo a tres preguntas: ¿Qué hice ayer? ¿Qué haré hoy? ¿Qué impedimentos tengo?"* | Registro formal de bitácora de Dailies (Días 1, 4, 8) con identificación temprana y resolución de 2 impedimentos reales (WebSockets en Nginx y DNS interno de Docker en n8n). |
| **9. Medición y Control** | Burndown Chart y Velocidad del Equipo | **[Scrum-Master]** pp. 57-59; **[Cátedra-HIA]** p. 5 | *"El Sprint Burndown Chart muestra la cantidad de trabajo pendiente a lo largo del tiempo del sprint... Permite visualizar de un vistazo si el equipo alcanzará el objetivo del sprint o si debe renegociar alcance con el PO."* | Gráfico de Burndown trazado día por día comparando la línea de quemado ideal vs real iniciando exactamente en **26 SP** y finalizando en 0 SP. |
| **10. Evento: Sprint Review** | Inspección del Incremento y Demostración | **[Scrum-Master]** pp. 50-51 | *"El propósito de la Sprint Review es inspeccionar el resultado del sprint y determinar adaptaciones futuras. El equipo presenta el incremento potencialmente desplegable a los interesados y el PO explica qué se ha completado y qué no."* | Demostración funcional en vivo ante el Product Owner: stack Docker Compose levantando en 20s, Nginx Gateway enrutando tráfico, base MySQL persistente y aislada y flujos n8n activos. |
| **11. Evento: Retrospectiva** | Mejora Continua (*Kaizen*) | **[Scrum-Master]** pp. 52-53 | *"La Retrospectiva es la oportunidad del equipo para inspeccionarse a sí mismo y crear un plan de mejoras para el siguiente sprint... Aborda personas, relaciones, procesos y herramientas."* | Aplicación de la técnica *4Ls (Liked, Learned, Lacked, Longed for)* con compromisos concretos y accionables para el siguiente ciclo. |
| **12. Gestión de Riesgos** | Incertidumbre, Spikes y Planes de Mitigación | **[Scrum-Master]** pp. 24, 71-72; **[Cátedra-HIA]** p. 1 | *"En la gestión ágil, el riesgo se mitiga de forma inherente acortando el ciclo de retroalimentación... Cuando la incertidumbre técnica es alta, se recurre a un Spike (historia de investigación exploratoria)."* | Identificación formal de 10 riesgos de la arquitectura de contenedores y desarrollo exhaustivo de los 5 riesgos más severos (incluyendo la no exposición pública de bases de datos). |
| **13. Integración de IA** | Automatización Asistida y Juicio Crítico | **[Enunciado-TP]** pp. 1-3 | *"El equipo deberá planificar, ejecutar y revisar el desarrollo utilizando Scrum... apoyándose en IA generativa para optimizar la productividad... registrando herramienta, prompt, respuesta, análisis, correcciones y resultado final."* | Bitácora de 6 interacciones estratégicas de IA (generación de historias, criterios Gherkin, WebSockets en Nginx, pipeline CI/CD, riesgos y retrospectiva) con validación técnica humana. |

---

## 🏛️ Análisis Epistemológico Detallado

### 1. Variables de Gestión según la Cátedra HIA
El apunte de cátedra del Ing. Alfredo Espinoza (*Herramientas Informáticas en el Proceso de Gestión, p. 1*) establece:
> *"Todos los proyectos software a pesar de sus diferencias suelen tener una serie de variables o propiedades que los caracterizan: Alcance, Tiempo, Coste, Calidad, Recursos y Riesgos. Estas propiedades están presentes en todos los proyectos y se pueden utilizar para clasificar los proyectos, obtener información sobre los mismos y sacar conclusiones."*

**Fundamentación en el TP 2026:**
- En el enfoque tradicional (cascada), el **alcance** se fija rígidamente y fluctúan el tiempo y el costo.
- En nuestro proyecto Scrum con Docker, invertimos el triángulo de hierro: el **tiempo** (Sprint de 2 semanas) y los **recursos** (3 desarrolladores) son fijos, mientras que el **alcance** se gestiona de forma adaptativa mediante la priorización continua del Product Backlog, asegurando siempre la máxima **calidad** y mitigación de **riesgos**.

### 2. Los Tres Pilares Empíricos y los Cinco Valores Scrum
Marta Palacio (*Scrum Master v3.052, pp. 62-63*) enfatiza que Scrum no es una metodología prescriptiva cerrada, sino un marco de trabajo fundamentado en el empirismo:
> *"1. Transparencia: Los aspectos significativos del proceso deben ser visibles para aquellos que son responsables del resultado.*  
> *2. Inspección: Los usuarios de Scrum deben inspeccionar frecuentemente los artefactos y el progreso hacia un objetivo para detectar variaciones indeseadas.*  
> *3. Adaptación: Si el inspector determina que uno o más aspectos se desvían de los límites aceptables, el proceso o el material debe ser ajustado cuanto antes."*

Acompañando estos pilares, el proyecto ejercita los **5 valores de Scrum** (*Palacio, p. 63*):
- **Compromiso:** Asumir metas de Sprint realistas basadas en la capacidad demostrada (26 SP).
- **Coraje:** Reconocer impedimentos técnicos complejos y corregir la arquitectura de red hacia un aislamiento real.
- **Foco:** Trabajar exclusivamente en los microservicios seleccionados para el Sprint Backlog activo.
- **Apertura:** Visibilidad completa de métricas, riesgos y código en GitHub.
- **Respeto:** Confianza en la autonomía profesional y multidisciplinaria de cada integrante.

---

## 🔗 Conclusión Teórica de la Arquitectura
La integración metodológica implementada en el Trabajo Práctico no utiliza Scrum de manera superficial ni aislada. Se fundamenta en el marco normativo de la cátedra de Herramientas Informáticas Avanzadas y en los estándares internacionales de Scrum Manager®, asegurando una trazabilidad científica completa entre la teoría de gestión de proyectos y la implementación técnica de la plataforma de microservicios con Docker.
