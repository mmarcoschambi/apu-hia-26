#!/usr/bin/env bash
# DEPLOY VPS - Professional Environment Separation
# Sube solo los archivos livianos (Finviz, Telegram, Scanner) al VPS.
# Excluye la base de datos local pesada (Laboratory machine).

# Configuración por defecto
REMOTE_HOST="xxmalcomandaxx@trading-vps.us-central1-f.paper-trading-server"
REMOTE_DIR="/home/xxmalcomandaxx/swing-momentum-v1"

# Parsear argumentos
while [[ $# -gt 0 ]]; do
  case $1 in
    --host)
      REMOTE_HOST="$2"
      shift # past argument
      shift # past value
      ;;
    --dir)
      REMOTE_DIR="$2"
      shift
      shift
      ;;
    *)
      shift # past argument
      ;;
  esac
done

echo "🚀 Iniciando Deploy a la Torre de Control (VPS)..."
echo "📡 Host: $REMOTE_HOST"
echo "📁 Destino: $REMOTE_DIR"
echo "📁 Excluyendo Base de Datos Local y Research para mantener el VPS liviano."

# Ejecutar rsync con exclusiones críticas y verificación de error
rsync -avz --progress \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache/' \
    --exclude='.ruff_cache/' \
    --exclude='.streamli*/' \
    --exclude='data/*.db*' \
    --exclude='data/*.sqlite' \
    --exclude='data/*.pkl' \
    --exclude='data/*.bak*' \
    --exclude='data/*.corrupt*' \
    --exclude='data/*.backup' \
    --exclude='data/cache/' \
    --exclude='data/cache_backups/' \
    --exclude='data/screener_cache/' \
    --exclude='data/backtest_data/' \
    --exclude='data/prices/' \
    --exclude='data/history/' \
    --exclude='data/processed/' \
    --exclude='outputs/' \
    --exclude='quantconnect/' \
    --exclude='sp500/' \
    --exclude='scratch/' \
    --exclude='study/' \
    --exclude='experiments/' \
    --exclude='archive/' \
    --exclude='logs/' \
    --exclude='.env' \
    ./ "$REMOTE_HOST:$REMOTE_DIR"

if [ $? -eq 0 ]; then
    echo "✅ Deploy completado con éxito."
else
    echo "❌ ERROR: El deploy falló. Revisa la conexión SSH o el nombre del host."
    exit 1
fi

echo "⚠️  Recuerda que el .env no se sincroniza automáticamente por seguridad."
echo "💡 Para ejecutar tareas usa: ssh $REMOTE_HOST 'cd $REMOTE_DIR && ./run_vps_job.sh scripts/finviz_monitor.py'"
