#!/bin/bash
# Script para correr múltiples optimizaciones secuencialmente y guardar resultados
# Incluye validación OOS automática y protección golden guard para VCP

# Directorio para guardar logs
LOG_DIR="logs/optimization_runs"
mkdir -p "$LOG_DIR"

# Timestamp para esta sesión
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SESSION_DIR="$LOG_DIR/session_${TIMESTAMP}"
mkdir -p "$SESSION_DIR"

echo "======================================"
echo "Iniciando sesión de optimización: $TIMESTAMP"
echo "Resultados se guardarán en: $SESSION_DIR"
echo "======================================"
echo ""

# Verificar protección golden guard VCP
if [ -f "config/vcp_config.json" ]; then
    VCP_OOS=$(python3 -c "import json; cfg=json.load(open('config/vcp_config.json')); print(cfg.get('_oos_sharpe', 0))" 2>/dev/null)
    if [ ! -z "$VCP_OOS" ] && [ "$VCP_OOS" != "0" ]; then
        echo "🛡️  VCP Golden Guard detectado: _oos_sharpe=$VCP_OOS"
        echo "   VCP config está protegido contra re-optimización accidental"
        echo ""
    fi
fi

# Función para ejecutar optimización y guardar resultados
run_optimization() {
    local name=$1
    local cmd=$2
    local signal_type=$3  # nuevo parámetro para saber si hacer validación OOS
    local log_file="${SESSION_DIR}/${name}.log"
    local result_file="${SESSION_DIR}/${name}_result.txt"
    
    echo "--------------------------------------"
    echo "🚀 Iniciando: $name"
    echo "Comando: $cmd"
    echo "Log: $log_file"
    echo "Hora inicio: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "--------------------------------------"
    
    # Ejecutar comando y guardar salida
    START_TIME=$(date +%s)
    eval "$cmd" 2>&1 | tee "$log_file"
    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    # Guardar resultado final
    echo "=====================================" > "$result_file"
    echo "Optimización: $name" >> "$result_file"
    echo "Comando: $cmd" >> "$result_file"
    echo "Hora inicio: $(date -d @$START_TIME '+%Y-%m-%d %H:%M:%S')" >> "$result_file"
    echo "Hora fin: $(date -d @$END_TIME '+%Y-%m-%d %H:%M:%S')" >> "$result_file"
    echo "Duración: $((DURATION / 3600))h $((DURATION % 3600 / 60))m $((DURATION % 60))s" >> "$result_file"
    echo "Exit code: $EXIT_CODE" >> "$result_file"
    echo "=====================================" >> "$result_file"
    echo "" >> "$result_file"
    
    # Extraer últimas líneas del log (resultado final)
    echo "Últimas 50 líneas del log:" >> "$result_file"
    tail -50 "$log_file" >> "$result_file"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ COMPLETADO: $name (duración: $((DURATION / 60))m)" | tee -a "$result_file"
        
        # Si es una optimización con signal-type específico, ejecutar validación OOS
        if [ ! -z "$signal_type" ]; then
            echo "" | tee -a "$result_file"
            echo "🔍 Ejecutando validación OOS para $signal_type..." | tee -a "$result_file"
            local oos_log="${SESSION_DIR}/${name}_oos_validation.log"
            python3 validate_signal_oos.py --signal-type "$signal_type" \
                --start 2023-01-01 --end 2024-12-31 --tickers 120 \
                2>&1 | tee "$oos_log"
            local OOS_EXIT=${PIPESTATUS[0]}
            
            if [ $OOS_EXIT -eq 0 ]; then
                echo "✅ Validación OOS completada para $signal_type" | tee -a "$result_file"
                echo "   Ver resultados en: $oos_log" | tee -a "$result_file"
            else
                echo "⚠️  Validación OOS falló para $signal_type (exit code: $OOS_EXIT)" | tee -a "$result_file"
            fi
        fi
    else
        echo "❌ ERROR: $name (exit code: $EXIT_CODE)" | tee -a "$result_file"
    fi
    echo ""
}

# Ejecutar optimizaciones secuencialmente con validación OOS
# Nota: VCP tiene protección golden guard (_oos_sharpe: 1.30 stamped)
# Para re-optimizar VCP, primero verificar que quieres sobrescribir el config validado

run_optimization "01_vcp" \
    "python3 optimize_3tier.py --signal-type vcp --trials 200 --tickers 80" \
    "vcp"

run_optimization "02_pocket_pivot" \
    "python3 optimize_3tier.py --signal-type pocket_pivot --trials 200 --tickers 80" \
    "pocket_pivot"

run_optimization "03_flat_base" \
    "python3 optimize_3tier.py --signal-type flat_base --trials 200 --tickers 80" \
    "flat_base"

run_optimization "04_breakout" \
    "python3 optimize_3tier.py --signal-type breakout --trials 300 --tickers 80" \
    "breakout"

run_optimization "05_extended_period" \
    "python3 optimize_3tier.py --start 2019-01-01 --end 2025-12-31 --trials 270 --tickers 120" \
    ""  # no signal-type específico, no OOS validation

# Resumen final
echo "======================================"
echo "✅ TODAS LAS OPTIMIZACIONES COMPLETADAS"
echo "Hora fin: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"
echo ""
echo "📊 Resumen de resultados:"
echo ""
cat "$SESSION_DIR"/*_result.txt | grep -E "(Optimización:|Duración:|Exit code:|COMPLETADO|ERROR)"
echo ""

# Mostrar resultados OOS si existen
echo "📈 Resultados OOS Validation:"
echo ""
for oos_file in "$SESSION_DIR"/*_oos_validation.log; do
    if [ -f "$oos_file" ]; then
        echo "$(basename $oos_file):"
        grep -E "(VERDICT|OOS Sharpe|degradation)" "$oos_file" | head -5
        echo ""
    fi
done

echo "📁 Todos los resultados guardados en: $SESSION_DIR"
echo ""

# Crear índice de archivos generados
echo "Archivos generados:" > "$SESSION_DIR/INDEX.txt"
ls -lh "$SESSION_DIR" >> "$SESSION_DIR/INDEX.txt"

# Mostrar resumen de configs generados
echo "" >> "$SESSION_DIR/INDEX.txt"
echo "Configs actualizados:" >> "$SESSION_DIR/INDEX.txt"
for cfg in config/vcp_config.json config/pocket_pivot_config.json config/flat_base_config.json config/breakout_config.json; do
    if [ -f "$cfg" ]; then
        echo "  - $cfg" >> "$SESSION_DIR/INDEX.txt"
        OOS_SHARPE=$(python3 -c "import json; cfg=json.load(open('$cfg')); print(cfg.get('_oos_sharpe', 'N/A'))" 2>/dev/null)
        echo "    OOS Sharpe: $OOS_SHARPE" >> "$SESSION_DIR/INDEX.txt"
    fi
done

cat "$SESSION_DIR/INDEX.txt"
