#!/usr/bin/env bash
"""
DEPLOY VPS - Professional Environment Separation
Subre solo los archivos livianos (Finviz, Telegram, Scanner) al VPS.
Excluye la base de datos local pesada (Laboratory machine).
"""

# Configuración por defecto
REMOTE_HOST="xxmalcomandaxx@104.198.34.159"
PROJECT_DIR="/home/marcos/trade/momentum-v2"
REMOTE_DIR="/home/xxmalcomandaxx/trade/momentum-v2"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)
      REMOTE_HOST="$2"
      shift # past argument
      shift # past value
      ;;
    *)
      shift # past argument
      ;;
  esac
done

echo "🚀 Iniciando Deploy a la Torre de Control (VPS)..."
echo "📡 Host: $REMOTE_HOST"
echo "📁 Excluyendo Base de Datos Local (*.db) para mantener el VPS liviano."

# Ejecutar rsync con exclusiones críticas
rsync -avz --progress \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.streamlit/' \
    --exclude='data/*.db' \
    --exclude='data/*.pkl' \
    --exclude='outputs/walk_forward/' \
    --exclude='study/' \
    --exclude='logs/' \
    --exclude='.env' \
    ./ "$REMOTE_HOST:$REMOTE_DIR"

echo "✅ Deploy completado con éxito."
echo "⚠️  Recuerda que el .env no se sincroniza automáticamente por seguridad."
echo "💡 Para ejecutar tareas usa: ssh $REMOTE_HOST 'cd $REMOTE_DIR && ./run_vps_job.sh scripts/finviz_monitor.py'"
