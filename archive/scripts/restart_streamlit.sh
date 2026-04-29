#!/bin/bash
# Script para reiniciar Streamlit y limpiar cache de Python

echo "🔄 Limpiando cache de Python..."

# Limpiar archivos .pyc y __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

echo "✅ Cache de Python limpiado"
echo ""
echo "🚀 Ahora reinicia tu app de Streamlit:"
echo ""
echo "   1. Detén el proceso actual (Ctrl+C)"
echo "   2. Ejecuta: streamlit run app.py"
echo ""
echo "   O si usas el script:"
echo "   ./run_dashboard.sh"
echo ""
echo "⚠️  IMPORTANTE: Debe ser un reinicio completo, no un 'Rerun' desde la UI"
