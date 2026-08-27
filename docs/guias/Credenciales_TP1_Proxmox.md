# Credenciales de Acceso - Servidores TP1 Proxmox (HIA 2026)

Este documento registra todas las credenciales y accesos de los contenedores creados para el Trabajo Práctico 1.

---

## 1. Servidor de Base de Datos (`debianbd` - CT 300)
- **IP:** `192.168.1.95`
- **SSH:** `ssh root@192.168.1.95`
  - Usuario: `root`
  - Clave: `admin123` *(o ingreso directo mediante llave SSH)*
- **Motor PostgreSQL 15:**
  - Puerto: `5432`
  - Base de Datos: `postgres`
  - Usuario: `postgres`
  - Contraseña: `admin123`
  - Tabla creada: `productos`

---

## 2. Servidor CMS (`jmlpserver` - CT 201)
- **IP:** `192.168.1.96`
- **SSH:** `ssh root@192.168.1.96`
  - Usuario: `root`
  - Clave: `Admin2026!` *(o ingreso directo mediante llave SSH)*
- **Motor MariaDB / MySQL:**
  - Usuario: `root`
  - Contraseña: `Admin2026!`
- **Panel Web de Administración de Joomla:**
  - URL: `https://192.168.1.96/administrator`
  - Usuario: `admin`
  - Contraseña: `Admin2026!`
  - Email: `admin@example.com` (o el que ingreses en el asistente)
- **Panel Webmin:**
  - URL: `https://192.168.1.96:12322`
  - Usuario: `root`
  - Contraseña: `Admin2026!`

---

## 3. Servidor Hipervisor Proxmox VE
- **URL Web:** `https://192.168.1.94:8006`
- **Usuario:** `root@pam`
- **SSH:** `ssh root@192.168.1.94` *(ingreso directo por llave SSH)*
