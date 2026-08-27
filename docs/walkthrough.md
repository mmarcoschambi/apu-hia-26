# Walkthrough: Trabajo Práctico de Gestión de Proyectos con Scrum e IA (HIA 2026)

## 📌 Resumen de la Solución Implementada
Se completó la estructuración integral del entorno de trabajo, repositorios Git, worktrees y la documentación académica y técnica para el Trabajo Práctico de **Gestión de Proyectos con Scrum** de la materia *Herramientas Informáticas Avanzadas (APU - UNJu)*.

La arquitectura del proyecto gestionado se diseñó como una **Plataforma Modular de Microservicios 100% nativa en Docker & Docker Compose** (Gateway Nginx, MySQL 8.0 persistente, n8n Workflow Automation y GitHub Actions CI/CD), garantizando simplicidad de red, portabilidad absoluta y desacoplamiento total de hipervisores físicos.

---

## 📁 Estructura Completa de Archivos en el Worktree

```
D:\FACU\3er_año\HIA-worktrees\tp-scrum\
├── docs/
│   ├── enunciados/
│   │   ├── TP_Scrum_Gestion_Proyectos_2026.pdf              <-- Enunciado oficial activo (Scrum 2026)
│   │   └── TP1_Practica_Ambiente_Desarrollo_Proxmox_2026.pdf <-- [Referencia] Enunciado TP1 Infraestructura
│   ├── teoria/
│   │   ├── Herramientas_Informaticas_Gestion_Proyectos.pdf    <-- Apunte de Cátedra (Ing. Espinoza)
│   │   └── Scrum_Master_Guia.pdf                            <-- Manual Oficial Scrum Manager (M. Palacio)
│   ├── guias/                                               <-- [Referencia histórica del TP1 Proxmox]
│   │   ├── Credenciales_TP1_Proxmox.md
│   │   ├── Guia_Grabacion_Video_TP1.md
│   │   └── Guión y Presentación Técnica - TP1 Proxmox VE.md
│   ├── citas_teoria_desarrollo_scrum.md                    <-- Mapeo epistemológico y citas exclusivas
│   ├── informe_tp_scrum_2026.md                            <-- Informe maestro integral de 10 secciones
│   ├── tablero_scrum_backlog.json                          <-- Esquema JSON estructurado para Trello/GitHub
│   └── walkthrough.md                                      <-- Resumen ejecutivo de la solución
├── README.md
└── .gitignore
```

---

## 🎯 Contenido de los Documentos Principales

### 1. Documento Exclusivo de Mapeo Teórico Cruzado
- **Ruta:** [`D:\FACU\3er_año\HIA-worktrees\tp-scrum\docs\citas_teoria_desarrollo_scrum.md`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/citas_teoria_desarrollo_scrum.md)
- **Aspectos Teóricos Fundamentados:**
  - Modelo Iterativo e Incremental vs Cascada (*Espinoza, p. 2; Palacio, pp. 11-12*).
  - Comparativa de herramientas: Jira vs Trello vs Wrike vs GitHub Projects (*Espinoza, pp. 6-8*).
  - Tres Pilares Empíricos (Transparencia, Inspección, Adaptación) y Cinco Valores Scrum (*Palacio, pp. 62-63*).
  - Fábula del cerdo y la gallina: Comprometidos vs Implicados (*Palacio, p. 33*).
  - Definición de Hecho (DoD) y Criterios de Aceptación Gherkin (*Palacio, pp. 42-43*).
  - Estimación ágil con Story Points, Planning Poker y serie Fibonacci (*Palacio, pp. 54-57*).
  - Eventos Scrum (Sprint 2 semanas, Dailies de 15 min, Review y Retrospectiva) (*Palacio, pp. 44-53*).
  - Gestión de Riesgos e Incertidumbre con Spikes técnicos (*Palacio, p. 71; Espinoza, p. 1*).

### 2. Informe Maestro del Proyecto
- **Ruta:** [`D:\FACU\3er_año\HIA-worktrees\tp-scrum\docs\informe_tp_scrum_2026.md`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/informe_tp_scrum_2026.md)
- **Secciones Oficiales Cumplidas:**
  1. *Documento del Proyecto:* Nombre, contexto metodológico vs tecnológico, problema, justificación, objetivos SMART, alcance y entregables.
  2. *Selección de Herramienta:* GitHub Projects + Trello, flujo de 5 columnas, matriz de roles con **Product Owner puro**.
  3. *Product Backlog:* 5 Épicas nativas en Docker, 15 Historias de Usuario completas con subtareas técnicas, priorización MoSCoW, Story Points y criterios de aceptación formales Gherkin (`Dado/Cuando/Entonces`).
  4. *Planificación del Sprint:* Sprint 1 de 2 semanas (10 días), **26 Story Points** unificados (consistencia matemática total), capacidad de 180 hs ideales, Gantt y Burndown chart iniciando en 26 SP y terminando en 0 SP.
  5. *Matriz de 10 Riesgos:* Categorización y cálculo de probabilidad × impacto en entornos Docker.
  6. *Análisis Profundo de 5 Riesgos Críticos:* Disparadores (*Triggers*), medidas de prevención proactivas y planes de contingencia (comandos de restore `gunzip < backup.sql.gz`, límites `mem_limit`, git-secrets y gestión de alcance).
  7. *Ejecución del Sprint:* Bitácora de Dailies (Días 1, 4, 8), resolución de 2 bloqueos reales (WebSockets en Nginx y DNS interno de Docker `mysql:3306`), políticas de branching (GitHub Flow) y DoD.
  8. *Sprint Review & Retrospectiva:* Demostración funcional ante el PO y dinámica 4Ls con compromisos de mejora.
  9. *Bitácora de Inteligencia Artificial:* 6 interacciones estratégicas con herramienta, prompt exacto, respuesta cruda, análisis crítico del equipo, correcciones aplicadas y resultado final incorporado.
  10. *Conclusiones Finales y Cierre.*

### 3. Esquema Estructurado del Tablero (JSON)
- **Ruta:** [`D:\FACU\3er_año\HIA-worktrees\tp-scrum\docs\tablero_scrum_backlog.json`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/tablero_scrum_backlog.json)
- **Utilidad:** Exportable e importable para cargar las 5 épicas, 15 historias, estados, prioridades y asignaciones directamente en Trello o GitHub Projects.

---

## 🔍 Validación y Versionado Git
- Todos los cambios se encuentran versionados en la rama `feature/tp-scrum` dentro del worktree de trabajo.
