# Workflows de n8n — US-09: Webhooks y Alertas

Este directorio contiene los workflows exportados desde n8n que se cargan
automáticamente al iniciar el contenedor.

## Workflow incluido

| Archivo | Propósito | Webhook path |
|---------|-----------|--------------|
| `webhook-alert-flow.json` | Receptor HTTP que registra eventos en MySQL y dispara alertas SMTP para severidad `critical` | `POST /webhook/pmai-alerts` |

## Esquema del payload aceptado

```json
{
  "origen": "nginx-gateway",
  "tipo_evento": "deploy.failed",
  "severidad": "critical|warning|info",
  "title": "Fallo de despliegue",
  "mensaje": "Detalle legible del incidente"
}
```

## Importación

### Automática (recomendada)

El entrypoint del contenedor `docker/n8n/Dockerfile` ejecuta la CLI de n8n
para importar este directorio al iniciar. Si la imagen es la upstream
oficial, montá este directorio como volumen (ya configurado en
`docker-compose.yml`).

### Manual

1. Iniciá sesión en `http://localhost/`
2. Menú ☰ → **Workflows** → **Import from File...**
3. Seleccioná `webhook-alert-flow.json`
4. Activá el toggle del workflow

## Variables de entorno requeridas

| Variable | Default | Descripción |
|----------|---------|-------------|
| `N8N_SMTP_HOST` | smtp.gmail.com | Servidor SMTP saliente |
| `N8N_SMTP_PORT` | 587 | Puerto SMTP |
| `N8N_SMTP_USER` | (vacío) | Usuario SMTP |
| `N8N_SMTP_PASS` | (vacío) | Password SMTP (recomendado: app password) |
| `N8N_SMTP_SENDER` | n8n-alerts@apu-hia-26.local | From address |
| `ALERT_RECIPIENT` | ops@apu-hia-26.local | Default de destinatario (configurable por workflow) |

## Pruebas rápidas

```bash
curl -X POST http://localhost/webhook/pmai-alerts \
  -H "Content-Type: application/json" \
  -d '{"origen":"manual","tipo_evento":"smoke.test","severidad":"info","title":"OK","mensaje":"smoke test"}'
```

Si el evento tiene `severidad=critical`, además del INSERT en MySQL se
disparará un correo al destinatario configurado.
