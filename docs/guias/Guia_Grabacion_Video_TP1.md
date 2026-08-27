# Guion y Estructura para la Grabación del Video - TP1 Proxmox HIA (2026)

Este documento te sirve como guía paso a paso para grabar el video explicativo de ~8 minutos requerido en el TP1.

---

## ⏱️ Estructura del Video (8 Minutos)

### 1. Presentación e Introducción (~1 min)
- Presentación de los integrantes del grupo (nombres completos y LU).
- Mencionar la materia (*Herramientas Informáticas Avanzadas*) y el objetivo del TP (*Virtualización y gestión de contenedores con Proxmox VE*).
- Mostrar la consola web de Proxmox (`https://192.168.1.94:8006`).

---

### 2. Demostración de los Servidores Desplegados (~2.5 min)

#### A. Servidor Base de Datos (`debianbd` - CT 300)
- Mostrar en Proxmox el contenedor `300 (debianbd)` con sus especificaciones (1 CPU, 2 GB RAM, 10 GB Disco).
- Abrir **DBeaver** o **pgAdmin** en Windows y conectarse a `192.168.1.95:5432`.
- Ejecutar un `SELECT * FROM productos;` para mostrar la tabla creada con sus registros.

#### B. Servidor CMS (`jmlpserver` - CT 201)
- Mostrar el contenedor `201 (jmlpserver)` con sus especificaciones (1 CPU, 1 GB RAM, 20 GB Disco).
- Abrir el navegador en `https://192.168.1.96/` (sitio Joomla) y `https://192.168.1.96/administrator` mostrando el inicio de sesión del panel de control.

---

### 3. Demostración de Backups y Disaster Recovery (~2 min)
- Mostrar el almacenamiento **`local`** -> pestaña **Backups**, señalando el archivo `.tar.zst` del backup realizado.
- Explicar la prueba de *Disaster Recovery*: el contenedor original `200` fue respaldado, eliminado y restaurado exitosamente como `300` preservando los datos de PostgreSQL.
- Mostrar en `Datacenter -> Backup` la tarea de **Backup diario programado** configurada para ejecutarse automáticamente.

---

### 4. Demostración de las 3 Características Avanzadas (~2.5 min)

#### Característica 1: Control de Acceso (RBAC) y Pools
- Mostrar el **Pool `Desarrollo`** que contiene únicamente al contenedor `jmlpserver`.
- Cerrar sesión como `root` e iniciar sesión como **`alumno@pve`** (Clave: `Admin2026!`).
- **Punto clave:** Mostrar cómo el usuario `alumno` solo tiene permisos sobre su CMS y no puede ver ni modificar la base de datos de producción (`debianbd`).

#### Característica 2: Micro-segmentación con Firewall Integrado
- Mostrar en `debianbd (300) -> Firewall` la política estricta de entrada (**`DROP`**).
- Mostrar las dos únicas reglas de entrada permitidas:
  - Puerto `5432` (PostgreSQL).
  - Puerto `22` (SSH de administración).
- Explicar que cualquier intento de conexión a otros puertos queda bloqueado por defecto.

#### Característica 3: Sistema de Notificaciones y Matchers
- Ir a `Datacenter -> Notifications`.
- Mostrar el **Target** de notificación configurado (`notificaciones-tp1` hacia el correo) y el **Matcher** que intercepta eventos del clúster y backups.
- Hacer clic en el target y darle a **Test** para mostrar la alerta enviada.

---

## 📋 Resumen de URLs y Credenciales para el Video

| Servicio | URL / Host | Usuario | Contraseña |
| :--- | :--- | :--- | :--- |
| **Proxmox Web (Admin)** | `https://192.168.1.94:8006` | `root@pam` | *(Tu clave habitual)* |
| **Proxmox Web (Alumno)**| `https://192.168.1.94:8006` | `alumno@pve` | `Admin2026!` |
| **Joomla Frontend** | `https://192.168.1.96/` | - | - |
| **Joomla Admin** | `https://192.168.1.96/administrator` | `admin` | `Admin2026!` |
| **PostgreSQL Remoto** | `192.168.1.95:5432` (db: `postgres`) | `postgres` | `admin123` |
