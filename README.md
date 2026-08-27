# Herramientas Informáticas Avanzadas (HIA 2026) — APU / UNJu

## 📌 Trabajo Práctico: Gestión Ágil de Proyectos con Scrum e Inteligencia Artificial

Este repositorio contiene la planificación metodológica, documentación técnica y artefactos declarativos de la **Plataforma Modular de Automatización y Microservicios Cloud con Docker (PMA-Docker 2026)** para la carrera de *Analista Programador Universitario (Facultad de Ingeniería – Universidad Nacional de Jujuy)*.

---

## 👥 Scrum Team

- **Product Owner (Puro Negocio):** Marcos (APU-08421)
- **Scrum Master & Backend Dev:** Integrante 2 (APU-08512)
- **Developer & DevOps/QA:** Integrante 3 (APU-08633)

---

## 📁 Estructura del Repositorio

```
.
├── docker-compose.yml                      # Orquestación declarativa base (Nginx, n8n, MySQL 8.0)
├── docker-compose.override.yml.example     # Plantilla para desarrollo local (127.0.0.1:3306)
├── .env.example                            # Variables de entorno documentadas
├── .gitignore                              # Exclusión de secretos, overrides y datos
├── nginx/
│   └── nginx.conf                          # Gateway Proxy inverso + soporte WebSockets
├── mysql/
│   └── init/
│       └── 01-init.sql                     # Schema inicial y seed data
├── docs/
│   ├── enunciados/
│   │   └── TP_Scrum_Gestion_Proyectos_2026.pdf # Enunciado oficial de la cátedra
│   ├── teoria/
│   │   ├── Herramientas_Informaticas_Gestion_Proyectos.pdf # Apunte Cátedra (Ing. Espinoza)
│   │   └── Scrum_Master_Guia.pdf           # Manual Oficial Scrum Manager (M. Palacio)
│   ├── informe_tp_scrum_2026.md            # Informe maestro integral de 10 secciones (26 SP)
│   ├── citas_teoria_desarrollo_scrum.md    # Mapeo epistemológico y citas cruzadas
│   ├── tablero_scrum_backlog.json          # Esquema de backlog y épicas en JSON
│   └── walkthrough.md                      # Resumen ejecutivo y bitácora técnica
└── README.md
```

---

## 🚀 Despliegue del Entorno de Microservicios

1. **Configurar variables:**
   ```bash
   cp .env.example .env
   ```
2. **Levantar el stack:**
   ```bash
   docker compose up -d
   ```
3. **Acceso:**
   - **Gateway Web:** `http://localhost`
   - **Healthcheck Gateway:** `http://localhost/healthz`
   - **Base de Datos:** Aislada internamente en `app-network` (`internal: true`).
