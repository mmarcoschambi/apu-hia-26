# **Guión Maestro y Presentación Técnica: TP1 Proxmox VE**

**Cátedra:** Herramientas Informáticas Avanzadas | **Carrera:** Analista Programador Universitario (APU)

**Duración Objetivo:** 8:00 minutos | **Modalidad:** Video colaborativo de 3 integrantes con participación equitativa.

---

## **1. Ficha Técnica y Distribución de Roles**

| Integrante | Tiempo Estimado | Bloque Práctico Obligatorio (Puntos TP1) | Tema de Investigación (Ítem 4) | Entregables / Foco en Pantalla |
| :--- | :--- | :--- | :--- | :--- |
| **Integrante 1 (Marcos)** | 00:00 - 02:40 (2:40 min) | **Ítem 1:** Instalación Proxmox VE + **Ítem 2.b:** Despliegue Servidor CMS (Joomla en CT 201 `jmlpserver`) | **Ítem 4.b:** Control de Acceso, Usuarios, Grupos y Pools (RBAC) | Panel PVE (https://192.168.1.94:8006, nodo `hia`), CT 201 jmlpserver en Chrome (https://192.168.1.96/administrator), Pool Desarrollo, usuario 'alumno@pve' con rol PVEVMUser. |
| **Integrante 2** | 02:40 - 05:20 (2:40 min) | **Ítem 2.a:** Despliegue Servidor BD (Debian + PostgreSQL manual en CT 300 `debianbd`) + Conexión Externa DBeaver/pgAdmin | **Ítem 4.c:** Firewalls Integrados a Nivel de Contenedor | CT 300 debianbd (192.168.1.95), consola PostgreSQL activa, tabla 'productos' en DBeaver/pgAdmin 4, reglas de Firewall (Input DROP + Puerto 5432 ACCEPT). |
| **Integrante 3** | 05:20 - 08:00 (2:40 min) | **Ítem 3.a, 3.b, 3.c:** Ciclo de Seguridad DRP (Backup manual CT 200, Drop, Restore como CT 300) + **Ítem 3.d:** Backup Programado Diario | **Ítem 4.e:** Servidor de Notificaciones (Alertas por Correo SMTP) | Storage local (.tar.zst), tareas/logs de restauración de CT 300, Scheduler Datacenter Backup (vzdump.cron), Target SMTP en Gmail (STARTTLS 587) y prueba en vivo. |

---

## **2. Estructura de Diapositivas y Escenas Visuales**

1. **Escena 1 (00:00 - 00:30): Portada y Presentación Grupal.** Pantalla dividida con cámaras de los 3 integrantes o slide con Nombres completos y Libretas Universitarias.
2. **Escena 2 (00:30 - 01:30): Infraestructura Base y Proxmox VE (Ítem 1).** Vista del navegador web en `https://192.168.1.94:8006` mostrando resumen de recursos del nodo `hia`.
3. **Escena 3 (01:30 - 02:40): Servidor CMS (Ítem 2.b) y RBAC con Pools (Ítem 4.b).** Acceso al frontend y panel `/administrator` de Joomla (`https://192.168.1.96`) y demostración del login con usuario `alumno@pve` con permisos restringidos.
4. **Escena 4 (02:40 - 04:00): Servidor de Base de Datos (Ítem 2.a) y DBeaver/pgAdmin.** Verificación del servicio PostgreSQL en `debianbd` (`192.168.1.95:5432`) y consulta SQL de la tabla `productos` desde la máquina anfitriona Windows.
5. **Escena 5 (04:00 - 05:20): Seguridad y Firewall Integrado (Ítem 4.c).** Demostración de reglas de firewall en CT 300, bloqueo de puertos no autorizados (HTTP/80) y paso exclusivo para el puerto 5432.
6. **Escena 6 (05:20 - 06:45): Ciclo de Desastre y Restauración DRP (Ítem 3.a, 3.b, 3.c).** Muestra del archivo de backup `.tar.zst` en `local:backup`, evidencia del proceso DRP y verificación de que el CT 300 es el resultado restaurado exitosamente del contenedor 200 original.
7. **Escena 7 (06:45 - 07:30): Automatización y Backups Programados (Ítem 3.d).** Pestaña `Datacenter > Backup` con la tarea diaria programada (`vzdump.cron`).
8. **Escena 8 (07:30 - 08:00): Notificaciones SMTP y Cierre (Ítem 4.e).** Configuración del Matcher y Target SMTP (`smtp.gmail.com:587`) y confirmación de prueba. Conclusión final.

---

## **3. Guión Paso a Paso con Diálogos Textuales y Cues de Pantalla**

### **BLOQUE 1: Introducción, Entorno Base, CMS y RBAC (00:00 - 02:40)**

*\[Acción en Pantalla: Cámara de los 3 integrantes o diapositiva de presentación institucional de la UNJu / HIA\].*

**Integrante 1 (Marcos):** "Buenas tardes profesor y compañeros. Somos el grupo conformado por Marcos [Apellido - LU], [Nombre Integrante 2 - LU] y [Nombre Integrante 3 - LU]. En esta oportunidad presentamos la defensa práctica del Trabajo Práctico Número 1 sobre Entornos de Virtualización con Proxmox VE para la materia Herramientas Informáticas Avanzadas."

*\[Acción en Pantalla: Transición a la interfaz web de Proxmox VE en https://192.168.1.94:8006\].*

**Integrante 1 (Marcos):** "Para la infraestructura base correspondiente al **Punto 1**, realizamos la instalación de Proxmox VE sobre nuestro entorno virtualizado. En la configuración de red, seleccionamos la opción de **Adaptador Puente (Bridged)** asociada directamente a la interfaz física de red cableada Ethernet. Esto nos permitió asignarle una **IP fija estática (la 192.168.1.94)**, garantizando que el hipervisor sea accesible de forma directa desde la red local sin depender de asignaciones dinámicas por DHCP. Como vemos en pantalla, la interfaz web del nodo **`hia`** responde de forma fluida en el puerto 8006."

*\[Acción en Pantalla: Mostrar el contenedor CT 201 jmlpserver en el árbol de Proxmox y abrir una pestaña en Chrome con la IP https://192.168.1.96 y https://192.168.1.96/administrator\].*

**Integrante 1 (Marcos):** "Pasando al **Punto 2.b**, desplegamos un servidor web utilizando la plantilla preinstalada de TurnKey Linux Joomla en el contenedor CT 201 `jmlpserver` con 1 núcleo de CPU, 1 GB de RAM y 20 GB de almacenamiento. Al ingresar desde el navegador Chrome del sistema anfitrión a la IP `192.168.1.96`, constatamos que el frontend y el panel administrativo cargan de forma inmediata y estable en la red local."

*\[Acción en Pantalla: Ir a Datacenter > Resource Pools > Desarrollo, mostrar el grupo Programadores y desloguearse de root para loguearse como 'alumno@pve'\].*

**Integrante 1 (Marcos):** "Como primera característica de investigación del **Ítem 4**, implementamos el modelo de Control de Acceso Basado en Roles mediante *Pools* (Ítem 4.b). El concepto teórico de **RBAC y Pools** resuelve la administración delegada y el aislamiento multi-inquilino (*Multi-Tenancy*). En entornos corporativos no es seguro otorgar privilegios de root a todos los desarrolladores. Con los *Resource Pools* agrupamos los servidores por proyecto, y aplicando el *Principio de Menor Privilegio*, asignamos al grupo 'Programadores' y a nuestro usuario 'alumno@pve' el rol PVEVMUser únicamente sobre el pool 'Desarrollo'. Al cerrar la sesión de root e iniciar como 'alumno@pve', observamos en pantalla cómo el sistema aísla por completo el resto del nodo: el usuario solo ve su CMS asignado y no tiene visibilidad ni acceso a la base de datos de producción. Le cedo la palabra a mi compañero para la sección de Base de Datos y Seguridad."

---

### **BLOQUE 2: Servidor Debian, PostgreSQL y Firewall Integrado (02:40 - 05:20)**

*\[Acción en Pantalla: Mostrar el contenedor CT 300 debianbd en Proxmox (IP 192.168.1.95), consola abierta con PostgreSQL corriendo y ventana de DBeaver / pgAdmin 4 en Windows\].*

**Integrante 2:** "Gracias. Continuando con el **Punto 2.a**, creamos un contenedor basado en Debian denominado `debianbd` con 1 vCPU, 2 GB de RAM y 10 GB de disco. Dentro del mismo, instalamos y configuramos de forma manual el motor relacional PostgreSQL 15, ajustando los archivos postgresql.conf y pg_hba.conf para admitir conexiones remotas autenticadas."

*\[Acción en Pantalla: Ejecutar en DBeaver / pgAdmin 4 la consulta: SELECT * FROM productos; mostrando los registros\].*

**Integrante 2:** "Desde nuestro sistema anfitrión Windows utilizamos el cliente DBeaver / pgAdmin 4 para establecer conexión remota mediante TCP/IP al puerto 5432. Creamos la base de datos correspondiente y la tabla `productos` con clave primaria autoincremental y campos descriptivos. Ejecutamos la consulta SQL en vivo, comprobando la persistencia y disponibilidad de los datos."

*\[Acción en Pantalla: Ir a CT 300 > Firewall > Rules y Firewall > Log\].*

**Integrante 2:** "Para nuestra segunda característica de investigación del **Ítem 4**, implementamos el *Firewall Integrado de Proxmox* (Ítem 4.c). En lugar de depender exclusivamente de reglas internas, gestionamos la seguridad desde el hipervisor. Establecimos una política estricta de entrada en modo DROP, bloqueando cualquier tráfico entrante no autorizado, y definimos reglas explícitas ACCEPT únicamente para el protocolo TCP en el puerto 5432 (PostgreSQL) y el puerto 22 (SSH). Comprobamos que intentar acceder por otros puertos es rechazado y registrado en el log del firewall en tiempo real. A continuación, mi compañero expondrá la estrategia de respaldos y notificaciones."

---

### **BLOQUE 3: Ciclo de Backups, Restore y Notificaciones SMTP (05:20 - 08:00)**

*\[Acción en Pantalla: Ir a Storage local > Backups, seleccionar el archivo vzdump-lxc-200-*.tar.zst y mostrar sus notas\].*

**Integrante 3:** "Muchas gracias. Abordando los **Puntos 3.a, 3.b y 3.c**, procedimos con la gestión del ciclo de vida y respaldo de datos. Como se observa en la pestaña *Storage local > Backups*, ejecutamos previamente un respaldo en caliente del contenedor de base de datos original CT 200, generándose el archivo comprimido de respaldo `.tar.zst`."

*\[Acción en Pantalla: Seleccionar el archivo de backup en local > Backups, mostrar el botón Restore y señalar el CT 300 en el árbol\].*

**Integrante 3:** "Para simular un escenario de recuperación ante desastres (DRP), el contenedor original CT 200 fue eliminado por completo. Seguidamente, ejecutamos el proceso de restauración desde este archivo de respaldo asignando un nuevo identificador: el **CT 300**. Como demostró mi compañero en el Bloque 2, el contenedor `300` es la instancia activa restaurada que conserva intactas todas las configuraciones, usuarios y la tabla `productos`."

*\[Acción en Pantalla: Mostrar Datacenter > Backup y /etc/pve/vzdump.cron con la tarea programada diaria\].*

**Integrante 3:** "Para el **Punto 3.d**, configuramos una tarea automatizada en *Datacenter > Backup* con frecuencia diaria en modo Snapshot dirigida a nuestros contenedores, verificando que el scheduler de Proxmox ejecuta la tarea sin intervención humana y deposita los respaldos en el almacenamiento."

*\[Acción en Pantalla: Ir a Datacenter > Notifications > Targets (smtp-gmail) > Matchers (matcher-backups-tp1) > Botón Test\].*

**Integrante 3:** "Finalmente, como tercera característica de investigación del **Ítem 4**, implementamos el *Sistema Centralizado de Notificaciones* de Proxmox VE (Ítem 4.e). Configuramos un target SMTP autenticado contra Gmail (`smtp.gmail.com:587` con STARTTLS) y definimos un matcher que captura los eventos de respaldo y alertas. Presionamos el botón Test y confirmamos la emisión del reporte. Con esto concluimos la demostración completa del trabajo práctico. Muchas gracias por su atención."

---

## **4. Checklist Técnico de Grabación**

- **Resolución de Grabación:** 1080p (1920x1080) a 30 o 60 fps con OBS Studio.
- **Zoom del Navegador:** 110% o 125% en Proxmox para que los números de IP (`192.168.1.94/95/96`), puertos y logs sean totalmente legibles.
- **Pestañas Preparadas:** 
  1. Proxmox web admin en `https://192.168.1.94:8006` con `root@pam`.
  2. Proxmox web incógnito con usuario `alumno@pve` (Clave: `Admin2026!`).
  3. Sitio Joomla en `https://192.168.1.96` y `/administrator` (`admin` / `Admin2026!`).
  4. DBeaver / pgAdmin 4 conectado a `192.168.1.95:5432` (`postgres` / `admin123`).
  5. Bandeja de entrada de Gmail / Datacenter Notifications.
