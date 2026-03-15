#!/bin/bash
# ==============================================================================
# EXPAND UNIVERSE EN BATCHES - Procesar JSON en lotes para evitar timeouts
# ==============================================================================
# Divide automáticamente el JSON en batches y procesa uno por uno
# con delays entre cada batch para respetar rate limits.
#
# Usage:
#   ./expand_universe_batches.sh --source json --batch-size 500
#   ./expand_universe_batches.sh --tickers-file large_list.txt --batch-size 1000
# ==============================================================================

set -e

# Default parameters
SOURCE_TYPE=""
TICKERS_FILE=""
BATCH_SIZE=500
DELAY_BETWEEN_BATCHES=600  # 10 minutes
START_DATE="2020-01-01"
END_DATE=$(date +%Y-%m-%d)
WORKERS=5
SKIP_AUDIT_PER_BATCH=true  # Solo auditar al final

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --source)
            SOURCE_TYPE="$2"
            shift 2
            ;;
        --tickers-file)
            TICKERS_FILE="$2"
            shift 2
            ;;
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --delay)
            DELAY_BETWEEN_BATCHES="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--source json] [--tickers-file FILE] [--batch-size N] [--delay SECONDS] [--workers N]"
            exit 1
            ;;
    esac
done

echo "================================================================================"
echo "  🏎️  EXPAND UNIVERSE EN BATCHES"
echo "================================================================================"
echo ""
echo "  Batch size:  $BATCH_SIZE tickers"
echo "  Delay:       $DELAY_BETWEEN_BATCHES segundos entre batches"
echo "  Workers:     $WORKERS"
echo "  Período:     $START_DATE → $END_DATE"
echo ""

# ==============================================================================
# FASE 1: Validar y generar lista de tickers nuevos
# ==============================================================================
echo "================================================================================"
echo "  📋 PASO 1: Validación y generación de lista limpia"
echo "================================================================================"
echo ""

if [ "$SOURCE_TYPE" = "json" ]; then
    echo "📂 Validando desde JSON: scripts/universe/tickers_universo.json"
    python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json --output new_tickers_to_add.txt
    TICKERS_FILE="new_tickers_to_add.txt"
elif [ -z "$TICKERS_FILE" ]; then
    echo "❌ Error: Debe especificar --source json o --tickers-file"
    exit 1
fi

if [ ! -f "$TICKERS_FILE" ]; then
    echo "❌ Error: Archivo no encontrado: $TICKERS_FILE"
    exit 1
fi

# Contar tickers (sin comentarios ni líneas vacías)
TOTAL_TICKERS=$(grep -v "^#" "$TICKERS_FILE" | grep -v "^$" | wc -l)

if [ "$TOTAL_TICKERS" -eq 0 ]; then
    echo ""
    echo "✅ No hay tickers nuevos. Todos ya están en la base de datos."
    exit 0
fi

echo ""
echo "✅ Total tickers a procesar: $TOTAL_TICKERS"

# Calcular número de batches
TOTAL_BATCHES=$(( ($TOTAL_TICKERS + $BATCH_SIZE - 1) / $BATCH_SIZE ))
echo "📦 Se crearán $TOTAL_BATCHES batches de máximo $BATCH_SIZE tickers"
echo ""

# ==============================================================================
# PASO 2: Dividir en batches
# ==============================================================================
echo "================================================================================"
echo "  ✂️  PASO 2: Dividiendo en batches"
echo "================================================================================"
echo ""

# Crear directorio temporal para batches
BATCH_DIR="batches_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BATCH_DIR"

# Limpiar archivo de tickers (sin comentarios ni vacías)
grep -v "^#" "$TICKERS_FILE" | grep -v "^$" > "$BATCH_DIR/tickers_clean.txt"

# Dividir en batches
cd "$BATCH_DIR"
split -l "$BATCH_SIZE" -d -a 3 tickers_clean.txt batch_
cd ..

BATCH_FILES=($(ls "$BATCH_DIR"/batch_* 2>/dev/null))
echo "✅ Creados ${#BATCH_FILES[@]} batches en: $BATCH_DIR/"
echo ""

# Mostrar info de batches
for i in "${!BATCH_FILES[@]}"; do
    batch_file="${BATCH_FILES[$i]}"
    batch_count=$(wc -l < "$batch_file")
    echo "  Batch $((i+1))/$TOTAL_BATCHES: $(basename $batch_file) → $batch_count tickers"
done

echo ""
read -p "🤔 ¿Continuar con el procesamiento? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Cancelado por el usuario"
    exit 0
fi

# ==============================================================================
# PASO 3: Procesar cada batch
# ==============================================================================
echo ""
echo "================================================================================"
echo "  🚀 PASO 3: Procesando batches"
echo "================================================================================"
echo ""

BATCH_SUCCESS=0
BATCH_FAILED=0
START_TIME=$(date +%s)

for i in "${!BATCH_FILES[@]}"; do
    batch_file="${BATCH_FILES[$i]}"
    batch_num=$((i+1))
    batch_count=$(wc -l < "$batch_file")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📦 BATCH $batch_num/$TOTAL_BATCHES ($(basename $batch_file))"
    echo "  Tickers: $batch_count | Hora: $(date +%H:%M:%S)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Procesar batch (skip validation y audit por batch)
    if ./expand_universe_complete.sh \
        --tickers-file "$batch_file" \
        --skip-validation \
        --skip-audit \
        --workers "$WORKERS" \
        --start-date "$START_DATE" \
        --end-date "$END_DATE"; then
        
        BATCH_SUCCESS=$((BATCH_SUCCESS + 1))
        echo ""
        echo "  ✅ Batch $batch_num completado exitosamente"
    else
        BATCH_FAILED=$((BATCH_FAILED + 1))
        echo ""
        echo "  ⚠️  Batch $batch_num falló (continuando con el siguiente)"
    fi
    
    # Delay entre batches (excepto el último)
    if [ $batch_num -lt $TOTAL_BATCHES ]; then
        echo ""
        echo "  ⏸️  Esperando $DELAY_BETWEEN_BATCHES segundos antes del siguiente batch..."
        echo "     (Rate limit cooldown + sistema estable)"
        
        # Progress bar para el delay
        for ((j=1; j<=DELAY_BETWEEN_BATCHES; j+=30)); do
            remaining=$((DELAY_BETWEEN_BATCHES - j))
            echo -ne "     ⏳ $remaining segundos restantes...\r"
            sleep 30
        done
        echo ""
        echo ""
    fi
done

# ==============================================================================
# PASO 4: Auditoría final de todo el universo
# ==============================================================================
echo ""
echo "================================================================================"
echo "  🔍 PASO 4: Auditoría Final del Universo Completo"
echo "================================================================================"
echo ""

if [ -f audit_data_gaps.py ]; then
    python3 audit_data_gaps.py
    echo ""
    echo "✅ Auditoría completa. Ver: gaps_report.csv"
else
    echo "⚠️  Script de auditoría no encontrado"
fi

# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
ELAPSED_HOURS=$(echo "scale=1; $ELAPSED / 3600" | bc)

echo ""
echo "================================================================================"
echo "  ✅ PROCESAMIENTO EN BATCHES COMPLETADO"
echo "================================================================================"
echo ""
echo "  📊 Estadísticas:"
echo "     Total tickers:      $TOTAL_TICKERS"
echo "     Total batches:      $TOTAL_BATCHES"
echo "     Batches exitosos:   $BATCH_SUCCESS"
echo "     Batches fallidos:   $BATCH_FAILED"
echo "     Tiempo total:       ${ELAPSED_HOURS} horas ($((ELAPSED / 60)) minutos)"
echo ""
echo "  📦 Archivos generados:"
echo "     - data/ticker_cache.db         (OHLCV histórico)"
echo "     - data/precomputed_metrics.pkl (Indicadores)"
echo "     - data/pattern_cache.pkl       (Patrones ⭐)"
echo "     - data/pattern_matrix.pkl      (Matriz confidence ⭐)"
echo "     - gaps_report.csv              (Auditoría)"
echo ""
echo "  📂 Batches guardados en: $BATCH_DIR/"
echo "     (Puedes eliminar esta carpeta si todo salió bien)"
echo ""
echo "  🎯 Próximos pasos:"
echo "     - Ver stats:     python3 manage_universe.py --info"
echo "     - Ver patrones:  python3 -c \"import pickle; print(f'Patrones: {len(pickle.load(open(\\\"data/pattern_cache.pkl\\\", \\\"rb\\\")))}')\"" 
echo "     - Run backtest:  streamlit run app.py"
echo ""
echo "================================================================================"

# Opción de cleanup
echo ""
read -p "🗑️  ¿Eliminar directorio de batches ($BATCH_DIR)? (yes/no): " -r
if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    rm -rf "$BATCH_DIR"
    echo "✅ Directorio eliminado"
else
    echo "📂 Directorio conservado: $BATCH_DIR/"
fi

echo ""
echo "🏁 PROCESO COMPLETADO"
