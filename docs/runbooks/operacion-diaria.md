# Runbook — Operación Diaria

## Chequeo de salud del stack

```bash
bash scripts/health/compose-health.sh
```

Salida esperada: `RESULTADO: stack saludable`. Si algún servicio aparece
con `unhealthy`, continuá con [diagnóstico de incidentes](incidentes.md).

## Listar estado de contenedores

```bash
docker compose ps --format json | jq -r '.Name + "\t" + .State + "\t" + (.Health // "n/a")'
```

## Inspeccionar logs en vivo

```bash
# Todos los servicios
docker compose logs -f --tail=100

# Servicio específico
docker compose logs -f --tail=200 mysql-backup
```

## Verificar espacio de backups

```bash
docker compose exec mysql-backup ls -lh /backups/
docker compose exec mysql-backup du -sh /backups/
```

## Forzar un backup manual inmediato

```bash
# Levanta un job one-shot sin tocar el cron del sidecar
docker compose run --rm \
  -e BACKUP_RUN_ONCE=true \
  mysql-backup
```

## Restaurar un backup

```bash
# Listar backups disponibles
ls -lh backups/

# Copiar del volumen al host
docker compose exec mysql-backup cp /backups/pmai_db_YYYYMMDDTHHMMSSZ.sql.gz /tmp/

# Restaurar (contenedor temporal)
docker compose exec -T mysql \
  gunzip < /tmp/pmai_db_*.sql.gz | mysql -u root -p"${MYSQL_ROOT_PASSWORD}" pmai_db
```

## Rotación de logs

Configurada en `docker-compose.yml` con `max-size: 10m` y `max-file: 3`
(US-14). Sin acción manual necesaria.

## Inspeccionar redes

```bash
docker network inspect pmai_app_net --format '{{.Id}} {{.Internal}}'
docker network inspect pmai_gateway_net --format '{{.Id}} {{.Internal}}'
docker network inspect pmai_backup_net --format '{{.Id}} {{.Internal}}'
```

- `pmai_app_net` y `pmai_backup_net` deben reportar `Internal: true`.
- `pmai_gateway_net` debe reportar `Internal: false` (necesita egreso al host).
