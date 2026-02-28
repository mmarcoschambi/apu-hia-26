#!/bin/bash
# Quick Setup for Heatmap Optimization System
# ============================================

echo "=================================="
echo "🔧 HEATMAP OPTIMIZATION SETUP"
echo "=================================="

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q optuna>=3.5.0 plotly>=5.18.0 tqdm>=4.66.0

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi

# Create directories
echo ""
echo "📁 Creating output directories..."
mkdir -p config outputs/optimization outputs/range_analysis

echo "✅ Directories created"

# Make scripts executable
echo ""
echo "🔨 Making scripts executable..."
chmod +x optimize_with_heatmaps.py
chmod +x analyze_parameter_ranges.py
chmod +x apply_optimized_params.py
chmod +x test_heatmap_optimization.py
chmod +x generate_optimization_summary.py

echo "✅ Scripts are now executable"

# Quick validation
echo ""
echo "🧪 Validating setup..."
python3 -c "import optuna, plotly, tqdm; print('✅ All imports working')"

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================="
    echo "✅ SETUP COMPLETE!"
    echo "=================================="
    echo ""
    echo "📚 Quick Start:"
    echo ""
    echo "  1. Test the system (10 trials, 3 months):"
    echo "     python test_heatmap_optimization.py"
    echo ""
    echo "  2. Run full optimization (100 trials, 1 year):"
    echo "     python optimize_with_heatmaps.py --trials 100 --limit 50"
    echo ""
    echo "  3. Analyze specific ranges:"
    echo "     python analyze_parameter_ranges.py --analysis switches"
    echo ""
    echo "  4. Generate summary dashboard:"
    echo "     python generate_optimization_summary.py"
    echo ""
    echo "  5. Apply best config to Streamlit:"
    echo "     python apply_optimized_params.py"
    echo ""
    echo "📖 Full guide: HEATMAP_OPTIMIZATION_GUIDE.md"
    echo "=================================="
else
    echo "❌ Validation failed"
    exit 1
fi
