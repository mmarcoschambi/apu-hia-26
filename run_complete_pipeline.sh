#!/bin/bash
# COMPLETE VALIDATION & WALK FORWARD PIPELINE
# ============================================

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║     🏎️  BUGATTI VALIDATION & WALK FORWARD PIPELINE               ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Apply optimal parameters
echo "📋 Step 1/4: Applying optimal parameters..."
python3 apply_optimal_params.py
echo ""

# Step 2: Validate convergence
echo "🔍 Step 2/4: Validating convergence..."
python3 validation_baseline.py --phase 1 2>&1 | tail -30
echo ""

read -p "Continue to Walk Forward? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted by user."
    exit 1
fi

# Step 3: Walk Forward (quick or full)
echo ""
echo "🚀 Step 3/4: Walk Forward Analysis..."
echo "Choose mode:"
echo "  [1] Quick (6m train, 2m test, 10 trials) - ~10 min"
echo "  [2] Full  (12m train, 3m test, 50 trials) - ~60 min"
read -p "Select [1-2]: " -n 1 -r MODE
echo ""

if [ "$MODE" = "1" ]; then
    echo "Running QUICK mode..."
    bash run_walk_forward.sh --quick
else
    echo "Running FULL mode..."
    bash run_walk_forward.sh
fi

# Step 4: Analyze robust ranges
echo ""
echo "📊 Step 4/4: Analyzing robust ranges..."
python3 analyze_robust_ranges.py

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                       ✅ PIPELINE COMPLETE                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📂 Results:"
echo "   • Walk Forward: outputs/walk_forward_results.json"
echo "   • Production Config: config/production_params.json"
echo ""
echo "🚀 Next Steps:"
echo "   1. Review robust ranges in config/production_params.json"
echo "   2. Update app.py with production params"
echo "   3. Run final backtest: python3 bugatti_bolide_X.py --use-optimal"
echo "   4. Deploy to live trading"
echo ""
