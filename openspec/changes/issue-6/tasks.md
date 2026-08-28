# Tasks: US-06: Automatización de Respaldos Lógicos de Base de Datos (mysqldump)

## Phase 0: Verificación previa
- [x] 0.1 Revisar estado del workspace y rama feature
- [x] 0.2 Confirmar que Docker Engine y Compose v2 están disponibles

## Phase 1: Implementación
- [x] 1.1 Crear scripts/backup/mysqldump.sh con retention + compress
- [x] 1.2 Declarar servicio mysql-backup con backup-network
- [x] 1.3 Montar script y volumen mysql_backups

## Phase 2: Validación
- [x] 2.1 `docker compose config` exit code 0
- [x] 2.2 Cada BACKUP_INTERVAL_HOURS se genera /backups/pmai_db_<ts>.sql.gz
- [x] 2.3 Backups > BACKUP_RETENTION_DAYS días se eliminan automáticamente

## Phase 3: Cierre
- [x] 3.1 Commit por historia siguiendo convención conventional commits
- [x] 3.2 Push a rama feature y apertura de PR
