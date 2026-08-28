# Proposal: US-06: Automatización de Respaldos Lógicos de Base de Datos (mysqldump)

## Intent
Sidecar mysql-backup que ejecuta mysqldump periódico con compresión gzip, conectado a MySQL vía red backup-network aislada. Retención automática configurable.

## Scope
- Epic: EP-02
- Sprint: 2
- Story Points: 2
- Status: **Implemented**

## Affected Files
- `scripts/backup/mysqldump.sh`
- `docker-compose.yml:170-194`

## Acceptance Criteria
- [ ] Cada BACKUP_INTERVAL_HOURS se genera /backups/pmai_db_<ts>.sql.gz
- [ ] Backups > BACKUP_RETENTION_DAYS días se eliminan automáticamente

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
