# ==============================================================================
# US-11: Dockerfile custom n8n - PMA-Docker 2026
# ==============================================================================
# Imagen basada en n8nio/n8n con auto-import de workflows al iniciar.
# Publicada en GitHub Container Registry (ghcr.io/mmarcoschambi/apu-hia-26/n8n-pmai).
# ==============================================================================
ARG N8N_VERSION=1.45.1

FROM n8nio/n8n:${N8N_VERSION}

USER root

# Paquetes extra: tini para signal handling y jq para parseo en entrypoint
RUN apk add --no-cache tini jq bash curl \
    && apk add --no-cache --virtual .build-deps \
    && rm -rf /var/cache/apk/*

# Workflows pre-empaquetados y script de importación.
# El build context debe ser la raíz del proyecto (ver workflows/.github).
COPY n8n/workflows/ /opt/n8n-workflows/
COPY docker/n8n/entrypoint.sh /usr/local/bin/entrypoint-pmai.sh
RUN chmod +x /usr/local/bin/entrypoint-pmai.sh \
    && chown -R node:node /opt/n8n-workflows

# Directorio de trabajo del usuario node (donde n8n guarda estado)
WORKDIR /home/node

USER node

# Etiquetas OCI para trazabilidad en GHCR
LABEL org.opencontainers.image.title="n8n-pmai" \
      org.opencontainers.image.description="n8n con workflows de la Plataforma PMA-Docker 2026" \
      org.opencontainers.image.source="https://github.com/mmarcoschambi/apu-hia-26" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="APU UNJu - HIA 2026"

# Healthcheck heredado del upstream + endpoint específico
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:5678/healthz || exit 1

ENTRYPOINT ["tini", "--", "/usr/local/bin/entrypoint-pmai.sh"]
CMD ["worker"]
