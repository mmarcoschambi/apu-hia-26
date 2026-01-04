#!/bin/bash

# QUICK START - Sistema de Trading Momentum
# ==========================================

echo "=================================="
echo "🚀 MOMENTUM TRADING SYSTEM"
echo "=================================="
echo ""

# Función para mostrar menú
show_menu() {
    echo "Selecciona una opción:"
    echo ""
    echo "  📊 INFORMACIÓN"
    echo "  1) Ver universo de tickers"
    echo "  2) Ver cache de datos"
    echo ""
    echo "  ➕ AGREGAR TICKERS"
    echo "  3) Agregar tickers manualmente"
    echo "  4) Agregar top S&P 500 + NASDAQ 100"
    echo ""
    echo "  🔬 BACKTESTING"
    echo "  5) Backtest 2024 (1 año) ⚡"
    echo "  6) Backtest 2020-2024 (5 años)"
    echo "  7) Backtest 2015-2024 (10 años)"
    echo "  8) Backtest custom (tú eliges fechas)"
    echo ""
    echo "  📈 LIVE TRADING"
    echo "  9) Abrir dashboard (Streamlit)"
    echo "  10) Live scanner"
    echo "  11) Market health check"
    echo ""
    echo "  📚 AYUDA"
    echo "  12) Ver guías de documentación"
    echo ""
    echo "  0) Salir"
    echo ""
}

while true; do
    show_menu
    read -p "Opción: " option
    echo ""
    
    case $option in
        1)
            echo "📊 Información del Universo:"
            echo "----------------------------"
            python3 manage_universe.py --info
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        2)
            echo "💾 Información del Cache:"
            echo "------------------------"
            python3 manage_universe.py --cache-info
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        3)
            echo "➕ Agregar Tickers Manualmente"
            echo "------------------------------"
            read -p "Ingresa tickers separados por comas (ej: AAPL, MSFT, NVDA): " tickers
            python3 manage_universe.py --add "$tickers"
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        4)
            echo "📊 Agregando Top S&P 500 + NASDAQ 100..."
            echo "----------------------------------------"
            python3 add_major_indices.py
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        5)
            echo "🔬 Backtest 2024 (1 año)"
            echo "-----------------------"
            echo "⏱️  Tiempo estimado:"
            echo "  - Primera vez: ~15-30 minutos"
            echo "  - Con cache: ~5-10 minutos"
            echo ""
            read -p "¿Continuar? (s/n): " confirm
            if [ "$confirm" = "s" ]; then
                python3 backtest_dynamic_universe.py --start 2024-01-01 --end 2024-12-31
            fi
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        6)
            echo "🔬 Backtest 2020-2024 (5 años)"
            echo "-----------------------------"
            echo "⏱️  Tiempo estimado:"
            echo "  - Primera vez: ~45-90 minutos"
            echo "  - Con cache: ~15-25 minutos"
            echo ""
            read -p "¿Continuar? (s/n): " confirm
            if [ "$confirm" = "s" ]; then
                python3 backtest_dynamic_universe.py --start 2020-01-01 --end 2024-12-31
            fi
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        7)
            echo "🔬 Backtest 2015-2024 (10 años)"
            echo "------------------------------"
            echo "⏱️  Tiempo estimado:"
            echo "  - Primera vez: ~90-180 minutos"
            echo "  - Con cache: ~30-45 minutos"
            echo ""
            read -p "¿Continuar? (s/n): " confirm
            if [ "$confirm" = "s" ]; then
                python3 backtest_dynamic_universe.py --start 2015-01-01 --end 2024-12-31
            fi
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        8)
            echo "🔬 Backtest Custom"
            echo "-----------------"
            read -p "Fecha inicio (YYYY-MM-DD): " start_date
            read -p "Fecha fin (YYYY-MM-DD): " end_date
            read -p "¿Usar market filter? (s/n): " use_filter
            
            if [ "$use_filter" = "n" ]; then
                python3 backtest_dynamic_universe.py --start "$start_date" --end "$end_date" --no-market-filter
            else
                python3 backtest_dynamic_universe.py --start "$start_date" --end "$end_date"
            fi
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        9)
            echo "📈 Abriendo Dashboard..."
            echo "-----------------------"
            echo "Se abrirá en tu navegador (http://localhost:8501)"
            echo "Presiona Ctrl+C para cerrar"
            echo ""
            streamlit run app.py
            ;;
        
        10)
            echo "📡 Live Scanner"
            echo "--------------"
            python3 live_scanner.py
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        11)
            echo "🚦 Market Health Check"
            echo "---------------------"
            python3 market_health_check.py
            echo ""
            read -p "Presiona ENTER para continuar..."
            ;;
        
        12)
            echo "📚 Documentación Disponible:"
            echo "---------------------------"
            echo ""
            echo "  📖 SISTEMA_LISTO_RESUMEN.md"
            echo "     └─ Resumen completo del sistema configurado"
            echo ""
            echo "  📖 UNIVERSO_Y_CACHE_GUIDE.md"
            echo "     └─ Guía de universo dinámico y cache"
            echo ""
            echo "  📖 LIVE_TRADING_GUIDE.md"
            echo "     └─ Guía de trading en vivo"
            echo ""
            echo "  📖 BACKTESTING.md"
            echo "     └─ Guía de backtesting"
            echo ""
            echo "  📖 MARKET_FILTERS.md"
            echo "     └─ Guía de filtros de mercado"
            echo ""
            read -p "Ver algún archivo? (nombre o ENTER para volver): " doc_file
            if [ ! -z "$doc_file" ]; then
                # Check direct match
                if [ -f "docs/$doc_file" ]; then
                    less "docs/$doc_file"
                elif [ -f "docs/guides/$doc_file" ]; then
                    less "docs/guides/$doc_file"
                elif [ -f "$doc_file" ]; then
                    less "$doc_file"
                else
                    echo "❌ Archivo no encontrado en docs/ ni docs/guides/"
                fi
            fi
            ;;
        
        0)
            echo "👋 ¡Hasta luego!"
            exit 0
            ;;
        
        *)
            echo "❌ Opción inválida"
            read -p "Presiona ENTER para continuar..."
            ;;
    esac
    
    echo ""
    echo "=================================="
    echo ""
done
