#!/bin/bash
#
# DUAL VALIDATION WORKFLOW
# =========================
# 
# 1. Walk Forward con V6_PRO (rápido) → encuentra rangos robustos
# 2. Validación con Advanced (producción) → verifica que funcionen
# 3. Selecciona params que funcionen en AMBOS motores
#
# NEW: Ahora optimiza los porcentajes de salida TP1/TP2/Runner
#
# Usage:
#   bash run_dual_validation.sh [--quick] [--tp-preset optimize|classic|balanced|aggressive_runner|conservative|extreme]
#
# TP Presets:
#   optimize: Busca la distribución óptima (default)
#   classic: 50% TP1, 30% TP2, 20% Runner (tradicional - MATA Alpha)
#   balanced: 33% TP1, 33% TP2, 34% Runner (equilibrado)
#   aggressive_runner: 25% TP1, 30% TP2, 45% Runner (busca home runs)
#   conservative: 40% TP1, 35% TP2, 25% Runner (asegura ganancias)
#   extreme: 20% TP1, 30% TP2, 50% Runner (máximo runner, más agresivo)

set -e

echo "================================================================================"
echo "🚀 DUAL VALIDATION WORKFLOW"
echo "================================================================================"
echo ""

# Parse arguments
QUICK_MODE=false
TP_PRESET="optimize"

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --tp-preset)
            TP_PRESET="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--quick] [--tp-preset optimize|classic|balanced|aggressive_runner|conservative|extreme]"
            exit 1
            ;;
    esac
done

# ============================================================================
# STEP 0: Check for existing optimal TP configuration
# ============================================================================

echo ""
echo "================================================================================"
echo "🔍 CHECKING FOR EXISTING OPTIMAL TP CONFIGURATION"
echo "================================================================================"
echo ""

# Check if optimal TP exists
if [ -f "config/tp_optimal.json" ]; then
    echo "✅ Found saved optimal TP configuration:"
    python3 -c "
import json
from datetime import datetime
with open('config/tp_optimal.json', 'r') as f:
    config = json.load(f)
print(f\"   TP1: {config['tp1_pct']*100:.0f}%, TP2: {config['tp2_pct']*100:.0f}%, Runner: {config['runner_pct']*100:.0f}%\")
print(f\"   Sharpe: {config.get('sharpe', 'N/A')}\")
print(f\"   Source: {config.get('source', 'unknown')}\")
saved_date = datetime.fromisoformat(config['timestamp'])
days_old = (datetime.now() - saved_date).days
print(f\"   Age: {days_old} days old\")
if days_old > 7:
    print(f\"   ⚠️  Warning: Configuration is {days_old} days old\")
"
    
    # Ask if user wants to use it or re-optimize
    if [ "$TP_PRESET" = "optimize" ]; then
        echo ""
        read -p "Use this configuration? (y/n, default=y): " USE_SAVED
        USE_SAVED=${USE_SAVED:-y}
        
        if [ "$USE_SAVED" != "y" ]; then
            echo "🔄 Will re-optimize TP distribution..."
            rm -f config/tp_optimal.json
        else
            echo "✅ Using saved optimal TP configuration"
        fi
    fi
else
    if [ "$TP_PRESET" = "optimize" ]; then
        echo "❌ No saved optimal TP found"
        echo "💡 Walk Forward will optimize TP dynamically (slower)"
        echo ""
        read -p "Run optimize_tp_distributions.py first? (y/n, default=n): " RUN_OPTIMIZE
        RUN_OPTIMIZE=${RUN_OPTIMIZE:-n}
        
        if [ "$RUN_OPTIMIZE" = "y" ]; then
            echo ""
            echo "🔧 Running TP optimization first..."
            python3 optimize_tp_distributions.py --mode optimize --trials 50
            echo ""
        fi
    else
        echo "✅ Using preset: $TP_PRESET"
    fi
fi

# ============================================================================
# STEP 1: Walk Forward Optimization (V6_PRO - Fast)
# ============================================================================

# Define robust universe for validation (Top ~40 Liquid Leaders)
# Mix of Mega Cap, Growth, and Semiconductors to ensure robustness
UNIVERSE="AAPL MSFT GOOGL NVDA TSLA META AMZN NFLX AMD AVGO QCOM INTC TXN ADBE CRM COST CSCO AMAT MU LRCX PYPL ADP BKNG INTU PANW VRTX REGN KLAC SNPS CDNS MAR FTNT MELI ORLY CTAS PCAR"

echo ""
echo "================================================================================"
echo "📊 STEP 1: WALK FORWARD OPTIMIZATION (V6_PRO Engine)"
echo "================================================================================"
echo ""

if [ "$QUICK_MODE" = true ]; then
    echo "⚡ Quick mode: 2 windows, 20 trials each"
    python3 walk_forward_validation.py \
        --train-months 12 \
        --test-months 3 \
        --walk-months 6 \
        --trials 20 \
        --start 2023-01-01 \
        --end 2024-12-31 \
        --tickers $UNIVERSE \
        --tp-preset "$TP_PRESET"
else
    echo "🔧 Full mode: Extended windows, more trials"
    python3 walk_forward_validation.py \
        --train-months 12 \
        --test-months 3 \
        --walk-months 3 \
        --trials 50 \
        --start 2020-01-01 \
        --end 2024-12-31 \
        --tickers $UNIVERSE \
        --tp-preset "$TP_PRESET"
fi

echo ""
echo "✅ Walk Forward complete!"
echo ""

# ============================================================================
# STEP 2: Validate Top Params with Advanced
# ============================================================================

echo ""
echo "================================================================================"
echo "🔬 STEP 2: VALIDATION WITH ADVANCED ENGINE (Production)"
echo "================================================================================"
echo ""

if [ "$QUICK_MODE" = true ]; then
    echo "⚡ Quick validation: Top 3 configs, 2 years"
    python3 validate_top_params_with_advanced.py \
        --top 3 \
        --period 2023-01-01:2024-12-31 \
        --min-trades 5
else
    echo "🔧 Full validation: Top 5 configs, 5 years"
    python3 validate_top_params_with_advanced.py \
        --top 5 \
        --period 2020-01-01:2024-12-31 \
        --min-trades 10
fi

echo ""
echo "✅ Validation complete!"
echo ""

# ============================================================================
# STEP 3: Summary
# ============================================================================

echo ""
echo "================================================================================"
echo "📋 RESULTS SUMMARY"
echo "================================================================================"
echo ""
echo "📁 Files generated:"
echo "   • outputs/walk_forward_results.json - Walk Forward raw results"
echo "   • config/validated_production_params.json - RECOMMENDED params for production"
echo ""
echo "🎯 TP Distribution used: $TP_PRESET"
if [ "$TP_PRESET" == "optimize" ]; then
    echo "   Los porcentajes óptimos de TP1/TP2/Runner fueron optimizados"
else
    echo "   TP1/TP2/Runner usaron preset fijo: $TP_PRESET"
fi
echo ""
echo "💡 Next Steps:"
echo "   1. Review: cat config/validated_production_params.json"
echo "   2. Backtest with recommended params:"
echo "      python3 simplified_backtest.py --start 2020-01-01 --end 2024-12-31"
echo "   3. If satisfied, use in production (app.py or live_scanner.py)"
echo ""
echo "💡 Para probar otras distribuciones de TP:"
echo "   bash run_dual_validation.sh --tp-preset balanced  # 33/33/34"
echo "   bash run_dual_validation.sh --tp-preset aggressive_runner  # 25/30/45"
echo ""
echo "✅ Dual validation workflow complete!"
