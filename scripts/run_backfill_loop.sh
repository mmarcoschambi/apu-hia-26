#!/bin/bash
# scripts/run_backfill_loop.sh
# Bucle nocturno optimizado para descargar deslistados usando el pipeline híbrido inteligente (yfinance + Tiingo).

# =========================================================
# ⚙️ CONFIGURACIÓN DEL PROCESO
# Índices permitidos: "SP500", "RUSSELL1000", "RUSSELL2000", "NASDAQ100"
INDEX="RUSSELL1000"
TOKEN="ea2f4e71ace0edac90940307608edcb356db8d82"
DELAY_SECS=3900 # 65 minutos (para asegurar el reset del límite por hora de Tiingo)
# =========================================================

echo "⏰ ========================================================"
echo "🚀 INICIANDO PROCESO DE BACKFILL HÍBRIDO NOCTURNO"
echo "==========================================================="
echo "Índice objetivo: $INDEX"
echo "Este script descargará activos gratis vía yfinance y recurrirá"
echo "a Tiingo para deslistados en ciclos espaciados de 65 minutos."
echo ""

for i in {1..8}
do
    echo "-----------------------------------------------------------"
    echo "🔄 CICLO DE DESCARGA #$i de 8 - $(date)"
    echo "-----------------------------------------------------------"
    
    # Ejecutamos el backfill híbrido inteligente de faltantes y truncados del índice especificado
    .venv/bin/python3 scripts/hybrid_backfill.py --token "$TOKEN" --index "$INDEX" --all
    
    # Si detectamos que no hay nada más que hacer, el script saldrá de inmediato de forma limpia.
    
    if [ $i -lt 8 ]; then
        echo "💤 Esperando $((DELAY_SECS / 60)) minutes para el siguiente ciclo..."
        sleep $DELAY_SECS
    fi
done

echo "✅ Bucle nocturno completado. Proceso finalizado."
