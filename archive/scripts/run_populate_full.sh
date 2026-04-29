#!/bin/bash
# Populate tickers faltantes con data completa 2020-2024

echo "🏎️ POPULATE CUSTOM TICKER LIST"
echo "================================"
echo ""
echo "Descargará ~284 tickers faltantes"
echo "Período: 2020-01-01 → 2024-12-31"
echo "Tiempo estimado: 30-40 minutos"
echo ""
read -p "¿Continuar? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Iniciando descarga..."
    python3 populate_custom_list.py \
      --skip-existing \
      --start-date 2020-01-01 \
      --end-date 2024-12-31 \
      --batch-size 10
    
    echo ""
    echo "✅ Completado!"
    echo ""
    echo "Próximo paso:"
    echo "  ./quick_run_bugatti.sh"
else
    echo "Cancelado."
fi
