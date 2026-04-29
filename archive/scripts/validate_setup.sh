#!/bin/bash
# Validate Heatmap Optimization Setup
# ====================================

echo "🔍 Validating Heatmap Optimization Setup..."
echo ""

ERRORS=0

# Check scripts exist
echo "📝 Checking scripts..."
SCRIPTS=(
    "optimize_with_heatmaps.py"
    "analyze_parameter_ranges.py"
    "apply_optimized_params.py"
    "generate_optimization_summary.py"
    "inspect_optimization_results.py"
    "test_heatmap_optimization.py"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            echo "  ✅ $script (executable)"
        else
            echo "  ⚠️  $script (not executable - run: chmod +x $script)"
            ERRORS=$((ERRORS+1))
        fi
    else
        echo "  ❌ $script (missing)"
        ERRORS=$((ERRORS+1))
    fi
done

# Check docs
echo ""
echo "📚 Checking documentation..."
DOCS=(
    "HEATMAP_OPTIMIZATION_GUIDE.md"
    "HEATMAP_SYSTEM_RESUMEN.md"
    "SISTEMA_HEATMAPS_INSTALADO.txt"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "  ✅ $doc"
    else
        echo "  ❌ $doc (missing)"
        ERRORS=$((ERRORS+1))
    fi
done

# Check directories
echo ""
echo "📁 Checking directories..."
DIRS=(
    "config"
    "outputs/optimization"
    "outputs/range_analysis"
)

for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "  ✅ $dir/"
    else
        echo "  ⚠️  $dir/ (missing - will be created)"
        mkdir -p "$dir"
    fi
done

# Check modified code
echo ""
echo "🔧 Checking code modifications..."
if grep -q "if risk_dollars is not None:" src/backtest/vectorbt_engine_advanced.py; then
    echo "  ✅ risk_dollars parameter (configurable)"
else
    echo "  ❌ risk_dollars still hardcoded"
    ERRORS=$((ERRORS+1))
fi

if grep -q "self.require_positive_rs = True  # Can be overridden" src/backtest/vectorbt_engine_advanced.py || \
   grep -q "self.require_positive_rs = True  # Default: True" src/backtest/vectorbt_engine_advanced.py; then
    echo "  ✅ require_positive_rs parameter (configurable)"
else
    echo "  ⚠️  require_positive_rs might still be hardcoded"
fi

# Check Python imports
echo ""
echo "🐍 Checking Python dependencies..."
python3 -c "import optuna" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✅ optuna"
else
    echo "  ❌ optuna (run: pip install optuna>=3.5.0)"
    ERRORS=$((ERRORS+1))
fi

python3 -c "import plotly" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✅ plotly"
else
    echo "  ❌ plotly (run: pip install plotly>=5.18.0)"
    ERRORS=$((ERRORS+1))
fi

python3 -c "import tqdm" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✅ tqdm"
else
    echo "  ❌ tqdm (run: pip install tqdm>=4.66.0)"
    ERRORS=$((ERRORS+1))
fi

# Summary
echo ""
echo "═════════════════════════════════════════════════════════════"

if [ $ERRORS -eq 0 ]; then
    echo "✅ VALIDATION PASSED - All checks OK!"
    echo ""
    echo "Ready to start:"
    echo "  1. Quick test:  python test_heatmap_optimization.py"
    echo "  2. Full run:    python optimize_with_heatmaps.py --trials 100"
else
    echo "⚠️  VALIDATION FAILED - $ERRORS error(s) found"
    echo ""
    echo "Fix issues and run again."
    echo "Or run setup script: ./setup_heatmap_optimization.sh"
fi

echo "═════════════════════════════════════════════════════════════"
