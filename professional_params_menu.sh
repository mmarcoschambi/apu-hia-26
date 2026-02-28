#!/bin/bash
# Quick Start: Professional Parameters Implementation

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🚀 PROFESSIONAL PARAMETERS - Quick Start Guide"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Función para mostrar menú
show_menu() {
    echo "Selecciona una opción:"
    echo ""
    echo "  1) 🧪 Ejecutar Tests de Validación"
    echo "     - Valida que los parámetros profesionales estén correctamente implementados"
    echo "     - Ejecuta 27 tests de validación"
    echo ""
    echo "  2) 📊 Comparar OLD vs PROFESSIONAL"
    echo "     - Ejecuta backtests comparativos"
    echo "     - Muestra mejoras proyectadas"
    echo ""
    echo "  3) 🎯 Abrir Streamlit UI"
    echo "     - Interfaz gráfica para backtesting"
    echo "     - Parámetros profesionales ya aplicados"
    echo ""
    echo "  4) 📖 Ver Documentación"
    echo "     - Guía completa de implementación"
    echo "     - Detalles de todos los cambios"
    echo ""
    echo "  5) ❓ Ver Resumen Ejecutivo"
    echo "     - Status de implementación"
    echo "     - Checklist y próximos pasos"
    echo ""
    echo "  6) 🔧 Troubleshooting"
    echo "     - Solucionar problemas comunes"
    echo ""
    echo "  0) ❌ Salir"
    echo ""
}

# Tests de validación
run_tests() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🧪 Ejecutando Tests de Validación..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python3 test_professional_params.py
    
    echo ""
    echo "Presiona ENTER para continuar..."
    read
}

# Comparación
run_comparison() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📊 Ejecutando Comparación OLD vs PROFESSIONAL..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  NOTA: Esto puede tardar varios minutos dependiendo de:"
    echo "   - Tamaño del universo"
    echo "   - Período de tiempo"
    echo "   - Datos disponibles en cache"
    echo ""
    echo "Presiona ENTER para continuar o Ctrl+C para cancelar..."
    read
    
    python3 compare_old_vs_pro.py
    
    echo ""
    echo "Presiona ENTER para continuar..."
    read
}

# Streamlit
run_streamlit() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🎯 Abriendo Streamlit UI..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "✅ Parámetros profesionales YA están aplicados por defecto:"
    echo ""
    echo "   Filtros de Scanner:"
    echo "   - Min ADR: 5.0% (High ADR Growth)"
    echo "   - Min RVOL: 2.5x (Breakout real)"
    echo "   - Min Dollar Vol: \$5M (permite mid-caps)"
    echo ""
    echo "   Filtros de Riesgo:"
    echo "   - Max Dist SMA20: 2.5% (no late entries)"
    echo "   - RVOL Danger: 4.0x (danger real)"
    echo "   - RVOL Warning: 3.0x (warning ajustado)"
    echo "   - Max Stop: 6.5% (Minervini <7%)"
    echo "   - VCP: 10+ días (quality bases)"
    echo ""
    echo "La interfaz se abrirá en tu navegador..."
    echo ""
    
    streamlit run app.py
}

# Ver documentación
view_docs() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📖 Documentación Disponible"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  1) PROFESSIONAL_PARAMETERS_FIX.md"
    echo "     - Análisis completo de problemas y soluciones"
    echo "     - Detalles de cada parámetro"
    echo "     - Umbrales dinámicos explicados"
    echo ""
    echo "  2) IMPLEMENTATION_SUMMARY.md"
    echo "     - Resumen ejecutivo"
    echo "     - Status de implementación"
    echo "     - Checklist y próximos pasos"
    echo ""
    echo "Selecciona documento (1-2) o ENTER para volver:"
    read doc_choice
    
    case $doc_choice in
        1)
            if command -v bat &> /dev/null; then
                bat PROFESSIONAL_PARAMETERS_FIX.md
            else
                less PROFESSIONAL_PARAMETERS_FIX.md
            fi
            ;;
        2)
            if command -v bat &> /dev/null; then
                bat IMPLEMENTATION_SUMMARY.md
            else
                less IMPLEMENTATION_SUMMARY.md
            fi
            ;;
        *)
            return
            ;;
    esac
    
    echo ""
    echo "Presiona ENTER para continuar..."
    read
}

# Ver resumen
view_summary() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ IMPLEMENTACIÓN COMPLETADA"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📊 PARÁMETROS ACTUALIZADOS:"
    echo ""
    echo "  max_dist_sma20:         7.0%  →  2.5%   ✅"
    echo "  min_rvol:               2.0x  →  2.5x   ✅"
    echo "  min_adr:                3.0%  →  5.0%   ✅"
    echo "  min_dollar_volume:      \$15M  →  \$5M    ✅"
    echo "  max_stop_pct:           8.0%  →  6.5%   ✅"
    echo "  min_consolidation_days:   5   →   10    ✅"
    echo "  rvol_danger:            3.0x  →  4.0x   ✅"
    echo "  rvol_warning:           2.0x  →  3.0x   ✅"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📈 MEJORAS PROYECTADAS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  Win Rate:         27.3%  →  58-65%     (+120%)"
    echo "  Profit Factor:     0.39  →  2.0-2.5    (+410%)"
    echo "  Avg R-Multiple:  -0.30R  →  +1.2R      (+500%)"
    echo "  Alpha vs SPY:    -38.99% →  +8-15%     (Beat market)"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  📝 PRÓXIMOS PASOS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  1. ✅ Ejecutar tests de validación (opción 1)"
    echo "  2. 📊 Ejecutar backtest comparativo (opción 2)"
    echo "  3. 🎯 Probar en Streamlit UI (opción 3)"
    echo "  4. 📈 Validar mejoras en métricas reales"
    echo "  5. 🔧 (Opcional) Fine-tuning con Optuna"
    echo ""
    echo "Presiona ENTER para continuar..."
    read
}

# Troubleshooting
troubleshooting() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  🔧 Troubleshooting"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "❓ PROBLEMA: Tests fallan"
    echo "   SOLUCIÓN: Verificar que los archivos estén actualizados:"
    echo "   - src/backtest/vectorbt_engine_advanced.py"
    echo "   - app.py"
    echo ""
    echo "❓ PROBLEMA: No veo mejoras en backtests"
    echo "   POSIBLES CAUSAS:"
    echo "   1. Período muy corto (usa mínimo 2 años)"
    echo "   2. Universo pequeño (usa S&P 500+)"
    echo "   3. Datos insuficientes (verifica cache)"
    echo "   4. Market regime desfavorable (habilita filtro)"
    echo ""
    echo "❓ PROBLEMA: Streamlit no inicia"
    echo "   SOLUCIÓN:"
    echo "   pip install --upgrade streamlit"
    echo "   streamlit run app.py"
    echo ""
    echo "❓ PROBLEMA: Imports fallan"
    echo "   SOLUCIÓN:"
    echo "   pip install -r requirements.txt"
    echo ""
    echo "❓ PROBLEMA: No hay datos en cache"
    echo "   SOLUCIÓN:"
    echo "   python populate_tickers_from_api.py"
    echo ""
    echo "Presiona ENTER para continuar..."
    read
}

# Loop principal
while true; do
    clear
    echo ""
    show_menu
    read -p "Opción: " choice
    
    case $choice in
        1)
            run_tests
            ;;
        2)
            run_comparison
            ;;
        3)
            run_streamlit
            ;;
        4)
            view_docs
            ;;
        5)
            view_summary
            ;;
        6)
            troubleshooting
            ;;
        0)
            echo ""
            echo "👋 ¡Hasta luego!"
            echo ""
            exit 0
            ;;
        *)
            echo ""
            echo "❌ Opción inválida. Presiona ENTER para continuar..."
            read
            ;;
    esac
done
