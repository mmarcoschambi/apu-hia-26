#!/bin/bash
# ==============================================================================
# CONTINUAR BATCHES SIN CONFIRMACIONES
# ==============================================================================
# Continúa procesando los batches restantes sin pedir confirmaciones
# SKIP indicadores por batch (se calculan al final para todo el universo)
#
# Usage:
#   ./continue_batches_auto.sh
# ==============================================================================

set -e

BATCH_DIR="batches_20260309_170523"
WORKERS=5
START_DATE="2020-01-01"
END_DATE="2026-03-09"

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  🔄 CONTINUAR BATCHES AUTOMÁTICO (sin confirmaciones)"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "  📂 Batch dir: $BATCH_DIR"
echo "  🚀 Workers:   $WORKERS"
echo "  📅 Período:   $START_DATE → $END_DATE"
echo ""

if [ ! -d "$BATCH_DIR" ]; then
    echo "❌ Error: Directorio de batches no encontrado: $BATCH_DIR"
    exit 1
fi

# Contar batches
cd "$BATCH_DIR"
BATCH_FILES=(batch_*)
TOTAL_BATCHES=${#BATCH_FILES[@]}
echo "  📦 Total batches encontrados: $TOTAL_BATCHES"
echo ""

# Verificar batch_000 ya procesado
if [ -f "batch_000" ]; then
    echo "  ✅ batch_000 ya completado (skip)"
    START_FROM=1
else
    START_FROM=0
fi

echo ""
echo "  🚀 Iniciando desde batch_$(printf "%03d" $START_FROM)..."
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

START_TIME=$(date +%s)
BATCH_SUCCESS=0
BATCH_FAILED=0

for i in $(seq $START_FROM $((TOTAL_BATCHES - 1))); do
    batch="batch_$(printf "%03d" $i)"
    batch_num=$((i + 1))
    batch_count=$(wc -l < "$batch")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📦 BATCH $batch_num/$TOTAL_BATCHES ($batch)"
    echo "  Tickers: $batch_count | Hora: $(date +%H:%M:%S)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # FASE A: Descarga
    echo "  📥 Descargando datos..."
    if python3 ../expand_universe.py \
        --ticker-file "$batch" \
        --workers "$WORKERS" \
        --start-date "$START_DATE" \
        --end-date "$END_DATE"; then
        echo "  ✅ Descarga OK"
    else
        echo "  ⚠️  Descarga con errores (continuando)"
    fi
    echo ""
    
    # FASE B: Patrones (SKIP indicadores)
    echo "  🎯 Pre-calculando patrones..."
    if python3 ../precompute_patterns.py \
        --tickers-file "$batch" \
        --merge \
        --step 5 \
        --start "$START_DATE" \
        --end "$END_DATE"; then
        echo "  ✅ Patrones OK"
        BATCH_SUCCESS=$((BATCH_SUCCESS + 1))
    else
        echo "  ⚠️  Patrones con errores"
        BATCH_FAILED=$((BATCH_FAILED + 1))
    fi
    
    echo ""
    echo "  ✅ Batch $batch_num/$TOTAL_BATCHES completado"
    echo ""
    
    # Delay entre batches (excepto el último)
    if [ $batch_num -lt $TOTAL_BATCHES ]; then
        echo "  ⏸️  Esperando 10 minutos antes del siguiente batch..."
        sleep 600
        echo ""
    fi
done

cd ..

# Resumen
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_HOURS=$(echo "scale=1; $ELAPSED / 3600" | bc)

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "  ✅ BATCHES COMPLETADOS"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "  📊 Estadísticas:"
echo "     Procesados:         $((TOTAL_BATCHES - START_FROM))"
echo "     Exitosos:           $BATCH_SUCCESS"
echo "     Con errores:        $BATCH_FAILED"
echo "     Tiempo total:       ${ELAPSED_HOURS} horas"
echo ""
echo "  📦 Archivos generados:"
echo "     - data/ticker_cache.db"
echo "     - data/pattern_cache.pkl ⭐"
echo "     - data/pattern_matrix.pkl ⭐"
echo ""
echo "  🎯 Próximos pasos:"
echo "     1. Calcular indicadores para todo:"
echo "        echo 'yes' | python3 precompute_all_indicators.py --full"
echo ""
echo "     2. Auditoría final:"
echo "        python3 audit_data_gaps.py"
echo ""
echo "     3. Verificar:"
echo "        python3 manage_universe.py --info"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
