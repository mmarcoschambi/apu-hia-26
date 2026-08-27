# Walkthrough: Trabajo Práctico de Gestión de Proyectos con Scrum e IA (HIA 2026)

## 📌 Resumen de la Solución Implementada
Se completó la estructuración integral del entorno de trabajo, repositorios Git, worktrees y la documentación académica y técnica para el Trabajo Práctico de **Gestión de Proyectos con Scrum** de la materia *Herramientas Informáticas Avanzadas (APU - UNJu)*.

La arquitectura del proyecto gestionado se diseñó como una **Plataforma Modular de Microservicios 100% nativa en Docker & Docker Compose**, respaldada por archivos declarativos reales y verificables en el repositorio (`docker-compose.yml`, `nginx/nginx.conf`, `mysql/init/01-init.sql`, `.env.example` y `.gitignore` con exclusión estricta de secretos y overrides).

---

## 📁 Estructura Completa de Archivos en el Worktree

```
D:\FACU\3er_año\HIA-worktrees\tp-scrum\
├── docker-compose.yml                                      <-- [NUEVO] Orquestación base multicapa verificada
├── docker-compose.override.yml.example                     <-- [NUEVO] Plantilla para desarrollo local (127.0.0.1:3306)
├── .env.example                                            <-- [NUEVO] Plantilla de variables seguras
├── .gitignore                                              <-- [ACTUALIZADO] Exclusión estricta de overrides y secretos
├── nginx/
│   └── nginx.conf                                          <-- [NUEVO] Configuración Gateway + WebSockets para n8n
├── mysql/
│   └── init/
│       └── 01-init.sql                                     <-- [NUEVO] Esquema inicial y seed de tabla productos
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
└── README.md
```

---

## 🛡️ Evidencia de Seguridad y Aislamiento de Red

### 1. Frontera de Red Real (`app-network` vs `gateway-net`)
- **`nginx-gateway`:** Conectado a `gateway-net`. Expone puertos `80` y `443` hacia el exterior.
- **`n8n-automation`:** Conectado a ambas redes (`gateway-net` para recibir tráfico del proxy y `app-network` para consultar datos).
- **`mysql-db`:** Conectado **exclusivamente a `app-network`**. Posee directiva `expose: ["3306"]` para habilitar conectividad interna por DNS hacia `n8n` sin abrir ningún puerto en la interfaz de red del host (`0.0.0.0`).

### 2. Validación Automatizada de Esquema YAML
```text
YAML validation SUCCESSFUL! Services: ['nginx-gateway', 'n8n-automation', 'mysql-db']
Networks: ['gateway-net', 'app-network']
Volumes: ['mysql_data', 'n8n_data']
MySQL networks: ['app-network']
MySQL expose: ['3306']
MySQL ports: NONE (Cerrado al host)
```

### 3. Exclusiones en `.gitignore`
```text
.gitignore:14:docker-compose.override.yml	docker-compose.override.yml
.gitignore:7:.env				.env
.gitignore:15:data/				data/
.gitignore:16:mysql_data/			mysql_data/
```

---

## 🎯 Resumen de Entregables Principales

1. **Informe Maestro (10 Secciones):** [`docs/informe_tp_scrum_2026.md`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/informe_tp_scrum_2026.md) (Velocidad unificada en **26 SP**, 5 Épicas, 15 Historias Gherkin, DoD estricta, 10 Riesgos con 5 profundos, Dailies, Retrospectiva 4Ls y 6 interacciones de IA).
2. **Citas Teóricas Cruzadas:** [`docs/citas_teoria_desarrollo_scrum.md`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/citas_teoria_desarrollo_scrum.md) (Citas textuales de Espinoza y Palacio).
3. **Tablero JSON:** [`docs/tablero_scrum_backlog.json`](file:///D:/FACU/3er_a%C3%B1o/HIA-worktrees/tp-scrum/docs/tablero_scrum_backlog.json).
4. **Infraestructura Declarativa:** `docker-compose.yml`, `nginx/nginx.conf`, `mysql/init/01-init.sql`, `.env.example`.
