# Runbook — Diagnóstico de Incidentes

## Servicio `unhealthy` en `docker compose ps`

1. Ver logs del servicio:
   ```bash
   docker compose logs --tail=200 <servicio>
   ```
2. Si es `mysql`: confirmar espacio en disco del host (`df -h`) y que el
   volumen `pmai_mysql_data` no esté corrupto.
3. Si es `nginx-gateway`: `docker compose exec nginx-gateway wget -qO- http://127.0.0.1/healthz`
4. Si es `mysql-backup`: revisar conectividad con `docker compose exec mysql-backup mysqladmin ping -h mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD"`.

## Webhook receptor no responde

1. Confirmar que el workflow `webhook-alert-flow.json` está **activo** en n8n.
2. Probar con curl:
   ```bash
   curl -v -X POST http://localhost/webhook/pmai-alerts \
     -H "Content-Type: application/json" \
     -d '{"origen":"test","tipo_evento":"diagnostico","severidad":"info","title":"OK","mensaje":"prueba"}'
   ```
3. Si responde 404, el workflow no está activo o el path cambió.

## SMTP no envía alertas

1. Validar variables `N8N_SMTP_*` en `.env` (especialmente `N8N_SMTP_USER` y `N8N_SMTP_PASS`).
2. Para Gmail, usar **App Password** (no la contraseña normal) y confirmar
   `N8N_SMTP_STARTTLS=true`.
3. Probar manualmente desde un workflow n8n con un nodo Send Email.

## Espacio en disco agotado

```bash
# Volúmenes Docker
docker system df -v

# Backups antiguos
docker compose exec mysql-backup ls -lh /backups/ | head
```

Si el volumen `pmai_mysql_backups` está lleno, ajustar
`BACKUP_RETENTION_DAYS` en `.env` y reiniciar el sidecar:
```bash
docker compose up -d mysql-backup
```

## Rollback de deploy de producción

```bash
ssh deploy@host 'cd /srv/apu-hia-26 && git checkout <SHA_PRE_DEPLOY> && docker compose pull && docker compose up -d'
```

Donde `<SHA_PRE_DEPLOY>` es el SHA anterior al release problemático,
obtenible desde `git log --oneline` en el host de producción.

## Pérdida de red interna

Si `pmai_app_net` desaparece tras un reinicio abrupto del daemon Docker:

```bash
docker compose down
docker compose up -d
```

Los volúmenes nombrados (`pmai_mysql_data`, `pmai_n8n_data`,
`pmai_mysql_backups`) persisten fuera de las redes, así que no se pierde
datos. Verificar post-restart con `scripts/health/compose-health.sh`.
