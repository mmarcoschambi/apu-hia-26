# Proposal: US-09: Implementación de Flujo de Webhooks y Alertas Automáticas

## Intent
Workflow n8n exportado en n8n/workflows/webhook-alert-flow.json. Receptor HTTP en /webhook/pmai-alerts, registra en MySQL, dispara SMTP si severidad=critical.

## Scope
- Epic: EP-03
- Sprint: 2
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `n8n/workflows/webhook-alert-flow.json`
- `n8n/workflows/README.md`
- `docker-compose.yml:81-94`

## Acceptance Criteria
- [ ] POST /webhook/pmai-alerts responde 200 con JSON
- [ ] Eventos con severity=critical disparan email

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
