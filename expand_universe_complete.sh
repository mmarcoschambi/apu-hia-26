#!/bin/bash
# ==============================================================================
# EXPAND UNIVERSE COMPLETE - Pipeline completo de expansión de universo
# ==============================================================================
# Workflow integrado:
#   1. Validar tickers desde JSON (deduplicación)
#   2. Descargar datos históricos OHLCV
#   3. Pre-calcular indicadores técnicos
#   4. Pre-calcular patrones (VCP, Cup&Handle, etc.)
#   5. Auditar calidad de datos
#
# Usage:
#   ./expand_universe_complete.sh --source json
#   ./expand_universe_complete.sh --tickers-file my_tickers.txt
#   ./expand_universe_complete.sh --tickers-file my_tickers.txt --skip-patterns
# ==============================================================================

set -e  # Exit on error

# Default parameters
SOURCE_TYPE=""
TICKERS_FILE=""
START_DATE="2020-01-01"
END_DATE=$(date +%Y-%m-%d)
WORKERS=5
SKIP_VALIDATION=false
SKIP_DOWNLOAD=false
SKIP_INDICATORS=false
SKIP_PATTERNS=false
SKIP_AUDIT=false

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
        --start-date)
            START_DATE="$2"
            shift 2
            ;;
        --end-date)
            END_DATE="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --skip-validation)
            SKIP_VALIDATION=true
            shift
            ;;
        --skip-download)
            SKIP_DOWNLOAD=true
            shift
            ;;
        --skip-indicators)
            SKIP_INDICATORS=true
            shift
            ;;
        --skip-patterns)
            SKIP_PATTERNS=true
            shift
            ;;
        --skip-audit)
            SKIP_AUDIT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--source json] [--tickers-file FILE] [--workers N] [--start-date DATE] [--end-date DATE] [--skip-*]"
            exit 1
            ;;
    esac
done

echo "================================================================================"
echo "  🏎️  EXPAND UNIVERSE COMPLETE - Pipeline Automatizado"
echo "================================================================================"
echo ""
echo "  Período:  $START_DATE → $END_DATE"
echo "  Workers:  $WORKERS"
echo ""

# ==============================================================================
# FASE 1: VALIDACIÓN Y DEDUPLICACIÓN
# ==============================================================================
if [ "$SKIP_VALIDATION" = false ]; then
    echo "================================================================================"
    echo "  📋 FASE 1: Validación y Deduplicación"
    echo "================================================================================"
    echo ""
    
    if [ "$SOURCE_TYPE" = "json" ]; then
        echo "📂 Usando JSON: scripts/universe/tickers_universo.json"
        python3 add_tickers_from_json.py --source scripts/universe/tickers_universo.json --output new_tickers_to_add.txt
        TICKERS_FILE="new_tickers_to_add.txt"
    elif [ -z "$TICKERS_FILE" ]; then
        echo "❌ Error: Debe especificar --source json o --tickers-file"
        exit 1
    else
        echo "📂 Usando archivo: $TICKERS_FILE"
    fi
    
    # Check if file has tickers to add
    if [ ! -f "$TICKERS_FILE" ]; then
        echo "❌ Error: Archivo no encontrado: $TICKERS_FILE"
        exit 1
    fi
    
    # Count non-comment lines
    TICKER_COUNT=$(grep -v "^#" "$TICKERS_FILE" | grep -v "^$" | wc -l)
    
    if [ "$TICKER_COUNT" -eq 0 ]; then
        echo ""
        echo "✅ No hay tickers nuevos para agregar. Todos ya están en la base de datos."
        exit 0
    fi
    
    echo ""
    echo "✅ Validación completa: $TICKER_COUNT tickers nuevos a procesar"
    echo ""
else
    echo "⏭️  Saltando validación (--skip-validation)"
    if [ -z "$TICKERS_FILE" ]; then
        echo "❌ Error: --tickers-file requerido cuando se salta validación"
        exit 1
    fi
fi

# ==============================================================================
# FASE 2: DESCARGA DE DATOS HISTÓRICOS
# ==============================================================================
if [ "$SKIP_DOWNLOAD" = false ]; then
    echo "================================================================================"
    echo "  📥 FASE 2: Descarga de Datos Históricos"
    echo "================================================================================"
    echo ""
    
    python3 expand_universe.py \
        --ticker-file "$TICKERS_FILE" \
        --workers "$WORKERS" \
        --start-date "$START_DATE" \
        --end-date "$END_DATE"
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Error en descarga de datos. Abortando pipeline."
        exit 1
    fi
    
    echo ""
    echo "✅ Descarga completada"
    echo ""
else
    echo "⏭️  Saltando descarga (--skip-download)"
fi

# ==============================================================================
# FASE 3: PRE-CÁLCULO DE INDICADORES
# ==============================================================================
if [ "$SKIP_INDICATORS" = false ]; then
    echo "================================================================================"
    echo "  📊 FASE 3: Pre-cálculo de Indicadores Técnicos"
    echo "================================================================================"
    echo ""
    
    python3 precompute_all_indicators.py --tickers-file "$TICKERS_FILE"
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "⚠️  Error en pre-cálculo de indicadores. Continuando..."
    else
        echo ""
        echo "✅ Indicadores pre-calculados"
    fi
    echo ""
else
    echo "⏭️  Saltando indicadores (--skip-indicators)"
fi

# ==============================================================================
# FASE 4: PRE-CÁLCULO DE PATRONES
# ==============================================================================
if [ "$SKIP_PATTERNS" = false ]; then
    echo "================================================================================"
    echo "  🎯 FASE 4: Pre-cálculo de Patrones Técnicos"
    echo "================================================================================"
    echo ""
    
    python3 precompute_patterns.py \
        --tickers-file "$TICKERS_FILE" \
        --merge \
        --start "$START_DATE" \
        --end "$END_DATE" \
        --step 5
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "⚠️  Error en pre-cálculo de patrones. Continuando..."
    else
        echo ""
        echo "✅ Patrones pre-calculados"
    fi
    echo ""
else
    echo "⏭️  Saltando patrones (--skip-patterns)"
fi

# ==============================================================================
# FASE 5: AUDITORÍA DE CALIDAD
# ==============================================================================
if [ "$SKIP_AUDIT" = false ]; then
    echo "================================================================================"
    echo "  🔍 FASE 5: Auditoría de Calidad de Datos"
    echo "================================================================================"
    echo ""
    
    if [ -f audit_data_gaps.py ]; then
        python3 audit_data_gaps.py
        echo ""
        echo "✅ Auditoría completa. Ver gaps_report.csv para detalles"
    else
        echo "⚠️  Script de auditoría no encontrado (audit_data_gaps.py)"
    fi
    echo ""
else
    echo "⏭️  Saltando auditoría (--skip-audit)"
fi

# ==============================================================================
# RESUMEN FINAL
# ==============================================================================
echo "================================================================================"
echo "  ✅ PIPELINE COMPLETADO"
echo "================================================================================"
echo ""
echo "  📦 Archivos generados:"
echo "     - data/ticker_cache.db         (OHLCV histórico)"
echo "     - data/precomputed_metrics.pkl (Indicadores)"
echo "     - data/pattern_cache.pkl       (Patrones por fecha)"
echo "     - data/pattern_matrix.pkl      (Matriz de confidence)"
echo ""
echo "  🎯 Próximos pasos:"
echo "     - Verificar universo: python3 manage_universe.py --info"
echo "     - Ver cache info:     python3 manage_universe.py --cache-info"
echo "     - Run backtest:       streamlit run app.py"
echo "     - Optimize params:    python3 bugatti_optuna.py"
echo ""
echo "================================================================================"
