#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}👀 INICIANDO MONITOREO INTELIGENTE...${NC}"
echo "Esperando a que se libere la base de datos para auditar..."

# Lista de scripts que bloquean la DB
WATCH_LIST=("populate_historical_openbb.py" "cache_intraday_data.py" "populate_tickers_from_api.py")

while true; do
    BUSY=0
    
    # Revisar si alguno de los scripts está corriendo
    for script in "${WATCH_LIST[@]}"; do
        if pgrep -f "$script" > /dev/null; then
            BUSY=1
            echo -ne "\r⏳ En ejecución: $script - Esperando... $(date +%H:%M:%S)"
            break
        fi
done

    # Si no hay nada corriendo, salimos del bucle
    if [ $BUSY -eq 0 ]; then
        echo -e "\n\n${GREEN}✅ ¡Procesos finalizados! La vía está libre.${NC}"
        break
    fi

    sleep 10
done

# --- FASE 2: AUDITORÍA ---
echo -e "\n${YELLOW}🚀 Ejecutando Auditoría de Huecos...${NC}"
python3 audit_data_gaps.py

# --- FASE 3: AUTO-REPARACIÓN (Si es necesaria) ---
if [ -f "fix_gaps_detected.sh" ]; then
    echo -e "\n${RED}🚩 Se detectaron huecos.${NC}"
    echo -e "${GREEN}🔧 Iniciando reparación automática inmediata...${NC}"
    
    chmod +x fix_gaps_detected.sh
    ./fix_gaps_detected.sh
    
    # Borrar el script de arreglo una vez usado para no confundir después
    rm fix_gaps_detected.sh
    
    echo -e "\n${GREEN}✨ ¡Reparación completada!${NC}"
    
    # Re-auditar para confirmar (opcional, pero recomendado)
    echo -e "${YELLOW}🔍 Verificación final...${NC}"
    python3 audit_data_gaps.py
else
    echo -e "\n${GREEN}✨ No se detectaron huecos que requieran acción. Todo limpio.${NC}"
fi

echo -e "\n🎉 FIN DEL FLUJO INTELIGENTE"
