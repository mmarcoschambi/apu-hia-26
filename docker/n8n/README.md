# Imagen custom n8n — US-11

Imagen Docker basada en [`n8nio/n8n`](https://hub.docker.com/r/n8nio/n8n) que
incluye los workflows de la plataforma PMA-Docker 2026 pre-empaquetados y
los auto-importa al iniciar el contenedor.

## Build local

```bash
docker build \
  -t ghcr.io/mmarcoschambi/apu-hia-26/n8n-pmai:dev \
  -f docker/n8n/Dockerfile \
  docker/n8n/
```

## Estructura

```
docker/n8n/
├── Dockerfile         # Imagen custom con tag OCI y healthcheck propio
├── entrypoint.sh      # Espera MySQL + auto-importa workflows + handoff upstream
├── workflows/         # (bind mount en runtime desde n8n/workflows/)
└── README.md
```

## Publicación en GHCR

El workflow `.github/workflows/docker-build.yml` publica automáticamente
cambios a `main` con tags `latest` y semánticos (`vX.Y.Z`) en
`ghcr.io/mmarcoschambi/apu-hia-26/n8n-pmai`.
