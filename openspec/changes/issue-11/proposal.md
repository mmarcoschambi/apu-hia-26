# Proposal: US-11: Pipeline de Construcción de Imágenes Docker y Publicación en GHCR

## Intent
Workflow docker-build.yml construye n8n-pmai desde docker/n8n/Dockerfile, publica en ghcr.io con tags semánticos, cache GHA, SBOM y escaneo Trivy.

## Scope
- Epic: EP-04
- Sprint: 2
- Story Points: 3
- Status: **Implemented**

## Affected Files
- `.github/workflows/docker-build.yml`
- `docker/n8n/Dockerfile`
- `docker/n8n/entrypoint.sh`

## Acceptance Criteria
- [ ] Push a main publica tag 'latest' en ghcr.io
- [ ] Tag vX.Y.Z publica versión semántica

## Rollback Plan
- Revertir los archivos listados en *Affected Files*.
- Re-ejecutar `docker compose config` para validar manifest.
