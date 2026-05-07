#!/bin/bash
# Wrapper para ejecutar scripts en el VPS con el entorno y variables correctas

PROJECT_DIR="/home/xxmalcomandaxx/swing-momentum-v1"
cd "$PROJECT_DIR" || exit 1

# Cargar y exportar todas las variables del .env
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
else
    echo "ERROR: Archivo .env no encontrado en $PROJECT_DIR"
    exit 1
fi

# Ejecutar el script de Python (.venv) pasando todos los argumentos originales
exec .venv/bin/python "$@"