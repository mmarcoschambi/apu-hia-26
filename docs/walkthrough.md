# Walkthrough: Trabajo Práctico de Gestión de Proyectos con Scrum e IA (HIA 2026)

## 📌 Resumen de la Solución Implementada
Se completó la estructuración integral del entorno de trabajo, repositorios Git, worktrees y la documentación académica y técnica para el Trabajo Práctico de **Gestión de Proyectos con Scrum** de la materia *Herramientas Informáticas Avanzadas (APU - UNJu)*.

La arquitectura se encuentra completamente alineada con las mejores prácticas de la industria y la rigurosidad de auditoría:
1. **Contrato DNS Unificado:** El servicio de base de datos se declara como `mysql` y cuenta con alias de red `['mysql', 'mysql-db']`, haciendo coincidir al 100% la especificación ágil con el hostname utilizado por n8n (`DB_MYSQLDB_HOST=mysql`).
2. **Aislamiento de Red Externo Real (`internal: true`):** La red `app-network` está declarada con `internal: true`, impidiendo físicamente cualquier enrutamiento o filtración de paquetes hacia o desde el exterior.
3. **Cero Exposición de Puertos en el Host:** MySQL utiliza `expose: ["3306"]` sin directiva `ports`, eliminando cualquier socket en `0.0.0.0` del host.
4. **Protección Integral de Secretos en `.gitignore`:** Exclusión explícita de `secrets/`, `certs/`, `.env`, `docker-compose.override.yml` y volúmenes de datos.

---

## 📁 Estructura de Archivos del Repositorio

```
D:\FACU\3er_año\HIA-worktrees\tp-scrum\
├── docker-compose.yml                                      <-- [VERIFICADO] Orquestación base con internal: true y aliases DNS
├── docker-compose.override.yml.example                     <-- [VERIFICADO] Plantilla para desarrollo local (127.0.0.1:3306)
├── .env.example                                            <-- [VERIFICADO] Plantilla de variables seguras
├── .gitignore                                              <-- [VERIFICADO] Exclusión estricta de secrets/, certs/ y overrides
├── nginx/
│   └── nginx.conf                                          <-- Gateway + WebSockets para n8n
├── mysql/
│   └── init/
│       └── 01-init.sql                                     <-- Esquema inicial y seed de tabla productos
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
│   ├── informe_tp_scrum_2026.md                            <-- Informe maestro integral de 10 secciones (26 SP unificados)
│   ├── tablero_scrum_backlog.json                          <-- Esquema JSON estructurado para Trello/GitHub
│   └── walkthrough.md                                      <-- Resumen ejecutivo de la solución
└── README.md
```

---

## 🔍 Evidencia de Validación Técnica

### 1. Validación Estructural de YAML
```text
Services: ['nginx-gateway', 'n8n-automation', 'mysql']
Networks: {
  'gateway-net': {'driver': 'bridge', 'name': 'pmai_gateway_net'},
  'app-network': {'driver': 'bridge', 'name': 'pmai_app_net', 'internal': True}
}
MySQL service aliases: ['mysql', 'mysql-db']
n8n DB_MYSQLDB_HOST: ['DB_MYSQLDB_HOST=mysql']
```

### 2. Validación de Reglas `.gitignore`
```text
.gitignore:13:secrets/			secrets/my_key.pem
.gitignore:14:certs/			certs/server.crt
.gitignore:17:docker-compose.override.yml	docker-compose.override.yml
.gitignore:7:.env			.env
```
