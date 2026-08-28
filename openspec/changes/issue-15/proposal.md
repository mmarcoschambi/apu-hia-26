# Proposal: US-15: Gestión Centralizada de Secretos y Variables de Entorno Seguras

## Intent
.env.example versionado con valores dummy; .env real excluido por .gitignore. Trufflehog en CI detecta secretos accidentales.

## Scope
- Epic: EP-05
- Sprint: 1
- Story Points: 2
- Status: **Implemented**

## Affected Files
- `.env.example`
- `.gitignore`
- `.github/workflows/ci-validation.yml`

## Acceptance Criteria
- [ ] .env no aparece en `git status` ni en commits
- [ ] Trufflehog falla el build si detecta secretos verificados

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
