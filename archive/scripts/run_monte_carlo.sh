#!/bin/bash

# CONFIGURACIÓN
# ==========================================
NUM_RUNS=3                 # Cuántas veces quieres repetir la prueba
L1_TICKERS=150             # Tickers para capa 1 (Hardware friendly)
L2_TICKERS=80              # Tickers para capa 2
TRIALS_L1=50               # Intentos de optimización Capa 1
TRIALS_L2=30               # Intentos de optimización Capa 2
OUTPUT_FILE="MONTE_CARLO_RESULTS_$(date +%Y%m%d_%H%M%S).txt"
# ==========================================

echo "🏎️  INICIANDO SIMULACIÓN MONTE CARLO (Bugatti Bolide)"
echo "    Runs: $NUM_RUNS | Tickers L1: $L1_TICKERS | Trials: $TRIALS_L1"
echo "    Resultados resumidos en: $OUTPUT_FILE"
echo "======================================================"

# Crear cabecera del reporte
echo "BUGATTI BOLIDE - MONTE CARLO REPORT" > "$OUTPUT_FILE"
echo "Fecha: $(date)" >> "$OUTPUT_FILE"
echo "Config: $L1_TICKERS tickers / $TRIALS_L1 trials" >> "$OUTPUT_FILE"
echo "------------------------------------------------------" >> "$OUTPUT_FILE"

for i in $(seq 1 $NUM_RUNS); do
    # Generar semilla aleatoria entre 1 y 10000
    SEED=$((1 + RANDOM % 10000))
    
    echo ""
    echo "🎲 [RUN $i/$NUM_RUNS] Usando Semilla (Seed): $SEED"
    echo "    (Esto seleccionará un set único de tickers aleatorios)"
    
    # Escribir en reporte
    echo "" >> "$OUTPUT_FILE"
    echo ">>> RUN #$i (Seed: $SEED)" >> "$OUTPUT_FILE"
    
    # Ejecutar Bugatti Bolide X
    # Capturamos la salida en una variable para buscar el Sharpe final, pero dejamos que se vea en pantalla
    # Usamos 'tee' para ver en pantalla y guardar en log temporal
    LOG_TEMP="temp_run_$i.log"
    
    python3 bugatti_bolide_X.py \
        --layer1-tickers $L1_TICKERS \
        --layer2-tickers $L2_TICKERS \
        --layer1-trials $TRIALS_L1 \
        --layer2-trials $TRIALS_L2 \
        --seed $SEED \
        --run-oos \
        | tee "$LOG_TEMP"
    
    # Extraer resultados clave del log para el resumen
    SHARPE_VAL=$(grep "VALIDATION sharpe" "$LOG_TEMP" | tail -n 1 | awk '{print $3}')
    if [ -z "$SHARPE_VAL" ]; then
        # Intento alternativo de busqueda si el formato cambia
        SHARPE_VAL=$(grep -A 5 "VALIDATION RESULTS" "$LOG_TEMP" | grep "Sharpe Ratio" | awk '{print $3}')
    fi
    
    BEST_L2_VAL=$(grep "LAYER 2 RESULTS" -A 2 "$LOG_TEMP" | grep "SHARPE:" | awk '{print $2}')
    
    # Extraer parámetros ganadores (un hack rápido con grep, mejor ver el JSON completo)
    # Solo sacamos un par de ejemplo para ver si convergen
    RISK_PARAM=$(grep "risk_dollars:" "$LOG_TEMP" | tail -n 1)
    
    echo "    Resultado Validación (Sharpe): $SHARPE_VAL" >> "$OUTPUT_FILE"
    echo "    Resultado In-Sample (Sharpe):  $BEST_L2_VAL" >> "$OUTPUT_FILE"
    
    # Limpieza
    rm "$LOG_TEMP"
    
    echo "✅ Run $i completado."
    echo "------------------------------------------------------"
    
    # Pequeña pausa para enfriar CPU si es necesario
    sleep 2
done

echo ""
echo "🏁 SIMULACIÓN COMPLETADA"
echo "📄 Revisa el resumen en: $OUTPUT_FILE"
echo "📂 Los reportes detallados (JSON) están en outputs/bolide_walkforward/"
