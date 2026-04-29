#!/bin/bash

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   🚀 INICIANDO ACTUALIZACIÓN COMPLETA DEL SISTEMA   ${NC}"
echo -e "${BLUE}====================================================${NC}"

# 1. Asegurar que tenemos la lista completa de tickers actualizada
echo -e "\n${YELLOW}1️⃣  Generando lista maestra de tickers desde la DB...${NC}"
sqlite3 data/ticker_cache.db "SELECT ticker FROM universe" > all_tickers_universe.txt
COUNT=$(wc -l < all_tickers_universe.txt)
echo -e "${GREEN}   ✅ Lista generada con $COUNT tickers.${NC}"

# 2. Poblar/Verificar Historial Diario (OHLCV) - 50 Años
# Nota: Si ya se está ejecutando en otra terminal, esto verificará lo que falte.
echo -e "\n${YELLOW}2️⃣  Actualizando Historial Diario (50 años) para TODO el universo...${NC}"
echo -e "   ☕ Esto puede tomar tiempo. Si ya corriste una parte, esto solo llenará huecos."
python3 populate_historical_openbb.py --years 50 --no-skip

# 3. Poblar/Verificar Datos Intradía (5m) - Últimos 60 días
echo -e "\n${YELLOW}3️⃣  Actualizando Datos Intradía (5m) para TODOS los tickers...${NC}"
echo -e "   📊 Verificando $COUNT tickers..."
python3 cache_intraday_data.py --universe all_tickers_universe.txt --days 60

# 4. Limpieza
echo -e "\n${YELLOW}4️⃣  Limpiando archivos temporales...${NC}"
rm all_tickers_universe.txt

echo -e "\n${BLUE}====================================================${NC}"
echo -e "${GREEN}   ✅✅✅ PROCESO COMPLETO FINALIZADO ✅✅✅   ${NC}"
echo -e "${BLUE}====================================================${NC}"
